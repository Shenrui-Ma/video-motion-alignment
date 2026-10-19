"""Sequential CPU-only consumers for the remaining fixed four completed cases.

No inference launches, process stops, or GPU tracker calls. Technical errors are
retained and abort this watcher; genuine pending/priority/lock states wait25sec.
"""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
POST = HERE.parent
SIDE = Path('/Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/analysis/flexiact_generated_pose158_r50_retry_20261017')
ADMIN = SIDE / 'admin/priority_v2'
REMOTE = '/data5/researcher/h3_runs/timing_flexiact_auto_r50_retry_20261017'
RPOST = REMOTE + '/analysis/postrun'
PYTHON = '/home/researcher/miniconda3/envs/comfyui/bin/python'
SSH = ['ssh', '-J', 'H3_SERVER_B', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-o', 'ServerAliveInterval=20', '-o', 'ServerAliveCountMax=3']
ORDER = ['crouch', 'fitness', 'one_leg', 'rotate']
AUDIT = HERE / 'followup_cpu'; AUDIT.mkdir(exist_ok=True)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n'); temp.replace(path)


def invoke(command, timeout=960):
    stamp = str(time.time_ns())
    write(AUDIT / (stamp + '.command.json'), {'command': command})
    r = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
    (AUDIT / (stamp + '.log')).write_text(r.stdout + '\nSTDERR\n' + r.stderr)
    if r.returncode not in (0, 75):
        raise RuntimeError('Technical failure retained: ' + stamp + ', returncode=' + str(r.returncode))
    return r


def remote_command(args):
    return SSH + ['H3_SERVER_A', shlex.join(['env', 'CUDA_VISIBLE_DEVICES=', 'PYTHONDONTWRITEBYTECODE=1',
        'TMPDIR=' + REMOTE + '/temp', 'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'MKL_NUM_THREADS=1', PYTHON, *args])]


def last_json(stdout):
    lines = stdout.splitlines()
    for line in reversed(lines):
        try: return json.loads(line)
        except ValueError: pass
    return None


def retry_busy(command):
    while True:
        r = invoke(command)
        data = last_json(r.stdout)
        busy = r.returncode == 75 or (data and data.get('status') == 'busy') or 'BUSY_SERVER_OR_ONLINE' in r.stdout or 'BUSY_MAC' in r.stdout
        if not busy: return r, data
        time.sleep(25)


def download_proofs(source):
    dest = HERE / 'media_identity' / source; dest.mkdir(parents=True, exist_ok=True)
    invoke(['rsync', '-a', '--include=*.json', '--exclude=*', '-e', shlex.join(SSH),
            'H3_SERVER_A:' + RPOST + '/audit/media_identity/' + source + '/', str(dest) + '/'])
    return dest


def wait_completed(run):
    script = 'import json;from pathlib import Path;print((Path(' + repr(REMOTE) + ')/"logs/controller_state.json").read_text())'
    previous = None
    while True:
        r = invoke(remote_command(['-c', script]), 45)
        state = json.loads(r.stdout)
        if state.get('status') == 'failed': raise RuntimeError('Producer reported failure; CPU watcher stops for review')
        if run in state.get('completed', []): return state
        compact = {k: state.get(k) for k in ('status', 'current', 'completed')}
        if compact != previous:
            write(AUDIT / 'WAITING.json', compact); print(json.dumps({'waiting_for': run, **compact}), flush=True); previous = compact
        time.sleep(25)


def consume(source):
    run = 'r50_source_' + source + '_seed2026101701_auto'
    wait_completed(run)
    print(json.dumps({'source': source, 'stage': 'producer_completed'}), flush=True)
    while True:
        _, data = retry_busy([sys.executable, str(HERE / 'input_archive_v3/local_entry.py'), '--run', run])
        if data and data.get('status') == 'case_ready': break
        if data and data.get('status') in ('not_ready', 'waiting', 'stabilizing', 'pending', 'changed', 'wait_stable', 'waiting_stability'):
            time.sleep(25); continue
        # Readiness has explicit phase_started=false statuses; retain actual snapshot.
        if data and data.get('phase_started') is False:
            time.sleep(25); continue
        raise RuntimeError('Unexpected completed-case consumption state: ' + repr(data))
    retry_busy(remote_command([RPOST + '/audit/input_archive_v3/remote_entry.py', '--entry', 'identity', '--source', source]))
    folder = download_proofs(source)
    identity = json.loads((folder / 'SUMMARY.json').read_text())
    exact = all(v['exact'] for v in identity['proofs'].values())
    if exact and not (folder / 'REUSED_MF_SCORE.json').exists():
        retry_busy(remote_command([RPOST + '/audit/reuse_flex_remaining_scores.py', '--source', source])); download_proofs(source)
    metric = RPOST + '/completed_cases/' + run + '/final/' + run + '/METRIC_INPUTS.json'
    mapping = RPOST + '/completed_cases/' + run + '/final/' + run + '/edited49_8fps.mapping.json'
    if not (SIDE / 'records' / ('automatic_' + source) / 'COMPLETE.json').exists():
        _, pose = retry_busy([sys.executable, str(ADMIN / 'local_entry.py'), '--source', source, '--method', 'automatic', '--metric-inputs', metric, '--mapping', mapping])
        if not pose or pose.get('status') != 'complete': raise RuntimeError('Unexpected actual pose state: ' + repr(pose))
    result = ADMIN / 'results' / (source + '.json')
    if not result.exists(): retry_busy([sys.executable, str(ADMIN / 'physical_local.py'), '--source', source])
    if not result.exists(): raise RuntimeError('Physical pair result unavailable after successful execution')
    timing = json.loads(result.read_text())
    r = invoke(remote_command([RPOST + '/audit/collect_efficiency.py', REMOTE, run]))
    efficiency = json.loads(r.stdout); write(HERE / ('EFFICIENCY_' + source + '.json'), efficiency)
    record = {'source': source, 'run_id': run, 'status': 'cpu_complete', 'identity_exact': exact,
              'official_mf_status': 'reused_identical_input' if exact else 'requires_gpu_tracking_after_root_release',
              'identity_summary': {'file': str(folder / 'SUMMARY.json'), 'sha256': sha(folder / 'SUMMARY.json')},
              'physical_result': {'file': str(result), 'sha256': sha(result)},
              'physical_lags': timing['result']['paired_lag_summary'],
              'efficiency': {'file': str(HERE / ('EFFICIENCY_' + source + '.json')), 'sha256': sha(HERE / ('EFFICIENCY_' + source + '.json'))},
              'no_gpu_launches': True}
    write(AUDIT / (source + '_COMPLETE.json'), record)
    print(json.dumps({'source': source, 'stage': 'cpu_complete', 'identity_exact': exact, 'official_mf_status': record['official_mf_status'], 'physical_result': record['physical_result']}), flush=True)


def main():
    for source in ORDER:
        if not (AUDIT / (source + '_COMPLETE.json')).exists(): consume(source)
    write(AUDIT / 'COMPLETE.json', {'status': 'remaining_four_cpu_complete', 'sources': ORDER, 'no_gpu_launches': True})
    print('ALL_FOUR_CPU_COMPLETE', flush=True)

if __name__ == '__main__':
    try: main()
    except Exception as e:
        import traceback
        write(AUDIT / 'FAILURE.json', {'error': repr(e), 'traceback': traceback.format_exc(), 'time': time.time(), 'retry': 'requires_review'})
        raise
