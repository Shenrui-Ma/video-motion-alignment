"""Independent torch-free audit of candidate QP and applied uniform energy."""
import copy
import importlib.util
import json
import math
from pathlib import Path

_spec=importlib.util.spec_from_file_location('_uniform_field_audit_base',Path(__file__).with_name('uniform_field_audit_base.py'))
_base=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_base)
require,close,FieldAuditError=_base.require,_base.close,_base.FieldAuditError


def check_uniform_layer(row):
    a,candidate,e,u,c=(row[k] for k in ('alpha','candidate_alpha','bin_energy','uniform_energy','control'))
    n=len(a)
    require(n>0 and len(candidate)==len(e)==n,'uniform vector shape')
    require(len(u['modifiable_mask'])==n,'uniform mask shape')
    mask=u['modifiable_mask']
    require(mask==c['solver_succeeded'],'mask must be successfully solved candidate bins')
    require(not mask[0] and not mask[-1],'uniform endpoints')
    require(all(math.isfinite(x) and 0<=x<=.5 for x in a),'applied alpha bounds')
    require(u['candidate_alpha']==candidate and u['applied_alpha']==a,'duplicate alpha mismatch')
    denominator=sum(x for x,m in zip(e,mask) if m)
    numerator=sum(x*y*y for x,y,m in zip(e,candidate,mask) if m)
    require(close(denominator,u['modifiable_energy']) and close(numerator,u['candidate_modifiable_energy']),'RMS sufficient statistics')
    require(close(sum(x*y*y for x,y,m in zip(e,a,mask) if m),u['applied_modifiable_energy']),
            'applied modifiable energy mismatch')
    require(u['accumulation_dtype']=='float64','RMS accumulation')
    dtype=u['applied_dtype']
    floor={'torch.float32':2**-126,'torch.float64':2**-1022}.get(dtype)
    require(floor is not None and u['energy_floor']==floor,'unrecognized energy floor')
    fallback=denominator<=floor
    require(u['near_zero_energy_fallback']==fallback,'energy fallback mismatch')
    require(u['no_modifiable_bins']==(not any(mask)),'empty mask flag')
    b=.25 if fallback else math.sqrt(numerator/denominator)
    require(close(u['uniform_alpha'],b,1e-7),'incorrect uniform RMS')
    for t in range(n):
        require(close(a[t],b if mask[t] else .25,1e-7),'nonuniform applied alpha or fixed bin changed')
        if not mask[t]:require(candidate[t]==.25,'candidate changed unsupported bin')
    target=sum(x*y*y for x,y in zip(e,candidate));actual=sum(x*y*y for x,y in zip(e,a))
    require(close(target,u['candidate_total_energy']) and close(actual,u['applied_total_energy']),'full energy mismatch')
    require(close(actual,row['applied_energy']),'runtime applied energy')
    require(close(actual-target,u['energy_error']),'energy error mismatch')
    relative=0. if target==0 else (actual-target)/target
    require(close(relative,u['energy_relative_error'],1e-7),'relative energy error mismatch')
    if not fallback:require(abs(actual-target)<=3e-7*max(target,1e-300),'same-forward energy not matched')
    # Preserve the original QP checks on the candidate, never on uniform a.
    view=copy.deepcopy(row);view['alpha']=candidate;view['applied_energy']=target
    proof=_base.check_layer(view)
    proof.update(uniform_energy_fallback=fallback,energy_relative_error=relative,
                 nonuniform_candidate=(max(candidate)-min(candidate)>1e-7),uniform_alpha=b)
    return proof


def check_uniform(doc):
    require(doc.get('schema')=='h3-temporal-gain-field-uniform-energy-v1','wrong uniform schema')
    require(doc['feature_config']['mode']=='gain_field_uniform_energy','wrong uniform mode')
    require(doc.get('independent_field_trajectory_energy_matched') is False,'invalid cross-trajectory claim')
    rows=[row for f in doc['feature_forward_summaries'] for row in f['layers']]
    proofs=[check_uniform_layer(row) for row in rows]
    candidate=copy.deepcopy(doc)
    candidate['schema']='h3-temporal-gain-field-v1';candidate['feature_config']['mode']='gain_field'
    for f in candidate['feature_forward_summaries']:
        for row in f['layers']:
            row['alpha']=row['candidate_alpha']
            row['applied_energy']=row['uniform_energy']['candidate_total_energy']
    # This retains all frozen field counting, anchor and candidate-KKT checks.
    result=_base.check_field(candidate)
    result.update(candidate_alpha_min=result['alpha_min'],candidate_alpha_max=result['alpha_max'],
                  candidate_alpha_mean=result['alpha_mean'])
    applied=[a for row in rows for a in row['alpha']]
    result.update(schema=doc['schema'],uniform_energy_fallbacks=sum(p['uniform_energy_fallback'] for p in proofs),
        max_energy_relative_error=max(abs(p['energy_relative_error']) for p in proofs),
        candidate_nonuniform_layers=sum(p['nonuniform_candidate'] for p in proofs),
        candidate_qp_verified=True,applied_uniform_energy_verified=True,
        alpha_min=min(applied),alpha_max=max(applied),alpha_mean=sum(applied)/len(applied))
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('audit');args=p.parse_args()
    print(json.dumps(check_uniform(json.loads(Path(args.audit).read_text())),indent=2))
