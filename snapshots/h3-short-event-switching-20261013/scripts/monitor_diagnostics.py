"""Archive each completed encoding diagnostic while the GPU queue runs."""
from pathlib import Path
import json
import subprocess
import sys
import time

LAB = Path(__file__).resolve().parents[1]
REMOTE_STATE = '/data5/researcher/h3_runs/short_event_switching_20261013/logs/diagnostic_state.json'

if __name__ == '__main__':
    completed_before = None
    deadline = time.monotonic() + 90 * 60
    while time.monotonic() < deadline:
        try:
            result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12',
                'researcher@192.0.2.1', 'cat ' + REMOTE_STATE], capture_output=True, text=True, timeout=40)
            result.check_returncode()
            state = json.loads(result.stdout)
            (LAB/'logs/live_diagnostic_state.json').write_text(json.dumps(state, indent=2)+'\n')
            complete = tuple(state.get('completed', []))
            terminal = state.get('status','').startswith('diagnostics_complete') or state.get('status') == 'failed'
            if complete != completed_before or terminal:
                args = [sys.executable, str(LAB/'scripts/collect_run.py')]
                if complete or terminal:
                    args.append('--full')
                proc = subprocess.run(args, capture_output=True, text=True, timeout=900)
                proc.check_returncode()
                print(json.dumps({'archived_unix':time.time(),'completed':complete,'status':state.get('status'),'collection':proc.stdout.strip()}), flush=True)
                completed_before = complete
            if terminal:
                break
        except Exception as error:
            print(json.dumps({'error':repr(error),'unix':time.time()}), flush=True)
        time.sleep(30)
