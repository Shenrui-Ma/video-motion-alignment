"""Recompute the existing R126 pose scan on CPU with content-bound endpoints."""
from pathlib import Path
import hashlib
import json
import sys
import time

ROOT = Path(__file__).resolve().parent
EVIDENCE = Path('/Users/researcher/DevProjects/h3-ive-handkerchief-full-context-metrics-r126-20261020/audit/visible_arm_feasibility_20261020')
sys.path.insert(0, str(EVIDENCE / 'scripts'))
sys.path.insert(0, str(EVIDENCE / 'extensions'))
import arm_features
import scan_current_pose
from H3AutomaticWindowRouter.automatic_window_policy import candidate
from H3AutomaticWindowRouter.geometry import Geometry
import content_visibility


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    case = json.loads((EVIDENCE / 'CASE.json').read_text())
    geometry = Geometry.from_case(case)
    pose_dir = EVIDENCE / 'actual/poses'
    source = pose_dir / 'long_0059_video.pose.json'
    native = pose_dir / 'r126_long_0059_seed2026101701_native_00001_.pose.json'
    original = json.loads((EVIDENCE / 'actual/SUMMARY.json').read_text())
    assert sha(source) == original['coverage']['source']['pose_sha256']
    assert sha(native) == original['coverage']['native']['pose_sha256']
    assert sha(EVIDENCE / 'actual/SCAN.json') == original['scan_sha256']
    scan_current_pose.features = lambda raw, g, c: content_visibility.features(
        raw, g, c, case['evaluation_crop_xywh'], arm_features)
    started = time.monotonic()
    scan = scan_current_pose.observe(source, native, 0, geometry)
    eligible = [c for row in scan['windows'] if (c := candidate(row)) is not None]
    (ROOT / 'R126_BOUNDARY_SCAN.json').write_text(
        json.dumps(scan, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    result = {
        'scope': 'CPU replay of final source/ordinary pose; not an online run',
        'source_pose_sha256': sha(source), 'native_pose_sha256': sha(native),
        'original_scan_sha256': original['scan_sha256'],
        'candidate_scan_sha256': sha(ROOT / 'R126_BOUNDARY_SCAN.json'),
        'module_sha256': sha(ROOT / 'content_visibility.py'),
        'frozen_arm_features_sha256': sha(EVIDENCE / 'scripts/arm_features.py'),
        'frozen_scan_sha256': sha(EVIDENCE / 'scripts/scan_current_pose.py'),
        'original_qualified_windows': len(original['qualifying_rows']),
        'candidate_qualified_windows': len(eligible), 'candidates': eligible,
        'candidate_baseline_counts': {k: sum(r['baseline'] == k for r in scan['windows'])
            for k in sorted({r['baseline'] for r in scan['windows']})},
        'crop_xywh': case['evaluation_crop_xywh'], 'valid_frames': geometry.valid_frames,
        'CPU_seconds': time.monotonic() - started, 'new_model_inference': False,
        'conclusion': 'Out-of-content elbows are excluded from arm direction; visible-wrist measurement is a separate descriptor problem.'
    }
    (ROOT / 'R126_REPLAY_RESULT.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
