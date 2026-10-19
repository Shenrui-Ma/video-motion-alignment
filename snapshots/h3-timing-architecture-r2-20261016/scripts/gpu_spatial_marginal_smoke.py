"""Root-only model-free CUDA admission smoke; never run beside an owned service.

Tiny strided BF16 56-head/head128 test by default; --actual-shape uses the
87592-token layout without materializing an N*N matrix. No weights/services.
"""
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

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extensions_staged'))
from H3SpatialMarginalRouter import core


def bitwise(a,b):
    return a.shape==b.shape and a.dtype==b.dtype and torch.equal(a.contiguous().view(torch.uint8),b.contiguous().view(torch.uint8))


def error(a,b):
    d=a.float()-b.float()
    return {'max_abs':float(d.abs().max()),'rms':float(d.square().mean().sqrt())}


def dense_transport(q,k,v,plan):
    p=(q.float()@k.float().transpose(-1,-2)/math.sqrt(q.shape[-1])).softmax(-1)
    ra,rb=plan['reference_video_segment'];qa,qb=plan['query_interval_half_open'];rows=plan['frame_rows'];times=(rb-ra)//rows
    for qi in range(qa,qb):
        t=plan['latent_interval_half_open'][0]+(qi-qa)//rows
        spatial=p[:,:,qi,ra:rb].reshape(1,q.shape[1],times,rows).sum(-2)
        p[:,:,qi,ra:rb]=0
        p[:,:,qi,ra+t*rows:ra+(t+1)*rows]=spatial
    return (p@v.float()).transpose(1,2).reshape(1,q.shape[-2],-1)


def run_case(actual=False,high_mass=False):
    n=87592 if actual else 69
    plan=({'reference_video_segment':[7910,47516],'query_interval_half_open':[61188,66846],
           'latent_interval_half_open':[14,20],'frame_rows':943,'seq_len':87592} if actual else
          {'reference_video_segment':[3,35],'query_interval_half_open':[45,61],
           'latent_interval_half_open':[1,3],'frame_rows':8,'seq_len':69})
    gen=torch.Generator(device='cuda').manual_seed(26101603)
    packed=torch.randn(1,n,3,56,128,generator=gen,device='cuda',dtype=torch.bfloat16)
    q,k,v=packed.permute(2,0,3,1,4).unbind(0)
    ra,rb=plan['reference_video_segment'];qa,qb=plan['query_interval_half_open']
    if high_mass:q.zero_();k.zero_();q[...,0]=4;k[:,:,ra:rb,0]=32
    saved=packed.clone();torch.cuda.synchronize();start=time.monotonic();torch.cuda.reset_peak_memory_stats()
    native=core.route_attention(q,k,v,56,plan,mode='native')
    stats=[];actual_output=core.route_attention(q,k,v,56,plan,mode='spatial_marginal',diagnostics=stats)
    zero=core.route_attention(q,k,v,56,plan,mode='spatial_marginal',alpha=0.)
    with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
        forced=F.scaled_dot_product_attention(q,k,v).transpose(1,2).reshape(1,n,-1)
    checks={'native_matches_forced_flash':bitwise(native,forced),'alpha0_bitwise_native':bitwise(zero,native),
            'untargeted_bitwise_native':bitwise(native[:,:qa],actual_output[:,:qa]) and bitwise(native[:,qb:],actual_output[:,qb:]),
            'input_qkv_unchanged':bitwise(packed,saved),'all_finite':bool(torch.isfinite(actual_output).all()),
            'audit_finite':float(stats[0][3])==1.}
    comparisons={}
    if not actual:
        comparisons['independent_dense_transport']=error(actual_output,dense_transport(q,k,v,plan))
        e=comparisons['independent_dense_transport'];checks['dense_tolerance']=e['max_abs']<=.03 and e['rms']<=.003
        static_v=v.clone();rows=plan['frame_rows'];static_v[:,:,ra:rb]=v[:,:,ra:ra+rows].repeat(1,1,(rb-ra)//rows,1)
        sn=core.route_attention(q,k,static_v,56,plan,mode='native')
        sm=core.route_attention(q,k,static_v,56,plan,mode='spatial_marginal')
        comparisons['static_value_zero_correction']=error(sm,sn)
        e=comparisons['static_value_zero_correction'];checks['static_zero_with_roundoff_tolerance']=e['max_abs']<=.03 and e['rms']<=.003
        if high_mass:checks['reference_mass_above_0999']=float(stats[0][0])>.999
    torch.cuda.synchronize()
    record={'actual_shape':actual,'high_ref_mass':high_mass,'shape':list(q.shape),'strides':list(q.stride()),
            'checks':checks,'passed':all(checks.values()),'comparisons':comparisons,'sampled_stats':stats[0].cpu().tolist(),
            'seconds':time.monotonic()-start,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
            'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'plan':plan}
    del packed,saved,q,k,v,native,actual_output,zero,forced,stats
    gc.collect();torch.cuda.empty_cache()
    return record


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--actual-shape',action='store_true');args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    if not torch.cuda.is_available() or torch.cuda.device_count()!=1:
        raise RuntimeError('Root must first admit an idle GPU and pin exactly one UUID')
    torch.set_num_threads(1)
    cases=[run_case(),run_case(high_mass=True)]
    if args.actual_shape:cases.append(run_case(actual=True))
    report={'schema':'h3-spatial-marginal-smoke-v1','torch':torch.__version__,'cuda':torch.version.cuda,
            'device':torch.cuda.get_device_name(0),'core_sha256':hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest(),
            'tolerance':{'max_abs':.03,'rms':.003},'cases':cases,'passed':all(c['passed'] for c in cases),
            'scope':'Model-free CUDA kernel check, not video evidence; alpha0 bitwise, static cancellation tolerance only'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
