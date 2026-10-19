"""Original CPU DWPose on each full107 x0 video, using existing host9 weights."""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time
from contract import ROOT, adult_only, check_package, read, require, require_sequence, sha, validate_pose_shape
sys.path.insert(0, str(ROOT / 'vendor'))
from common import write


def acquire(lock, seconds=600):
    deadline = time.monotonic() + seconds
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            require(time.monotonic() < deadline, 'CPU consumer lock exceeded600s')
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--decoded', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'CPU pose must hide CUDA')
    p = check_package()
    for name, digest in p['host9']['external_sha256'].items():
        require(sha(name) == digest, 'pose dependency ' + name)
    source = read(ROOT / 'inputs/source.pose.json')
    validate_pose_shape(source, p['geometry'])
    result = read(args.decoded / 'RESULT.json')
    require(result['status'] == 'complete' and result['protocol_sha256'] == sha(ROOT / 'configs/PROTOCOL.json'), 'decode complete/protocol')
    require_sequence(result['steps'])
    for row in result['steps']:
        require(sha(args.decoded / row['file']) == row['sha256'], 'decoded video changed')
        require(row['snapshot_sha256'] == p['snapshots'][row['index']]['sha256'], 'wrong decoded snapshot')
    if args.validate_only:
        print('CPU pose inputs validated; no pose model invoked')
        return
    args.output.mkdir(parents=True, exist_ok=True)
    selected, rejected = adult_only(source, p['geometry'])
    write(args.output / 'source.pose.json', selected)
    receipts = []
    environment = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1',
                       OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4',
                       NUMEXPR_NUM_THREADS='4', TMPDIR=str(ROOT / 'temp'))
    for item in result['steps']:
        i = item['index']
        folder = args.output / f'step{i:03d}'
        receipt_path = folder / 'COMPLETE.json'
        if receipt_path.exists():
            receipt = read(receipt_path)
            require(receipt['video_sha256'] == item['sha256'] and receipt['protocol_sha256'] == sha(ROOT / 'configs/PROTOCOL.json'), 'existing pose receipt input changed')
            require(sha(folder / 'adult.pose.json') == receipt['adult_pose_sha256'] and sha(folder / f'step{i:03d}.pose.json') == receipt['raw_pose_sha256'], 'existing pose changed')
            receipts.append(receipt)
            continue
        folder.mkdir(exist_ok=False)
        video = args.decoded / item['file']
        start = time.monotonic()
        with open(p['host9']['cpu_lock'], 'a') as lock:
            acquire(lock)
            wait = time.monotonic() - start
            command = [sys.executable, str(ROOT / 'vendor/pose_probe.py'), '--video', str(video),
                       '--output-dir', str(folder), '--aux-root', p['host9']['aux_root'],
                       '--threads', '4', '--stride', '1']
            with (folder / 'pose.log').open('x') as log:
                subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
        raw_path = folder / f'step{i:03d}.pose.json'
        raw = read(raw_path)
        validate_pose_shape(raw, p['geometry'])
        require(raw['video']['sha256'] == item['sha256'], 'pose video SHA')
        require(raw['provenance'] == source['provenance'], 'source and target CPU pose runtimes differ')
        adult, excluded = adult_only(raw, p['geometry'])
        write(folder / 'adult.pose.json', adult)
        receipt = dict(index=i, status='complete', protocol_sha256=sha(ROOT / 'configs/PROTOCOL.json'),
                       video_sha256=item['sha256'], raw_pose_sha256=sha(raw_path),
                       adult_pose_sha256=sha(folder / 'adult.pose.json'), rejected_adult_frames=excluded,
                       selected_visible_frames=sum(r['selected_person'] is not None for r in adult['frames'][:98]),
                       CPU_lock_wait_seconds=wait, total_seconds=time.monotonic() - start, GPU_calls=0)
        write(receipt_path, receipt)
        receipts.append(receipt)
        print(__import__('json').dumps(receipt), flush=True)
    require_sequence(receipts)
    write(args.output / 'COMPLETE.json', dict(status='complete', protocol_sha256=sha(ROOT / 'configs/PROTOCOL.json'),
          source_pose_sha256=sha(ROOT / 'inputs/source.pose.json'), source_adult_pose_sha256=sha(args.output / 'source.pose.json'),
          source_rejected_frames=rejected, steps=receipts, fixed_observation_denominator=20, GPU_calls=0))


if __name__ == '__main__':
    main()
