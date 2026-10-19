"""Serial transfer CPU consumer, gated on the primary watcher completing."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/data5/researcher/h3_runs/timing_autoresearch_20261016')
    parser.add_argument('--primary-pid', type=int, default=52623)
    parser.add_argument('--timeout-minutes', type=int, default=240)
    args = parser.parse_args()
    root = Path(args.root)
    home = root/'analysis/pose'
    lock = (home/'transfer_cpu_consumer.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another transfer CPU consumer already owns the lock')
    plan = json.loads((home/'TRANSFER_CPU_PLAN.json').read_text())
    for path, digest in [(home/'watch_transfer.py', plan['transfer_watcher_sha256']),
                         (root/'scripts/timing_metrics.py', plan['frozen_metrics_sha256'])]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Frozen/prepared source hash differs: {path}')
    expected = {'s05_full_seed1_phase_zero_x0', 's05_full_seed1_hard_x0',
                's05_full_seed1_mass_late11_x0', 's05_full_seed1_phase_plus12_x0',
                's05_full_seed1_phase_minus12_x0'}
    state_path = home/'transfer_cpu_consumer_state.json'
    state = {'pid': os.getpid(), 'primary_pid': args.primary_pid, 'status': 'waiting_for_primary',
             'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'remote_transfer_root': plan['remote_root'], 'cases': {}, 'no_gpu': True}

    def save():
        state['updated_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        state_path.write_text(json.dumps(state, indent=2)+'\n')

    save()
    print(json.dumps(state), flush=True)
    deadline = time.monotonic()+args.timeout_minutes*60
    while True:
        proc_file = Path(f'/proc/{args.primary_pid}/cmdline')
        try:
            active = 'watch_pilot.py' in proc_file.read_bytes().decode(errors='replace')
        except FileNotFoundError:
            active = False
        try:
            completed = json.loads((home/'pilot/watcher_completed.json').read_text())
            formal_done = expected.issubset(completed.get('completed', []))
        except (OSError, json.JSONDecodeError):
            formal_done = False
        if not active and formal_done:
            break
        if time.monotonic() >= deadline:
            state.update(status='primary_gate_timeout', primary_process_active=active, primary_formal_complete=formal_done)
            save()
            raise RuntimeError('Primary completion gate not satisfied; no transfer pose started')
        time.sleep(60)
    environment = os.environ.copy()
    environment.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    state['status'] = 'consuming_serially'
    save()
    for label, case in plan['cases'].items():
        state['active_case'] = label
        save()
        log_path = home/f'transfer_case{label}.consumer.log'
        with log_path.open('w') as log:
            outcome = subprocess.run(case['command_argv'], env=environment, stdout=log, stderr=subprocess.STDOUT)
        state['cases'][label] = {'returncode': outcome.returncode, 'log': str(log_path), 'requested': case['runs']}
        # A successful watcher process can still report per-video failures, which
        # remain in its formal inventory. Do not turn those into success claims.
        remote_state = Path(plan['remote_root'])/'analysis/pose/pilot/watcher_completed.json'
        if remote_state.is_file():
            state['cases'][label]['watcher_inventory'] = json.loads(remote_state.read_text())
        save()
        print(json.dumps({'case': label, **state['cases'][label]}), flush=True)
        if outcome.returncode:
            state['status'] = 'consumer_failed'
            save()
            raise RuntimeError(f'Transfer case{label} consumer failed; logs retained')
    state.pop('active_case', None)
    state['status'] = 'consumers_finished_check_per_video_inventory'
    save()
    print(json.dumps(state), flush=True)


if __name__ == '__main__':
    main()
