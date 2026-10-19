"""CPU evidence of actual official-loader input equality; never assigns scores."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def verify_freeze(root, path, expected):
    require(sha(path) == expected, 'runtime freeze differs')
    data = json.loads(Path(path).read_text())
    files = data['files']
    items = files.items() if isinstance(files, dict) else ((r['file'], r['sha256']) for r in files)
    for name, value in items:
        digest = value['sha256'] if isinstance(value, dict) else value
        require(sha(root / name) == digest, 'runtime member differs: ' + name)


def compare_arrays(left, right):
    import numpy as np
    summary = {'left_shape': list(left.shape), 'right_shape': list(right.shape),
               'left_dtype': str(left.dtype), 'right_dtype': str(right.dtype)}
    if left.shape != right.shape or left.dtype != right.dtype:
        return dict(summary, exact=False, reason='shape_or_dtype_differs')
    require(left.dtype == np.uint8 and left.ndim == 4 and left.shape[-1] == 3,
            'expected decoded uint8 RGB frames')
    frames = []
    for index, (a, b) in enumerate(zip(left, right)):
        delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
        frames.append({'index': index, 'left_rgb_sha256': hashlib.sha256(a.tobytes()).hexdigest(),
                       'right_rgb_sha256': hashlib.sha256(b.tobytes()).hexdigest(),
                       'differing_channels': int(np.count_nonzero(delta)),
                       'maximum_absolute_channel_error': int(delta.max()),
                       'mean_absolute_channel_error': float(delta.mean())})
    return dict(summary, exact=all(r['differing_channels'] == 0 for r in frames), frames=frames)


def probe(path, binary):
    command = [binary, '-v', 'error', '-select_streams', 'v:0', '-show_streams', '-show_frames',
               '-show_entries', 'stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time',
               '-of', 'json', str(path)]
    data = json.loads(subprocess.check_output(command, text=True, timeout=90))
    stream = data['streams'][0]
    return {'width': stream['width'], 'height': stream['height'],
            'average_frame_rate': stream['avg_frame_rate'],
            'timestamps_seconds': [float(r['best_effort_timestamp_time']) for r in data['frames']]}


def original_reader(benchmark, root):
    import cv2
    import numpy as np
    import torch
    cv2.setNumThreads(1)
    torch.set_num_threads(1)
    require(not torch.cuda.is_initialized(), 'CUDA must remain uninitialized')
    if benchmark == 'flexiact':
        spec = importlib.util.spec_from_file_location('frozen_flexiact_adapter', root / 'metric_adapter.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.load_functions('vendor/co-tracker/cotracker/utils/visualizer.py',
                                     ['read_video_from_path'], {'cv2': cv2, 'np': np})['read_video_from_path']
    sys.path.insert(0, str(root / 'metric_runtime'))
    from ive_mf_adapter import official_class
    cls = official_class()
    instance = cls.__new__(cls)
    instance.max_frames = None
    return instance.read_video_file


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--benchmark', choices=['flexiact', 'ivebench'], required=True)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--freeze', type=Path, required=True)
    p.add_argument('--freeze-sha256', required=True)
    for name in ('left', 'right'):
        p.add_argument('--' + name, type=Path, required=True)
        p.add_argument('--' + name + '-sha256', required=True)
    p.add_argument('--frames', type=int, required=True)
    p.add_argument('--fps', type=int, required=True)
    p.add_argument('--ffprobe', default='/usr/bin/ffprobe')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'CPU-only environment required')
    require(not a.output.exists(), 'existing proof must be retained')
    verify_freeze(a.runtime, a.freeze, a.freeze_sha256)
    for name in ('left', 'right'):
        require(sha(getattr(a, name)) == getattr(a, name + '_sha256'), name + ' video SHA differs')
    metadata = {name: probe(getattr(a, name), a.ffprobe) for name in ('left', 'right')}
    for value in metadata.values():
        times = value['timestamps_seconds']
        require(len(times) == a.frames and all(abs(t - i/a.fps) < 1e-6 for i,t in enumerate(times)),
                'frame count or physical timebase differs')
    reader = original_reader(a.benchmark, a.runtime)
    comparison = compare_arrays(reader(str(a.left)), reader(str(a.right)))
    import torch
    require(not torch.cuda.is_initialized(), 'unexpected CUDA initialization')
    result = {'schema': 'official-loader-video-identity-proof-v1', 'benchmark': a.benchmark,
              'runtime_freeze_sha256': a.freeze_sha256, 'proof_code_sha256': sha(__file__),
              'left': {'file': str(a.left), 'sha256': a.left_sha256},
              'right': {'file': str(a.right), 'sha256': a.right_sha256}, 'metadata': metadata,
              'same_physical_timebase': True, 'comparison': comparison,
              'cuda_initialized': False, 'score_reused': False,
              'scope': 'Actual official-reader RGB equality only. Score reuse additionally requires bound source, tracker settings, cached score and release evidence.'}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps({'output': str(a.output), 'sha256': sha(a.output), 'exact': comparison['exact']}))


if __name__ == '__main__':
    main()
