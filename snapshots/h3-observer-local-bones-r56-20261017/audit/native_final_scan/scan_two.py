"""Offline potential observability of two complete Native90 outputs; CPU only."""
from collections import Counter
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BASE = Path('/data3/researcher/h3_runs/timing_auto_motion_r26_20261017/analysis/ivebench_physical_time_eval_20261017')
EXPECTED_FREEZE = '6e14dbf25ed28567848396f01eb70827ad0476570c542c44f3b757485a5ca794'
PAIRS = ('short_0263', 'short_0370')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x') as file:
        json.dump(value, file, allow_nan=False)
        file.write('\n')


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    assert sha(ROOT / 'FREEZE.json') == '8bece353fc71a8a968a17502d8ff29bfabcb13f04957cb54830f77546717f037'
    for relative, digest in json.loads((ROOT / 'FREEZE.json').read_text())['files'].items():
        assert sha(ROOT / relative) == digest, relative
    for entry in json.loads((HERE / 'SOURCE_CODE.json').read_text())['files']:
        assert sha(HERE / entry['copy']) == entry['sha256']
    assert sha(BASE / 'FREEZE.json') == EXPECTED_FREEZE
    sys.path.insert(0, str(BASE))
    import pose90
    import run_pair
    pose90.frozen()
    assert sha(BASE / 'timing_metrics.py') == sha(ROOT / 'source_snapshot/scripts/timing_metrics.py')
    with pose90.LOCK.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if any((p.parent / 'native.mp4').exists()
               and not any((p.parent / name).exists() for name in ('response.json', 'failure.json'))
               for p in (pose90.AUTO / 'audit/observations').glob('step*/request.json')):
            return 75
        sys.path.insert(0, str(ROOT))
        import arm_features
        sys.path.insert(0, str(ROOT / 'source_snapshot/scripts'))
        sys.path.insert(0, str(HERE / 'source_code/scripts'))
        # Load the pure geometry module without importing the ComfyUI node package.
        package = types.ModuleType('H3AutomaticWindowRouter')
        package.__path__ = [str(ROOT / 'source_snapshot/extensions/H3AutomaticWindowRouter')]
        sys.modules['H3AutomaticWindowRouter'] = package
        import scan_current_pose as scanner
        policy_path = HERE / 'source_code/extensions/H3AutomaticWindowRouter/automatic_window_policy.py'
        spec = importlib.util.spec_from_file_location('r56_offline_signed_policy', policy_path)
        policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(policy)
        protocol = json.loads((ROOT / 'source_snapshot/configs/protocol.json').read_text())
        destination = HERE / 'results'
        destination.mkdir(exist_ok=False)
        records = []
        started = time.monotonic()
        for pair in PAIRS:
            case = next(c for c in protocol['cases'] if c['source_id'] == pair)
            frozen_case = next(c for c in pose90.P['cases'] if c['pair_id'] == pair)
            source_path = ROOT / 'source_snapshot' / case['source_pose_path']
            assert sha(source_path) == frozen_case['source_pose_sha256'] == case['source_pose_sha256']
            # This validator binds the full90 encoded video, decoder geometry,
            # exact source mapping, postrun completion and original pose runtime.
            native_raw, receipt = run_pair.generated(pair, 'native')
            original_native_pose = Path(receipt['pose_file'])
            assert native_raw['video']['container_frame_count'] == 90
            pose_path = destination / (pair + '.native90.pose.json')
            shutil.copyfile(original_native_pose, pose_path)
            geometry = scanner.Geometry.from_case(case)
            original_features = scanner.features
            original = scanner.observe(source_path, pose_path, 0, geometry)
            scanner.features = arm_features.features
            try:
                changed = scanner.observe(source_path, pose_path, 0, geometry)
            finally:
                scanner.features = original_features
            # The observer API requires an index; these inputs are final outputs,
            # so no denoising-step index is asserted in this offline record.
            for observation in (original, changed):
                observation.pop('physical_index')
                observation['input_stage'] = 'decoded_complete_native_video'
            eligible = [proposal for row in changed['windows']
                        if (proposal := policy.candidate(row, threshold=.5)) is not None]
            output = destination / (pair + '.json')
            record = {'pair_id': pair, 'scope': 'Potential detection on the final Native output; no online start/stop or generation claim.',
                      'source_pose_sha256': sha(source_path), 'native_pose_sha256': sha(pose_path),
                      'native_generated_receipt': receipt, 'pose_reused': True,
                      'pose_source': 'Full90 model output, before score crop/prefix encoding.',
                      'observer_api_index_argument': 0, 'candidate_feature_sha256': sha(ROOT / 'arm_features.py'),
                      'original': original, 'arm_only': changed,
                      'eligible_signed_proposals': eligible,
                      'counters': {'original_status': original['status'], 'candidate_status': changed['status'],
                                   'baseline': dict(Counter(row['baseline'] for row in changed['windows'])),
                                   'measurement': dict(Counter(row['status'] for row in changed['windows'])),
                                   'eligible_at_original_gain_threshold_05': len(eligible)}}
            save(output, record)
            records.append({'pair_id': pair, 'file': str(output), 'sha256': sha(output),
                            'counters': record['counters'], 'eligible_signed_proposals': eligible})
        report = {'schema': 'h3-arm-only-final-native-scan-v1', 'fixed_requested_pairs': list(PAIRS),
                  'status': 'complete', 'denoising_policy_executed': False,
                  'scope': 'Final-output detection capability only; confidence, lag and gain thresholds preserved.',
                  'original_evaluator_freeze_sha256': EXPECTED_FREEZE,
                  'candidate_freeze_sha256': sha(ROOT / 'FREEZE.json'),
                  'records': records, 'cpu_seconds': time.monotonic() - started}
        save(destination / 'REPORT.json', report)
        save(destination / 'FILE_INVENTORY.json', {p.name: sha(p) for p in destination.iterdir() if p.is_file()})
        print(json.dumps({'status': 'complete', 'cpu_seconds': report['cpu_seconds'], 'records': records}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
