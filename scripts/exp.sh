--100doh


PYTHONPATH=. python -m engine \
    environment=dev \
    data=100doh


PYTHONPATH=. python -m engine \
    environment=dev \
    expname=art/hA_\${hA.mode}_\${training.w_sdf} \
    data.index=SMu1_0650


--
# optimize hand articulation

PYTHONPATH=. python -m engine -m \
    expname=art/hA_\${hA.mode}_\${training.w_sdf} \
    hA.mode=learn,gt training.w_sdf=0.01,0 


--


PYTHONPATH=. python -m engine -m \
    expname=honey_grow/hand_text_\${data.index}_\${oTh.mode}_wm\${training.w_mask} \
    oTh=gt,learn \
    data.index=BB12_0000,AP12_0050,MDF10_0000,SMu41_0000,SS2_0000 \
    training.w_mask=1,10


MC2_0000,GSF11_1000,SM2_0000


--    
PYTHONPATH=. python -m engine -m \
    expname=honey_grow/hand_text_\${data.index}_\${oTh.mode} \
    oTh=gt,learn \
    data.index=MC2_0000,GSF11_1000,SM2_0000


PYTHONPATH=. python -m engine -m \
    expname=honey_grow/hand_text_\${data.index}_\${oTh.mode}_wm\${training.w_mask} \
    oTh=gt,learn \
    data.index=MC2_0000,GSF11_1000,SM2_0000 \
    training.w_mask=1


# bu 
PYTHONPATH=. python -m engine -m \
    expname=honey_grow/hand_text_\${data.index}_\${oTh.mode}_wm\${training.w_mask} \
    oTh=learn \
    data.index=SM2_0000 \
    training.w_mask=50




# separation


---
PYTHONPATH=. python -m engine \
    expname=dev/hand_text \
    environment=dev 




PYTHONPATH=. python -m engine -m \
    expname=render_label2_rgb/\${blend_train.method}_order\${training.label_prob} \
    blend_train.method=vol,soft,hard training.occ_mask=label training.label_prob=1 \


PYTHONPATH=. python -m engine -m \
    expname=render_label2_rgb/\${blend_train.method}_order\${training.label_prob} \
    blend_train.method=soft training.occ_mask=label training.label_prob=2 \



---
PYTHONPATH=. python -m engine -m \
    expname=render_label2/\${blend_train.method}_order\${training.label_prob} \
    blend_train.method=vol,soft,hard training.occ_mask=label training.label_prob=1 \
    training.w_eikonal=0 training.w_rgb=0 

PYTHONPATH=. python -m engine -m \
    expname=render_label2/\${blend_train.method}_order\${training.label_prob} \
    blend_train.method=soft training.occ_mask=label training.label_prob=2 \
    training.w_eikonal=0 training.w_rgb=0 environment=dev


--
PYTHONPATH=. python -m engine -m \
    expname=dev/order\${training.label_prob}_wd\${training.w_depth} \
    blend_train.method=vol training.occ_mask=label training.label_prob=1 \
    training.w_eikonal=0 training.w_rgb=0  environment=dev



PYTHONPATH=. python -m engine -m \
    expname=render_label/order\${training.label_prob}_wd\${training.w_depth} \
    blend_train.method=soft training.occ_mask=label training.label_prob=1,2 training.w_depth=1.0,0.0 \
    training.w_eikonal=0 training.w_rgb=0 

PYTHONPATH=. python -m engine -m \
    expname=render_label/\${blend_train.method}_\${training.occ_mask}_\${training.label_prob} \
    blend_train.method=soft training.occ_mask=label training.label_prob=1 training.w_depth 1.0 \
    training.w_eikonal=0 training.w_rgb=0 environment=dev


--


PYTHONPATH=. python -m engine \
    expname=test_requeue/\${data.index}_\${blend_train.method}_\${training.occ_mask} \
    data.index=AP12_0050,SM2_0000 \
    blend_train.method=soft training.occ_mask=label \
    environment=learn \


# only mask, make sure gradient works? 
PYTHONPATH=. python -m engine -m \
    expname=only_mask/\${blend_train.method}_\${training.occ_mask} \
    blend_train.method=soft,hard training.occ_mask=indp,union,label \
    training.w_eikonal=0 training.w_rgb=0 

# see soft or hard blending~~
PYTHONPATH=. python -m engine -m \
    expname=soft_hard/\${blend_train.method}_\${training.occ_mask} \
    blend_train.method=soft,hard training.occ_mask=indp,union,label \



