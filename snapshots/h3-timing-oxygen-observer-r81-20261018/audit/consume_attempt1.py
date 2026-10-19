"""Administrative transfer/CPU consumption for frozen R81 attempt1. No CUDA launch."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from contract import check_package, require, require_sequence, sha
sys.path.insert(0, str(ROOT / 'vendor'))
from common import write

HOST41 = 'H3_SERVER_B'
HOST9 = 'H3_SERVER_A'
R41 = '/data3/researcher/h3_runs/timing_oxygen_observer_r81_20261018'
R9 = '/data5/researcher/h3_runs/timing_oxygen_observer_r81_20261018'
P9 = '/home/researcher/miniconda3/envs/comfyui/bin/python'
AUDIT = ROOT / 'audit/consumer_attempt1'


def ssh(host, command, **kwargs):
    return subprocess.run(['ssh', '-o', 'ConnectTimeout=20', host, command], check=True, **kwargs)


def snapshot():
    code = "from pathlib import Path; p=Path(" + repr(R41 + '/outputs/attempt1/RESULT.json') + "); print(p.read_text() if p.exists() else '{}')"
    result = ssh(HOST41, 'python3 -c ' + shlex.quote(code), capture_output=True, text=True, timeout=40)
    return json.loads(result.stdout)


def transfer():
    p = check_package()
    deadline = time.monotonic() + 6000
    previous = None
    while True:
        record = snapshot()
        state = (record.get('status'), len(record.get('steps', [])))
        if state != previous:
            write(AUDIT / 'DECODE_PROGRESS.json', record)
            print(json.dumps({'decode_state': state}), flush=True)
            previous = state
        if record.get('status') == 'complete':
            break
        require(record.get('status') not in ('failed', 'failed_cleanup'), 'decoder failed; retain actual failure')
        require(time.monotonic() < deadline, 'bounded decoder observation timeout')
        time.sleep(30)
    require(record['protocol_sha256'] == sha(ROOT / 'configs/PROTOCOL.json'), 'decoder protocol differs')
    require_sequence(record['steps'])
    files = ['RESULT.json']
    for i, row in enumerate(record['steps']):
        require(row['file'] == f'step{i:03d}.mp4' and row['snapshot_sha256'] == p['snapshots'][i]['sha256'], 'decoder snapshot/file identity')
        files.extend([row['file'], f'step{i:03d}.json'])
    archive = AUDIT / 'decoded_attempt1.tar'
    require(not archive.exists(), 'keep earlier transfer evidence')
    command = 'tar -C ' + shlex.quote(R41 + '/outputs/attempt1') + ' -cf - ' + ' '.join(map(shlex.quote, files))
    with archive.open('xb') as stream:
        ssh(HOST41, command, stdout=stream, timeout=600)
    destination = ROOT / 'outputs/attempt1'
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        require(sorted(m.name for m in members) == sorted(files) and all(m.isfile() for m in members), 'archive exact regular-file set')
        for member in members:
            stream = tar.extractfile(member)
            with (destination / member.name).open('xb') as target:
                while block := stream.read(1024 * 1024):
                    target.write(block)
    local = json.loads((destination / 'RESULT.json').read_text())
    require(local == record, 'RESULT changed during transfer')
    validation = []
    for row in local['steps']:
        video = destination / row['file']
        require(sha(video) == row['sha256'], 'MP4 SHA mismatch')
        require(json.loads(video.with_suffix('.json').read_text()) == row, 'per-step JSON differs from completed RESULT')
        raw = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_streams', '-show_frames',
                                       '-show_entries', 'stream=width,height,r_frame_rate:frame=best_effort_timestamp_time', '-of', 'json', str(video)], text=True, timeout=45)
        probe = json.loads(raw)
        stream = probe['streams'][0]
        require([stream['width'], stream['height']] == [1312, 736] and Fraction(stream['r_frame_rate']) == 24, 'frame geometry/fps')
        pts = [float(frame['best_effort_timestamp_time']) for frame in probe['frames']]
        require(len(pts) == 107 and all(abs(t-i/24) < 1e-5 for i, t in enumerate(pts)), 'original physical timestamps')
        validation.append({'index': row['index'], 'sha256': row['sha256'], 'frames': len(pts), 'PTS_24fps_verified': True})
    write(AUDIT / 'TRANSFER_VALIDATED.json', {'status': 'complete', 'archive_sha256': sha(archive), 'protocol_sha256': record['protocol_sha256'], 'steps': validation})
    remote_archive = R9 + '/audit/decoded_attempt1.tar'
    subprocess.run(['scp', str(archive), HOST9 + ':' + remote_archive], check=True, timeout=600)
    command = 'cd ' + shlex.quote(R9) + ' && test ! -e outputs/attempt1 && mkdir outputs/attempt1 && tar -C outputs/attempt1 -xf audit/decoded_attempt1.tar'
    ssh(HOST9, command, timeout=120)
    return record


def consume():
    require((AUDIT / 'TRANSFER_VALIDATED.json').is_file(), 'validated transfer required')
    env = "CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4 "
    commands = [
        ('pose', ['scripts/pose_all.py', '--decoded', 'outputs/attempt1', '--output', 'poses/attempt1']),
        ('original', ['scripts/scan_all.py', '--representation', 'original', '--poses', 'poses/attempt1', '--output', 'results/attempt1/original']),
        ('visible', ['scripts/scan_all.py', '--representation', 'visible', '--poses', 'poses/attempt1', '--output', 'results/attempt1/visible'])]
    for name, args in commands:
        command = 'cd ' + shlex.quote(R9) + ' && ' + env + shlex.quote(P9) + ' -u ' + ' '.join(map(shlex.quote, args)) + ' > audit/CONSUME_' + name + '.log 2>&1'
        write(AUDIT / 'CPU_PROGRESS.json', {'stage': name, 'status': 'running', 'started_unix': time.time()})
        print(json.dumps({'CPU_stage': name}), flush=True)
        ssh(HOST9, command, timeout=12000)
    write(AUDIT / 'CPU_PROGRESS.json', {'status': 'complete', 'finished_unix': time.time()})


def collect():
    require(json.loads((AUDIT / 'CPU_PROGRESS.json').read_text())['status'] == 'complete', 'CPU work complete required')
    paths = ['poses/attempt1', 'results/attempt1', 'audit/CONSUME_pose.log', 'audit/CONSUME_original.log', 'audit/CONSUME_visible.log']
    archive = AUDIT / 'cpu_results.tar.gz'
    with archive.open('xb') as stream:
        ssh(HOST9, 'tar -C ' + shlex.quote(R9) + ' -czf - ' + ' '.join(map(shlex.quote, paths)), stdout=stream, timeout=600)
    with tarfile.open(archive) as tar:
        for member in tar:
            path = Path(member.name)
            require(not path.is_absolute() and '..' not in path.parts and (member.isdir() or member.isfile()), 'safe result archive')
            target = ROOT / path
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as output:
                input_stream = tar.extractfile(member)
                while block := input_stream.read(1024 * 1024):
                    output.write(block)
    summaries = {}
    for representation in ('original', 'visible'):
        summary = json.loads((ROOT / 'results/attempt1' / representation / 'SUMMARY.json').read_text())
        require(summary['status'] == 'complete' and summary['fixed_observation_denominator'] == 20, 'full replay result required')
        for row in summary['steps']:
            require(sha(ROOT / 'results/attempt1' / representation / row['full_evidence']) == row['full_evidence_sha256'], 'observer evidence SHA')
        summaries[representation] = {k: summary[k] for k in ('first_qualified_candidate_index', 'first_persistent_ON_index', 'ON_indices')}
    write(AUDIT / 'COMPLETE.json', {'status': 'complete', 'cpu_archive_sha256': sha(archive), 'summaries': summaries, 'GPU_calls_by_consumer': 0})
    print(json.dumps(summaries), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['all', 'transfer', 'consume', 'collect'])
    action = parser.parse_args().action
    AUDIT.mkdir(parents=True, exist_ok=True)
    for name, function in [('transfer', transfer), ('consume', consume), ('collect', collect)]:
        if action in ('all', name):
            function()
