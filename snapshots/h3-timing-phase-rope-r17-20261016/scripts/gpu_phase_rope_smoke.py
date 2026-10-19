"""Root-executed GPU tensor smoke: actual backend, checkpoint RoPE, full shape.
No DiT weights loaded. This script never starts services or generation.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

def coordinate_rope(query, positions, frequency):
    """Independent full 96-dimensional split-half coordinate recomputation."""
    import torch
    per_axis = positions.to(query).unsqueeze(-1) * frequency.to(query)
    angles = torch.cat(tuple(per_axis.unbind(1)), dim=-1)
    c, s = angles.cos()[None, None], angles.sin()[None, None]
    first, second = query[..., :48], query[..., 48:96]
    result = query.clone()
    result[..., :48], result[..., 48:96] = first*c-second*s, first*s+second*c
    return result


def independent_rotated_q(q, frequency, delta):
    import torch
    out=q.clone()
    angles=frequency.to(device=q.device,dtype=torch.float32)*(delta*5/3)
    for i in range(16):
        c,s=angles[i].cos(),angles[i].sin()
        matrix=torch.stack((c,-s,s,c)).reshape(2,2)
        pair=torch.stack((q[...,i],q[...,i+48]),-1).float()
        pair=pair@matrix.T
        out[...,i],out[...,i+48]=pair.to(q.dtype).unbind(-1)
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--gpu-uuid')
    parser.add_argument('--checkpoint',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--cpu-self-test',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/'extensions'))
    if args.cpu_self_test:
        os.environ['CUDA_VISIBLE_DEVICES']=''
        import torch
        from H3PhaseRoPE.core import TemporalRotation
        result=coordinate_checks(torch.linspace(.0001,1,16),TemporalRotation,'cpu',False)
        assert not torch.cuda.is_initialized()
        print(json.dumps({'passed':True,'CUDA_initialized':False,'toy_frequency':True,'coordinate_checks':result}))
        return
    if not all((args.gpu_uuid,args.checkpoint,args.output)):
        parser.error('--gpu-uuid, --checkpoint and --output required')
    if args.gpu_uuid!='GPU-REDACTED':
        raise ValueError('R17 explicitly admitted .9 GPU3 UUID required')
    if args.output.exists(): raise FileExistsError(args.output)
    if not args.output.resolve().is_relative_to(root/'audit'):
        raise ValueError('smoke output must remain in R17 audit')
    query=subprocess.check_output(['nvidia-smi','-i',args.gpu_uuid,'--query-gpu=uuid,memory.used,utilization.gpu',
                                  '--format=csv,noheader,nounits'],text=True).strip()
    uuid,memory,util=[v.strip() for v in query.split(',')]
    processes=subprocess.check_output(['nvidia-smi','-i',args.gpu_uuid,'--query-compute-apps=pid',
                                      '--format=csv,noheader,nounits'],text=True).strip()
    if uuid!=args.gpu_uuid or int(memory)>64 or int(util)!=0 or processes:
        raise RuntimeError('selected GPU not idle before torch/CUDA import')
    os.environ['CUDA_VISIBLE_DEVICES']=uuid
    import torch
    torch.set_num_threads(4)
    from safetensors import safe_open
    import service
    sys.path[:0]=[str(service.CORE),service.DEPENDENCIES]
    sys.argv=['r17-tensor-smoke']
    from compatibility_bootstrap import install
    install()
    import comfy.cli_args
    comfy.cli_args.args.disable_xformers=True
    comfy.cli_args.args.use_pytorch_cross_attention=True
    from comfy.ldm.modules.attention import attention_pytorch
    import comfy.ldm.minimax.model as h3
    from H3PhaseRoPE.core import TemporalRotation, phase_attention, PhaseState, PhaseAttentionOverride
    from H3PhaseRoPE.audited_flash import flash_attention_lse
    if h3.optimized_attention.__name__!='attention_pytorch':
        raise RuntimeError('actual H3 native backend entry mismatch')
    pins=json.loads((root/'configs/parent_core_hashes.json').read_text())
    for name in ('comfy/ldm/minimax/model.py','comfy/ldm/modules/attention.py'):
        if hashlib.sha256((service.CORE/name).read_bytes()).hexdigest()!=pins[name]:
            raise RuntimeError('actual core source mismatch: '+name)
    parent=json.loads((root/'configs/parent_native_attention.json').read_text())
    heads=parent['first_attention']['heads']
    if heads!=56: raise ValueError('frozen R3 attention evidence changed')
    with safe_open(args.checkpoint,framework='pt',device='cpu') as f:
        keys=[k for k in f.keys() if k.endswith('rope.inv_freq')]
        if len(keys)!=1: raise ValueError('expected exactly one checkpoint RoPE buffer')
        frequency=f.get_tensor(keys[0])
    rotation=TemporalRotation(frequency,4.)
    record={'schema':'r17-gpu-numerical-gate-v1','success':False,'pid':os.getpid(),
            'started_unix':time.time(),'GPU':uuid,'admission':query,'checkpoint':str(args.checkpoint),
            'frequency_key':keys[0],'rotation':rotation.metadata(),'torch':str(torch.__version__),
            'native_source':str(service.CORE/'comfy/ldm/modules/attention.py'),
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'head_evidence':'actual R3 audit56; no inference from hidden5376', 'cases':[]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    def save(): args.output.write_text(json.dumps(record,indent=2)+'\n')
    save()
    try:
        torch.backends.cuda.matmul.allow_tf32=False
        generator=torch.Generator(device='cuda').manual_seed(7413)
        for high_mass in (False,True):
            packed=torch.randn(1,256,3,heads,128,generator=generator,device='cuda',dtype=torch.bfloat16)
            q,k,v=[x.transpose(1,2) for x in packed.unbind(2)]
            if high_mass:
                q[:,:,200:224]=q[:,:,200:201].clone()
                k[:,:,12:160]=(q[:,:,200:201].float()*3+.25*torch.randn(1,heads,148,128,
                    generator=generator,device='cuda')).bfloat16()
            original=[x.clone() for x in (q,k,v)]
            native=attention_pytorch(q,k,v,heads,skip_reshape=True)
            flash=flash_attention_lse(q,k,v)[0].transpose(1,2).reshape(1,256,heads*128)
            if not torch.equal(native,flash): raise RuntimeError('actual native vs explicitFlash mismatch')
            plan={'seq_len':256,'query_interval_half_open':[200,224],'reference_video_segment':[12,160]}
            for delta,alpha in [(0.,.5),(4.,0.),(4.,.5),(-4.,.5)]:
                rng=torch.cuda.get_rng_state().clone();cpu_rng=torch.get_rng_state().clone()
                result=phase_attention(q,k,v,heads,plan,rotation=TemporalRotation(frequency,delta),alpha=alpha)
                if not all(torch.equal(a,b) for a,b in zip(original,(q,k,v))): raise RuntimeError('input mutation')
                if not torch.equal(rng,torch.cuda.get_rng_state()) or not torch.equal(cpu_rng,torch.get_rng_state()): raise RuntimeError('RNG mutation')
                if not torch.isfinite(result).all(): raise RuntimeError('nonfinite output')
                if not torch.equal(result[:,:200],native[:,:200]) or not torch.equal(result[:,224:],native[:,224:]): raise RuntimeError('outside-query change')
                row={'high_mass':high_mass,'delta':delta,'alpha':alpha}
                if delta==0 or alpha==0:
                    if not torch.equal(result,native): raise RuntimeError('zero mismatch')
                    row['native_bitwise']=True
                else:
                    qp=independent_rotated_q(q[:,:,200:224],frequency,delta)
                    torch.testing.assert_close(TemporalRotation(frequency,delta)(q[:,:,200:224]),qp,atol=.03125,rtol=0)
                    p=(q.float()@k.float().transpose(-1,-2)/(128**.5)).softmax(-1)
                    m=p[:,:,200:224,12:160].sum(-1,keepdim=True)
                    if high_mass and float(m.min())<=.999: raise RuntimeError('high mass not exercised')
                    rp=(qp.float()@k[:,:,12:160].float().transpose(-1,-2)/(128**.5)).softmax(-1)
                    p[:,:,200:224,12:160]=(1-alpha)*p[:,:,200:224,12:160]+alpha*m*rp
                    oracle=(p@v.float()).transpose(1,2).reshape(1,256,heads*128)
                    error=result[:,200:224].float()-oracle[:,200:224]
                    maximum,rms=float(error.abs().max()),float(error.square().mean().sqrt())
                    if maximum>=.025 or rms>=.003: raise RuntimeError(f'dense tolerance exceeded {maximum}/{rms}')
                    row.update(max_abs=maximum,rms=rms,tolerance=[.025,.003],min_ref_mass=float(m.min()))
                record['cases'].append(row)
                del result
            del packed,q,k,v,original,native,flash
        record['coordinate_checks']=coordinate_checks(frequency,TemporalRotation,'cuda',True)
        # Actual packed length and parent reference segment; never allocate N x N.
        plan=parent['validated_layout'];n=parent['first_attention']['qkv_shape'][2]
        gen=torch.Generator(device='cuda').manual_seed(819)
        packed=torch.randn(1,n,3,heads,128,generator=gen,device='cuda',dtype=torch.bfloat16)
        q,k,v=[x.transpose(1,2) for x in packed.unbind(2)]
        native=attention_pytorch(q,k,v,heads,skip_reshape=True)
        zero=phase_attention(q,k,v,heads,plan,rotation=TemporalRotation(frequency,0.),alpha=.5)
        if not torch.equal(native,zero): raise RuntimeError('fullshape native/zero mismatch')
        del zero
        outside=lambda x: (x[:,:plan['query_interval_half_open'][0]],x[:,plan['query_interval_half_open'][1]:])
        original=[x.clone() for x in (q,k,v)]
        fullrows=[]
        for delta in (4.,-4.):
            rng=torch.cuda.get_rng_state().clone();stats=[]
            output=phase_attention(q,k,v,heads,plan,rotation=TemporalRotation(frequency,delta),alpha=.5,diagnostics=stats)
            if not bool(torch.isfinite(output).all()): raise RuntimeError('nonfinite full output')
            if not all(torch.equal(a,b) for a,b in zip(outside(native),outside(output))): raise RuntimeError('fullshape outside query changed')
            if not all(torch.equal(a,b) for a,b in zip(original,(q,k,v))): raise RuntimeError('fullshape QKV mutation')
            if not torch.equal(rng,torch.cuda.get_rng_state()): raise RuntimeError('fullshape RNG mutation')
            fullrows.append({'delta':delta,'all_finite':True,'outside_bitwise':True,'stats':stats[0].cpu().tolist()})
            del output
        torch.cuda.synchronize()
        record.update(success=True,fullshape=list(q.shape),fullshape_zero_actual_native_bitwise=True,
                      fullshape_signed=fullrows,peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                      finished_unix=time.time(),scope='random tensor actual-backend/full-shape; no H3 DiT or quality proof')
        save();print(json.dumps(record,indent=2))
    except BaseException as error:
        record.update(error=repr(error),finished_unix=time.time());save();raise



def coordinate_checks(frequency, TemporalRotation, device, try_kitchen=True):
    import torch
    generator = torch.Generator(device=device).manual_seed(159)
    raw = torch.randn(1, 4, 8, 128, generator=generator, device=device, dtype=torch.float64)
    positions = torch.tensor([[0,0,0], [5/3,1,2], [47*5/3,3,4], [65*5/3,5,6],
                              [6960,1,1], [7196,2,3], [7274+1/3,3,2], [7304+1/3,4,4]],
                             device=device, dtype=torch.float64)
    base = coordinate_rope(raw, positions, frequency.double())
    rows = []
    for delta in (-4.0, 4.0, 0.25):
        shifted = positions.clone()
        shifted[:, 0] += delta * 5/3
        direct = coordinate_rope(raw, shifted, frequency.double())
        composed = TemporalRotation(frequency.double(), delta)(base)
        error = composed-direct
        torch.testing.assert_close(composed, direct, atol=2e-10, rtol=2e-10)
        assert torch.equal(composed[...,16:48], base[...,16:48])
        assert torch.equal(composed[...,64:], base[...,64:])
        rows.append({'delta_frames': delta, 'max_abs_fp64': float(error.abs().max()),
                     'rms_fp64': float(error.square().mean().sqrt())})
    result = {'independent_full_coordinate_recomputation': rows,
              'includes_large_packed_time_coordinates': True,
              'kitchen': {'status': 'not_requested', 'claim': 'mathematical comparison only'}}
    if not try_kitchen:
        return result
    try:
        from compatibility_bootstrap import install
        install()
        import comfy_kitchen as kitchen
        # Current .9 Core disables this compiled CUDA backend for torch cu121.
        # Explicitly call the installed eager partial-RoPE implementation instead
        # of asking the registry to select an unsupported CUDA13 kernel.
        kitchen.disable_backend('cuda')
        from comfy_kitchen.backends.eager import rope as eager_rope
    except ImportError as error:
        raise RuntimeError('Installed kitchen eager comparison unavailable; no native check claimed') from error
    function = getattr(eager_rope, 'rms_rope_split_half_', None)
    if not callable(function):
        raise RuntimeError('Installed eager partial split-half API is unavailable')
    def table(pos, dtype):
        # Current H3 rope_freqs and rope_rotation_table use FP32 coordinates.
        axes = pos.float().unsqueeze(-1) * frequency.to(device=device, dtype=torch.float32).view(1,1,-1)
        angles = torch.cat(tuple(axes.unbind(1)), -1)
        c, s = angles.cos(), angles.sin()
        return torch.stack((c,-s,s,c), -1).reshape(1,8,1,48,2,2).to(dtype)
    rows = []
    for dtype in (torch.float32, torch.bfloat16):
        original = raw.to(dtype).transpose(1,2).contiguous()
        weights = torch.ones(128, device=device, dtype=dtype)
        base_q, _ = function(original.clone(), original.clone(), table(positions,dtype),
                             weights, weights, epsilon=1e-5, rot_dim=96)
        base_q = base_q.transpose(1,2)
        for delta in (-4.0,4.0,0.25):
            shifted = positions.clone()
            shifted[:,0] += delta * 5/3
            direct_q, _ = function(original.clone(), original.clone(), table(shifted,dtype),
                                   weights, weights, epsilon=1e-5, rot_dim=96)
            composed = TemporalRotation(frequency,delta)(base_q)
            error = composed.float()-direct_q.transpose(1,2).float()
            maximum, rms = float(error.abs().max()), float(error.square().mean().sqrt())
            # Extra rotation adds BF16 rounding; large FP32 coordinates add
            # argument rounding for fractional frame offsets. Do not demand bitwise.
            tolerance = (0.005,0.0006) if dtype==torch.float32 else (0.0625,0.012)
            assert maximum <= tolerance[0] and rms <= tolerance[1], (dtype,delta,maximum,rms)
            assert torch.equal(composed[...,16:48], base_q[...,16:48])
            assert torch.equal(composed[...,64:], base_q[...,64:])
            rows.append({'dtype': str(dtype), 'delta_frames': delta, 'max_abs': maximum,
                         'rms': rms, 'predeclared_max_rms_tolerance': list(tolerance)})
    result['kitchen'] = {'status':'passed', 'api':'comfy_kitchen.backends.eager.rope.rms_rope_split_half_',
                         'module':str(Path(eager_rope.__file__).resolve()), 'rot_dim':96,
                         'module_sha256':hashlib.sha256(Path(eager_rope.__file__).read_bytes()).hexdigest(),
                         'backend_selection':'explicit installed eager implementation; CUDA backend disabled locally',
                         'service_relation':'same partial split-half eager implementation; does not test CUDA13 or Triton fused full-RoPE kernel',
                         'scope':'actual installed eager API, tiny tensors, unit RMS weights, no model forward', 'rows':rows}
    return result


if __name__=='__main__':main()