--
PYTHONPATH=. python -m engine \
    expname=dev_blend/\${blend_train.method} \
    environment=dev \
    blend_train.method=soft


PYTHONPATH=. python -m engine \
    expname=dev_blend/\${blend_train.method} \
    training.monitoring=none \
    blend_train.method=hard



DATA=AP12_0050
python -m train --config configs/volsdf_hoi.yaml \
    --expname learn_oTh/unknown_${DATA} --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/${DATA} \
    --oTh:learn_R 1 --oTh:learn_t 1 --oTh:mode learn \
    --slurm --sl_ngpu 2 


DATA=AP12_0050
python -m train --config configs/volsdf_hoi.yaml \
    --expname learn_oTh/gt_${DATA} --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/${DATA} \
    --slurm --sl_ngpu 2 




-
DATA=SMu1_0650
python -m train --config configs/volsdf_hoi.yaml \
    --expname learn_oTh/unknown_${DATA} --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/${DATA} \
    --oTh:learn_R 1 --oTh:learn_t 1 --oTh:mode learn \
    --slurm --sl_ngpu 2 


DATA=SMu1_0650
python -m train --config configs/volsdf_hoi.yaml \
    --expname learn_oTh/gt_${DATA} --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/${DATA} \
    --slurm --sl_ngpu 2 






DATA=MDF10_0000
python -m train --config configs/volsdf_hoi.yaml \
    --expname learn_oTh/unknown_${DATA} --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/${DATA} \
    --oTh:learn_R 1 --oTh:learn_t 1 --oTh:mode learn \
    --slurm --sl_ngpu 2 


DATA=MDF10_0000
python -m train --config configs/volsdf_hoi.yaml \
    --expname learn_oTh/gt_${DATA} --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/${DATA} \
    --slurm --sl_ngpu 2 




DATA=MDF10_0090
python -m train --config configs/volsdf_hoi.yaml \
    --expname learn_oTh/unknown_${DATA} --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/${DATA} \
    --oTh:learn_R 1 --oTh:learn_t 1 --oTh:mode learn \
    --slurm --sl_ngpu 2 


DATA=MDF10_0090
python -m train --config configs/volsdf_hoi.yaml \
    --expname learn_oTh/gt_${DATA} --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/${DATA} \
    --slurm --sl_ngpu 2 



in objnorm coord
python -m train --config configs/volsdf_hoi.yaml \
    --expname ho3d_known_cam/MDF10_0090 --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/MDF10_0090 \
    --slurm --sl_ngpu 2 

python -m train --config configs/volsdf_hoi.yaml \
    --expname ho3d_known_cam/MDF10_0090_hand --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/MDF10_0090 \
    --model:joint_frame hand_norm \
    --slurm --sl_ngpu 2 



python -m train --config configs/volsdf_hoi.yaml \
    --expname ho3d_known_cam/MDF10_0000 --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/MDF10_0000 \
    --slurm --sl_ngpu 2 

python -m train --config configs/volsdf_hoi.yaml \
    --expname ho3d_known_cam/MDF10_0000_hand --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/MDF10_0000 \
    --model:joint_frame hand_norm \
    --slurm --sl_ngpu 2 



python -m train --config configs/volsdf_hoi.yaml \
    --expname ho3d_known_cam/SMu1_0650 --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/SMu1_0650 \
    --slurm --sl_ngpu 2 

python -m train --config configs/volsdf_hoi.yaml \
    --expname ho3d_known_cam/SMu1_0650_hand --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/SMu1_0650 \
    --model:joint_frame hand_norm \
    --slurm --sl_ngpu 2 




-
python -m train --config configs/volsdf_hoi.yaml \
    --expname dev/MDF10_0090 --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/MDF10_0090 \
 \




python -m train --config configs/volsdf_hoi.yaml \
    --expname scale_radius/-1 --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius -1 --data:type HOI_dtu \
    --slurm --sl_ngpu 2 

python -m train --config configs/volsdf_hoi.yaml \
    --expname scale_radius/3 --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 --data:scale_radius 3 --data:type HOI_dtu \
    --slurm --sl_ngpu 2 


-
python -m train --config configs/volsdf_hoi.yaml \
    --expname debug/sdf_0.01 --training:occ_mask indp  \
    --training:w_mask 1.0 --training:w_flow 0.0 --training:fg 1 --training:w_sdf 0.01 \


--=
python -m train --config configs/volsdf.yaml --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/00006755 \
    --expname dev/agnostic_blue  --training:w_mask 1.0 --training:w_flow 0.0 --training:fg 1 \
    --slurm --ddp


