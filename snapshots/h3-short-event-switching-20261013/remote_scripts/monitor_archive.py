"""Keep local evidence current while the sequential remote queue runs."""
import json
import subprocess
import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
RENDER_PYTHON = '/Users/researcher/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
REMOTE_STATE = '/data5/researcher/h3_runs/short_event_switching_20261013/logs/controller_state.json'


def command(argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=900)
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])
    return result.stdout.strip()


def collect_and_render(full=False):
    command([sys.executable, str(LAB / 'scripts/collect_run.py')] + (['--full'] if full else []))
    validation = command([sys.executable, str(LAB / 'scripts/verify_archive.py')])
    command([RENDER_PYTHON, str(LAB / 'scripts/render_review.py')])
    print(json.dumps({'archived_unix': time.time(), 'full': full, 'validation': validation}), flush=True)


if __name__ == '__main__':
    last_completed = None
    terminal_seen = 0
    deadline = time.monotonic() + 9 * 3600
    while time.monotonic() < deadline:
        try:
            proc = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12',
                'researcher@192.0.2.1', 'cat ' + REMOTE_STATE],
                capture_output=True, text=True, timeout=40)
            if proc.returncode:
                raise RuntimeError(proc.stderr[-1000:])
            state = json.loads(proc.stdout)
            (LAB / 'logs/live_remote_state.json').write_text(json.dumps(state, indent=2))
            completed = tuple(state.get('completed', []))
            if completed != last_completed:
                collect_and_render(full=(len(completed) % 2 == 0))
                last_completed = completed
            terminal = state.get('status') in ('all_queued_jobs_complete', 'complete_wait_window_expired', 'failed')
            if terminal:
                terminal_seen += 1
                if terminal_seen >= 2:
                    collect_and_render(full=True)
                    break
            else:
                terminal_seen = 0
        except Exception as exc:
            print(json.dumps({'unix': time.time(), 'monitor_error': repr(exc)}), flush=True)
        time.sleep(30)
