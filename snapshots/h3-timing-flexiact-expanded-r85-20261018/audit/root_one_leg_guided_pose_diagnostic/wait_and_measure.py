"""Read completed one_leg history, then run the existing CPU pose probe once."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time

ROOT = Path('/data5/researcher/h3_runs/timing_flexiact_expanded_r85_20261018')
HERE = ROOT / 'audit/root_one_leg_guided_pose_diagnostic'
RUN = 'r85_one_leg__movie_man_9_seed2026101701_forced'
PROBE = Path('/data5/researcher/h3_runs/timing_oxygen_online_r86_20261018/scripts/pose_probe.py')
EXPECTED_PROBE_SHA = '04c6dd432ddf102300a4cd065f4de8b9c2bc0661ce1abb06d994330b32ae693f'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
for key in ['OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
    os.environ[key] = '2'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(name, data):
    p = HERE / name
    assert not p.exists(), str(p)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def identity():
    pid = os.getpid()
    raw = Path(f'/proc/{pid}/cmdline').read_bytes()
    assert raw
    tail = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return {'pid': pid, 'uid': os.getuid(), 'start_ticks': tail[19],
            'cmdline_sha256': hashlib.sha256(raw).hexdigest(),
            'cmdline': raw.replace(b'\0', b' ').decode()}


def video_entries(value):
    if isinstance(value, dict):
        if isinstance(value.get('filename'), str) and value['filename'].endswith('.mp4'):
            yield value
        for child in value.values():
            yield from video_entries(child)
    elif isinstance(value, list):
        for child in value:
            yield from video_entries(child)


def main():
    HERE.mkdir(exist_ok=True)
    assert not (HERE / 'STARTED.json').exists(), 'An actual measurement is already registered'
    assert sha(PROBE) == EXPECTED_PROBE_SHA
    waiter = identity()
    save('WAIT_STARTED.json', {'identity': waiter, 'created_unix': time.time(),
        'scope': 'CPU-only filesystem wait; no inference API writes or process control',
        'poll_seconds': 60, 'deadline_seconds': 5400})
    end = time.monotonic() + 5400
    history_path = ROOT / 'logs' / (RUN + '_history.json')
    while True:
        if history_path.exists():
            history = json.loads(history_path.read_text())
            status = history['status']
            if status.get('status_str') == 'error':
                raise RuntimeError('Generation history records an actual error')
            if status.get('completed') is True and status.get('status_str') == 'success':
                break
        if time.monotonic() >= end:
            raise TimeoutError('No completed success history within the bounded CPU wait')
        time.sleep(60)
    job_path = ROOT / 'logs' / (RUN + '_job.json')
    job = json.loads(job_path.read_text())
    assert history['prompt'][1] == job['prompt_id'], 'History/prompt mismatch'
    entries = {x['filename']: x for x in video_entries(history.get('outputs', {}))
               if x['filename'].startswith(RUN + '_')}
    assert len(entries) == 1, entries
    item = next(iter(entries.values()))
    assert item.get('type', 'output') == 'output'
    video = (ROOT / 'output' / item.get('subfolder', '') / item['filename']).resolve()
    assert video.is_relative_to(ROOT / 'output') and video.is_file()
    first = video.stat()
    time.sleep(3)
    second = video.stat()
    assert (first.st_size, first.st_mtime_ns) == (second.st_size, second.st_mtime_ns)
    ffprobe = shutil.which('ffprobe')
    assert ffprobe, 'Existing ffprobe is required; no installation is attempted'
    info = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,nb_frames,avg_frame_rate', '-of', 'json', str(video)], timeout=30))
    stream = info['streams'][0]
    assert (stream['width'], stream['height'], int(stream['nb_frames']), stream['avg_frame_rate']) == (1152, 768, 158, '24/1')
    reference = json.loads((ROOT / 'audit/root_one_leg_pose_diagnostic/poses/source_one_leg_video.pose.json').read_text())
    assert reference['provenance']['script_sha256'] == EXPECTED_PROBE_SHA
    destination = HERE / 'poses'
    destination.mkdir(exist_ok=False)
    args = [str(PROBE), '--threads', '2', '--frame-end', '146', '--output-dir', str(destination), '--video', str(video)]
    save('STARTED.json', {'identity': identity(), 'pose_argv': args, 'python': sys.executable,
        'created_unix': time.time(), 'CUDA_VISIBLE_DEVICES': os.environ['CUDA_VISIBLE_DEVICES'],
        'history_file': str(history_path), 'history_sha256': sha(history_path), 'prompt_id': job['prompt_id'],
        'video_file': str(video), 'video_sha256': sha(video), 'video_bytes': second.st_size,
        'closed_output_checks': {'actual_history_success': True, 'stable_size_mtime_3s': True, 'stream': stream},
        'probe_sha256': sha(PROBE), 'scope': 'Posthoc descriptive pose, all147valid frames, CPU only'})
    sys.argv = args
    runpy.run_path(str(PROBE), run_name='__main__')
    pose = destination / (video.stem + '.pose.json')
    result = json.loads(pose.read_text())
    assert len(result['frames']) == 147
    assert result['video']['sha256'] == sha(video)
    assert result['extraction'] == {'start': 0, 'end': 146, 'stride': 1}
    assert result['provenance'] == reference['provenance'], 'Source/forced pose provenance changed'
    import torch
    assert not torch.cuda.is_initialized()
    save('COMPLETE.json', {'status': 'complete', 'identity': identity(), 'completed_unix': time.time(),
        'pose': str(pose), 'pose_sha256': sha(pose), 'same_source_pose_provenance': True,
        'cuda_initialized': torch.cuda.is_initialized(), 'statistics': result['statistics']})
    print(json.dumps({'completed': str(pose), 'cuda_initialized': False}), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        HERE.mkdir(exist_ok=True)
        if not (HERE / 'FAILURE.json').exists():
            save('FAILURE.json', {'error': repr(error), 'identity': identity(), 'time_unix': time.time()})
        raise
