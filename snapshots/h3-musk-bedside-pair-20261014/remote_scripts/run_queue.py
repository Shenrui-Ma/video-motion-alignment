"""Sequential task queue with saved history, deadline and owned-service cleanup."""
import json
import subprocess
import time
from pathlib import Path

import job
import service


def write_state(**values):
    service.write_json(service.RUN / 'logs/controller_state.json', dict(observed_unix=time.time(), **values))


def sample_resources(name):
    result = subprocess.run(['nvidia-smi', '-i', service.GPU,
        '--query-gpu=memory.used,memory.free,utilization.gpu,temperature.gpu',
        '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=20)
    row = {'unix': time.time(), 'job': name, 'gpu_csv': result.stdout.strip()}
    with (service.RUN / 'logs/resources.jsonl').open('a') as f:
        f.write(json.dumps(row) + '\n')


def run():
    deadline = time.monotonic() + 3 * 3600
    completed = []
    current = None
    idle_since = None
    try:
        while time.monotonic() < deadline:
            plan = json.loads((service.RUN / 'configs/queue.json').read_text())
            if len(plan['jobs']) > 2 or len(set(plan['jobs'])) != len(plan['jobs']):
                raise RuntimeError('Queue has duplicates or exceeds two-formal-job cap')
            pending = [name for name in plan['jobs'] if name not in completed]
            if not pending:
                if plan.get('sealed'):
                    write_state(status='all_queued_jobs_complete', completed=completed)
                    return
                if idle_since is None:
                    idle_since = time.monotonic()
                if time.monotonic() - idle_since > 900:
                    write_state(status='complete_wait_window_expired', completed=completed)
                    return
                write_state(status='awaiting_review_or_additional_controls', completed=completed)
                time.sleep(20)
                continue
            idle_since = None
            current = pending[0]
            record_path = service.RUN / 'logs' / (current + '_job.json')
            if not record_path.exists():
                job.submit(current)
            started = time.monotonic()
            while time.monotonic() < deadline:
                result = job.status(current)
                status = result['status']
                if isinstance(status, dict):
                    status = status['status_str']
                sample_resources(current)
                write_state(status=status, current=current, completed=completed)
                if status == 'success':
                    completed.append(current)
                    current = None
                    break
                if status in ('error', 'unknown_missing', 'submission_uncertain'):
                    raise RuntimeError(f'{current}: {status}; inspect before retry')
                if time.monotonic() - started > 3600:
                    raise TimeoutError(f'{current}: exceeded 60-minute job budget')
                time.sleep(30)
            else:
                raise TimeoutError('Controller deadline reached during generation')
        raise TimeoutError('Controller 3-hour deadline reached')
    except BaseException as exc:
        write_state(status='failed', current=current, completed=completed, error=repr(exc))
        raise
    finally:
        service.stop()


if __name__ == '__main__':
    run()
