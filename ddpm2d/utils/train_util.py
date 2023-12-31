import os
from typing import Tuple
from omegaconf import OmegaConf
import numpy as np
from PIL import Image
import torch
import torch as th
import wandb
from tqdm import tqdm
import importlib
from jutils.model_utils import load_my_state_dict


def load_from_checkpoint(ckpt, cfg_file=None):
    if not os.path.exists(ckpt):
        ckpt = ckpt.replace('/home', '/private/home')

    if cfg_file is None:
        cfg_file = ckpt.split('checkpoints')[0] + '/config.yaml'
    print('use cfg file', cfg_file)
    cfg = OmegaConf.load(cfg_file)
    # legacy:
    cfg.model.module = cfg.model.module.replace('ddpm.', 'ddpm2d.')
    cfg.model.resume_ckpt = None  # save time to load base model :p
    if not cfg.model.module.startswith('ddpm2d.'):
        cfg.model.module = 'ddpm2d.' + cfg.model.module
    module = importlib.import_module(cfg.model.module)
    model_cls = getattr(module, cfg.model.model)
    model = model_cls(cfg, )
    model.init_model()

    print('loading from checkpoint', ckpt)    
    weights = torch.load(ckpt)['state_dict']
    load_my_state_dict(model, weights)
    return model


def save_model(
    glide_model: th.nn.Module, checkpoints_dir: str, train_idx: int, epoch: int
):
    th.save(
        glide_model.state_dict(),
        os.path.join(checkpoints_dir, f"glide-ft-{epoch}x{train_idx}.pt"),
    )
    tqdm.write(
        f"Saved checkpoint {train_idx} to {checkpoints_dir}/glide-ft-{epoch}x{train_idx}.pt"
    )


def pred_to_pil(pred: th.Tensor) -> Image:
    scaled = ((pred + 1) * 127.5).round().clamp(0, 255).to(th.uint8).cpu()
    reshaped = scaled.permute(2, 0, 3, 1).reshape([pred.shape[2], -1, 3])
    return Image.fromarray(reshaped.numpy())


def pil_image_to_norm_tensor(pil_image):
    """
    Convert a PIL image to a PyTorch tensor normalized to [-1, 1] with shape [B, C, H, W].
    """
    return th.from_numpy(np.asarray(pil_image)).float().permute(2, 0, 1) / 127.5 - 1.0


def resize_for_upsample(
    original, low_res_x, low_res_y, upscale_factor: int = 4
) -> Tuple[th.Tensor, th.Tensor]:
    """
    Resize/Crop an image to the size of the low resolution image. This is useful for upsampling.

    Args:
        original: A PIL.Image object to be cropped.
        low_res_x: The width of the low resolution image.
        low_res_y: The height of the low resolution image.
        upscale_factor: The factor by which to upsample the image.

    Returns:
        The downsampled image and the corresponding upscaled version cropped according to upscale_factor.
    """
    high_res_x, high_res_y = low_res_x * upscale_factor, low_res_y * upscale_factor
    high_res_image = original.resize((high_res_x, high_res_y), Image.LANCZOS)
    high_res_tensor = pil_image_to_norm_tensor(pil_image=high_res_image)
    low_res_image = high_res_image.resize(
        (low_res_x, low_res_y), resample=Image.BICUBIC
    )
    low_res_tensor = pil_image_to_norm_tensor(pil_image=low_res_image)
    return low_res_tensor, high_res_tensor


def mean_flat(tensor):
    """
    Take the mean over all non-batch dimensions.
    """
    return tensor.mean(dim=list(range(1, len(tensor.shape))))


def wandb_setup(
    batch_size: int,
    side_x: int,
    side_y: int,
    learning_rate: float,
    use_fp16: bool,
    device: str,
    data_dir: str,
    base_dir: str,
    project_name: str = "glide-text2im-finetune",
):
    return wandb.init(
        project=project_name,
        config={
            "batch_size": batch_size,
            "side_x": side_x,
            "side_y": side_y,
            "learning_rate": learning_rate,
            "use_fp16": use_fp16,
            "device": device,
            "data_dir": data_dir,
            "base_dir": base_dir,
        },
    )
