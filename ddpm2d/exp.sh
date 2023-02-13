
CUDA_VISIBLE_DEVICES=4   PYTHONPATH=. python -m ddpm2d.engine -m --config-name geom_glide  \
  expname=ddpm_novel_sunday/hoi4d_\${model.model}_\${mode.uv} \
  model.model=CondGeomGlide mode.cond=1 mode.uv=0,1 \
  environment.slurm=True


CUDA_VISIBLE_DEVICES=6   PYTHONPATH=. python -m ddpm2d.engine -m --config-name geom_glide  \
  expname=ddpm_novel_sunday/hoi4d_\${model.model} \
  model.model=GeomGlide mode.cond=0  \
  environment.slurm=True

CUDA_VISIBLE_DEVICES=5   PYTHONPATH=. python -m ddpm2d.engine -m --config-name geom_glide  \
  expname=ddpm_novel_sunday/hoi4d_\${model.model} \
  model.model=ObjGeomGlide mode.cond=-1  \
  environment.slurm=True


---
PYTHONPATH=. python -m ddpm2d.engine -m --config-name geom_glide  \
  expname=ddpm_novel_only/hoi4d_\${model.model} \
  model.model=CondGeomGlide mode.cond=True \
  data@trainsets=hoi4d data@testsets=hoi4d \
  environment.slurm=False eval=True \



PYTHONPATH=. python -m ddpm2d.engine -m --config-name geom_glide  \
  expname=ddpm_novel_only/\${ho3d.split}_\${model.model} \
  model.model=GeomGlide mode.cond=False \
  ho3d.split=SM2,train_seg \
  environment.slurm=True  \


PYTHONPATH=. python -m ddpm2d.engine -m --config-name geom_glide  \
  expname=ddpm_novel_only/\${ho3d.split}_\${model.model} \
  model.model=CondGeomGlide mode.cond=True \
  ho3d.split=SM2,train_seg \
  environment.slurm=True  \

PYTHONPATH=. python -m ddpm2d.engine -m --config-name geom_glide  \
  expname=ddpm_novel_only/hoi4d_\${model.model} \
  model.model=CondGeomGlide mode.cond=True \
  data@trainsets=hoi4d \
  environment.slurm=True  \



CUDA_VISIBLE_DEVICES=7  PYTHONPATH=. python -m ddpm2d.engine -m --config-name geom_glide  \
  expname=ddpm_novel_only/hoi4d_\${model.model} \
  model.model=GeomGlide mode.cond=False \
  data@trainsets=hoi4d data@testsets=hoi4d \
  environment.slurm=True 

CUDA_VISIBLE_DEVICES=7  PYTHONPATH=. python -m ddpm2d.engine -m --config-name geom_glide  \
  expname=ddpm_novel_only/hoi4d_\${model.model} \
  model.model=ObjGeomGlide mode.cond=False  \
  data@trainsets=hoi4d data@testsets=hoi4d \
  environment.slurm=True 





PYTHONPATH=. python -m ddpm.engine -m --config-name geom_glide  \
  expname=hand_ddpm_geom/\${ho3d.split}_\${model.model} \
  model.model=CondGeomGlide mode.cond=True learning_rate=1e-4 \
  ho3d.split=SM2,train_seg \
  environment.slurm=True  \


CUDA_VISIBLE_DEVICES=7 PYTHONPATH=. python -m ddpm.engine -m --config-name geom_glide  \
  expname=geom/pretrained_ho3d_cam_\${ho3d.split}_\${zfar}_\${learning_rate} \
  ho3d.split=SM2,train_seg  zfar=1 model.model=GeomGlide learning_rate=1e-4,1e-3 \
  environment.slurm=True logging=none \


CUDA_VISIBLE_DEVICES=7 PYTHONPATH=. python -m ddpm.engine -m --config-name geom_glide  \
  expname=ddpm_geom/100_depth_\${ho3d.split} \
  model.model=GeomGlide ho3d.split=SM2,train_seg  \
  environment.slurm=True logging=none \



CUDA_VISIBLE_DEVICES=7 PYTHONPATH=. python -m ddpm.engine -m --config-name geom_glide  \
  expname=geom/ho3d_cam_\${ho3d.split} \
  ho3d.split=SM2  model.model=GeomGlide \
  save_topk=-1 \
  environment.slurm=False \


CUDA_VISIBLE_DEVICES=7 PYTHONPATH=. python -m ddpm.engine -m --config-name sem_glide  \
  expname=ddpm2/glide_\${ho3d.split} \
  ho3d.split=SM2,train_seg \
  save_topk=-1 \
  environment.slurm=False \


CUDA_VISIBLE_DEVICES=1 python -m models.glide_base -m   \
  expname=dev/tmp \
  logging=none 


CUDA_VISIBLE_DEVICES=7 PYTHONPATH=. python engine.py -m --config-name sem_glide  \
  expname=ddpm/glide_\${ho3d.split} \
  ho3d.split=SM2,train_seg \
  save_topk=-1 \
  environment.slurm=True \
