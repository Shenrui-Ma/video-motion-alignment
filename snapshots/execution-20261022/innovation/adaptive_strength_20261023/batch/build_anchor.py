"""Prepare two independently named anchor pilots; never mutates a live queue."""
import copy
import hashlib
import json
from pathlib import Path

B = Path(__file__).resolve().parent
OUT = B / 'anchor_pilots'


def main():
    if (OUT / 'PUBLISHED.json').exists():
        raise RuntimeError('Published anchor package is immutable; create a new version')
    original = json.loads((B / 'jobs.json').read_text())['jobs']
    (OUT / 'graphs').mkdir(parents=True, exist_ok=True)
    jobs, checks = [], []
    for task in ('short_0252', 'short_0358'):
        source = next(j for j in original if j['id'] == f'adapt41_{task}_dynamic_dof')
        job = copy.deepcopy(source)
        source_graph = json.loads((B / source['graph']).read_text())
        graph = copy.deepcopy(source_graph)
        job['id'] = f'adapt41_{task}_dynamic_anchor'
        job['graph'] = f"graphs/{job['id']}.json"
        job['expected_output_prefix'] = job['id'] + '/'
        job['max_attempts'] = 1
        graph['14']['inputs']['filename_prefix'] = job['id'] + '/{attempt_id}'
        graph['50']['class_type'] = 'H3AnchoredGuidance'
        i = graph['50']['inputs']
        i['mode'] = 'anchor'
        i.pop('collateral', None)
        i['audit_dir'] = i['audit_dir'].replace('feature_guidance', 'feature_anchor')
        m = job['metadata']
        m['method'] = 'dynamic_anchor'
        m['innovation_parameters'] = copy.deepcopy(i)
        m['innovation_status'] = 'independent_anchor_pilot'
        m['calibration'] = 'per-layer first-valid-step temporal/complement energy; first-step alpha=.25'
        m['attention_formula'] = 'O + alpha(layer,step)*m_ref*(S_same - R_all)'
        raw = (json.dumps(graph, ensure_ascii=False, indent=2) + '\n').encode()
        m['graph_sha256'] = hashlib.sha256(raw).hexdigest()
        (OUT / job['graph']).write_bytes(raw)
        unchanged = [k for k in graph if k not in ('14', '50')]
        assert all(graph[k] == source_graph[k] for k in unchanged)
        assert all(m[k] == source['metadata'][k] for k in (
            'prompt', 'seed', 'geometry', 'valid_frames', 'fps', 'comparison_outputs'))
        assert i['alpha_prior'] == .25 and i['alpha_max'] == .5
        assert i['step_start'] == 0 and i['step_end'] == 20
        jobs.append(job)
        checks.append({'task': task, 'source_job': source['id'], 'changed_nodes': ['14', '50'],
                       'same_prompt_seed_cache_model_geometry': True, 'graph_sha256': m['graph_sha256']})
    (OUT / 'jobs.json').write_text(json.dumps({'jobs': jobs}, ensure_ascii=False, indent=2) + '\n')
    (OUT / 'SCIENCE_CHECK.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'jobs': len(jobs), 'directory': str(OUT), 'checks': checks}))


if __name__ == '__main__':
    main()
