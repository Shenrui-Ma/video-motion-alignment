"""Root-admitted, model-free BF16 checks for the R27 dynamic temporal-union operator."""
import argparse
import gc
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import torch
import torch.nn.functional as F
from torch.nn.attention import SDPBackend, sdpa_kernel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'extensions'))
from H3TemporalRouter import core
from H3TemporalRouter.mask import QueryGain
from H3TemporalRouter import sealed_r3_core as sealed


def bits(a, b):
    return a.shape == b.shape and a.dtype == b.dtype and torch.equal(a.contiguous().view(torch.uint8), b.contiguous().view(torch.uint8))


def dense(q, k, v, plan, gain):
    probabilities = (q.float() @ k.float().transpose(-1, -2) / math.sqrt(q.shape[-1])).softmax(-1)
    qa, qb = plan['query_interval_half_open']; ra, rb = plan['reference_video_segment']
    rows = plan['frame_rows']; lo = plan['latent_interval_half_open'][0]
    for index in range(qa, qb):
        old = probabilities[:, :, index, ra:rb].clone()
        mass = old.sum(-1, keepdim=True)
        t = lo + (index - qa) // rows
        a, b = ra + t * rows, ra + (t + 1) * rows
        aligned = (q[:, :, index:index+1].float() @ k[:, :, a:b].float().transpose(-1,-2) / math.sqrt(q.shape[-1])).softmax(-1).squeeze(-2)
        weight = float(gain.tensor.flatten()[index - qa])
        probabilities[:, :, index, ra:rb] *= 1 - weight
        probabilities[:, :, index, a:b] += weight * mass * aligned
    return (probabilities @ v.float()).transpose(1, 2).reshape(1, q.shape[-2], -1)


