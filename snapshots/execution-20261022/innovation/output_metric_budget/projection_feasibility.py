"""CPU feasibility math only. Not a replacement for the real quantized kernel."""
import math
import torch


def regular_hadamard(group_size, *, dtype=torch.float64, device="cpu"):
    if group_size < 4 or group_size & (group_size - 1) or int(math.log2(group_size)) % 2:
        raise ValueError("group size must be a power of 4")
    h4=torch.tensor([[1,1,1,-1],[1,1,-1,1],[1,-1,1,1],[-1,1,1,1]],dtype=dtype,device=device)
    h=h4
    while h.shape[0] < group_size:h=torch.kron(h,h4)
    return h / math.sqrt(group_size)


def rotate_rows(x, group_size):
    if x.shape[-1] % group_size:raise ValueError("incomplete rotation group")
    h=regular_hadamard(group_size,dtype=x.dtype,device=x.device)
    return (x.reshape(-1,x.shape[-1]//group_size,group_size)@h).reshape_as(x)


def streamed_weight_sketch(q_rot, row_scale, projection, *, group_size, row_chunk=256):
    """Return W_dequant^T R without materializing all floating-point W.

    q_rot [O,I] int8; row_scale [O] or [O,1]; R [O,k], shared by heads.
    Rotation is across original feature groups, BEFORE splitting attention heads.
    """
    if q_rot.ndim!=2 or projection.ndim!=2 or projection.shape[0]!=q_rot.shape[0]:raise ValueError("bad geometry")
    if q_rot.dtype!=torch.int8 or row_chunk<=0:raise ValueError("require int8 and positive chunk")
    scale=row_scale.reshape(-1)
    if scale.numel()!=q_rot.shape[0] or not torch.isfinite(scale).all() or not torch.isfinite(projection).all():raise ValueError("bad scale/projection")
    out=torch.zeros((q_rot.shape[1],projection.shape[1]),dtype=projection.dtype,device=projection.device)
    for start in range(0,q_rot.shape[0],row_chunk):
        stop=min(start+row_chunk,q_rot.shape[0])
        out.add_(q_rot[start:stop].to(projection.dtype).T @ (scale[start:stop,None].to(projection.dtype)*projection[start:stop]))
    return rotate_rows(out.T,group_size).T


def row_quantized_surrogate(x,q_rot,row_scale,*,group_size):
    """Reference row INT8 quantization, not bit-exact CUDA operator emulation."""
    y=rotate_rows(x,group_size)
    scale=y.abs().amax(-1,keepdim=True)/127
    safe=scale.clamp_min(torch.finfo(x.dtype).tiny)
    rounded=(y/safe).round().clamp(-127,127)
    restored=rounded*scale
    return restored @ q_rot.to(x.dtype).T * row_scale.reshape(1,-1)
