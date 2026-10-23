"""Prepare independent ten-case methods from the frozen direction graph package."""
import copy
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
SOURCE = OUT.parent / 'direction_package'
REMOTE = '/home/research-user/h3_runs/benchmark_schedule_20261022_host9a'
METHODS = ['partial_temporal_rope', 'temporal_coverage']


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def method_inputs(method, source):
    inputs = {name: copy.deepcopy(source[name]) for name in ['model', 'positive', 'enabled', 'alpha', 'start_frame', 'end_frame', 'run_id']}
    inputs.update(block_start=0, block_end=50, audit_dir=REMOTE+'/audit/'+method)
    if method == 'partial_temporal_rope':
        inputs.update(frequency_mask=json.dumps([0]*8+[1]*8), delta_frames=0.,
                      delta_mode='reference_origin', schedule='all')
    else:
        inputs.update(step_start=0, step_end=20, radius=2, entropy=.5,
                      temporal_penalty=.25, iterations=128, tolerance=.0002,
                      min_quality_span=.001, minimum_mean_gap=0.)
    return inputs


def build():
    source_jobs = json.loads((SOURCE/'jobs.json').read_text())['jobs']
    results = []
    for method in METHODS:
        package = OUT/method
        jobs, checks = [], []
        for original in source_jobs:
            sid = original['metadata']['task_id']
            rid = f'innov_{sid}_{method}'
            original_graph = SOURCE/original['graph']
            graph = json.loads(original_graph.read_text())
            inputs = method_inputs(method, graph['50']['inputs'])
            graph['50'] = {'class_type': 'H3PartialRoPE' if method == 'partial_temporal_rope' else 'H3TemporalCoverage', 'inputs': inputs}
            graph['14']['inputs']['filename_prefix'] = rid+'/{attempt_id}'
            job = copy.deepcopy(original)
            job.update(id=rid, graph='graphs/'+rid+'.json', expected_output_prefix=rid+'/')
            job['metadata'].update(method=method, cohort='innovation', innovation_parameters=copy.deepcopy(inputs),
                direction_source_graph_sha256=sha(original_graph), innovation_status='prepared_gpu_unverified')
            if method == 'partial_temporal_rope':
                job['metadata']['delta_derivation'] = 'At first PackedLayout: (reference_video_origin-output_video_origin)/(5/3), after validating every video-bin time coordinate.'
                job['metadata']['attention_formula'] = 'O + alpha*m_ref*(Attention(R_low(delta)Q,K_all_reference_video,V_all_reference_video)-Attention(Q,K_all_reference_video,V_all_reference_video))'
            save(package/job['graph'], graph)
            jobs.append(job)
            checks.append(dict(task_id=sid, source_graph_sha256=sha(original_graph), graph_sha256=sha(package/job['graph']),
                               changed_nodes=['14', '50'], exact_other_nodes=True, prompt_seed_cache_preserved=True))
        save(package/'jobs.json', {'jobs': jobs})
        save(package/'pilot_jobs.json', {'jobs': jobs[:2]})
        save(package/'verification.json', {'total_graphs': len(jobs), 'checks': checks, 'runtime_gpu_verified': False,
             'pilot_order': [j['metadata']['task_id'] for j in jobs[:2]]})
        results.append(dict(method=method, count=len(jobs), jobs=str(package/'jobs.json')))
    paths = sorted((ROOT/'innovation/partial_rope/H3PartialRoPE').glob('*.py'))
    paths += [ROOT/'innovation/partial_rope/H3PartialRoPE/source_contract.json']
    paths += sorted((ROOT/'innovation/temporal_coverage').glob('*.py'))
    save(OUT/'deployment_files.json', {'files': [dict(file=str(p), sha256=sha(p)) for p in paths],
         'packages': results, 'assets_dependency': str(SOURCE/'assets.json'),
         'cache_manifest_dependency': str(SOURCE/'cache_manifests'),
         'deployment_status': 'not_deployed', 'gpu_validation': 'pending'})
    return results


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