def run_case(actual=False, high_mass=False):
    if actual:
        metadata=json.loads((ROOT/'configs/parent_conditioning.json').read_text())
        segments=metadata['packed_layout']['segments'];refs=[s for s in segments if s[2]=='ref_img']
        # Unique reference video is identified by actual latent_t42 token count;
        # the producer records image then video, not by the generic ref_img label.
        rows=943;ref=[s for s in refs if s[1]-s[0]==42*rows]
        target=[s for s in segments if s[2]=='video']
        if len(ref)!=1 or len(target)!=1:raise ValueError('ambiguous actual parent layout')
        n=metadata['packed_layout']['seq_len']
        plan={'seq_len':n,'frame_rows':rows,'latent_interval_half_open':[0,42],
              'query_interval_half_open':target[0][:2],'reference_video_segment':ref[0][:2]}
    else:
        n=69;plan={'seq_len':n,'frame_rows':8,'latent_interval_half_open':[0,4],
                  'query_interval_half_open':[35,67],'reference_video_segment':[3,35]}
    generator = torch.Generator(device='cuda').manual_seed(26101616)
    packed = torch.randn(1,n,3,56,128,device='cuda',dtype=torch.bfloat16,generator=generator)
    q,k,v = packed.permute(2,0,3,1,4).unbind(0)
    qa,qb = plan['query_interval_half_open'];ra,rb = plan['reference_video_segment']
    if high_mass:
        q.zero_(); k.zero_(); q[...,0]=4; k[:,:,ra:rb,0]=32
    original = packed.clone(); rng = torch.cuda.get_rng_state().clone()
    shape=(42,23,41) if actual else (4,1,8)
    local=torch.zeros(shape);local[0]=1;local[-1]=1
    if actual:local[14:20]=1
    values={'empty':torch.zeros(shape),'local':local,'full':torch.ones(shape)}
    start=time.monotonic();torch.cuda.reset_peak_memory_stats()
    native=sealed.route_attention(q,k,v,56,plan,mode='native')
    checks={};comparisons={}
    if not actual:
        with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
            forced=F.scaled_dot_product_attention(q,k,v).transpose(1,2).reshape(1,n,-1)
        checks['native_matches_forced_flash']=bits(native,forced)
        zero=core.route_attention(q,k,v,56,plan,mode='mass_preserve',query_gain=QueryGain(torch.zeros(shape),shape))
        one=core.route_attention(q,k,v,56,plan,mode='mass_preserve',query_gain=QueryGain(torch.ones(shape),shape))
        full=sealed.route_attention(q,k,v,56,plan,mode='mass_preserve')
        checks['zero_exact_native']=bits(zero,native);checks['one_exact_sealed_full']=bits(one,full)
        del forced,zero,one,full
    for variant, value in values.items():
        torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();variant_start=time.monotonic()
        starting_allocated=torch.cuda.memory_allocated();starting_reserved=torch.cuda.memory_reserved()
        gain=QueryGain(value,shape);stats=[]
        output=core.route_attention(q,k,v,56,plan,mode='mass_preserve',query_gain=gain,diagnostics=stats)
        checks[variant+'_full_finite']=bool(torch.isfinite(output).all())
        checks[variant+'_outside_exact']=bits(output[:,:qa],native[:,:qa]) and bits(output[:,qb:],native[:,qb:])
        zero_indices=(gain.tensor.flatten()==0).nonzero().flatten().to(q.device)+qa
        checks[variant+'_zero_rows_exact']=bits(output.index_select(1,zero_indices),native.index_select(1,zero_indices))
        if not actual:
            diff=output.float()-dense(q,k,v,plan,gain)
            error={'max_abs':float(diff.abs().max()),'rms':float(diff.square().mean().sqrt())}
            comparisons[variant]=error;checks[variant+'_dense_tolerance']=error['max_abs']<=.03 and error['rms']<=.003
        if variant=='empty':checks['empty_exact_native']=bits(output,native)
        if actual and variant=='full':
            sealed_full=sealed.route_attention(q,k,v,56,plan,mode='mass_preserve')
            checks['actual_all_bins_exact_sealed_full']=bits(output,sealed_full)
            del sealed_full
        if high_mass and stats:checks[variant+'_mass_above_0999']=float(stats[0][0])>.999
        comparisons.setdefault(variant,{}).update(seconds=time.monotonic()-variant_start,starting_allocated_bytes=starting_allocated,starting_reserved_bytes=starting_reserved,increment_peak_allocated_bytes=torch.cuda.max_memory_allocated()-starting_allocated,peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved())
        del output,stats,gain
    checks['QKV_unchanged']=bits(packed,original);checks['global_CUDA_RNG_unchanged']=bits(rng,torch.cuda.get_rng_state())
    torch.cuda.synchronize()
    record={'actual_shape':actual,'high_mass':high_mass,'shape':list(q.shape),'plan':plan,'checks':checks,
            'comparisons':comparisons,'passed':all(checks.values()),'seconds':time.monotonic()-start,
            'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved()}
    del packed,original,q,k,v,native
    gc.collect();torch.cuda.empty_cache()
    return record


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--root-admitted',action='store_true');args=parser.parse_args()
    import os,subprocess
    if not args.root_admitted or os.environ.get('CUDA_VISIBLE_DEVICES')!='GPU-REDACTED':raise ValueError('requires explicit root admission and exact GPU3 UUID')
    pending=subprocess.check_output(['nvidia-smi','--id='+os.environ['CUDA_VISIBLE_DEVICES'],'--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).strip()
    if pending:raise RuntimeError('selected GPU has compute processes')
    if args.output.exists():raise FileExistsError(args.output)
    if not torch.cuda.is_available() or torch.cuda.device_count()!=1:raise RuntimeError('admit one idle GPU UUID first')
    torch.set_num_threads(1)
    cases=[run_case(),run_case(high_mass=True),run_case(actual=True)]
    record={'schema':'h3-r27-kernel-gate-v1','protocol_sha256':hashlib.sha256((ROOT/'configs/protocol.json').read_bytes()).hexdigest(),
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(core.__file__),Path(sealed.__file__),ROOT/'extensions/H3TemporalRouter/mask.py')},'torch':torch.__version__,'cuda':torch.version.cuda,
            'core_sha256':hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest(),
            'sealed_core_sha256':hashlib.sha256(Path(sealed.__file__).read_bytes()).hexdigest(),
            'cases':cases,'passed':all(x['passed'] for x in cases),'GPU_allocated_end':torch.cuda.memory_allocated(),
            'GPU_reserved_end':torch.cuda.memory_reserved(),'NFE':0,'model_weights_loaded':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record));raise SystemExit(0 if record['passed'] else 1)


if __name__=='__main__':main()