python -m train --config configs/volsdf_hoi.yaml \
    --expname depth/sdf_no --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0. \
    --slurm --sl_ngpu 2 

python -m train --config configs/volsdf_hoi.yaml \
    --expname depth/sdf_0.01 --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.01 \
    --slurm --sl_ngpu 2 

python -m train --config configs/volsdf_hoi.yaml \
    --expname depth/sdf_0.1 --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 0.1 \
    --slurm --sl_ngpu 2 


python -m train --config configs/volsdf_hoi.yaml \
    --expname depth/sdf_1 --training:occ_mask indp  \
    --training:w_flow 0.0  --training:w_sdf 1 \
    --slurm --sl_ngpu 2 





python -m train --config configs/volsdf_hoi.yaml \
    --expname dev/indp --training:occ_mask indp  \
    --training:w_mask 1.0 --training:w_flow 0.0 --training:fg 1 \



python -m train --config configs/volsdf_hoi.yaml \
    --expname occ/union --training:occ_mask union  \
    --training:w_mask 1.0 --training:w_flow 0.0 --training:fg 1 \
    --slurm --ddp

python -m train --config configs/volsdf_hoi.yaml \
    --expname occ/indp --training:occ_mask indp  \
    --training:w_mask 1.0 --training:w_flow 0.0 --training:fg 1 --test_train 1 \
    --slurm --ddp


-
python -m train --config configs/volsdf_hoi.yaml \
    --expname cmp/hybrid_blue  --training:w_mask 1.0 --training:w_flow 0.0 --training:fg 1 \
    --slurm --ddp

python -m train --config configs/volsdf.yaml --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/00006755 \
    --expname cmp/agnostic_blue  --training:w_mask 1.0 --training:w_flow 0.0 --training:fg 1 \
    --slurm --ddp

--

python -m train --config configs/volsdf_hoi.yaml \
    --expname dev/rgb_blue  --training:w_mask 1.0 --training:w_flow 0.0 --training:fg 1 \


--
python -m train --config configs/volsdf.yaml \
    --expname syn/rgb_dtu  --training:w_mask 1.0 --training:w_flow 0.0 --training:fg 1 \
    --slurm --ddp

python -m train --config configs/volsdf.yaml \
    --expname syn/flow_dtu  --training:w_mask 1.0 --training:w_flow 1.0 --training:fg 1 \
    --slurm --ddp


-


python -m train --config configs/volsdf.yaml  --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/00006755 \
    --expname syn/rgb_blue  --training:w_mask 1.0 --training:w_flow 0.0 --training:fg 1 \
    --slurm --ddp

python -m train --config configs/volsdf.yaml  --data:data_dir /checkpoint/yufeiy2/vhoi_out/syn_data/00006755 \
    --expname syn/flow_blue  --training:w_mask 1.0 --training:w_flow 1.0 --training:fg 1 \
    --slurm --ddp

---

python -m train --config configs/volsdf.yaml  \
    --expname right_mask/mask_rgb_cam  --training:w_mask 1.0 --training:w_flow 0.0 \
    --camera:mode para --training:num_iters 500000 \
    --training:i_val 2000 --training:i_val_mesh 2000 --training:i_save 2000 \
    --slurm --ddp

python -m train --config configs/volsdf.yaml  \
    --expname right_mask/mask_flow_cam  --training:w_mask 1.0 --training:w_flow 1.0 \
    --camera:mode para --training:num_iters 500000 \
    --training:i_val 2000 --training:i_val_mesh 2000 --training:i_save 2000 \
    --slurm --ddp        




--
python -m train --config configs/volsdf.yaml  \
    --expname right_mask/mask_rgb_bg  --training:w_mask 1.0 --training:w_flow 0.0 --training:fg 0 \
    --slurm --ddp

python -m train --config configs/volsdf.yaml  \
    --expname right_mask/mask_flow_bg  --training:w_mask 1.0 --training:w_flow 1.0 --training:fg 0 \
    --slurm --ddp        


python -m train --config configs/volsdf.yaml  \
    --expname right_mask/mask_rgb  --training:w_mask 1.0 --training:w_flow 0.0 \
    --slurm --ddp


python -m train --config configs/volsdf.yaml  \
    --expname right_mask/mask_flow  --training:w_mask 1.0 --training:w_flow 1.0 \
    --slurm --ddp        


