from copy import deepcopy
import logging
import wandb
from models.frameworks import get_model
from models.cameras import get_camera
from models.base import get_optimizer, get_scheduler
from utils import flow_util, rend_util, train_util, mesh_util, io_util
from utils.dist_util import get_local_rank, init_env, is_master, get_rank, get_world_size
from utils.print_fn import log
from utils.logger import Logger
from utils.checkpoints import CheckpointIO
from dataio import get_data

from jutils import slurm_utils, mesh_utils, plot_utils, image_utils, geom_utils
import os
import os.path as osp
import sys
import time
import functools
from tqdm import tqdm
from glob import glob
import numpy as np
from hydra import main

import torch
import torch.nn.functional as F
import torch.distributed as dist
from torch.utils.data.dataloader import DataLoader
from torch.utils.data.distributed import DistributedSampler
from torch.nn.parallel import DistributedDataParallel as DDP

import tools.vis_clips as tool_clip
import tools.icp_recon as icp_tool
from utils.utis import update_pythonpath_relative_hydra

def main_function(gpu=None, ngpus_per_node=None, args=None):
    init_env(args, gpu, ngpus_per_node)
    
    #----------------------------
    #-------- shortcuts ---------
    rank = get_rank()
    local_rank = get_local_rank()
    world_size = get_world_size()
    i_backup = int(args.schdl.i_backup // world_size) if args.schdl.i_backup > 0 else -1
    i_val = int(args.schdl.i_val // world_size) if args.schdl.i_val > 0 else -1
    i_val_mesh = int(args.schdl.i_val_mesh // world_size) if args.schdl.i_val_mesh > 0 else -1
    special_i_val_mesh = [int(i // world_size) for i in [100, 1000, 5000, args.training.num_iters]]
    exp_dir = args.training.exp_dir
    mesh_dir = os.path.join(exp_dir, 'meshes')
    metric_dir = os.path.join(exp_dir, 'metrics')
    os.makedirs(metric_dir, exist_ok=True)
    
    device = torch.device('cuda', local_rank)
    print('local ran', device)


    # logger
    logger = Logger(
        log_dir=exp_dir,
        img_dir=os.path.join(exp_dir, 'imgs'),
        monitoring=args.training.get('monitoring', 'tensorboard'),
        monitoring_dir=os.path.join(exp_dir, 'events'),
        rank=rank, is_master=is_master(), multi_process_logging=(world_size > 1),
        cfg=args,)

    log.info("=> Experiments dir: {}".format(exp_dir))

    if is_master():
        # backup codes
        io_util.backup(os.path.join(exp_dir, 'backup'))
        # save configs
        io_util.save_config(args, os.path.join(exp_dir, 'config.yaml'))
    
    dataset, val_dataset = get_data(args, return_val=True, val_downscale=args.data.get('val_downscale', 4.0))
    bs = args.data.get('batch_size', None)
    # save GT obj
    gt_oObj = val_dataset.oObj
    mesh_utils.dump_meshes([osp.join(mesh_dir, 'oObj')], gt_oObj)

    if args.ddp:
        train_sampler = DistributedSampler(dataset)
        dataloader = DataLoader(dataset, sampler=train_sampler, batch_size=bs) #, collate_fn=mesh_utils.collate_meshes)
        val_sampler = DistributedSampler(val_dataset)
        valloader = DataLoader(val_dataset, sampler=val_sampler, batch_size=bs , collate_fn=mesh_utils.collate_meshes)
    else:
        dataloader = DataLoader(dataset,
            batch_size=bs,
            shuffle=True,
            pin_memory=args.data.get('pin_memory', False),
            collate_fn=mesh_utils.collate_meshes)
        valloader = DataLoader(val_dataset,
            batch_size=1,
            shuffle=True,
            collate_fn=mesh_utils.collate_meshes)
    
    # Create model
    posenet, focal_net = get_camera(args, datasize=len(dataset)+1, H=dataset.H, W=dataset.W)
    model, trainer, render_kwargs_train, render_kwargs_test, volume_render_fn, flow_render_fn = get_model(args, data_size=len(dataset)+1, cam_norm=dataset.max_cam_norm)
    
    trainer.train_dataloader = dataloader
    trainer.val_dataloader = valloader
    trainer.init_camera(posenet, focal_net)
    trainer.init_hand_texture(dataloader)
    trainer.to(device)
    model.to(device)
    posenet.to(device)
    focal_net.to(device)

    log.info(model)
    log.info("=> Nerf params: " + str(train_util.count_trainable_parameters(model)))
    log.info("=> Camera params: " + str(train_util.count_trainable_parameters(posenet) + train_util.count_trainable_parameters(focal_net)))
    
    trainer.H = dataset.H
    trainer.W = dataset.W
    render_kwargs_train['H'] = dataset.H
    render_kwargs_train['W'] = dataset.W
    render_kwargs_test['H'] = val_dataset.H
    render_kwargs_test['W'] = val_dataset.W
    valH, valW = render_kwargs_test['H'], render_kwargs_test['W']
    print(render_kwargs_train['H'])
    render_kwargs_surface = deepcopy(render_kwargs_test)
    render_kwargs_surface['H'] = render_kwargs_train['H'] // args.data.surface_downscale
    render_kwargs_surface['W'] = render_kwargs_train['W'] // args.data.surface_downscale
    render_kwargs_surface['rayschunk'] = args.data.surface_rayschunk

    # build optimizer
    optimizer = get_optimizer(args, model, posenet, focal_net)
    trainer.optimizer = optimizer
    
    # checkpoints
    checkpoint_io = CheckpointIO(checkpoint_dir=os.path.join(exp_dir, 'ckpts'), allow_mkdir=is_master())
    if world_size > 1:
        dist.barrier()
    # Register modules to checkpoint
    checkpoint_io.register_modules(
        posenet=posenet,
        focalnet=focal_net,
        model=model,
        optimizer=optimizer,
    )

    # Load checkpoints
    load_dict = checkpoint_io.load_file(
        args.training.ckpt_file,
        ignore_keys=args.training.ckpt_ignore_keys,
        only_use_keys=args.training.ckpt_only_use_keys,
        map_location=device)

    logger.load_stats('stats.p')    # this will be used for plotting
    it = load_dict.get('global_step', 0)
    epoch_idx = load_dict.get('epoch_idx', 0)

    # pretrain if needed. must be after load state_dict, since needs 'is_pretrained' variable to be loaded.
    #---------------------------------------------
    #-------- init perparation only done in master
    #---------------------------------------------
    if is_master():
        pretrain_config = {'logger': logger}
        if 'lr_pretrain' in args.training:
            pretrain_config['lr'] = args.training.lr_pretrain
            if(model.implicit_surface.pretrain_hook(pretrain_config)):
                checkpoint_io.save(filename='latest.pt'.format(it), global_step=it, epoch_idx=epoch_idx)

    # Parallel training
    if args.ddp:
        trainer = DDP(trainer, device_ids=args.device_ids, output_device=local_rank, find_unused_parameters=False)

    # build scheduler
    scheduler = get_scheduler(args, optimizer, last_epoch=it-1)
    trainer.scheduler = scheduler
    t0 = time.time()
    log.info('=> Start training..., it={}, lr={}, in {}'.format(it, optimizer.param_groups[0]['lr'], exp_dir))
    end = (it >= args.training.num_iters) and (not args.test_train)
    test_train = args.test_train
    with tqdm(range(args.training.num_iters), disable=not is_master()) as pbar:
        if is_master():
            pbar.update(it)
        while it <= args.training.num_iters and not end or test_train:
            try:
                if args.ddp:
                    train_sampler.set_epoch(epoch_idx)
                for (indices, model_input, ground_truth) in dataloader:
                    int_it = int(it // world_size)
                    # do a warm up for the first warm_hand iterations
                    # if int_it < args.training.warm_hand:
                    #     trainer.warm_hand(args, indices, model_input, ground_truth, render_kwargs_train, int_it)
                    #     continue
                    #-------------------
                    # validate
                    #-------------------
                    if is_master():

                        if i_val > 0 and int_it % i_val == 1 or test_train or int_it in special_i_val_mesh:
                            print('validation!!!!!')
                            test_train = 0
                            with torch.no_grad():
                                (val_ind, val_in, val_gt) = next(iter(valloader))
                                
                                trainer.eval()
                                val_ind = val_ind.to(device)
                                print('test H', render_kwargs_test['H'])
                                loss_extras = trainer(args, val_ind, val_in, val_gt, render_kwargs_test, 0)

                                target_rgb = val_gt['rgb'].to(device)    
                                target_mask = val_in['object_mask'].to(device)
                                target_flow = val_in['flow_fw'].to(device)
    
                                ret = loss_extras['extras']

                                to_img = functools.partial(
                                    rend_util.lin2img, 
                                    H=render_kwargs_test['H'], W=render_kwargs_test['W'],
                                    batched=render_kwargs_test['batched'])
                                logger.add_imgs(to_img(target_rgb), 'gt/gt_rgb', it)
                                logger.add_imgs(to_img(target_mask.unsqueeze(-1).float()), 'gt/gt_mask', it)
                                logger.add_imgs(to_img(flow_util.batch_flow_to_image(target_flow)), 'gt/gt_flo_fw', it)

                                if hasattr(trainer, 'val'):
                                    if args.ddp:
                                        trainer.module.val(logger, ret, to_img, it, render_kwargs_test, 
                                            val_ind, val_in, val_gt)
                                    else:
                                        trainer.val(logger, ret, to_img, it, render_kwargs_test, 
                                            val_ind, val_in, val_gt)
                                
                                logger.add_imgs(to_img(ret['normals_volume']/2.+0.5), 'obj/predicted_normals', it)
                    # TODO: this validation step is very ugly... 
                    #-------------------
                    # validate mesh
                    #-------------------
                    if is_master():
                        if i_val > 0 and int_it % i_val == 1 or test_train or int_it in special_i_val_mesh:
                            print('validating mesh!!!!!')
                            with torch.no_grad():
                                io_util.cond_mkdir(mesh_dir)
                                try:
                                    mesh_util.extract_mesh(
                                        model.implicit_surface, 
                                        N=64,
                                        filepath=os.path.join(mesh_dir, '{:08d}.ply'.format(it)),
                                        volume_size=args.data.get('volume_size', 2.0),
                                        show_progress=is_master())
                                    logger.add_meshes('obj', os.path.join('meshes', '{:08d}.ply'.format(it)), it)
                                    
                                    jObj = mesh_utils.load_mesh(os.path.join(mesh_dir, '{:08d}.ply'.format(it)))
                                    
                                    # compute F-score and CD 
                                    gt_oObj = val_dataset.oObj
                                    if gt_oObj is not None:
                                        jTh = ret['jTh']
                                        hObj = mesh_utils.apply_transform(jObj, geom_utils.inverse_rt(mat=jTh, return_mat=True).cpu())

                                        metric = quant_log(hObj, gt_oObj, scale=False)
                                        with open(osp.join(metric_dir, 'no_scale.txt'), 'a') as f:
                                            f.write('it: {}, metric: {}\n'.format(it, metric))
                                        logger.log_metrics({f'no_scale/{k}': v for k,v in metric.items()}, it)
                                        
                                        metric = quant_log(hObj, gt_oObj,  scale=True)
                                        with open(osp.join(metric_dir, 'scale.txt'), 'a') as f:
                                            f.write('it: {}, metric: {}\n'.format(it, metric))
                                        logger.log_metrics({f'scale/{k}': v for k,v in metric.items()}, it)
                                        jHand = ret['hand']
                                        jHoi = mesh_utils.join_scene([jObj.to(device), jHand.to(device)])
                                        image_list = mesh_utils.render_geom_rot(jHoi, scale_geom=True)
                                        logger.add_gifs(image_list, 'render/hoi_one_frame', it)
                                except ValueError:
                                    log.warn('No surface extracted; pass')
                                    pass
                    #-------------------
                    # validate camera pose 
                    #-------------------
                    if is_master():
                        if i_val_mesh > 0 and (int_it % i_val_mesh == 1 or int_it in special_i_val_mesh) and it != 0:
                            logging.info('vis camera pose')
                            print('validating camera pose!!!!!')
                            with torch.no_grad():
                                extrinsics_list = []
                                intrinsics_list = []
                                novel_list = []
                                for val_ind, val_in, val_gt in valloader:
                                    val_ind = val_ind.to(device)
                                    # c2w = posenet(val_ind, val_in, val_gt)
                                    c2w = trainer.get_jTc(val_ind, val_in, val_gt)[0]
                                    intrinsics = focal_net(val_ind, val_in, val_gt, H=valH, W=valW).cpu().detach().numpy()
                                    novel = trainer.sample_jTc(val_ind, val_in, val_gt)[0]
                                    
                                    extrinsics_list.append(c2w)  # c2w=wTc=jTc camera extrinsics are w2c matrix
                                    novel_list.append(novel)
                                    intrinsics_list.append(intrinsics)
                            extrinsics_list = torch.cat(extrinsics_list)
                            novel_list = torch.cat(novel_list)
                            cams_orign = plot_utils.vis_cam(wTc=extrinsics_list, color='blue', size=0.05, focal=2) # size can be specified
                            cams_novel = plot_utils.vis_cam(wTc=novel_list, color='red', size=0.05, focal=2) # size can be specified
                            coord = plot_utils.create_coord(device)
                            scene = mesh_utils.join_scene(cams_orign + cams_novel + [coord])
                            image_utils.save_gif(
                                mesh_utils.render_geom_rot(scene, scale_geom=True, out_size=1024), 
                                os.path.join(logger.log_dir, 'cams', '%08d' % it))
                            logger.log_metrics({
                                'cam': wandb.Video(os.path.join(logger.log_dir, 'cams', '%08d' % it) + '.gif')
                            }, it)

                    #-------------------
                    # validate rendering
                    #-------------------
                    # NOTE: not validating mesh before 3k, as some of the instances of DTU for NeuS training will have no large enough mesh at the beginning.
                    if is_master() and i_val > 0 and int_it % i_val == 1 or test_train or int_it in special_i_val_mesh:
                        logging.info('vis tool_clip run_render')
                        one_time_loader = DataLoader(dataset, batch_size=1, shuffle=False, collate_fn=mesh_utils.collate_meshes)
                        try:
                            print('run clip!!!!!')
                            with torch.no_grad():
                                file_list = tool_clip.run(
                                    one_time_loader, trainer, 
                                    os.path.join(logger.log_dir, 'meshes'), '%08d' % it, 224, 224,
                                    N=256, volume_size=args.data.get('volume_size', 2.0))
                                
                            for file in file_list:
                                name = os.path.basename(file)[9:-4]
                                logger.add_gif_files(file, 'render/' + name, it)
                        except ValueError:
                            log.warn('No surface extracted; pass')
                            pass
                        with torch.no_grad():
                            file_list = tool_clip.run_render(
                                one_time_loader, trainer, 
                                os.path.join(logger.log_dir, 'nvs'), '%08d' % it, render_kwargs_surface, max_t=10)
                        for file in file_list:
                            name = os.path.basename(file)[9:-4]
                            logger.add_gif_files(file, 'nvs/' + name, it)
                    #-------------------
                    # validate novel view rendering~~
                    #-------------------

                    if it >= args.training.num_iters:
                        end = True
                        break
                    
                    #-------------------
                    # train
                    #-------------------
                    start_time = time.time()
                    trainer.train()
                    optimizer.zero_grad()

                    ret = trainer.forward(args, indices, model_input, ground_truth, render_kwargs_train, it)

                    losses = ret['losses']
                    extras = ret['extras']

                    # all but contact 
                    for k, v in losses.items():
                        losses[k] = torch.mean(v)
        
                    losses['total'].backward()
                    if args.training.clip is not None:
                        torch.nn.utils.clip_grad_norm_(trainer.parameters(), args.training.clip)
                    grad_norms = train_util.calc_grad_norm(model=model, posenet=posenet, focalnet=focal_net)
                    optimizer.step()
        
                    scheduler.step(it)  # NOTE: important! when world_size is not 1

                    #-------------------
                    # logging
                    #-------------------
                    # done every i_save seconds
                    if (args.schdl.i_save > 0) and (time.time() - t0 > args.schdl.i_save):
                        if is_master():
                            checkpoint_io.save(filename='latest.pt', global_step=it, epoch_idx=epoch_idx)
                        # this will be used for plotting
                        logger.save_stats('stats.p')
                        t0 = time.time()
                    
                    if is_master():
                        #----------------------------------------------------------------------------
                        #------------------- things only done in master -----------------------------
                        #----------------------------------------------------------------------------
                        pbar.set_postfix(lr=optimizer.param_groups[0]['lr'], loss_total=losses['total'].item())

                        if i_backup > 0 and int_it % i_backup == 0 and it > 0:
                            checkpoint_io.save(filename='{:08d}.pt'.format(it), global_step=it, epoch_idx=epoch_idx)

                    #----------------------------------------------------------------------------
                    #------------------- things done in every child process ---------------------------
                    #----------------------------------------------------------------------------

                    #-------------------
                    # log grads and learning rate
                    for k, v in grad_norms.items():                        
                        logger.add('grad', k + f'_{it%2}', v, it)
                    logger.add('learning rates', 'whole', optimizer.param_groups[0]['lr'], it)

                    #-------------------
                    # log losses
                    for k, v in losses.items():
                        logger.add('losses', k, v.data.cpu().numpy().item(), it)
                        # print losses
                    if it % args.schdl.print_freq == 0 and is_master():
                        print(args.expname)
                        print('Iters [%04d] %f' % (it, losses['total']))
                        for k, v in losses.items():
                            if k != 'total':
                                print('\t %010s:%.4f' % (k, v.item()))

                    logger.add('metric', 'hA', (extras['hA'].cpu() - ground_truth['hA']).abs().mean(), it)

                    #-------------------
                    # log extras
                    names = ["radiance", "alpha", "implicit_surface", "implicit_nablas_norm", "sigma_out", "radiance_out"]
                    for n in names:
                        p = "whole"
                        # key = "raw.{}".format(n)
                        key = n
                        if key in extras:
                            logger.add("extras_{}".format(n), "{}.mean".format(p), extras[key].mean().data.cpu().numpy().item(), it)
                            logger.add("extras_{}".format(n), "{}.min".format(p), extras[key].min().data.cpu().numpy().item(), it)
                            logger.add("extras_{}".format(n), "{}.max".format(p), extras[key].max().data.cpu().numpy().item(), it)
                            logger.add("extras_{}".format(n), "{}.norm".format(p), extras[key].norm().data.cpu().numpy().item(), it)
                    if 'scalars' in extras:
                        for k, v in extras['scalars'].items():
                            logger.add('scalars', k, v.mean(), it)                           

                    #---------------------
                    # end of one iteration
                    end_time = time.time()
                    log.debug("=> One iteration time is {:.2f}".format(end_time - start_time))
                    
                    it += world_size
                    if is_master():
                        pbar.update(world_size)
                #---------------------
                # end of one epoch
                epoch_idx += 1

            except KeyboardInterrupt:
                if is_master():
                    checkpoint_io.save(filename='latest.pt'.format(it), global_step=it, epoch_idx=epoch_idx)
                    # this will be used for plotting
                logger.save_stats('stats.p')
                sys.exit()

    if is_master():
        checkpoint_io.save(filename='final_{:08d}.pt'.format(it), global_step=it, epoch_idx=epoch_idx)
        logger.save_stats('stats.p')
        # save web 
        # last = lambda x: sorted(glob(os.path.join(logger.log_dir, x)))[-1]
        # web_utils.run(logger.log_dir + '/web/', 
        #     [['gt_rgb', 'predicted_rgb', 'predicted mask', 'meshes'],
        #         [last('imgs/val/gt_rgb/*.png'), 
        #         last('imgs/val/predicted_rgb/*.png'),
        #         last('imgs/val/pred_mask_volume/*.png'),
        #         last('meshes/*.ply'),
        #     ]],
        #     width=400
        # ) 
        # log.info("Everything done.")


def quant_log(hObj, gt_oObj, scale=False, N=1):
    oObj, _ = icp_tool.register_meshes(hObj, gt_oObj, scale=scale, N=N)
    metrics = {}
    metrics['cd'] = mesh_utils.cdscore(oObj, gt_oObj)[0]
    th_list = np.array([5, 10, 15, 20, 50, 100]) * 1e-3
    f_list = mesh_utils.fscore(oObj, gt_oObj, th=th_list)
    for t in range(len(th_list)):
        metrics[str(th_list[t])] = f_list[t][0]
    print(metrics)
    return metrics



def origin_main():
    # Arguments
    parser = io_util.create_args_parser()
    parser.add_argument("--ddp", action='store_true', help='whether to use DDP to train.')
    parser.add_argument("--port", type=int, default=None, help='master port for multi processing. (if used)')
    slurm_utils.add_slurm_args(parser)
    args, unknown = parser.parse_known_args()
    config = io_util.load_config(args, unknown)

    
    slurm_utils.slurm_wrapper(args, config.training.exp_dir, main_function, {'args':config})


@main(config_path="configs", config_name="volsdf_nogt")
def main(args):
    update_pythonpath_relative_hydra()
    main_function(None, None, args)


if __name__ == "__main__":
    # hydra_main()
    main()
