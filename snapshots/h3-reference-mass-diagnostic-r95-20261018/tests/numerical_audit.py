"""Bounded deterministic CPU evidence; writes only this package's audit file."""
import json,sys
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from r95_kernel import route_attention,MODES
from oracle import fixture,dense_attention,dense_oracle

torch.set_num_threads(2)
def plain(value):
    if isinstance(value,torch.Tensor):return value.item()
    if isinstance(value,dict):return {k:plain(v) for k,v in value.items()}
    return value

rows=[]
for dtype in (torch.float64,torch.float32,torch.float16,torch.bfloat16):
    for mode in MODES:
        for gain,bias in ((3,None),(3,-40),(3,40),(.0001,9),(1e300,-40),(1e-300,40)):
            q,k,v,p=fixture(dtype,bias);logs=[]
            got=route_attention(q,k,v,2,p,mode=mode,reference_gain=gain,attention=dense_attention,audit=logs)
            oracle=dense_oracle(q,k,v,p,gain=gain,mode=mode)
            qa,qb=p['query_interval_half_open']
            difference=got[:,qa:qb].double()-oracle[:,qa:qb].double()
            rows.append({'dtype':str(dtype),'mode':mode,'gain':gain,'reference_logit_bias_fixture':bias,
                         'selected_max_abs_error':difference.abs().max().item(),
                         'selected_rms_error':difference.square().mean().sqrt().item(),
                         'finite':bool(torch.isfinite(got).all()),'audit':plain(logs[0])})

# Independently show the cancellation of separately rounded BF16 aggregates.
q,k,v,p=fixture(torch.bfloat16,9);r=.0001
full,flse=dense_attention(q,k,v);qa,qb=p['query_interval_half_open'];ra,rb=p['reference_video_segment']
ref,rlse=dense_attention(q[:,:,qa:qb],k[:,:,ra:rb],v[:,:,ra:rb])
m=(rlse-flse[:,:,qa:qb]).clamp(max=0).exp()
naive=(full[:,:,qa:qb].float()+(r-1)*m.unsqueeze(-1)*ref.float())/(1+(r-1)*m.unsqueeze(-1))
naive=naive.to(q.dtype).transpose(1,2).reshape(1,qb-qa,-1)
expected=dense_oracle(q,k,v,p,gain=r,mode='reference_group_gain')[:,qa:qb]
safe=route_attention(q,k,v,2,p,reference_gain=r,attention=dense_attention)[:,qa:qb]
witness={'dtype':str(q.dtype),'gain':r,'ref_mass_mean':m.mean().item(),
         'naive_formula_selected_max_abs_error':(naive.double()-expected.double()).abs().max().item(),
         'explicit_complement_selected_max_abs_error':(safe.double()-expected.double()).abs().max().item(),
         'note':'This is a controlled rounded-aggregate witness, not a model trajectory.'}

# Values nearly constant in V make a real change smaller than BF16 resolution.
q,k,v,p=fixture(torch.bfloat16);v.fill_(1);v[:,:,6:18,0]=1.0078125;logs=[]
route_attention(q,k,v,2,p,reference_gain=1.001,attention=dense_attention,audit=logs)
rounding={'dtype':'torch.bfloat16','gain':1.001,'audit':plain(logs[0]),
          'note':'Mass changes can coexist with zero written entries after the output cast.'}
report={'scope':'CPU dense attention, deterministic fixture, no CUDA; real Flash kernel behavior unmeasured',
        'torch_version':torch.__version__,'lse_dtype':'torch.float32, matching original parent contract',
        'rows':rows,'cancellation_witness':witness,'rounding_witness':rounding,
        'cuda_initialized':torch.cuda.is_initialized()}
dest=ROOT/'audit/NUMERICAL_AUDIT.json';dest.parent.mkdir(exist_ok=True)
dest.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'file':str(dest),'cases':len(rows),'cancellation_witness':witness,
                  'max_errors_by_dtype':{d:max(x['selected_max_abs_error'] for x in rows if x['dtype']==d) for d in sorted({x['dtype'] for x in rows})},
                  'rounding_witness':rounding,'all_finite':all(x['finite'] for x in rows)},indent=2))
