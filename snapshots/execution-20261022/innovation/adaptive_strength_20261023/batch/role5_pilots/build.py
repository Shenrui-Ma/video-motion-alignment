"""Prepare two review-only role5 graphs from the frozen field pilots."""
import copy
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
B=OUT.parent
PACKAGE=B.parents[1]/'feature_gain_field_role5'


def prepare_one(source,old):
    job=copy.deepcopy(source);graph=copy.deepcopy(old);task=source['metadata']['task_id']
    if task not in ('short_0252','short_0358'):raise ValueError('unregistered role5 pilot')
    job['id']=f'adapt41_{task}_temporal_gain_field_role5'
    job['graph']=f"graphs/{job['id']}.json";job['expected_output_prefix']=job['id']+'/'
    job['max_attempts']=1
    graph['14']['inputs']['filename_prefix']=job['id']+'/{attempt_id}'
    assert graph['50']['class_type']=='H3TemporalGainField'
    graph['50']['class_type']='H3TemporalGainFieldRole5'
    inputs=graph['50']['inputs']
    inputs['audit_dir']=inputs['audit_dir'].replace('/feature_gain_field','/feature_gain_field_role5')
    m=job['metadata'];m.update(method='temporal_gain_field_role5',
        innovation_parameters=copy.deepcopy(inputs),innovation_status='review_only_not_deployed',
        baseline_field_job=source['id'],
        tangent_operator='same-position-role +/-5 where a full neighborhood exists; original +/-1 boundary',
        intervention_scope='neighbor indices only; role matching and temporal span change jointly',
        shadow_diagnostics={'steps':[0,9,19],'layers':[8,25,42],
            'scope':'same Q/D/m/probes; common interior; independent step-zero +/-1 anchors; no control effect'})
    changed=sorted(k for k in set(graph)|set(old) if graph.get(k)!=old.get(k))
    assert changed==['14','50'],changed
    old_inputs=old['50']['inputs']
    assert {k:v for k,v in inputs.items() if k!='audit_dir'}=={k:v for k,v in old_inputs.items() if k!='audit_dir'}
    for k in ('prompt','seed','geometry','valid_frames','fps','comparison_outputs'):
        assert m[k]==source['metadata'][k],k
    raw=(json.dumps(graph,ensure_ascii=False,indent=2)+'\n').encode()
    m['graph_sha256']=hashlib.sha256(raw).hexdigest()
    return job,raw,{'task':task,'source_field_job':source['id'],'changed_nodes':changed,
        'method_inputs_changed':['audit_dir'],'node_class_changed':True,
        'prompt_seed_cache_model_geometry_sampler_equal':True,
        'window_mask_prior_qp_parameters_equal':True,'graph_sha256':m['graph_sha256']}


def main():
    if (OUT/'PUBLISHED.json').exists() or (OUT/'ready').exists():raise RuntimeError('Published/staged plan is immutable')
    ready=json.loads((PACKAGE/'READY.json').read_text())
    assert ready['status']=='CPU_VERIFIED_NOT_DEPLOYED' and ready['test_exit_code']==0
    for name,sha in ready['source_shas'].items():
        assert hashlib.sha256((PACKAGE/name).read_bytes()).hexdigest()==sha,name
    source=json.loads((B/'field_pilots/jobs.json').read_text())['jobs']
    assert {x['metadata']['task_id'] for x in source}=={'short_0252','short_0358'}
    (OUT/'graphs').mkdir(exist_ok=True)
    jobs=[];checks=[]
    for oldjob in source:
        oldgraph=json.loads((B/'field_pilots'/oldjob['graph']).read_text())
        job,raw,check=prepare_one(oldjob,oldgraph);(OUT/job['graph']).write_bytes(raw)
        jobs.append(job);checks.append(check)
    (OUT/'jobs.json').write_text(json.dumps({'jobs':jobs},ensure_ascii=False,indent=2)+'\n')
    (OUT/'SCIENCE_CHECK.json').write_text(json.dumps({'checks':checks,
        'package_ready_sha256':hashlib.sha256((PACKAGE/'READY.json').read_bytes()).hexdigest(),
        'status':'REVIEW_ONLY_NOT_PUBLISHED','deployed':False,'live_queue_modified':False},indent=2)+'\n')
    print(json.dumps({'jobs':len(jobs),'review_only':True,'queue_modified':False}))


if __name__=='__main__':main()
