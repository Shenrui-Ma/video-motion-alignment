"""CPU-only numerical-definition check; no semantic phase or replay release decision."""
import argparse,ast,hashlib,json,math
from pathlib import Path
import torch

ROOT=Path(__file__).parent
BRANCHES=('Q_C','Q_R','K_R')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def eager_functions():
    p=ROOT/'frozen_eager_rope.py.txt'
    if sha(p)!='aee33a18bb5fe75ce24ebad389b830c9d5775d52723fc7df4864598547b2257c':raise ValueError('frozen eager source changed')
    scope={'torch':torch};wanted={'apply_rope_split_half1','_rms_rope1'}
    for node in ast.parse(p.read_text()).body:
        if getattr(node,'name',None) in wanted:exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),scope)
    return scope

def validate(raw,actual,weight,rope,eps,rot):
    tensors=(raw,actual,weight,rope)
    if any(t.device.type!='cpu' for t in tensors):raise ValueError('diagnostic requires CPU tensors')
    if raw.ndim!=4 or actual.shape!=raw.shape or actual.dtype!=raw.dtype:raise ValueError('Q/K shape or dtype mismatch')
    t,p,h,d=raw.shape
    if weight.shape!=(d,) or not 0<rot<=d or rot%2 or rope.shape!=(1,t*p,1,rot//2,2,2):raise ValueError('norm/RoPE geometry mismatch')
    if not math.isfinite(eps) or eps<=0 or any(not bool(torch.isfinite(x).all()) for x in tensors):raise ValueError('nonfinite input or invalid epsilon')

def materialized(raw,weight,eps,*,explicit_fp32=False):
    if explicit_fp32:
        x=raw.float();return (x*torch.rsqrt(x.square().mean(-1,keepdim=True)+eps)*weight.float()).to(raw.dtype)
    return torch.nn.functional.rms_norm(raw,(raw.shape[-1],),weight=weight,eps=eps)

def reapply(raw,weight,rope,eps,rot,*,explicit_fp32=False):
    funcs=eager_functions();t,p,h,d=raw.shape
    flat=raw.reshape(1,t*p,h,d)
    if not explicit_fp32:
        out=funcs['_rms_rope1'](flat,rope,weight,eps,split_half=True,rot_dim=rot)
    else:
        norm=materialized(flat,weight,eps,explicit_fp32=True)
        rotated=funcs['apply_rope_split_half1'](norm[...,:rot],rope)
        out=torch.cat((rotated,norm[...,rot:]),dim=-1)
    # Actual rms_rope_split_half_ ends in q.copy_(q_out), including when
    # a FP32 norm weight promoted the eager intermediate result.
    return out.to(raw.dtype).reshape_as(raw)

def inverse_matrix(actual,rope,rot):
    t,p,h,d=actual.shape
    matrix=rope.reshape(t,p,1,rot//2,2,2).double()
    det=torch.linalg.det(matrix)
    if bool((det.abs()<1e-12).any()):raise ValueError('singular captured rotary matrix')
    y=actual[...,:rot].double().reshape(t,p,h,2,rot//2).movedim(-2,-1)
    x=torch.linalg.solve(matrix,y.unsqueeze(-1)).squeeze(-1).movedim(-1,-2).reshape(t,p,h,rot)
    return torch.cat((x,actual[...,rot:].double()),dim=-1)

def error_per_head(pred,actual):
    if pred.shape!=actual.shape or pred.ndim!=4:raise ValueError('scores require identical T,P,H,D')
    if not bool(torch.isfinite(pred).all()) or not bool(torch.isfinite(actual).all()):raise ValueError('nonfinite predictions')
    rows=[]
    for h in range(actual.shape[2]):
        a=actual[:,:,h,:].double().flatten();p=pred[:,:,h,:].double().flatten();diff=(p-a).abs();rms=max(float(a.square().mean().sqrt()),1e-8)
        rows.append({'head':h,'actual_rms':rms,'nrmse':float(diff.square().mean().sqrt())/rms,'p99_abs_over_actual_rms':float(torch.quantile(diff,.99))/rms,'max_abs_over_actual_rms':float(diff.max())/rms,'mean_abs':float(diff.mean()),'max_abs':float(diff.max()),'exact_fraction':float((p==a).double().mean())})
    return rows

def diagnose(payload,*,strict_geometry=True):
    policy=json.loads((ROOT/'POLICY.json').read_text());rot=int(payload['rot_dim']);rows={};all_pass=True
    for name in BRANCHES:
        raw,actual=payload['raw_'+name],payload['actual_'+name]
        weight=payload['k_norm_weight' if name=='K_R' else 'q_norm_weight']
        eps=float(payload['k_norm_eps' if name=='K_R' else 'q_norm_eps'])
        rope=payload['rope_canvas' if name=='Q_C' else 'rope_reference']
        validate(raw,actual,weight,rope,eps,rot)
        if strict_geometry and (tuple(raw.shape[1:])!=(8,56,128) or rot!=96):raise ValueError('frozen H3 geometry differs')
        pred=reapply(raw,weight,rope,eps,rot)
        fp32=reapply(raw,weight,rope,eps,rot,explicit_fp32=True)
        norms=materialized(raw,weight,eps);inverse=inverse_matrix(actual,rope,rot)
        scores=error_per_head(pred,actual)
        for item in scores:
            item['numerical_definition_pass']=all(item[k]<=policy['head_gate'][k] for k in ('nrmse','p99_abs_over_actual_rms','max_abs_over_actual_rms'))
        dtype_ok=raw.dtype==torch.bfloat16
        branch_pass=dtype_ok and all(x['numerical_definition_pass'] for x in scores);all_pass &= branch_pass
        rows[name]={'dtype':str(raw.dtype),'shape':list(raw.shape),'numerical_definition_pass':branch_pass,'full':scores,
          'rotated_prefix':error_per_head(pred[...,:rot],actual[...,:rot]),
          'unrotated_tail':error_per_head(pred[...,rot:],actual[...,rot:]) if rot<raw.shape[-1] else None,
          'explicit_fp32_norm_to_actual':error_per_head(fp32,actual),
          'inverse_to_materialized_pre_rope_norm':error_per_head(inverse,norms)}
    return {'schema':'h3-passive-qk-numerical-diagnostic-v1','policy_sha256':sha(ROOT/'POLICY.json'),'numerical_definition_pass':bool(all_pass),
       'case':payload.get('case'),'method':payload.get('method'),'step_zero_based':payload.get('step_zero_based'),'layer_zero_based':payload.get('layer_zero_based'),
       'forward_identity':payload.get('forward_identity'),'branches':rows,'historical_replay_release_unchanged':True,'semantic_phase_validated':False,
       'arithmetic_note':'Primary is literal eager partial-RoPE definition. CPU/GPU reduction rounding may differ; explicitFP32 variant is separately reported. Inverse uses captured matrices and cannot undo BF16 quantization.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True);p.add_argument('--capture-sha256',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    torch.set_num_threads(1);torch.set_grad_enabled(False)
    if sha(a.capture)!=a.capture_sha256:raise ValueError('captured file identity differs')
    payload=torch.load(a.capture,map_location='cpu',weights_only=True)
    with torch.inference_mode():r=diagnose(payload)
    r['capture_sha256']=a.capture_sha256;r['gpu_used']=False
    out=Path(a.output)
    with out.open('x') as f:json.dump(r,f,indent=2,allow_nan=False);f.write('\n')
if __name__=='__main__':main()
