"""CPU comparison of two completed FlexiAct cases through the official reader."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import remote_consume as consumer

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    case = next(c for c in consumer.P['cases'] if c['source_id'] == args.source)
    auto = HERE.parent / 'completed_cases' / case['run_id']
    native = Path(case['parent_root']) / 'analysis/postrun/captured/batch'
    am = auto / 'final' / case['run_id'] / 'METRIC_INPUTS.json'
    nm = native / 'final' / case['parent_run'] / 'METRIC_INPUTS.json'
    out = HERE / 'media_identity' / args.source
    runtime = Path('/data5/researcher/h3_runs/flexiact_official_metric_20261017')
    freeze_sha = 'fa573e2065d1c140ef232513d73b909d2aa2902046d4a9becf609a6e549ad580'
    with consumer.locked():
        av, nv = read(am), read(nm)
        ready = read(auto / 'CASE_READY.json')
        assert ready['metric_inputs_sha256'] == sha(am) and ready['summary']['passed']
        for key in ('official_pair_id', 'original_source_sha256', 'target_sha256',
                    'physical_seconds', 'source_indices', 'full_output_indices',
                    'source_frames', 'source_fps', 'output_frames', 'output_fps'):
            assert av[key] == nv[key], key
        for value in (av, nv):
            assert sha(value['original_source']) == value['original_source_sha256']
            assert sha(value['target_image']) == value['target_sha256']
        for domain, n, fps in [('full158_output', 158, 24), ('edited49', 49, 8)]:
            target = out / (domain + '.json')
            left = {'file': nv[domain], 'sha256': nv[domain + '_sha256']}
            right = {'file': av[domain], 'sha256': av[domain + '_sha256']}
            if target.exists():
                old = read(target)
                assert old['left'] == left and old['right'] == right
                continue
            command = [sys.executable, str(HERE / 'prove_media_identity.py'),
                       '--benchmark', 'flexiact', '--runtime', str(runtime),
                       '--freeze', str(runtime / 'RUNTIME_FREEZE.json'),
                       '--freeze-sha256', freeze_sha, '--frames', str(n),
                       '--fps', str(fps), '--output', str(target)]
            for which, value in [('left', left), ('right', right)]:
                command += ['--' + which, value['file'], '--' + which + '-sha256', value['sha256']]
            subprocess.run(command, check=True, timeout=180, cwd=runtime)
        captures = {}
        for method, arc, run in [('auto', auto, case['run_id']), ('native', native, case['parent_run'])]:
            captures[method] = read(arc / 'audit/x0' / run / 'manifest.json')['final_sampler_result']
        result = {'schema': 'released-auto-native-media-comparison-v1', 'source_id': args.source,
                  'partial_batch': True, 'planned_denominator': 5,
                  'auto_metric_inputs': {'file': str(am), 'sha256': sha(am)},
                  'native_metric_inputs': {'file': str(nm), 'sha256': sha(nm)},
                  'case_ready': {'file': str(auto / 'CASE_READY.json'), 'sha256': sha(auto / 'CASE_READY.json')},
                  'final_latent_signatures': captures,
                  'proofs': {k: {'file': str(out / (k + '.json')), 'sha256': sha(out / (k + '.json')),
                                 'exact': read(out / (k + '.json'))['comparison']['exact']}
                             for k in ('full158_output', 'edited49')}, 'score_reused': False}
        path = out / 'SUMMARY.json'
        if path.exists():
            assert read(path) == result
        else:
            path.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        print(json.dumps({'summary': str(path), 'sha256': sha(path), 'proofs': result['proofs']}))


if __name__ == '__main__':
    try:
        main()
    except BlockingIOError:
        print('ONLINE_PRIORITY_OR_CPU_LOCK')
        raise SystemExit(75)
