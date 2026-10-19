"""Evaluate the predeclared leg protocol after the full R31 CPU archive closes."""
from pathlib import Path
import fcntl
import hashlib
import importlib.util
import json
import os
import time

ROOT = Path(__file__).resolve().parents[1]
ARC = ROOT / 'analysis/postrun/captured/batch'
LEG = ROOT / 'analysis/leg_evaluation'
REMOTE = Path('/data5/researcher/h3_runs/timing_karate_native_r31_20261017/analysis/postrun/captured/batch')
LOCK = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
OUT = ROOT / 'analysis/leg_results'

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def mapped(path):
    return ARC / Path(path).relative_to(REMOTE)

def main():
    if not (ARC / 'CPU_COMPLETE.json').exists():
        print('Full R31 CPU archive pending; no leg evaluation started')
        return
    assert read(ARC / 'CPU_COMPLETE.json')['passed'] is True
    frozen = read(LEG / 'FREEZE.json')
    for name, digest in frozen['files'].items():
        assert sha(LEG / name) == digest, name
    assert not OUT.exists(), 'Existing result requires review'
    with LOCK.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Shared CPU occupied; no leg evaluation started')
            return
        start = time.monotonic()
        summaries = [read(ARC / 'final' / f'r31_source_49617_seed{seed}_native/SUMMARY.json')
                     for seed in (2026101701, 2026101702)]
        source = mapped(summaries[0]['source_pose'])
        assert all(x['source_pose_sha256'] == sha(source) for x in summaries)
        source_raw = read(source)
        assert sha(ARC / 'input/source_49617_video.mp4') == source_raw['video']['sha256']
        bindings = {'__source__': {'pose_sha256': sha(source), 'video_sha256': source_raw['video']['sha256']}}
        targets = {}
        for summary in summaries:
            name = str(summary['seed'])
            video = mapped(summary['video'])
            assert sha(video) == summary['video_sha256']
            targets[name] = mapped(summary['pose'])
            bindings[name] = {'pose_sha256': summary['pose_sha256'], 'video_sha256': summary['video_sha256']}
        spec = importlib.util.spec_from_file_location('r31_leg_metrics', LEG / 'leg_metrics.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.compare(source, targets, bindings=bindings)
        OUT.mkdir()
        (OUT / 'RESULT.json').write_text(json.dumps(result, allow_nan=False, indent=2) + '\n')
        record = {'passed': True, 'freeze_sha256': sha(LEG / 'FREEZE.json'),
                  'result_sha256': sha(OUT / 'RESULT.json'), 'input_bindings': bindings,
                  'source_pose': str(source), 'targets': {k: str(v) for k, v in targets.items()},
                  'counts': {k: v['counts'] for k, v in result['whole_scan'].items()},
                  'CPU_seconds': time.monotonic() - start, 'pid': os.getpid(),
                  'no_new_pose_or_GPU': True,
                  'scope': 'Supplementary pose timing; correlated windows; visual quality and action fidelity require separate review'}
        (OUT / 'SUMMARY.json').write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps(record))

if __name__ == '__main__':
    main()
