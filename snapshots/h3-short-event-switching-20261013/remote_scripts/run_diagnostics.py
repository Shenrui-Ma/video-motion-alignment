"""Run the three frozen encoding/speed diagnostics, then await formal handoff."""
import json
import time
import job
import service
from run_queue import sample_resources

JOBS = [
    '06_anime_eye_insert_a_s1_benchmark2_chunked',
    '05_real_megumi_v_a_s1_benchmark2',
    '07_real_ary_v_a_s1_benchmark2',
]


def state(**fields):
    service.write_json(service.RUN / 'logs/diagnostic_state.json',
                       dict(observed_unix=time.time(), **fields))


def run():
    completed = []
    current = None
    deadline = time.monotonic() + 45 * 60
    try:
        for current in JOBS:
            if not (service.RUN / 'logs' / (current + '_job.json')).exists():
                job.submit(current)
            while time.monotonic() < deadline:
                result = job.status(current)
                status = result['status']
                if isinstance(status, dict):
                    status = status['status_str']
                sample_resources(current)
                state(status=status, current=current, completed=completed)
                if status == 'success':
                    completed.append(current)
                    break
                if status in ('error', 'unknown_missing', 'submission_uncertain'):
                    raise RuntimeError(f'{current}: {status}; no automatic retry')
                time.sleep(30)
            else:
                raise TimeoutError('Diagnostics exceeded 45-minute deadline')
        state(status='diagnostics_complete_waiting_formal_gate', completed=completed)
        # Do not leave a GPU service idle indefinitely if the caller disconnects.
        grace = time.monotonic() + 30 * 60
        while time.monotonic() < grace:
            registry = service.RUN / 'processes/controller.json'
            if registry.exists():
                record = json.loads(registry.read_text())
                if service.current_identity(record['pid']) == record['identity']:
                    state(status='diagnostics_complete_handed_to_formal', completed=completed)
                    return
            time.sleep(20)
        state(status='diagnostics_complete_idle_lease_expired', completed=completed)
        service.stop()
    except BaseException as exc:
        state(status='failed', current=current, completed=completed, error=repr(exc))
        service.stop()
        raise


if __name__ == '__main__':
    run()