-
python -m train --config configs/volsdf.yaml  \
    --expname right_mask/rgb_bg  --training:w_mask 0.0 --training:w_flow 0.0 --training:fg 0 \
    --slurm --ddp

python -m train --config configs/volsdf.yaml  \
    --expname right_mask/flow_bg  --training:w_mask 0.0 --training:w_flow 1.0 --training:fg 0 \
    --slurm --ddp        


python -m train --config configs/volsdf.yaml  \
    --expname right_mask/rgb  --training:w_mask 0.0 --training:w_flow 0.0 \
    --slurm --ddp


python -m train --config configs/volsdf.yaml  \
    --expname right_mask/flow  --training:w_mask 0.0 --training:w_flow 1.0 \
    --slurm --ddp        



---
python -m train --config configs/volsdf.yaml  \
    --expname gt_rightflow/rgb_bg  --training:w_mask 0.0 --training:w_flow 0.0 --training:fg 0 \
    --slurm --ddp

python -m train --config configs/volsdf.yaml  \
    --expname gt_rightflow/flow_bg  --training:w_mask 0.0 --training:w_flow 1.0 --training:fg 0 \
    --slurm --ddp        


python -m train --config configs/volsdf.yaml  \
    --expname gt_rightflow/rgb  --training:w_mask 0.0 --training:w_flow 0.0 \
    --slurm --ddp


python -m train --config configs/volsdf.yaml  \
    --expname gt_rightflow/flow  --training:w_mask 0.0 --training:w_flow 1.0 \
    --slurm --ddp        

--
python -m train --config configs/volsdf.yaml  \
    --expname paracam/rgb_bg  --training:w_mask 0.0 --training:w_flow 0.0 --training:fg 0 \
    --camera:mode para \
    --slurm --ddp

python -m train --config configs/volsdf.yaml  \
    --expname paracam/flow_bg  --training:w_mask 0.0 --training:w_flow 1.0 --training:fg 0 \
    --camera:mode para \
    --slurm --ddp        


python -m train --config configs/volsdf.yaml  \
    --expname paracam/rgb  --training:w_mask 0.0 --training:w_flow 0.0 \
    --camera:mode para \
    --slurm --ddp

python -m train --config configs/volsdf.yaml  \
    --expname paracam/mask  --training:w_mask 1.0 --training:w_flow 0.0 \
    --camera:mode para \
    --slurm --ddp    

python -m train --config configs/volsdf.yaml  \
    --expname paracam/flow  --training:w_mask 0.0 --training:w_flow 1.0 \
    --camera:mode para \
    --slurm --ddp        

python -m train --config configs/volsdf.yaml  \
    --expname paracam/flow_mask  --training:w_mask 1.0 --training:w_flow 1.0 \
    --camera:mode para \
    --slurm --ddp            


-
python -m train --config configs/volsdf.yaml  \
    --expname gt/rgb_bg  --training:w_mask 0.0 --training:w_flow 0.0 --training:fg 0 \
    --slurm --ddp

python -m train --config configs/volsdf.yaml  \
    --expname gt/flow_bg  --training:w_mask 0.0 --training:w_flow 1.0 --training:fg 0 \
    --slurm --ddp        


python -m train --config configs/volsdf.yaml  \
    --expname gt/rgb  --training:w_mask 0.0 --training:w_flow 0.0 \
    --slurm --ddp

python -m train --config configs/volsdf.yaml  \
    --expname gt/mask  --training:w_mask 1.0 --training:w_flow 0.0 \
    --slurm --ddp    

python -m train --config configs/volsdf.yaml  \
    --expname gt/flow  --training:w_mask 0.0 --training:w_flow 1.0 \
    --slurm --ddp        

python -m train --config configs/volsdf.yaml  \
    --expname gt/flow_mask  --training:w_mask 1.0 --training:w_flow 1.0 \
    --slurm --ddp            





----
python -m train --config configs/volsdf.yaml  \
    --expname sushi/rgb  --training:w_mask 0.0 --training:w_flow 0.0 \
    --slurm --ddp

python -m train --config configs/volsdf.yaml  \
    --expname sushi/mask  --training:w_mask 1.0 --training:w_flow 0.0 \
    --slurm --ddp    

python -m train --config configs/volsdf.yaml  \
    --expname sushi/flow  --training:w_mask 0.0 --training:w_flow 1.0 \
    --slurm --ddp        

python -m train --config configs/volsdf.yaml  \
    --expname sushi/flow_mask  --training:w_mask 1.0 --training:w_flow 1.0 \
    --slurm --ddp            