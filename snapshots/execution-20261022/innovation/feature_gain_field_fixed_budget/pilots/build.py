"""Build a review-only plan; no live manifest or deployment is touched."""
import copy
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
PACKAGE=OUT.parent
B=PACKAGE.parent/'adaptive_strength_20261023/batch'


def prepare_one(source,old):
    job=copy.deepcopy(source);graph=copy.deepcopy(old);task=source['metadata']['task_id']
    if task not in ('short_0252','short_0358','long_0039','long_0059'):raise ValueError('unregistered fixed-budget pilot')
    job['id']=f'adapt41_{task}_temporal_gain_field_fixed_budget'
    job['graph']=f"graphs/{job['id']}.json";job['expected_output_prefix']=job['id']+'/'
    job['max_attempts']=1
    graph['14']['inputs']['filename_prefix']=job['id']+'/{attempt_id}'
    assert graph['50']['class_type']=='H3TemporalGainField'
    graph['50']['class_type']='H3TemporalGainFieldFixedBudget'
    inputs=graph['50']['inputs'];inputs['mode']='gain_field_fixed_budget'
    inputs['audit_dir']=inputs['audit_dir'].replace('/feature_gain_field','/feature_gain_field_fixed_budget')
    m=job['metadata'];m.update(method='temporal_gain_field_fixed_budget',
        innovation_parameters=copy.deepcopy(inputs),innovation_status='review_only_not_deployed',
        baseline_field_job=source['id'],
        alpha_scope='capped radial scaling across solved bins per layer/step to fixed .25 energy; unsupported bins remain .25',
        temporal_regularization='unchanged field QP on candidate only; applied coefficients use capped radial normalization',
        ablation='same forward candidate QP; capped radial gain with full-resolution D_t fixed .25 energy budget',
        fixed_bins='valid-window endpoints, new anchors, no-evidence bins and failed solver segments remain .25',
        matching_scope='current forward fixed alpha .25 pre-W_o energy; not an independent weak trajectory')
    changed=sorted(k for k in set(graph)|set(old) if graph.get(k)!=old.get(k))
    assert changed==['14','50'],changed
    old_inputs=old['50']['inputs']
    assert {k:v for k,v in inputs.items() if k not in ('audit_dir','mode')}=={k:v for k,v in old_inputs.items() if k not in ('audit_dir','mode')}
    for k in ('prompt','seed','geometry','valid_frames','fps','comparison_outputs'):
        assert m[k]==source['metadata'][k],k
    raw=(json.dumps(graph,ensure_ascii=False,indent=2)+'\n').encode()
    m['graph_sha256']=hashlib.sha256(raw).hexdigest()
    return job,raw,{'task':task,'source_field_job':source['id'],'changed_nodes':changed,
        'method_inputs_changed':['audit_dir','mode'],'node_class_changed':True,
        'prompt_seed_cache_model_geometry_sampler_equal':True,'QP_anchor_probe_window_parameters_equal':True,
        'graph_sha256':m['graph_sha256']}


def main():
    if (OUT/'PUBLISHED.json').exists() or (OUT/'ready').exists():raise RuntimeError('Published plan is immutable')
    original=PACKAGE.parent/'feature_gain_field'
    for name in ('controller.py','components.py','frozen.py'):
        assert (PACKAGE/name).read_bytes()==(original/name).read_bytes(),name
    source=[]
    for directory in ('field_pilots','field_extension_two'):
        source.extend((directory,j) for j in json.loads((B/directory/'jobs.json').read_text())['jobs'])
    assert {x['metadata']['task_id'] for _,x in source}=={'short_0252','short_0358','long_0039','long_0059'}
    (OUT/'graphs').mkdir(exist_ok=True)
    jobs=[];checks=[]
    for directory,oldjob in source:
        oldgraph=json.loads((B/directory/oldjob['graph']).read_text())
        job,raw,check=prepare_one(oldjob,oldgraph);(OUT/job['graph']).write_bytes(raw)
        jobs.append(job);checks.append(check)
    (OUT/'jobs.json').write_text(json.dumps({'plan_status':'review_only','cohort':'fixed_budget_original_four','selection':'all four pre-existing core cases; independent of candidate benefit','jobs':jobs},ensure_ascii=False,indent=2)+'\n')
    (OUT/'SCIENCE_CHECK.json').write_text(json.dumps({'checks':checks,
        'status':'REVIEW_ONLY_NOT_PUBLISHED','deployed':False,'live_queue_modified':False},indent=2)+'\n')
    print(json.dumps({'jobs':len(jobs),'review_only':True,'queue_modified':False}))


if __name__=='__main__':main()
