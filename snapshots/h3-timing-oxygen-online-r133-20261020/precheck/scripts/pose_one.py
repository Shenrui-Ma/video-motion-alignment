"""Frozen CPU pose/ROI/scan for one decoded Native endpoint."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from precheck_support import ROOT, config, geometry, lifetime, require, sha, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', type=int, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--parent-json', required=True)
    args = parser.parse_args()
    lifetime.install_lifetime_guard(json.loads(args.parent_json))
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'pose must hide GPUs')
    value = config(); geom = geometry(value)
    require(args.index in value['indices'], 'bounded physical index')
    require(args.directory.resolve().is_relative_to(ROOT / 'audit'), 'owned output only')
    started = time.monotonic()
    out = args.directory / 'pose'; out.mkdir(exist_ok=False)
    subprocess.run([sys.executable, str(ROOT / 'scripts/pose_probe.py'), '--video', str(args.directory / 'native.mp4'),
                    '--output-dir', str(out), '--aux-root', value['runtime']['aux_root'], '--threads', '4', '--stride', '1'], check=True, timeout=480)
    from pose_domain import validate_pose
    from adult_selector import adult_only
    raw_path = out / 'native.pose.json'
    raw = validate_pose(raw_path, geom)
    require(raw['video']['sha256'] == sha(args.directory / 'native.mp4'), 'pose media binding')
    filtered, rejected = adult_only(raw, geom.video_geometry)
    target = out / 'native.adult.pose.json'; write(target, filtered)
    validate_pose(target, geom)
    write(out / 'adult_selection.json', dict(bounds=[.4, .75], rejected_frames=rejected,
          raw_pose_sha256=sha(raw_path), filtered_pose_sha256=sha(target),
          automation_scope='source-specified person position; temporal control online'))
    from scan_current_pose import observe
    observation = observe(ROOT / value['source_pose'], target, args.index, geom)
    write(args.directory / 'observer.json', observation)
    write(args.directory / 'pose_complete.json', dict(status='complete', index=args.index,
          pose_metric_seconds=time.monotonic() - started, raw_sha256=sha(raw_path),
          filtered_sha256=sha(target), observer_sha256=sha(args.directory / 'observer.json')))


if __name__ == '__main__':
    main()
