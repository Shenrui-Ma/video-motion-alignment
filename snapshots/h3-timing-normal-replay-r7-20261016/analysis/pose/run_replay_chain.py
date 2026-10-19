"""One authorized intake, followed by local CPU-only final replay validation."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

import consumer_r7 as intake

HERE = Path(__file__).resolve().parent
OLD = Path('/Users/researcher/DevProjects/h3-timing-autoresearch-20261016')
SHARED = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
RUN = 'r7_s05_normal_native_x0'


def main():
    with (HERE/'serial_chain.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        intake.save(HERE/'serial_chain_state.json', {'status':'waiting_for_formal_history', 'run_id':RUN, 'started_unix':time.time()})
        subprocess.run([sys.executable, str(HERE/'consumer_r7.py'), '--run-id', RUN, '--intake-only', '--wait'], check=True)
        manifest = HERE/'pilot'/(RUN+'_provenance')/'intake_manifest.json'
        if not manifest.is_file():
            raise ValueError('Intake ended without an admitted formal history/output')
        with SHARED.open('a') as heavy_lock:
            fcntl.flock(heavy_lock, fcntl.LOCK_EX)
            subprocess.run([sys.executable, str(HERE/'check_native_replay_local.py')], check=True)
        gate_path = HERE/'replication/native_replay_local_gate.json'
        gate = json.loads(gate_path.read_text())
        inherited = {'exact_final_replay':gate['passed'], 'early_x0_pose_status':'not_yet_independently_evaluated',
                     'scope':'Selected known-normal control. No old x0 exists. Final replay does not label early x0 as normal.',
                     'gate_sha256':intake.digest(gate_path)}
        if gate['passed']:
            paths = [OLD/'analysis/pose/pilot'/('s05_seed1_native_00001_.'+suffix) for suffix in
                     ('pose.json','threshold0.3.timing.json','threshold0.5.timing.json')]
            inherited['inherited_final_pose_files'] = [{'path':str(p), 'sha256':intake.digest(p)} for p in paths]
        else:
            inherited['inherited_final_pose_files'] = []
            inherited['restriction'] = 'Do not reuse old final pose as exact; retain mismatch and request fresh final evaluation.'
        intake.save(HERE/'replication/inherited_final_pose_reference.json', inherited)
        result = {'status':'complete', 'run_id':RUN, 'exact_final_replay':gate['passed'],
                  'completed_unix':time.time(), 'new_pose_or_gpu_started':False,
                  'early_x0_independent_pose_still_required':True, 'gate_sha256':intake.digest(gate_path)}
        intake.save(HERE/'serial_chain_state.json', result)
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        intake.save(HERE/'serial_chain_failure.json', {'error':repr(exc), 'retained':True, 'unix':time.time()})
        raise
