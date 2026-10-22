"""Freeze matched causal-layer pilots; never mutates a live queue."""
import copy
import hashlib
import json
from pathlib import Path

B=Path(__file__).resolve().parent
OUT=B/'layer_pilots'
PACKAGE=B.parents[1]/'feature_layer_budget'


def main():
    if (OUT/'PUBLISHED.json').exists():raise RuntimeError('Published layer plan is immutable')
    ready=json.loads((PACKAGE/'READY.json').read_text())
    evidence=json.loads((PACKAGE/ready['test_evidence']).read_text())
    if ready.get('status')!='CPU_VERIFIED_NOT_DEPLOYED' or evidence.get('exit_code')!=0:
        raise RuntimeError('CPU tests not successful')
    for name,sha in ready['source_shas'].items():
        if hashlib.sha256((PACKAGE/name).read_bytes()).hexdigest()!=sha:
            raise RuntimeError('Layer package READY checksum mismatch: '+name)
    jobs=[];checks=[];(OUT/'graphs').mkdir(parents=True,exist_ok=True)
    for source in json.loads((B/'anchor_pilots/jobs.json').read_text())['jobs']:
        job=copy.deepcopy(source);old=json.loads((B/'anchor_pilots'/source['graph']).read_text());g=copy.deepcopy(old)
        task=source['metadata']['task_id'];job['id']=f'adapt41_{task}_causal_layer_budget'
        job['graph']=f"graphs/{job['id']}.json";job['expected_output_prefix']=job['id']+'/'
        job['max_attempts']=1;g['14']['inputs']['filename_prefix']=job['id']+'/{attempt_id}'
        g['50']['class_type']='H3CausalLayerBudget';inputs=g['50']['inputs']
        inputs.pop('prior_weight');inputs.update(mode='layer_budget',
            audit_dir=inputs['audit_dir'].replace('feature_anchor','feature_layer_budget'))
        m=job['metadata'];m.update(method='causal_layer_budget',innovation_parameters=copy.deepcopy(inputs),
            innovation_status='independent_causal_layer_pilot_pending_runtime_check',
            calibration='per-layer first valid anchor; next-step allocation after complete 50-layer forward',
            alpha_scope='one scalar per layer; frozen from previous complete forward',
            attention_formula='O + alpha(step,layer)*m_ref*(S_same - R_all)',
            budget='previous-complete-step local relative pre-Wo correction energy; current drift recorded separately')
        assert {k:v for k,v in g.items() if k not in ('14','50')}=={k:v for k,v in old.items() if k not in ('14','50')}
        assert all(m[k]==source['metadata'][k] for k in ('prompt','seed','geometry','valid_frames','fps','comparison_outputs'))
        assert g['10']['inputs']['guider']==['7',0] and g['7']['inputs']['model']==['52',0]
        assert g['52']['inputs']['model']==['50',0] and inputs['model']==['41',0]
        assert g['41']['inputs']['model']==['1',0] and inputs['positive']==['5',0]
        assert inputs['alpha_prior']==.25 and inputs['alpha_max']==.5
        assert (inputs['step_start'],inputs['step_end'],inputs['block_start'],inputs['block_end'])==(0,20,0,50)
        raw=(json.dumps(g,ensure_ascii=False,indent=2)+'\n').encode();m['graph_sha256']=hashlib.sha256(raw).hexdigest()
        (OUT/job['graph']).write_bytes(raw);jobs.append(job)
        checks.append(dict(task=task,source=source['id'],changed_nodes=['14','50'],
            model_chain=['UNETLoader','MiniMaxH3SigmaShift','H3CausalLayerBudget','H3StudyTiming','BasicGuider','SamplerCustomAdvanced'],
            frozen_other_graph_nodes_equal=True,prompt_seed_cache_geometry_equal=True,graph_sha256=m['graph_sha256']))
    (OUT/'jobs.json').write_text(json.dumps({'jobs':jobs},ensure_ascii=False,indent=2)+'\n')
    (OUT/'SCIENCE_CHECK.json').write_text(json.dumps(dict(checks=checks,package_ready_sha256=hashlib.sha256((PACKAGE/'READY.json').read_bytes()).hexdigest(),live_queue_modified=False),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(jobs=len(jobs),queue_modified=False,output=str(OUT))))


if __name__=='__main__':main()
