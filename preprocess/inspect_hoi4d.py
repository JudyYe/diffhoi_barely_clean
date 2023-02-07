from scipy.spatial.transform import Rotation as Rt
from glob import glob
import pickle
import numpy as np
import imageio
import subprocess
import json
import os
import os.path as osp
import logging as log
from PIL import Image

import torch
import torchvision.transforms.functional as TF
from pytorch3d.renderer.cameras import PerspectiveCameras
from jutils import image_utils, geom_utils, mesh_utils, hand_utils

W = H = 512
device = 'cuda:0'
# hand_mask/  
# image/  
#   00000.png
# mask/  
# obj_mask/
# image.gif  
# cameras_hoi.npz  
# hands.npz  
data_dir = '/home/yufeiy2/scratch/data/HOI4D/'
exclude_list = ['rest', 'reachout', 'stop']
save_dir = '/home/yufeiy2/scratch/result/HOI4D/'
vis_dir = osp.join(save_dir, 'vis')

mapping = [
    '', 'ToyCar', 'Mug', 'Laptop', 'StorageFurniture', 'Bottle',
    'Safe', 'Bowl', 'Bucket', 'Scissors', '', 'Pliers', 'Kettle',
    'Knife', 'TrashCan', '', '', 'Lamp', 'Stapler', '', 'Chair'
]
rigid = [
    'Bowl', 'Bottle', 'Mug', 'ToyCar', 'Knife', 'Kettle',
]

name2id = {}
for i, name in enumerate(mapping):
    name2id[name] = i
# Bottle: C5

def read_masks(index, t):
    # 'ZY20210800001/H1/C11/N11/S125/s03/T1/2Dseg/mask/'
    fname = osp.join(data_dir, 'HOI4D_annotations', index, f'2Dseg/mask/{t:05d}.png')
    if not osp.exists(fname):
        fname = osp.join(data_dir, 'HOI4D_annotations', index, f'2Dseg/shift_mask/{t:05d}.png')
        if not osp.exists(fname):
            print(fname)
    mask = imageio.imread(fname)
    th = mask.max() / 2
    green_only = (mask[..., 0] < th) * (mask[..., 2] < th) * (mask[..., 1] > th)

    
    bbox = image_utils.mask_to_bbox((mask[..., 0] + mask[..., 2]) > th)
    if mapping[int(index.split('/')[2][1:])] == 'Stapler':
        red_only = (mask[..., 0] > th) * (mask[..., 2] < th) * (mask[..., 1] < th)
        blue_only = (mask[..., 2] > th) * (mask[..., 0] < th) * (mask[..., 1] < th)
        bbox = image_utils.mask_to_bbox(red_only + blue_only)
    elif mapping[int(index.split('/')[2][1:])] in rigid: 
        red_only = (mask[..., 0] > th) * (mask[..., 2] < th) * (mask[..., 1] < th)
        bbox = image_utils.mask_to_bbox(red_only)
        mask = np.stack([red_only, green_only, np.zeros_like(red_only)], -1) * 255
    else:
        print(mapping[int(index.split('/')[2][1:])])

    x, y = (bbox[0:2] + bbox[2:4]) / 2
    m = 75
    min_box = np.array([x - m, y - m, x+m, y+m])
    bbox = image_utils.joint_bbox(bbox, min_box)
    return mask[..., 0:3], bbox


