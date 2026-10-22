"""Torch-free, independent checks of candidate QP and applied fixed dose."""
import copy
import importlib.util
import json
import math
import sys
from pathlib import Path

_spec=importlib.util.spec_from_file_location('_budget_field_audit_base',Path(__file__).with_name('field_audit_base.py'))
_base=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_base)
require,close,FieldAuditError=_base.require,_base.close,_base.FieldAuditError


def check_budget_layer(row):
    a,candidate,e,b,c=(row[k] for k in ('alpha','candidate_alpha','bin_energy','fixed_budget','control'))
    n=len(a);mask=b['modifiable_mask']
    require(n>0 and len(candidate)==len(e)==len(mask)==n,'budget vector shape')
    require(all(type(x) is bool for x in mask),'budget boolean mask')
    require(mask==c['solver_succeeded'],'mask must equal successfully solved bins')
    require(not mask[0] and not mask[-1],'fixed endpoints')
    require(all(math.isfinite(x) and 0<=x<=.5 for x in a+candidate),'alpha bounds')
    require(all(math.isfinite(x) and x>=0 for x in e),'energy bounds')
    total=math.fsum(e);require(math.isfinite(total),'total energy finite')
    require(b['candidate_alpha']==candidate and b['applied_alpha']==a,'duplicate alpha mismatch')
    floor={'torch.float32':2**-126,'torch.float64':2**-1022}.get(b['applied_dtype'])
    require(floor is not None and b['energy_floor']==floor,'unknown energy floor')
    require(b['accumulation_dtype']=='float64','energy accumulation dtype')
    selected=math.fsum(x for x,m in zip(e,mask) if m)
    support=[i for i in range(n) if mask[i] and e[i]>0 and candidate[i]>0]
    capacity=.25*math.fsum(e[i]/selected for i in support) if selected>0 else 0.
    reason=('no_modifiable_bins' if not any(mask) else 'near_zero_energy' if selected<=floor
            else 'zero_candidate_support' if not support else 'insufficient_positive_support' if capacity<.0625 else None)
    require(b['fallback_reason']==reason and b['fallback_to_prior']==(reason is not None),'fallback reason inconsistent')
    require(b['no_modifiable_bins']==(not any(mask)),'no-modifiable flag')
    require(close(b['normalized_positive_support_capacity'],capacity,1e-12),'support capacity')
    require(b['normalized_target']==.0625,'frozen normalized target')
    require(b['zero_candidate_with_positive_energy']==sum(m and x>0 and y==0 for m,x,y in zip(mask,e,candidate)),
            'zero-candidate count')
    if reason is not None:
        require(b['solver']=='fixed_prior_fallback' and b['iterations']==0,'fallback solver')
        require(b['log_scale'] is None and b['scale'] is None,'fallback must not claim radial root')
        raw=[.25]*n
    else:
        log_c=b['log_scale'];require(isinstance(log_c,(int,float)) and math.isfinite(log_c),'finite log scale')
        raw=[]
        for m,v in zip(mask,candidate):
            raw.append(.25 if not m else 0. if v==0 else .5 if math.log(v)+log_c>=math.log(.5) else math.exp(math.log(v)+log_c))
        if log_c<=math.log(sys.float_info.max):
            require(close(b['scale'],math.exp(log_c),1e-12),'scale/log-scale disagree')
            require(b['scale_representation']=='float64','scale representation')
        else:require(b['scale'] is None and b['scale_representation']=='log_scale','overflowing multiplier representation')
        require(b['solver'] in ('uncapped_closed_form','bounded_log_bisection'),'unrecognized radial solver')
        require((b['iterations']==0 if b['solver']=='uncapped_closed_form' else 1<=b['iterations']<=96),'solver iteration bound')
        residual=math.fsum(e[i]/selected*raw[i]**2 for i in range(n) if mask[i])-.0625
        require(abs(residual)<=2e-13 and close(residual,b['normalized_solver_residual'],1e-13),'scalar root energy residual')
    for i in range(n):
        require(close(a[i],raw[i],1e-7),'applied gain not capped radial candidate')
        if not mask[i]:require(a[i]==.25 and candidate[i]==.25,'fixed or unknown bin changed')
    require(b['cap_mask']==[m and x==.5 for m,x in zip(mask,raw)],'cap mask')
    candidate_total=math.fsum(x*y*y for x,y in zip(e,candidate))
    candidate_selected=math.fsum(x*y*y for x,y,m in zip(e,candidate,mask) if m)
    applied_total=math.fsum(x*y*y for x,y in zip(e,a))
    applied_selected=math.fsum(x*y*y for x,y,m in zip(e,a,mask) if m)
    target=.0625*total;relative=(applied_total-target)/target if target>0 else 0.
    for name,value in {'modifiable_energy':selected,'source_total_energy':total,'target_modifiable_energy':.0625*selected,
                       'target_total_energy':target,'candidate_modifiable_energy':candidate_selected,
                       'candidate_total_energy':candidate_total,'applied_modifiable_energy':applied_selected,
                       'applied_total_energy':applied_total,'energy_error':applied_total-target}.items():
        require(close(b[name],value),name+' mismatch')
    require(close(row['applied_energy'],applied_total),'runtime applied energy')
    require(close(row['correction_energy'],total),'runtime correction energy')
    require(close(b['energy_relative_error'],relative,1e-7) and abs(relative)<=3e-7,'fixed dose energy mismatch')
    view=copy.deepcopy(row);view['alpha']=candidate;view['applied_energy']=candidate_total
    proof=_base.check_layer(view)
    proof.update(budget_fallback=reason is not None,energy_relative_error=relative,
        candidate_nonuniform=max(candidate)-min(candidate)>1e-7,
        applied_nonuniform=max(a)-min(a)>1e-7,capped_bins=sum(b['cap_mask']))
    return proof


def check_budget(doc):
    require(doc.get('schema')=='h3-temporal-gain-field-fixed-budget-v1','wrong budget schema')
    require(doc['feature_config']['mode']=='gain_field_fixed_budget','wrong budget mode')
    require(doc.get('independent_field_trajectory_energy_matched') is False,'invalid cross-trajectory claim')
    rows=[r for f in doc['feature_forward_summaries'] for r in f['layers']]
    proofs=[check_budget_layer(r) for r in rows]
    candidate=copy.deepcopy(doc);candidate['schema']='h3-temporal-gain-field-v1';candidate['feature_config']['mode']='gain_field'
    for f in candidate['feature_forward_summaries']:
        for r in f['layers']:r['alpha']=r['candidate_alpha'];r['applied_energy']=r['fixed_budget']['candidate_total_energy']
    result=_base.check_field(candidate)
    result.update(candidate_alpha_min=result['alpha_min'],candidate_alpha_max=result['alpha_max'],candidate_alpha_mean=result['alpha_mean'])
    applied=[a for r in rows for a in r['alpha']]
    result.update(schema=doc['schema'],budget_fallbacks=sum(p['budget_fallback'] for p in proofs),
        max_energy_relative_error=max(abs(p['energy_relative_error']) for p in proofs),
        candidate_nonuniform_layers=sum(p['candidate_nonuniform'] for p in proofs),
        applied_nonuniform_layers=sum(p['applied_nonuniform'] for p in proofs),capped_bins=sum(p['capped_bins'] for p in proofs),
        candidate_qp_verified=True,applied_fixed_budget_verified=True,
        alpha_min=min(applied),alpha_max=max(applied),alpha_mean=sum(applied)/len(applied))
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('audit');args=p.parse_args()
    print(json.dumps(check_budget(json.loads(Path(args.audit).read_text())),indent=2))
