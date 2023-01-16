# --------------------------------------------------------
# Written by Yufei Ye (https://github.com/JudyYe)
# Created on Sat Sep 17 2022
# --------------------------------------------------------
import torch
import torch.nn.functional as F

from .glide_base import BaseModule
from ..utils import glide_util

class Glide(BaseModule):
    def __init__(self, cfg, *args, **kwargs) -> None:
        super().__init__(cfg, *args, **kwargs)
        self.template_size = [3, cfg.side_y, cfg.side_x]
    
    def init_model(self,):
        cfg =self.cfg.model
        glide_model, glide_diffusion, glide_options = glide_util.load_model(
            glide_path=cfg.resume_ckpt,
            use_fp16=self.cfg.use_fp16,
            freeze_transformer=cfg.freeze_transformer,
            freeze_diffusion=cfg.freeze_diffusion,
            activation_checkpointing=cfg.activation_checkpointing,
            model_type='base',        
        )
        self.glide_model = glide_model
        self.diffusion = glide_diffusion
        self.glide_options = glide_options

        if self.cfg.resume_ckpt is not None and self.cfg.resume_ckpt.endswith('.ckpt'):
            sd = torch.load(self.cfg.resume_ckpt, map_location="cpu")
            if 'state_dict' in sd:
                sd = sd['state_dict']
            missing, unexpected = self.load_state_dict(sd, strict=False)
            if len(missing) > 0:
                print(f"Missing Keys: {missing}")
            if len(unexpected) > 0:
                print(f"Unexpected Keys: {unexpected}")

        return glide_model, glide_diffusion, glide_options

    def step(self, batch, batch_idx):
        device = self.device
        glide_model = self.glide_model
        glide_diffusion = self.diffusion
        tokens, masks, reals = batch['token'], batch['token_mask'], batch['image']

        timesteps = torch.randint(
            0, len(glide_diffusion.betas) - 1, (reals.shape[0],), device=device
        )
        batch_size = len(masks)
        noise = torch.randn([batch_size,] + self.template_size, device=device)
        x_t = glide_diffusion.q_sample(reals, timesteps, noise=noise,
            ).to(device)
        model_output = glide_model(
            x_t.to(device),
            timesteps.to(device),
            mask=masks.to(device),
            tokens=tokens.to(device),
        )
        epsilon = model_output[:, :3]
        loss = F.mse_loss(epsilon, noise.to(device).detach())        
        return loss, {'loss': loss}