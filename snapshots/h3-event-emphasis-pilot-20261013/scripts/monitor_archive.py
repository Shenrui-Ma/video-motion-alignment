"""Bounded active-run collection; accepts explicit pending verification states."""
import json
import subprocess
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PYTHON='/Users/researcher/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
REMOTE_STATE='/data5/researcher/h3_runs/event_emphasis_pilot_20261013/logs/controller_state.json'


def execute(script,args=(),allowed=(0,)):
    p=subprocess.run([PYTHON,'-B',str(ROOT/'scripts'/script),*args],capture_output=True,text=True,timeout=900)
    if p.returncode not in allowed:raise RuntimeError({'script':script,'rc':p.returncode,'stdout':p.stdout[-3000:],'stderr':p.stderr[-2000:]})
    return {'script':script,'rc':p.returncode,'stdout':p.stdout[-3000:]}


def collect(full):
    out=[execute('collect_run.py',['--full'] if full else [])]
    out.append(execute('verify_pair.py',allowed=(0,2)))
    out.append(execute('render_comparison.py',allowed=(0,2)))
    print(json.dumps({'unix':time.time(),'full':full,'operations':out}),flush=True)


def main():
    deadline=time.monotonic()+3*3600
    previous=None;terminal=0
    while time.monotonic()<deadline:
        try:
            p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','researcher@192.0.2.1',
                'cat '+REMOTE_STATE],capture_output=True,text=True,timeout=35)
            if p.returncode:raise RuntimeError(p.stderr[-1000:])
            state=json.loads(p.stdout);(ROOT/'logs/live_remote_state.json').write_text(json.dumps(state,indent=2))
            count=tuple(state.get('completed',[]))
            if count!=previous:
                collect(full=bool(count));previous=count
            if state.get('status') in ('all_queued_jobs_complete','failed','complete_wait_window_expired'):
                terminal+=1
                if terminal>=2:
                    collect(full=True);break
            else:terminal=0
        except Exception as exc:print(json.dumps({'unix':time.time(),'monitor_error':repr(exc)}),flush=True)
        time.sleep(30)


if __name__=='__main__':main()
