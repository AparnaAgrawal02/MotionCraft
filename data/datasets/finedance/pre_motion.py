import argparse
import os
from pathlib import Path
import smplx, pickle
import torch
import sys
from tqdm import tqdm
import glob
import numpy as np

sys.path.append(os.getcwd()) 

import torch


from pytorch3d.transforms import (axis_angle_to_matrix, matrix_to_axis_angle,
                                  matrix_to_quaternion, matrix_to_rotation_6d,
                                  quaternion_to_matrix, rotation_6d_to_matrix)


def quat_to_6v(q):
    assert q.shape[-1] == 4
    mat = quaternion_to_matrix(q)
    mat = matrix_to_rotation_6d(mat)
    return mat


def quat_from_6v(q):
    assert q.shape[-1] == 6
    mat = rotation_6d_to_matrix(q)
    quat = matrix_to_quaternion(mat)
    return quat


def ax_to_6v(q):
    assert q.shape[-1] == 3
    mat = axis_angle_to_matrix(q)
    mat = matrix_to_rotation_6d(mat)
    return mat


def ax_from_6v(q):
    assert q.shape[-1] == 6
    mat = rotation_6d_to_matrix(q)
    ax = matrix_to_axis_angle(mat)
    return ax


def quat_slerp(x, y, a):
    """
    Performs spherical linear interpolation (SLERP) between x and y, with proportion a

    :param x: quaternion tensor (N, S, J, 4)
    :param y: quaternion tensor (N, S, J, 4)
    :param a: interpolation weight (S, )
    :return: tensor of interpolation results
    """
    len = torch.sum(x * y, axis=-1)

    neg = len < 0.0
    len[neg] = -len[neg]
    y[neg] = -y[neg]

    a = torch.zeros_like(x[..., 0]) + a

    amount0 = torch.zeros_like(a)
    amount1 = torch.zeros_like(a)

    linear = (1.0 - len) < 0.01
    omegas = torch.arccos(len[~linear])
    sinoms = torch.sin(omegas)

    amount0[linear] = 1.0 - a[linear]
    amount0[~linear] = torch.sin((1.0 - a[~linear]) * omegas) / sinoms

    amount1[linear] = a[linear]
    amount1[~linear] = torch.sin(a[~linear] * omegas) / sinoms

    # reshape
    amount0 = amount0[..., None]
    amount1 = amount1[..., None]

    res = amount0 * x + amount1 * y

    return res



def motion_feats_extract(inputs_dir, outputs_dir):
    device = "cuda:0"
    print("extracting")
    raw_fps = 30
    data_fps = 30
    data_fps <= raw_fps
    if not os.path.exists(outputs_dir):
        os.makedirs(outputs_dir)
    # All motion is retargeted to this standard model.
    smplx_model = smplx.SMPLX(model_path='path_to_smplx_model', ext='npz', gender='neutral',
                             num_betas=10, flat_hand_mean=True, num_expression_coeffs=10, use_pca=False).eval().to(device)
        
    motions = sorted(glob.glob(os.path.join(inputs_dir, "*.npy")))
    for motion in tqdm(motions):
        name = os.path.splitext(os.path.basename(motion))[0].split(".")[0]
        print("name is", name)
        data = np.load(motion, allow_pickle=True)
        print(data.shape)
        pos = data[:,:3]   # length, c
        q = data[:,3:]
        root_pos = torch.Tensor(pos).to(device) # T, 3
        length = root_pos.shape[0]
        local_q_rot6d = torch.Tensor(q).to(device)    # T, 312
        print("local_q_rot6d", local_q_rot6d.shape)
        local_q = local_q_rot6d.reshape(length, 52, 6).clone()
        local_q = ax_from_6v(local_q).view(length, 156)           # T, 156
        
        smplx_output = smplx_model(
                betas = torch.zeros([root_pos.shape[0], 10], device=device, dtype=torch.float32),
                transl = root_pos,        # global translation
                global_orient = local_q[:, :3],
                body_pose = local_q[:, 3:66],           # 21
                jaw_pose = torch.zeros([root_pos.shape[0], 3], device=device, dtype=torch.float32),         # 1
                leye_pose = torch.zeros([root_pos.shape[0],  3], device=device, dtype=torch.float32),        # 1
                reye_pose= torch.zeros([root_pos.shape[0],  3], device=device, dtype=torch.float32),          # 1
                left_hand_pose = local_q[:, 66:66+45],   # 15
                right_hand_pose = local_q[:, 66+45:], # 15
                expression = torch.zeros([root_pos.shape[0], 10], device=device, dtype=torch.float32),
                return_verts = False
        )
        
        
        positions = smplx_output.joints.view(length, -1, 3)   # bxt, j, 3
        feet = positions[:, (7, 8, 10, 11)]  # # 150, 4, 3
        feetv = torch.zeros(feet.shape[:2], device=device)     # 150, 4
        feetv[:-1] = (feet[1:] - feet[:-1]).norm(dim=-1)
        contacts = (feetv < 0.01).to(local_q)  # cast to right dtype        # b, 150, 4

        mofea319 = torch.cat([contacts, root_pos, local_q_rot6d], dim=1)
        assert mofea319.shape[1] == 319
        mofea319 = mofea319.detach().cpu().numpy()
        np.save(os.path.join(outputs_dir, name+'.npy'), mofea319)
    return