def get_one_clip(index, t_start, t_end):
    f_start = int(t_start*15)
    f_end = int(t_end*15)
    # get_image with object centric crops 
    save_index = index.replace('/', '_') + f'_{f_start:05d}_{f_end:05d}'
    save_pref = osp.join(save_dir, save_index, '{:s}/{:05d}.png')
    hand_wrapper = hand_utils.ManopthWrapper().to('cuda:0')

    image_list = []
    camera_dict = {'cTw': [], 
                #    'wTh': [], 
                   'K_pix': [], 
                #    'hTo': [], 
                #    'onTo': []
                   }
    hand_dict = {'hA': [], 'beta': []}
    for t in range(f_start, f_end):
        masks, bbox = read_masks(index, t)
        bbox_sq = image_utils.square_bbox(bbox, 0.8)

        mask_crop = image_utils.crop_resize(masks, bbox_sq, H)
        obj_mask = (mask_crop[..., 0] > 10) * 255    # red object, green hand
        hand_mask = (mask_crop[..., 1] > 10) * 255 

        image = imageio.imread(osp.join(data_dir, 'HOI4D_release', index, f'align_rgb/{t:05d}.jpg'))
        crop = image_utils.crop_resize(image, bbox_sq, H)
        
        imwrite(save_pref.format('hand_mask', t-f_start), hand_mask)
        imwrite(save_pref.format('obj_mask', t-f_start), obj_mask)
        imwrite(save_pref.format('image', t-f_start), crop)

        blend = (mask_crop > 10) * crop + (mask_crop <= 10) * (0.5*crop)
        image_list.append(blend.clip(0, 255).astype(np.uint8))

        cMesh = vis_obj(bbox_sq, index, t)
        hA, beta, cTw, cam_intr_crop = vis_hand(hand_wrapper, crop, bbox_sq, index, t)
        f, p = mesh_utils.get_fxfy_pxpy(mesh_utils.intr_from_screen_to_ndc(cam_intr_crop, H, H))

        cHand, cJoints = hand_wrapper(cTw, hA, th_betas=beta)
        cHand.textures = mesh_utils.pad_texture(cHand, 'blue')
        cameras = PerspectiveCameras(f, p).to(device)
        cHoi = mesh_utils.join_scene([cHand, cMesh])
        iHand = mesh_utils.render_mesh(cHoi, cameras, out_size=H)
        # _, _, iHand = hand_wrapper.weak_proj(cam, pose, out_size=int(hoi_box[2] - hoi_box[0]), render=True)
        image_utils.save_images(iHand['image'], save_pref.format('overlay', t-f_start, )[:-4],
                                bg=TF.to_tensor(crop), mask=iHand['mask'],)

        camera_dict['cTw'].append(cTw.cpu().detach().numpy()[0])
        camera_dict['K_pix'].append(cam_intr_crop.cpu().detach().numpy()[0])
        hand_dict['hA'].append(hA.cpu().detach().numpy()[0])
        hand_dict['beta'].append(beta.cpu().detach().numpy()[0])

    make_gif(osp.join(save_dir, save_index, 'overlay/*.png'), osp.join(save_dir, save_index, 'overlay'))

    imageio.mimsave(osp.join(save_dir, save_index, 'image.gif'), image_list)
    
    for k, v in camera_dict.items():
        camera_dict[k] = np.array(v)
        print(k, camera_dict[k].shape)
    for k, v in hand_dict.items():
        hand_dict[k] = np.array(v)
        print(hand_dict[k].shape)
    np.savez_compressed(osp.join(save_dir, save_index, 'cameras_hoi.npz'), **camera_dict)
    np.savez_compressed(osp.join(save_dir, save_index, 'hands.npz'), **hand_dict)

    return


def make_gif(inp_file, save_file):
    image_list = [imageio.imread(img_file) for img_file in sorted(glob(inp_file))]
    os.makedirs(osp.dirname(save_file), exist_ok=True)
    imageio.mimsave(save_file + '.gif', image_list)


def imwrite(fname, image):
    os.makedirs(osp.dirname(fname), exist_ok=True)
    image = image.clip(0, 255).astype(np.uint8)
    imageio.imwrite(fname, image)    


def continuous_clip(index):
    clips = []
    action_file = osp.join(data_dir, 'HOI4D_annotations/', index, 'action/color.json')
    with open(action_file) as fp:
        act = json.load(fp)
    start = 0 
    stop = 0
    record = False
    for ev in act['events']:
        if not record:
            if ev['event'].lower() in exclude_list:
                continue
            else:
                record = True
                start = ev['startTime']
        else:
            if ev['event'].lower() in exclude_list:
                record = False
                stop = ev['startTime']
                clips.append([start, stop])
    return clips


