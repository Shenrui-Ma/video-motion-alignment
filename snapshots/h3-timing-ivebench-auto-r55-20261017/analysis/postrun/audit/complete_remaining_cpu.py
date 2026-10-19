"""Local, CPU-only continuation for the final two released R55 cases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
POST = HERE.parent
HOST = 'H3_SERVER_B'
ROOT = '/data3/researcher/h3_runs/timing_ivebench_auto_r55_20261017'
REMOTE = ROOT + '/analysis/postrun'
PHY = '/data3/researcher/h3_runs/timing_auto_motion_r26_20261017/analysis/ivebench_physical_time_eval_20261017'
LOCAL_PHY = Path('/Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/analysis/ivebench_physical_time_eval_20261017')
PY = '/data3/researcher/ComfyUI/.venv/bin/python'
SSH = ['ssh', '-o', 'ConnectTimeout=10', HOST]
ENV = ['env', 'CUDA_VISIBLE_DEVICES=', 'PYTHONDONTWRITEBYTECODE=1', 'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'MKL_NUM_THREADS=1', PY]


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def readiness(history, job):
    hs = history.get('status', {})
    if hs.get('status_str') == 'error' or job.get('status') in ('error', 'unknown_missing', 'submission_uncertain'):
        return 'failed'
    if hs.get('completed') is True and hs.get('status_str') == 'success' and job.get('status') == 'success':
        return 'ready'
    return 'pending'


def exact_for_reuse(summary):
    return all(summary['proofs'][domain]['exact'] is True for domain in ('full_video', 'score_video'))


def snapshot(pair):
    run = 'r55_' + pair + '_seed2026101701_auto'
    code = ('import json\nfrom pathlib import Path\nr=Path(' + repr(ROOT) + ')\nrun=' + repr(run) + '\n'
            'def read_live(p):\n'
            ' try: return json.loads(p.read_text())\n'
            ' except (FileNotFoundError,json.JSONDecodeError): return {}\n'
            'paths=[r/"logs"/(run+"_history.json"),r/"logs"/(run+"_job.json")]\n'
            'print(json.dumps([read_live(p) for p in paths]))')
    p = subprocess.run(SSH + [shlex.join(['python3', '-c', code])], text=True, capture_output=True, timeout=35)
    if p.returncode:
        raise RuntimeError('Read-only snapshot transport failed: ' + p.stderr[-1000:])
    try:
        history, job = json.loads(p.stdout)
    except json.JSONDecodeError:
        return 'pending'
    return readiness(history, job)


def phase(pair, name, args):
    logdir = HERE / 'remaining_completion' / pair
    logdir.mkdir(parents=True, exist_ok=True)
    while True:
        stamp = str(time.time_ns())
        started = time.monotonic()
        p = subprocess.run(SSH + [shlex.join(ENV + args)], text=True, capture_output=True, timeout=900)
        (logdir / (name + '_' + stamp + '.log')).write_text(p.stdout + '\nSTDERR\n' + p.stderr)
        if p.returncode == 0:
            return {'elapsed_seconds': time.monotonic() - started, 'log': str(logdir / (name + '_' + stamp + '.log'))}
        if p.returncode != 75:
            raise RuntimeError(name + ' failed with code ' + str(p.returncode) + '; see ' + str(logdir))
        time.sleep(30)


def fetch(remote, local, directory=False):
    local = Path(local)
    (local if directory else local.parent).mkdir(parents=True, exist_ok=True)
    args = ['rsync', '-a', '-e', 'ssh -o ConnectTimeout=10']
    if directory:
        args += ['--include=*/', '--include=*.json', '--include=*.log', '--exclude=*']
    args += [HOST + ':' + remote + ('/' if directory else ''), str(local) + ('/' if directory else '')]
    subprocess.run(args, check=True, timeout=180)


def download(pair):
    run = 'r55_' + pair + '_seed2026101701_auto'
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='')
    while True:
        p = subprocess.run([sys.executable, str(HERE / 'minimal_download.py'), '--run', run], text=True, capture_output=True, timeout=1200, env=env)
        logdir = HERE / 'remaining_completion' / pair
        logdir.mkdir(parents=True, exist_ok=True)
        (logdir / ('download_' + str(time.time_ns()) + '.log')).write_text(p.stdout + '\nSTDERR\n' + p.stderr)
        if p.returncode:
            raise RuntimeError('Existing minimal download failed; inspect preserved log')
        result = json.loads(p.stdout.strip().splitlines()[-1])
        if result['status'] == 'case_ready':
            return
        if result['status'] not in ('busy', 'pending', 'stabilizing', 'waiting_stability', 'success_files_present'):
            raise RuntimeError('Unexpected incremental status: ' + str(result['status']))
        time.sleep(30)


def report(pair, ready, identity, physical, receipt):
    path = HERE / 'PAIRED_PUBLIC_REPORT.json'
    old = read(path)
    score_path = HERE / 'media_identity' / pair / 'REUSED_MF_SCORE.json'
    physical_path = LOCAL_PHY / 'results' / (pair + '.json')
    views = physical['result']['paired_lag_summary']
    row = {'pair_id': pair, 'status': 'paired_complete' if score_path.exists() else 'physical_complete_MF_pending',
           'ON_indices': ready['summary']['active_denoising_indices'],
           'physical_views_per_method': len(views),
           'unknown_views_native': sum(v['methods']['native']['status'] == 'unknown' for v in views),
           'unknown_views_auto': sum(v['methods']['auto']['status'] == 'unknown' for v in views),
           'physical_evidence': {'file': str(physical_path), 'sha256': sha(physical_path)},
           'job_wall_seconds': ready['summary']['job_wall_seconds'],
           'NFE': ready['summary']['NFE'], 'actual_routed_blocks': ready['summary']['actual_routed_blocks'],
           'completion_receipt': {'file': str(receipt), 'sha256': sha(receipt)}}
    if score_path.exists():
        score = read(score_path)
        row.update(native_MF=score['motion_fidelity'], auto_MF=score['motion_fidelity'], MF_delta=0,
                   score_status='reused_identical_input', new_tracker_invocations=0,
                   score_evidence={'file': str(score_path), 'sha256': sha(score_path), 'json_pointer': '/motion_fidelity'})
    else:
        row.update(score_status='pending_actual_target_tracker', new_tracker_invocations=0,
                   media_exact=exact_for_reuse(identity))
    rows = [row if r['pair_id'] == pair else r for r in old['rows']]
    assert len(rows) == old['planned_denominator'] == 5
    updated = dict(old, rows=rows, completed_pairs=sum(r['status'] == 'paired_complete' for r in rows))
    archive = HERE / 'remaining_completion' / pair / 'PAIRED_PUBLIC_REPORT_BEFORE.json'
    if not archive.exists():
        save(archive, old)
    save(path, updated)


def complete(pair):
    start = time.time()
    run = 'r55_' + pair + '_seed2026101701_auto'
    local_case = POST / 'completed_cases' / run
    download(pair)
    phases = {'identity': phase(pair, 'identity', [REMOTE + '/audit/run_identity_pair.py', '--pair', pair])}
    local_identity = HERE / 'media_identity' / pair
    fetch(REMOTE + '/audit/media_identity/' + pair, local_identity, directory=True)
    identity = read(local_identity / 'SUMMARY.json')
    if exact_for_reuse(identity):
        phases['score_reuse'] = phase(pair, 'score_reuse', [REMOTE + '/audit/reuse_ive_score.py', '--pair', pair])
        fetch(REMOTE + '/audit/media_identity/' + pair, local_identity, directory=True)
    else:
        save(HERE / 'remaining_completion' / pair / 'MF_PENDING.json', {'reason': 'actual full or score RGB/PTS differs', 'tracker_started': False, 'identity_sha256': sha(local_identity / 'SUMMARY.json')})
    metric = REMOTE + '/completed_cases/' + run + '/final/' + run + '/METRIC_INPUTS.json'
    wrapper = PHY + '/admin/runtime_priority_v2/run_phase.py'
    phases['pose'] = phase(pair, 'pose', [wrapper, 'pose', '--pair', pair, '--method', 'auto', '--metric-inputs', metric])
    phases['physical_pair'] = phase(pair, 'physical_pair', [wrapper, 'pair', '--pair', pair, '--output', PHY + '/results/' + pair + '.json'])
    fetch(PHY + '/records/auto_' + pair, LOCAL_PHY / 'records' / ('auto_' + pair), directory=True)
    fetch(PHY + '/results/' + pair + '.json', LOCAL_PHY / 'results' / (pair + '.json'))
    ready = read(local_case / 'CASE_READY.json')
    physical = read(LOCAL_PHY / 'results' / (pair + '.json'))
    receipt = HERE / 'remaining_completion' / pair / 'COMPLETE.json'
    save(receipt, {'pair_id': pair, 'status': 'CPU_complete', 'elapsed_wall_seconds': time.time() - start,
                   'phases': phases, 'case_ready_sha256': sha(local_case / 'CASE_READY.json'),
                   'identity_sha256': sha(local_identity / 'SUMMARY.json'),
                   'physical_sha256': sha(LOCAL_PHY / 'results' / (pair + '.json')),
                   'actual_routed_blocks': ready['summary']['actual_routed_blocks'],
                   'ON_indices': ready['summary']['active_denoising_indices'],
                   'job_wall_seconds': ready['summary']['job_wall_seconds'],
                   'original_PT_downloaded': False, 'new_GPU_tracking_started': False})
    report(pair, ready, identity, physical, receipt)
    print(json.dumps({'pair_id': pair, 'receipt': str(receipt), 'ON_indices': ready['summary']['active_denoising_indices'], 'media_exact': exact_for_reuse(identity), 'job_wall_seconds': ready['summary']['job_wall_seconds']}), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--pair', choices=['short_0352', 'short_0370'], required=True)
    a = p.parse_args()
    logdir = HERE / 'remaining_completion' / a.pair
    logdir.mkdir(parents=True, exist_ok=True)
    try:
        while True:
            status = snapshot(a.pair)
            if status == 'ready':
                break
            if status == 'failed':
                raise RuntimeError('Producer reports actual failure; no consumption attempted')
            time.sleep(30)
        complete(a.pair)
    except Exception as error:
        save(logdir / ('FAILURE_' + str(time.time_ns()) + '.json'), {'error': repr(error), 'traceback': traceback.format_exc(), 'automatic_retry': False})
        raise


if __name__ == '__main__':
    main()
