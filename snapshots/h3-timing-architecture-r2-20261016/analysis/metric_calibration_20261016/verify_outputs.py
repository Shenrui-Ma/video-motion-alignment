"""Check calibration completeness and compare local support reports to frozen CLI."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

HOME = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = json.loads((HOME/'protocol.json').read_text())
    r = json.loads((HOME/'results.json').read_text())
    freeze = json.loads((HOME/'tool_freeze.json').read_text())
    for key, item in p['inputs'].items():
        if sha(item['path']) != item['sha256']:
            raise ValueError('External frozen file changed: '+key)
    for name, digest in freeze['files'].items():
        if sha(HOME/name) != digest:
            raise ValueError('Calibration definition changed: '+name)
    if r['protocol_sha256'] != sha(HOME/'protocol.json'):
        raise ValueError('Wrong result protocol')
    names = [v['id'] for v in p['variants']]
    if list(r['variants']) != names or len(names) != 11:
        raise ValueError('Missing or additional variants')
    count = 0
    for name in names:
        item = r['variants'][name]
        if sha(item['array_file']) != item['array_sha256']:
            raise ValueError('Transformed input changed: '+name)
        for threshold in p['confidence_thresholds']:
            for window in p['windows']:
                wkey = ':'.join(map(str, window))
                rows = item['diagnostics'][str(threshold)][wkey]
                if list(rows) != p['features']:
                    raise ValueError('Feature inventory changed')
                for feature, d in rows.items():
                    if len(d['curve']) != 49 or [x['lag_frames'] for x in d['curve']] != list(range(-24, 25)):
                        raise ValueError('Search curve incomplete')
                    count += 1
    # Re-serialize saved arrays only for exercising the original CLI; they remain
    # explicitly synthetic pose inputs, not a video or a new detector extraction.
    compat = HOME/'frozen_cli_verification'
    compat.mkdir(exist_ok=False)
    paths = {}
    source_raw = json.loads(Path(p['inputs']['source']['path']).read_text())
    spec = importlib.util.spec_from_file_location('frozen_clean', p['inputs']['metrics']['path'])
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    for name in names:
        with np.load(r['variants'][name]['array_file'], allow_pickle=False) as a:
            records = [{'frame': int(f), 'time_s': float(t), 'selected_person': 0,
                'persons': [{'coco17_xy': xy, 'coco17_score': confidence}]} for f, t, xy, confidence
                in zip(a['frames'], a['time_s'], a['xy'], a['confidence'])]
        path = compat/(name+'.synthetic_pose.json')
        path.write_text(json.dumps(m.clean({'schema': 'synthetic_pose_calibration_not_video',
            'video': source_raw['video'], 'frames': records}), allow_nan=False)+'\n')
        paths[name] = path
    subprocess_count = 0
    max_error_difference = 0.0
    environment = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1')
    for threshold in p['confidence_thresholds']:
        for family, members in p['common_support_groups'].items():
            dest = compat/f'{family}.threshold{threshold}.json'
            cmd = [sys.executable, p['inputs']['common_support_reference']['path'],
                   '--source', p['inputs']['source']['path'], '--confidence', str(threshold), '--output', str(dest)]
            for name in members:
                cmd += ['--run', f'{name}={paths[name]}']
            for window in p['windows']:
                cmd += ['--window', ':'.join(map(str, window))]
            proc = subprocess.run(cmd, capture_output=True, text=True, env=environment)
            (compat/(dest.stem+'.log')).write_text(proc.stdout+proc.stderr)
            if proc.returncode != 0:
                raise RuntimeError('Frozen common-support CLI failed')
            expected = json.loads(dest.read_text())['results']
            actual = r['common_support'][str(threshold)][family]
            for e in expected:
                a = next(v for v in actual if v['window'] == e['window'] and v['feature'] == e['feature'])
                if a['coverage'] != e['common_valid_fraction'] or a['status'] != e['status']:
                    raise ValueError('Common-support denominator differs from original evaluator')
                for name in members:
                    x = a['same_frame_errors'][name]
                    y = e['runs'][name]['same_frame_error_on_common_support']
                    if x is None or y is None:
                        if x != y:
                            raise ValueError('Missing-support semantics differ')
                    else:
                        max_error_difference = max(max_error_difference, abs(x-y))
                        if not np.isclose(x, y, rtol=1e-12, atol=1e-12):
                            raise ValueError('Common-support metric differs from frozen CLI')
            subprocess_count += 1
    report = {'status': 'pass', 'complete_variant_count': len(names),
              'diagnostic_cells': count, 'lag_curve_length_per_cell': 49,
              'external_inputs_and_frozen_tool_hashes_unchanged': True,
              'frozen_cli_family_threshold_checks': subprocess_count,
              'max_common_support_error_difference': max_error_difference,
              'results_sha256': sha(HOME/'results.json'), 'verification_script_sha256': sha(__file__),
              'limits': 'Verifies implementation and complete reporting, not population metric accuracy.'}
    (HOME/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