def decode_video(root, list_file):

    with open(osp.join(data_dir, 'Sets', list_file), 'r') as f:
        rgb_list = [os.path.join(root, i.strip(),'align_rgb') for i in f.readlines()]

    for rgb in rgb_list:
        depth = rgb.replace('align_rgb','align_depth')
        rgb_video = os.path.join(rgb, "image.mp4")
        # depth_video = os.path.join(depth, "depth_video.avi")

        cmd =  """ ffmpeg -i {} -f image2 -start_number 0 -vf fps=fps=15 -qscale:v 2 {}/%05d.{} -loglevel quiet """.format(rgb_video, rgb, "jpg")

        print(cmd)
        p = subprocess.Popen(cmd, shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        if err:
            log.info(err.decode())

        # cmd = """ ffmpeg -i {} -f image2 -start_number 0 -vf fps=fps=15 -qscale:v 2 {}/%05d.{} -loglevel quiet """.format(depth_video, depth, "png")
        # print(cmd)

        # p = subprocess.Popen(cmd, shell=True,
        #                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # out, err = p.communicate()
        # if err:
        #     log.info(err.decode())


def batch_clip(num=1):
    with open(osp.join(data_dir, 'Sets/test_vid_ins.txt')) as fp:
        index_list = [line.strip() for line in fp]
    cat_exist = {}
    for index in index_list:
        cat = int(index.split('/')[2][1:])

        if cat in cat_exist:
            if cat_exist[cat] >= num:
                continue
        else:
            cat_exist[cat] = 0
        if mapping[cat] not in rigid:
            print('continue', mapping[cat])
            continue
        cat_exist[cat] += 1
        clips = continuous_clip(index)
        print(clips)

        for cc in clips:
            get_one_clip(index, cc[0], cc[1])
    return

def read_rtd(file, num=0):
    with open(file, 'r') as f:
        cont = f.read()
        cont = eval(cont)
    if "dataList" in cont:
        anno = cont["dataList"][num]
    else:
        anno = cont["objects"][num]

    trans, rot, dim = anno["center"], anno["rotation"], anno["dimensions"]
    trans = np.array([trans['x'], trans['y'], trans['z']], dtype=np.float32)
    rot = np.array([rot['x'], rot['y'], rot['z']])
    dim = np.array([dim['length'], dim['width'], dim['height']], dtype=np.float32)
    rot = Rt.from_euler('XYZ', rot).as_matrix()
    return np.array(rot, dtype=np.float32), trans, dim



def load_intr(hoi_box, vid, fnum=0):
    cam_id = vid.split('/')[0]
    K = torch.FloatTensor(np.load(osp.join(data_dir, 'camera_params/%s/intrin.npy' % cam_id)))[None].to(device)
    cam_intr = image_utils.crop_cam_intr(K[0], torch.FloatTensor(hoi_box).to(device), (H, H))[None]
    return cam_intr


def vis_obj(hoi_box, vid, fnum):
    pose_dir = osp.join(data_dir, 'HOI4D_annotations/{}/objpose/{:d}.json')
    obj_dir = osp.join(data_dir, 'HOI4D_CAD_Model_for_release/rigid/{}/{:03d}.obj')
    rt, trans, dim = read_rtd(pose_dir.format(vid, fnum), 0)

    rt = torch.FloatTensor(rt)[None].to(device)
    trans = torch.FloatTensor(trans)[None].to(device)

    cat = mapping[int(vid.split('/')[2][1:])]
    obj_id = int(vid.split('/')[3][1:])
    oMesh = mesh_utils.load_mesh(obj_dir.format(cat, obj_id)).to(device)
    cTo = geom_utils.rt_to_homo(rt, trans)
    cMesh = mesh_utils.apply_transform(oMesh, cTo)

    # cam_intr_crop = load_intr(hoi_box, vid, )
    # f, p = mesh_utils.get_fxfy_pxpy(mesh_utils.intr_from_screen_to_ndc(cam_intr_crop, H, H))

    # cameras = PerspectiveCameras(f, p).to(device)

    # iMesh = mesh_utils.render_mesh(cMesh, cameras, out_size=H)
    # image_utils.save_images(iMesh['image'], osp.join(vis_dir, vid.replace('/', '_') + f'_{fnum}'))
    cMesh.textures = mesh_utils.pad_texture(cMesh, 'white')
    return cMesh


def vis_hand(hand_wrapper, crop, hoi_box, vid, fnum):
    device = 'cuda:0'
    # "poseCoeff" : refers to 3 global rotation + 45 mano pose parameters
    # "beta" : refers to 10 mano shape parameters. Shape of each human ID H* are the same.
    # "trans" ： refers to translation of the hand in camera frame
    # "kps2D" : refers to 21 keypoints projection coordination of rendered hand pose on each image.
    # theta = nn.Parameter(torch.FloatTensor(hand_info['poseCoeff']).unsqueeze(0))
    # beta = nn.Parameter(torch.FloatTensor(hand_info['beta']).unsqueeze(0))
    # trans = nn.Parameter(torch.FloatTensor(hand_info['trans']).unsqueeze(0))
    # hand_verts, hand_joints = manolayer(theta, beta)
    # kps3d = hand_joints / 1000.0 + trans.unsqueeze(1) # in meters
    # hand_transformed_verts = hand_verts / 1000.0 + trans.unsqueeze(1)
    right_bbox_dir = osp.join(data_dir, 'handpose/refinehandpose_right/{}/{:d}.pickle')
    cam_id = vid.split('/')[0]
        
    K = torch.FloatTensor(np.load(osp.join(data_dir, 'camera_params/%s/intrin.npy' % cam_id)))[None].to(device)
    if osp.exists(right_bbox_dir.format(vid, fnum)):
        with open(right_bbox_dir.format(vid, fnum), 'rb') as fp:
            obj = pickle.load(fp)
    else:
        print(right_bbox_dir.format(vid, fnum))
    
    pose = obj['poseCoeff']
    beta = obj['beta']
    trans = obj['trans']
    rot, hA = pose[:3], pose[3:]
    hA = torch.FloatTensor(hA, ).to(device)[None]
    rot = torch.FloatTensor(rot, ).to(device)[None]
    trans = torch.FloatTensor(trans, ).to(device)[None]
    beta = torch.FloatTensor(beta, ).to(device)[None]
    k2d = torch.FloatTensor(obj['kps2D'], ).to(device)[None]
    
    rot, trans = hand_utils.cvt_axisang_t_i2o(rot, trans)
    cTw = se3 = geom_utils.axis_angle_t_to_matrix(rot, trans)
    pose = torch.FloatTensor(pose[None]).to(device)

    # cHand, cJoints = hand_wrapper(cTw, hA, th_betas=beta)

    # K_crop = crop_intrinsics(K, hoi_box)
    cam_intr = image_utils.crop_cam_intr(K[0], torch.FloatTensor(hoi_box).to(device), (H, H))[None]
    # K_crop_intr = mesh_utils.intr_from_screen_to_ndc(cam_intr, H, H)
    return hA, beta, cTw, cam_intr


if __name__ == '__main__':
    # decode_video('/home/yufeiy2/scratch/data/HOI4D/HOI4D_release/', 'test_vid_ins.txt')
    # index = 'ZY20210800002/H2/C5/N45/S261/s02/T2'
    # clips = continuous_clip(index)
    # for cc in clips:
    #     # vis_obj()
    #     get_one_clip(index, cc[0], cc[1])

    batch_clip()