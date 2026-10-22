"""Run actual frozen state/block wrappers on CPU and audit their written trace."""
import argparse
import hashlib
import json
from pathlib import Path
from unittest import mock
import torch
from .attention import FeatureConfig,make_classes
from .test_feature_attention import FeatureAttentionTests,dense
from .frozen import load_frozen
from .audit import check_budget,check_budget_layer,FieldAuditError


def run(directory):
    torch.set_num_threads(1)
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    core=load_frozen().core;state_type,block_type=make_classes(core)
    q,k,v,heads,plan=FeatureAttentionTests().data(frames=7,spatial=3,lo=0,hi=7,h=3,d=8)
    layout=object();inputs={};torch.manual_seed(2210);noise=torch.randn_like(v)
    def attention_pytorch():pass
    def original(args):
        return args['transformer_options']['optimized_attention_override'](
            attention_pytorch,q,k,inputs['v'],heads,skip_reshape=True)
    with mock.patch.object(core,'flash_attention_lse',dense):
        state=state_type({},'mass_preserve',.25,0,0,0,24,0,50,0,20,
            'budget_complete',str(directory),feature_config=FeatureConfig())
        with mock.patch.object(state,'plan_for',return_value=plan):
            for step in range(20):
                for block in range(50):
                    inputs['v']=v*(1+.02*block)+noise*(.03*step)
                    args={'layout':layout,'transformer_options':{'block_index':block,
                        'minimax_h3_layout':layout,'sample_sigmas':torch.linspace(1,0,21)}}
                    block_type(state,block)(args,{'original_block':original})
    path=directory/'budget_complete.json';raw=path.read_bytes();saved=json.loads(raw)
    proof=check_budget(saved)
    assert proof['candidate_nonuniform_layers']>100,proof
    assert proof['max_energy_relative_error']<3e-7,proof
    assert proof['max_kkt']<1e-6,proof
    # Failure injections target different invariants on an actual dynamic row.
    import copy
    row=next(r for f in saved['feature_forward_summaries'] for r in f['layers']
             if max(r['candidate_alpha'])-min(r['candidate_alpha'])>.01)
    cases={}
    def fail(name,edit):
        bad=copy.deepcopy(row);edit(bad)
        try:check_budget_layer(bad)
        except (ValueError,KeyError) as exc:cases[name]=str(exc)
        else:raise AssertionError('corruption accepted: '+name)
    fail('wrong_applied_alpha',lambda r:r['alpha'].__setitem__(1,r['alpha'][1]+.01))
    fail('changed_unknown_endpoint',lambda r:r['alpha'].__setitem__(0,.3))
    fail('wrong_candidate_dose',lambda r:r['fixed_budget'].__setitem__('candidate_modifiable_energy',999.))
    fail('wrong_mask',lambda r:r['fixed_budget']['modifiable_mask'].__setitem__(1,False))
    fail('wrong_energy_error',lambda r:r['fixed_budget'].__setitem__('energy_error',1.))
    fail('wrong_applied_modifiable_energy',lambda r:r['fixed_budget'].__setitem__('applied_modifiable_energy',999.))
    fail('wrong_candidate_kkt',lambda r:r['control']['quadratic_rhs'].__setitem__(1,999.))
    fail('wrong_anchor',lambda r:r['control']['anchor_temporal'].__setitem__(1,999.))
    fail('false_fallback',lambda r:r['fixed_budget'].__setitem__('fallback_reason','near_zero_energy'))
    def coherent_changed_gain(r):
        r['alpha'][1]+=.01;r['fixed_budget']['applied_alpha'][1]=r['alpha'][1]
    fail('coherent_nonuniform_application',coherent_changed_gain)
    def coherent_wrong_scale(r):
        r['fixed_budget']['log_scale']+=.1
        r['fixed_budget']['scale']*=1.105170185988091
    fail('coherent_wrong_scale',coherent_wrong_scale)
    fail('wrong_fixed_dose_target',lambda r:r['fixed_budget'].__setitem__('target_total_energy',999.))
    fail('wrong_radial_solver_residual',lambda r:r['fixed_budget'].__setitem__('normalized_solver_residual',.01))
    fail('wrong_cap_mask',lambda r:r['fixed_budget']['cap_mask'].__setitem__(1,True))
    result={'audit':proof,'failure_injections':cases,'fixture_sha256':hashlib.sha256(raw).hexdigest(),
        'fixture_bytes':len(raw),'fixture_path':str(path),'model_or_gpu_inference':False,
        'scope':'actual state/block wrappers with dense CPU attention; 20 steps x 50 layers'}
    (directory/'integration_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);args=p.parse_args();run(args.out)
