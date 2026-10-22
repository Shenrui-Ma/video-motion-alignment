"""Stage two independent temporal-gain-field pilots without editing live queues."""
import copy
import hashlib
import json
from pathlib import Path

B = Path(__file__).resolve().parent
OUT = B / 'field_pilots'
PACKAGE = B.parents[1] / 'feature_gain_field'


def main():
    if (OUT / 'PUBLISHED.json').exists():
        raise RuntimeError('Published field plan is immutable')
    ready = json.loads((PACKAGE / 'READY.json').read_text())
    if ready.get('status') != 'CPU_VERIFIED_NOT_DEPLOYED' or ready.get('test_exit_code') != 0:
        raise RuntimeError('Field package has not passed CPU verification')
    for name, expected in ready['source_shas'].items():
        if hashlib.sha256((PACKAGE/name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Field READY checksum mismatch: '+name)
    original = json.loads((B / 'anchor_pilots/jobs.json').read_text())['jobs']
    (OUT / 'graphs').mkdir(parents=True, exist_ok=True)
    jobs, checks = [], []
    for source in original:
        job = copy.deepcopy(source)
        old = json.loads((B / 'anchor_pilots' / source['graph']).read_text())
        graph = copy.deepcopy(old)
        task = source['metadata']['task_id']
        job['id'] = f'adapt41_{task}_temporal_gain_field'
        job['graph'] = f"graphs/{job['id']}.json"
        job['expected_output_prefix'] = job['id'] + '/'
        job['max_attempts'] = 1
        graph['14']['inputs']['filename_prefix'] = job['id'] + '/{attempt_id}'
        graph['50']['class_type'] = 'H3TemporalGainField'
        inputs = graph['50']['inputs']
        inputs.update(mode='gain_field', smoothness=.625,
                      audit_dir=inputs['audit_dir'].replace('feature_anchor', 'feature_gain_field'))
        m = job['metadata']
        m.update(method='temporal_gain_field', innovation_parameters=copy.deepcopy(inputs),
                 innovation_status='independent_gain_field_pilot_pending_runtime_check',
                 calibration='per-run/layer/video-time-bin first-valid-step energy anchor',
                 alpha_scope='current layer and denoising step; vector over video-time bins, shared across heads',
                 attention_formula='O + alpha(step,layer,bin)*m_ref*(S_same - R_all)',
                 temporal_regularization='box-constrained strictly convex tridiagonal QP; mu=1, lambda=.625',
                 no_evidence_rule='fixed alpha=.25; smoothing edges cut; selected-window endpoints fixed .25')
        raw = (json.dumps(graph, ensure_ascii=False, indent=2) + '\n').encode()
        m['graph_sha256'] = hashlib.sha256(raw).hexdigest()
        (OUT / job['graph']).write_bytes(raw)
        assert {k: v for k, v in graph.items() if k not in ('14', '50')} == {
            k: v for k, v in old.items() if k not in ('14', '50')}
        assert all(m[k] == source['metadata'][k] for k in (
            'prompt', 'seed', 'geometry', 'valid_frames', 'fps', 'comparison_outputs'))
        assert inputs['alpha_prior'] == .25 and inputs['alpha_max'] == .5
        assert (inputs['step_start'], inputs['step_end']) == (0, 20)
        jobs.append(job)
        checks.append({'task': task, 'source_job': source['id'], 'changed_nodes': ['14', '50'],
                       'prompt_seed_cache_model_geometry_equal': True,
                       'graph_sha256': m['graph_sha256']})
    (OUT / 'jobs.json').write_text(json.dumps({'jobs': jobs}, ensure_ascii=False, indent=2) + '\n')
    (OUT / 'SCIENCE_CHECK.json').write_text(json.dumps({
        'checks': checks, 'package_ready_sha256': hashlib.sha256((PACKAGE/'READY.json').read_bytes()).hexdigest(),
        'cpu_ready_status': ready.get('status'), 'live_queue_modified': False}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'jobs': len(jobs), 'output': str(OUT), 'queue_modified': False}))


if __name__ == '__main__':
    main()
