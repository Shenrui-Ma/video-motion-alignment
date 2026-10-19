"""Bounded semantic-clock CPU consumer after the existing phase-late consumer."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
HOME = ROOT/'analysis/pose'
SEMANTIC = Path(str(ROOT)+'_semantic0')
RUNS = ['s05_semantic_b_p6_t6', 's05_semantic_c_p0_t6', 's05_semantic_d_p6_t0']
METRICS_SHA = 'eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e'
WATCHER_SHA = '8f6395dc87ec5797173f7dfbf73227746aac42ffe4678fb234318f6fa5cb56f4'


def main():
    lock = (HOME/'semantic_cpu_consumer.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for path, expected in [(ROOT/'scripts/timing_metrics.py', METRICS_SHA), (HOME/'watch_semantic.py', WATCHER_SHA)]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Frozen code changed: {path}')
    state = {'pid': os.getpid(), 'status': 'waiting_for_phase_late', 'runs': RUNS, 'no_gpu': True,
             'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    def save():
        state['updated_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        (HOME/'semantic_cpu_consumer_state.json').write_text(json.dumps(state, indent=2)+'\n')
    save()
    deadline = time.monotonic()+300*60
    while True:
        try:
            transfer = json.loads((HOME/'phase_late_cpu_consumer_state.json').read_text())
            pid = transfer['pid']
            try:
                active = 'consume_phase_late_after_offsets.py' in Path(f'/proc/{pid}/cmdline').read_bytes().decode(errors='replace')
            except FileNotFoundError:
                active = False
            done = transfer['status'] == 'finished_check_per_video_inventory'
            expected = {'s05_full_seed1_phase_minus12_late11_x0'}
            done = done and expected <= set(transfer.get('watcher_inventory', {}).get('completed', []))
            if done and not active:
                state['phase_late_completion'] = transfer
                break
        except (OSError, KeyError, json.JSONDecodeError):
            pass
        if time.monotonic() >= deadline:
            state['status'] = 'phase_late_gate_timeout'
            save()
            raise RuntimeError('Phase-late completion gate not satisfied; no pose started')
        time.sleep(60)
    env = os.environ.copy()
    env.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    command = [sys.executable, str(HOME/'watch_semantic.py'), '--root', str(SEMANTIC), '--tool-root', str(ROOT),
               '--source', str(HOME/'old_sam/05_real_megumi_v.pose.json'), '--history-only', '--timeout-minutes', '240']
    for run in RUNS:
        command += ['--run-id', run]
    for window in ['50:65', '69:81', '80:92', '99:111']:
        command += ['--window', window]
    state.update(status='consuming_serially', command=command)
    save()
    with (HOME/'semantic_followups.consumer.log').open('w') as log:
        outcome = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    state.update(status='finished_check_per_video_inventory' if outcome.returncode == 0 else 'consumer_failed',
                 returncode=outcome.returncode)
    inventory = SEMANTIC/'analysis/pose/pilot/watcher_completed.json'
    if inventory.is_file():
        state['watcher_inventory'] = json.loads(inventory.read_text())
    save()
    print(json.dumps(state), flush=True)
    if outcome.returncode:
        raise RuntimeError('CPU consumer failed; logs and failures retained')


if __name__ == '__main__':
    main()