def motion_feats_extract_axis(inputs_dir, outputs_dir):
    device = "cuda:0"
    print("extracting")
    raw_fps = 30
    data_fps = 30
    data_fps <= raw_fps
    if not os.path.exists(outputs_dir):
        os.makedirs(outputs_dir)
    # All motion is retargeted to this standard model.
    smplx_model = smplx.SMPLX(model_path='path_to_smplx_model', ext='npz', gender='neutral',
                             num_betas=10, flat_hand_mean=True, num_expression_coeffs=10, use_pca=False).eval().to(device)
        
    motions = sorted(glob.glob(os.path.join(inputs_dir, "*.npy")))
    for motion in tqdm(motions):
        name = os.path.splitext(os.path.basename(motion))[0].split(".")[0]
        print("name is", name)
        data = np.load(motion, allow_pickle=True)
        print(data.shape)
        pos = data[:,:3]   # length, c
        q = data[:,3:]
        root_pos = torch.Tensor(pos).to(device) # T, 3
        length = root_pos.shape[0]
        local_q_rot6d = torch.Tensor(q).to(device)    # T, 312
        print("local_q_rot6d", local_q_rot6d.shape)
        local_q = local_q_rot6d.reshape(length, 52, 6).clone()
        local_q = ax_from_6v(local_q).view(length, 156)           # T, 156
        
        smplx_output = smplx_model(
                betas = torch.zeros([root_pos.shape[0], 10], device=device, dtype=torch.float32),
                transl = root_pos,        # global translation
                global_orient = local_q[:, :3],
                body_pose = local_q[:, 3:66],           # 21
                jaw_pose = torch.zeros([root_pos.shape[0], 3], device=device, dtype=torch.float32),         # 1
                leye_pose = torch.zeros([root_pos.shape[0],  3], device=device, dtype=torch.float32),        # 1
                reye_pose= torch.zeros([root_pos.shape[0],  3], device=device, dtype=torch.float32),          # 1
                left_hand_pose = local_q[:, 66:66+45],   # 15
                right_hand_pose = local_q[:, 66+45:], # 15
                expression = torch.zeros([root_pos.shape[0], 10], device=device, dtype=torch.float32),
                return_verts = False
        )
        
        
        positions = smplx_output.joints.view(length, -1, 3)   # bxt, j, 3
        feet = positions[:, (7, 8, 10, 11)]  # # 150, 4, 3
        feetv = torch.zeros(feet.shape[:2], device=device)     # 150, 4
        feetv[:-1] = (feet[1:] - feet[:-1]).norm(dim=-1)
        contacts = (feetv < 0.01).to(local_q)  # cast to right dtype        # b, 150, 4

        mofea319 = torch.cat([contacts, root_pos, local_q], dim=1)
        assert mofea319.shape[1] == 163
        mofea319 = mofea319.detach().cpu().numpy()
        np.save(os.path.join(outputs_dir, name+'.npy'), mofea319)
    return
if __name__ == "__main__":
    # motion_feats_extract("./motion", "./motion_fea319")
    motion_feats_extract_axis("./motion", "./motion_fea163")