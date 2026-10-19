"""Native-arm passive post-attention/pre-W_O feature snapshots; no model calls."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

CAPTURE_STEPS = (6, 10, 14)
CAPTURE_BLOCK = 25
HEAD_INDICES = (0, 14, 28, 42)


def _signature(value):
    import torch
    if value.device.type != 'cpu' or not value.is_contiguous():
        raise ValueError('feature signature requires contiguous CPU tensor')
    return {'shape':list(value.shape),'dtype':str(value.dtype),
            'bytes':value.numel()*value.element_size(),
            'sha256':hashlib.sha256(value.view(torch.uint8).numpy()).hexdigest()}


def _file_sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def _exclusive_tensor_save(path,payload):
    """Publish complete bytes atomically, without overwriting an existing name."""
    import torch
    fd,temporary=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            torch.save(payload,stream);stream.flush();os.fsync(stream.fileno())
        # Same-directory hard link is atomic and refuses an existing destination.
        os.link(temporary,path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save_native_features(out,plan,*,output_dir,run_id,step,block,sigma_video,
                         num_heads=56,head_dim=128,selected_heads=HEAD_INDICES,
                         expected_grid=(42,23,41)):
    """Copy only selected native attention head outputs; return artifact metadata.

    Production defaults are fixed by the audited H3 architecture. Smaller
    explicit dimensions/head selections are supported only for tensor tests.
    `out` is [1,N,H*D], before native attention out_proj/W_O. No returned model
    tensor, attention recomputation, in-place write or global RNG/TF32 change.
    """
    import torch
    if type(step) is not int or step not in CAPTURE_STEPS or block != CAPTURE_BLOCK:
        raise ValueError('native feature checkpoint must be block25 at steps6/10/14')
    if not isinstance(run_id,str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',run_id) is None:
        raise ValueError('unsafe feature run identifier')
    if not math.isfinite(float(sigma_video)) or not 0 <= float(sigma_video) <= 1:
        raise ValueError('invalid actual video sigma')
    if any(type(v) is not int or v<1 for v in (num_heads,head_dim,*expected_grid)):
        raise ValueError('invalid feature geometry')
    if (not selected_heads or len(set(selected_heads))!=len(selected_heads)
            or any(type(h) is not int or not 0<=h<num_heads for h in selected_heads)):
        raise ValueError('invalid selected head indices')
    if out.ndim!=3 or out.shape[0]!=1 or out.shape[-1]!=num_heads*head_dim or out.dtype!=torch.bfloat16:
        raise ValueError('expected native [1,N,H*D] BF16 attention output')
    if plan.get('seq_len')!=out.shape[1]:raise ValueError('packed output length differs from validated layout')
    signature=plan.get('signature')
    if (not isinstance(signature,(list,tuple)) or len(signature)!=5
            or signature[2]%2 or signature[3]%2):
        raise ValueError('validated H3 grid signature is required')
    grid=(signature[1],signature[2]//2,signature[3]//2)
    if tuple(grid)!=tuple(expected_grid) or plan['frame_rows']!=grid[1]*grid[2]:
        raise ValueError('validated frame grid differs from expected capture grid')
    count=math.prod(grid)
    segments=[plan['reference_video_segment'],plan['target_video_segment']]
    if any(len(s)!=2 or not 0<=s[0]<s[1]<=out.shape[1] or s[1]-s[0]!=count for s in segments):
        raise ValueError('reference/target segments must contain complete matching grids')
    if max(segments[0][0],segments[1][0])<min(segments[0][1],segments[1][1]):
        raise ValueError('reference and output video segments overlap')
    root=Path(output_dir)
    if not root.is_absolute():raise ValueError('native feature directory must be absolute')
    root.mkdir(parents=True,exist_ok=True);run_dir=root/run_id
    if run_dir.is_symlink():raise ValueError('native feature run directory cannot be a symlink')
    run_dir.mkdir(exist_ok=True)
    path=run_dir/f'block{block}_step{step:03d}.pt'
    if path.exists():raise FileExistsError(path)
    head_index=torch.tensor(selected_heads,device=out.device,dtype=torch.long)
    unpacked=out.detach().reshape(1,out.shape[1],num_heads,head_dim)
    captured={}
    for name,(start,stop) in zip(('reference','target'),segments):
        selected=unpacked[:,start:stop].index_select(2,head_index)
        arranged=selected.reshape(1,*grid,len(selected_heads),head_dim).permute(0,4,1,2,3,5)
        cpu=arranged.to(device='cpu',copy=True).contiguous()
        if not bool(torch.isfinite(cpu).all()):raise ValueError('nonfinite captured native feature')
        captured[name]=cpu
        del selected,arranged
    meta={'schema':'h3-native-attention-features-v1','run_id':run_id,
          'mode':'native','block_index':block,'forward_index':step,
          'sampler_sigma_video':float(sigma_video),'sigma_scope':'actual video sampler sigma; not audio sigma',
          'stage':'route_attention returned [B,N,H*D], before native Attention.out_proj / W_O',
          'scope':'contextual native attention output, not reference ground-truth action or isolated motion',
          'source_shape':list(out.shape),'source_dtype':str(out.dtype),'num_heads':num_heads,
          'head_dim':head_dim,'head_indices':list(selected_heads),'grid':list(grid),
          'tensor_axis_order':['batch','selected_head','latent_time','patch_row','patch_col','head_channel'],
          'layout':json.loads(json.dumps(plan)),
          'tensors':{name:_signature(value) for name,value in captured.items()}}
    _exclusive_tensor_save(path,{**captured,'metadata':meta})
    return {'path':str(path),'sha256':_file_sha(path),'bytes':path.stat().st_size,'metadata':meta}
