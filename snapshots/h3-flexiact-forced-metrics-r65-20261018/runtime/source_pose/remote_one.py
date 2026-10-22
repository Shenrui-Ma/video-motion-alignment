"""One bounded CPU source extraction using the existing frozen DWPose script."""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def save(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def validate_pose(raw, video_sha, protocol):
    video, expected = raw['video'], protocol['geometry']
    require(video['sha256'] == video_sha, 'video identity')
    require(video['container_frame_count'] == expected['frames'], 'container frames')
    require(video['width'] == expected['width'] and video['height'] == expected['height'], 'geometry')
    require(math.isfinite(video['fps']) and video['fps'] == expected['fps'], 'FPS')
    require(raw['extraction'] == protocol['extraction'], 'extraction')
    require(len(raw['frames']) == expected['frames'], '158 records required')
    for i, frame in enumerate(raw['frames']):
        require(frame['frame'] == i and math.isfinite(frame['time_s']) and frame['time_s'] == i / 24, 'exact physical frame grid')
    p = raw['provenance']
    require(p['device'] == 'cpu' and p['providers'] == ['CPUExecutionProvider'] and p['threads'] == 4, 'CPU execution')
    return raw


def online_pending(protocol):
    for root in map(Path, protocol['online_priority_roots']):
        for folder in (root / 'audit/observations').glob('step*'):
            if (folder / 'request.json').exists() and (folder / 'native.json').exists() and not (folder / 'pose_complete.json').exists() and not (folder / 'response.json').exists():
                return True
    return False


def execute(source_id):
    protocol = read(HERE / 'PROTOCOL.json')
    require(source_id in protocol['sources'], 'fixed five sources only')
    freeze = read(HERE / 'FREEZE.json')
    for rel, digest in freeze['files'].items():
        require(sha(HERE / rel) == digest, 'sidecar code changed: ' + rel)
    if online_pending(protocol):
        raise BlockingIOError('online observer priority')
    lock_path = Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if online_pending(protocol):
            raise BlockingIOError('online observer priority')
        root = Path(protocol['root_remote'])
        require(sha(root / 'deploy_manifest.json') == protocol['producer_manifest_sha256'], 'producer identity')
        item = protocol['sources'][source_id]
        video = root / item['video']
        require(sha(video) == item['video_sha256'], 'source video bytes')
        require(sha(root / item['input_provenance']) == item['input_provenance_sha256'], 'input mapping bytes')
        for path, digest in protocol['frozen_external'].items():
            require(sha(path) == digest, 'frozen pose implementation/model changed')
        dest = HERE / source_id
        require(not dest.exists(), 'existing phase requires review; no silent overwrite')
        dest.mkdir()
        script = next(p for p in protocol['frozen_external'] if p.endswith('/pose_probe.py'))
        command = [sys.executable, script, '--video', str(video), '--output-dir', str(dest), '--threads', '4', '--stride', '1']
        start = time.monotonic()
        with (dest / 'pose.log').open('x') as log:
            proc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4', MKL_NUM_THREADS='4', NUMEXPR_NUM_THREADS='4'), timeout=protocol['timeout_seconds'])
        require(proc.returncode == 0, 'pose technical failure; preserve phase')
        pose = dest / (video.stem + '.pose.json')
        raw = validate_pose(read(pose), item['video_sha256'], protocol)
        require(sha(video) == item['video_sha256'], 'video changed during extraction')
        provenance = {'source_id': source_id, 'command': command, 'elapsed_seconds': time.monotonic() - start, 'video_path': str(video), 'video_sha256': sha(video), 'pose_path': str(pose), 'pose_sha256': sha(pose), 'input_provenance_sha256': item['input_provenance_sha256'], 'pose_provenance': raw['provenance'], 'code_freeze_sha256': sha(HERE / 'FREEZE.json'), 'protocol_sha256': sha(HERE / 'PROTOCOL.json'), 'statistics': raw['statistics'], 'extraction': raw['extraction'], 'valid_observation_frames': [0, 146], 'padding_frames': [147, 157], 'original_sample_indices': protocol['original_sample_indices'], 'status': 'complete'}
        save(dest / 'PROVENANCE.json', provenance)
        for rel, digest in freeze['files'].items():
            require(sha(HERE / rel) == digest, 'code changed during extraction')
        save(dest / 'COMPLETE.json', {'status': 'complete', 'source_id': source_id, 'code_freeze_sha256': sha(HERE / 'FREEZE.json'), 'files': {p.name: sha(p) for p in dest.iterdir() if p.is_file()}})
        return provenance


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(execute(args.source), allow_nan=False))
    except BlockingIOError:
        print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY')
        raise SystemExit(75)
