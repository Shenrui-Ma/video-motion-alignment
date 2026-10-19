"""Root-operated, model-free CUDA smoke. Does not load weights or launch services.

Default: tiny strided [1,56,*,128] BF16 QKV, including near-unit ref mass.
Optional --actual-shape: one native/full/dynamic/static round at the audited
[1,56,87592,128] layout; no dense NxN allocation. Run only after GPU admission.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extensions'))
from H3TemporalRouter import core


def dense(q, k, v):
    logits = q.float() @ k.float().transpose(-1, -2) / math.sqrt(q.shape[-1])
    return logits.softmax(-1) @ v.float(), logits.logsumexp(-1)


def bitwise(a, b):
    return (a.shape == b.shape and a.dtype == b.dtype
            and torch.equal(a.contiguous().view(torch.uint8), b.contiguous().view(torch.uint8)))


def error(a, b):
    diff = a.float()-b.float()
    return {'max_abs':float(diff.abs().max()),'rms':float(diff.square().mean().sqrt())}


def norms(full, dynamic, static):
    f,d,s=[x.float().reshape(-1) for x in (full,dynamic,static)]
    denom=d.norm()*s.norm()
    return {'full_rms':float(f.square().mean().sqrt()),
            'dynamic_rms':float(d.square().mean().sqrt()),
            'static_rms':float(s.square().mean().sqrt()),
            'dynamic_static_cosine':float((d@s)/denom) if float(denom)>0 else None,
            'decomposition_error':error(f,d+s),
            'scope':'same input QKV, not independently generated trajectories'}


def run_case(name, actual=False, high_mass=False):
    if actual:
        n=87592
        plan={'reference_video_segment':[7910,47516],
              'query_interval_half_open':[47986+14*943,47986+20*943],
              'latent_interval_half_open':[14,20],'frame_rows':943,'seq_len':87592}
    else:
        n=69
        plan={'reference_video_segment':[3,35],'query_interval_half_open':[45,61],
              'latent_interval_half_open':[1,3],'frame_rows':8,'seq_len':n}
    gen=torch.Generator(device='cuda').manual_seed(26101602)
    # Same interleaved projection-buffer stride family as native qkv_proj.
    packed=torch.randn(1,n,3,56,128,generator=gen,device='cuda',dtype=torch.bfloat16)
    q,k,v=packed.permute(2,0,3,1,4).unbind(0)
    ra,rb=plan['reference_video_segment'];qa,qb=plan['query_interval_half_open']
    if high_mass:
        q.zero_();k.zero_();q[...,0]=4;k[:,:,ra:rb,0]=32
    saved=packed.clone()
    torch.cuda.synchronize();start=time.monotonic();torch.cuda.reset_peak_memory_stats()
    outputs={}
    for mode in ('native','mass_preserve','dynamic_residual','static_component'):
        outputs[mode]=core.route_attention(q,k,v,56,plan,mode=mode)
    native=outputs['native']
    checks={}
    for mode in core.VALUE_SPLIT_MODES:
        zero=core.route_attention(q,k,v,56,plan,mode=mode,alpha=0)
        checks[mode+'_alpha0_bitwise_native']=bitwise(zero,native)
        checks[mode+'_untargeted_bitwise_native']=(bitwise(outputs[mode][:,:qa],native[:,:qa])
                                                    and bitwise(outputs[mode][:,qb:],native[:,qb:]))
    with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
        forced=F.scaled_dot_product_attention(q,k,v).transpose(1,2).reshape(1,n,56*128)
    checks['native_bitwise_forced_sdpa_flash']=bitwise(native,forced)
    checks['input_qkv_bitwise_unchanged']=bitwise(saved,packed)
    checks['all_outputs_finite']=all(bool(torch.isfinite(x).all()) for x in outputs.values())
    comparisons={}
    if not actual:
        for mode in outputs:
            expected=core.route_attention(q.float(),k.float(),v.float(),56,plan,
                                          mode=mode,attention=dense)
            comparisons[mode]=error(outputs[mode],expected)
            checks[mode+'_bf16_vs_fp32_within_tolerance']=(comparisons[mode]['max_abs']<=.03
                                                        and comparisons[mode]['rms']<=.003)
        _,all_lse=core.flash_attention_lse(q,k,v)
        _,ref_lse=core.flash_attention_lse(q[:,:,qa:qb],k[:,:,ra:rb],v[:,:,ra:rb])
        mass=(ref_lse-all_lse[:,:,qa:qb]).exp()
        mass_info={'min':float(mass.min()),'mean':float(mass.mean()),'max':float(mass.max())}
        if high_mass:checks['reference_mass_exceeds_0999']=float(mass.min())>.999
        static_v=v.clone();frame_rows=plan['frame_rows']
        static_v[:,:,ra:rb]=static_v[:,:,ra:ra+frame_rows].repeat(1,1,(rb-ra)//frame_rows,1)
        static_native=core.route_attention(q,k,static_v,56,plan,mode='native')
        static_dynamic=core.route_attention(q,k,static_v,56,plan,mode='dynamic_residual')
        checks['static_in_time_dynamic_bitwise_native']=bitwise(static_native,static_dynamic)
    else:
        mass_info=None
    correction=norms(outputs['mass_preserve'][:,qa:qb]-native[:,qa:qb],
                     outputs['dynamic_residual'][:,qa:qb]-native[:,qa:qb],
                     outputs['static_component'][:,qa:qb]-native[:,qa:qb])
    checks['bf16_decomposition_within_tolerance']=(correction['decomposition_error']['max_abs']<=.03
                                                 and correction['decomposition_error']['rms']<=.004)
    torch.cuda.synchronize()
    record={'name':name,'shape':list(q.shape),'strides':list(q.stride()),
            'dtype':str(q.dtype),'checks':checks,'passed':all(checks.values()),
            'dense_comparisons':comparisons,'same_input_corrections':correction,
            'reference_mass':mass_info,'elapsed_seconds':time.monotonic()-start,
            'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
            'peak_reserved_bytes':torch.cuda.max_memory_reserved(),
            'tolerances':{'bf16_dense_max':.03,'bf16_dense_rms':.003,
                          'bf16_decomposition_max':.03,'bf16_decomposition_rms':.004},
            'plan':plan}
    del outputs,packed,saved,q,k,v,native,forced
    gc.collect();torch.cuda.empty_cache()
    return record


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--actual-shape',action='store_true')
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    if not torch.cuda.is_available() or torch.cuda.device_count()!=1:
        raise RuntimeError('Root must admit one idle GPU and pin CUDA_VISIBLE_DEVICES before this script')
    torch.set_num_threads(1)
    cases=[run_case('tiny_strided'),run_case('tiny_high_reference_mass',high_mass=True)]
    if args.actual_shape:cases.append(run_case('audited_87592_token_shape',actual=True))
    record={'schema':'h3-value-split-smoke-v1','torch':torch.__version__,
            'cuda':torch.version.cuda,'device':torch.cuda.get_device_name(0),
            'core_sha256':hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest(),
            'cases':cases,'passed':all(x['passed'] for x in cases),
            'scope':'Model-free attention kernel checks; not H3 quality evidence'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record));raise SystemExit(0 if record['passed'] else 1)


if __name__=='__main__':main()
