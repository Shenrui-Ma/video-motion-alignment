"""Bounded CPU-only watcher. Submit/approval/service mutations are absent."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from r84_contract import SOURCES,read,sha
REMOTE=read(ROOT/'configs/runtime.json')['remote_root']
PY='/data3/researcher/ComfyUI/.venv/bin/python'
DEPS='/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/runtime_deps'
HOST='H3_SERVER_B'
DEADLINE=time.time()+4*3600


def save(data):
    data.update(observed_unix=time.time(),pid=os.getpid(),watcher_version=2)
    tmp=HERE/'WATCH_STATE.json.tmp';tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(HERE/'WATCH_STATE.json')


def remote(code, timeout=120):
    return subprocess.check_output(['ssh','-o','ConnectTimeout=15','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3',HOST,'python3 -c '+shlex.quote(code)],stderr=subprocess.STDOUT,timeout=timeout).decode()


def transient_status_error(error):
    if isinstance(error,subprocess.TimeoutExpired):return True
    if not isinstance(error,subprocess.CalledProcessError):return False
    raw=error.output or b''
    message=raw.decode(errors='replace') if isinstance(raw,bytes) else str(raw)
    return any(term in message for term in ('TimeoutError: timed out', 'Connection timed out',
        'Connection reset by peer', 'Connection closed by', 'Connection to UNKNOWN port',
        'Operation timed out', 'No route to host'))


def completed(source):
    run='r84_'+source+'_seed2026101701_forced'
    code = """from pathlib import Path
import json,subprocess,os
r=Path(REMOTE_PATH);run=RUN_NAME
j=r/'logs'/(run+'_job.json');h=r/'logs'/(run+'_history.json');m=r/'audit/x0'/run/'manifest.json'
if not j.exists():
 print(json.dumps({'status':'waiting_for_root_submit'}))
else:
 job=json.loads(j.read_text())
 if job.get('status') in ('error','failed'):
  print(json.dumps({'status':job['status'],'actual_job':job}))
 elif h.exists():
  hist=json.loads(h.read_text())
  if job.get('status')=='success':print(json.dumps({'status':hist['status']}))
  else:subprocess.run([CPU_PY,'scripts/job.py','status',run],cwd=r,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),check=True)
 elif not m.exists() or json.loads(m.read_text()).get('callback_count',0)<20:
  print(json.dumps({'status':'waiting_saved_sampling_progress'}))
 else:
  subprocess.run([CPU_PY,'scripts/job.py','status',run],cwd=r,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),check=True)
""".replace('REMOTE_PATH',repr(REMOTE)).replace('RUN_NAME',repr(run)).replace('CPU_PY',repr(PY))
    output=remote(code)
    value=json.loads(output.strip().splitlines()[-1]);status=value.get('status')
    if isinstance(status,dict):
        if status.get('status_str')=='error':raise RuntimeError('actual inference error: '+json.dumps(value))
        return status.get('completed') is True and status.get('status_str')=='success'
    if status in ('error','failed','unknown_missing'):raise RuntimeError('actual job state: '+json.dumps(value))
    return False


def consume(source):
    code="from pathlib import Path;import json,subprocess,os;r=Path("+repr(REMOTE)+");p=r/'analysis/postrun'/"+repr(source)+"/'PAIR_RUNTIME_GATE.json';env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH="+repr(DEPS)+");subprocess.run(["+repr(PY)+",'analysis/postrun/verify_pair.py','--source',"+repr(source)+"],cwd=r,env=env,check=True) if not p.exists() else None;g=json.loads(p.read_text());assert g['passed'] is True;print(json.dumps({'source':g['source_id'],'passed':g['passed'],'gate_sha':__import__('hashlib').sha256(p.read_bytes()).hexdigest()}))"
    out=remote(code,900);(HERE/(source+'_REMOTE_GATE.log')).write_text(out)
    for action in ('collect','render','publish'):
        cmd=[sys.executable,str(HERE/'consume.py'),action]
        if action!='publish':cmd+=['--source',source]
        result=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1200)
        (HERE/(source+'_'+action+'.log')).write_text(result.stdout)
        if result.returncode:raise RuntimeError(action+' failed; see consumer log')


def main():
    complete=[]
    for source in SOURCES:
        presentation=ROOT/'showcase'/source/'PRESENTATION.json'
        if presentation.exists():
            complete.append(source);continue
        transient=0
        while time.time()<DEADLINE:
            save(dict(state='waiting_actual_job',source=source,complete=complete))
            try:ready=completed(source);transient=0
            except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as e:
                if not transient_status_error(e):raise
                transient+=1
                raw=e.output or b''
                (HERE/(source+'_V2_TRANSPORT_ERROR_'+str(time.time_ns())+'.log')).write_bytes(raw if isinstance(raw,bytes) else raw.encode())
                save(dict(state='waiting_transport_or_HTTP',source=source,complete=complete,consecutive_transient_failures=transient,error=repr(e)))
                time.sleep(45);continue
            if ready:
                save(dict(state='cpu_verifying_and_consuming',source=source,complete=complete))
                consume(source);complete.append(source)
                save(dict(state='pair_ready',source=source,complete=complete))
                print(json.dumps({'source':source,'presentation_ready':True}),flush=True)
                break
            time.sleep(45)
        else:raise TimeoutError('bounded four-hour CPU watcher expired')
    save(dict(state='complete',complete=complete))


if __name__=='__main__':
    try:main()
    except BaseException as e:
        save(dict(state='failed',error=repr(e),traceback=traceback.format_exc()))
        raise
