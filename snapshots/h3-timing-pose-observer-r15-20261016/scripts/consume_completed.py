"""Local unique coordinator: wait without CPU lock, then one frozen CPU pass."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
REMOTE='/data5/researcher/h3_runs/timing_pose_observer_r15_20261016'
PY='/home/researcher/miniconda3/envs/comfyui/bin/python'
OPTIONS=['-o','ConnectTimeout=10','-o','BatchMode=yes','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3']
HOST='H3_SERVER_A'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def remote_read(relative):
    result=subprocess.run(['ssh',*OPTIONS,HOST,'cat',REMOTE+'/'+relative],text=True,capture_output=True)
    if result.returncode:return None,result.stderr
    return json.loads(result.stdout),None
def copy(relative,destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['scp',*OPTIONS,'-q',HOST+':'+REMOTE+'/'+relative,str(destination)],check=True)
def main():
    analysis=ROOT/'analysis';analysis.mkdir(exist_ok=True)
    with (analysis/'consumer_coordinator.lock').open('a') as own:
        fcntl.flock(own,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state={'pid':os.getpid(),'started_unix':time.time(),'status':'waiting_for_seven_decodes','cpu_lock_held':False,'connection':'direct H3_SERVER_A','poll_seconds':61,'errors':[]}
        save(analysis/'consumer_state.json',state)
        for _ in range(90):
            execution,error=remote_read('analysis/x0_decoded/execution.json')
            if error:
                state['errors'].append({'time':time.time(),'phase':'wait','error':error[-1000:]});save(analysis/'consumer_state.json',state)
            elif execution['status']=='failed':raise RuntimeError('Producer failed; preserve evidence, no pose inference')
            elif execution['status']=='complete':break
            time.sleep(61)
        else:raise TimeoutError('Bounded producer wait exhausted; no analysis started')
        rows=execution['rows']
        if len(rows)!=7 or len({r['stem'] for r in rows})!=7:raise ValueError('Seven unique decodes required')
        if any(r['exit_code']!=0 or not r['pid_absent'] or r['gpu_after']['compute'] for r in rows) or execution['after']['compute']:
            raise ValueError('Sequential decoder cleanup gate failed')
        save(analysis/'x0_decoded_execution.json',execution)
        state.update(status='producer_complete_downloading',cpu_lock_held=False);save(analysis/'consumer_state.json',state)
        for row in rows:
            stem=row['stem']
            for suffix in ('.json','.mp4','.log'):
                copy('analysis/x0_decoded/'+stem+suffix,analysis/'x0_decoded'/(stem+suffix))
            d=json.loads((analysis/'x0_decoded'/(stem+'.json')).read_text())
            if d['status']!='complete' or sha(analysis/'x0_decoded'/(stem+'.mp4'))!=d['output_sha256']:
                raise ValueError('Downloaded decoded artifact does not bind record')
        lock_path=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
        with lock_path.open('a') as heavy:
            # This lock is acquired only when real CPU evaluation is ready.
            fcntl.flock(heavy,fcntl.LOCK_EX)
            state.update(status='cpu_evaluation',cpu_lock_held=True);save(analysis/'consumer_state.json',state)
            command=['ssh',*OPTIONS,HOST,PY,'-u',REMOTE+'/scripts/evaluate_decoded.py','--execute']
            with (analysis/'cpu_evaluation.log').open('x') as log:
                process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
                state['cpu_ssh_pid']=process.pid;save(analysis/'consumer_state.json',state)
                rc=process.wait()
            state.update(cpu_exit_code=rc,cpu_lock_held=False);save(analysis/'consumer_state.json',state)
            if rc:raise RuntimeError('CPU SSH/evaluation failed; inspect remote processes before any manual retry')
        subprocess.run(['scp',*OPTIONS,'-qr',HOST+':'+REMOTE+'/analysis/pose',str(analysis)],check=True)
        completion=json.loads((analysis/'pose/completion.json').read_text())
        if completion['status']!='complete' or not completion['cpu_only']:raise ValueError('CPU completion gate differs')
        files=[]
        for path in sorted(analysis.rglob('*')):
            if path.is_file() and path.suffix not in ('.lock',) and path.name not in ('FINAL_ARCHIVE_MANIFEST.json','consumer_state.json'):
                files.append({'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':sha(path)})
        save(analysis/'FINAL_ARCHIVE_MANIFEST.json',{'status':'complete','files':files,'count':len(files),'created_unix':time.time()})
        state.update(status='complete',finished_unix=time.time(),cpu_lock_held=False);save(analysis/'consumer_state.json',state)
        print(json.dumps({'status':'complete','archive_files':len(files),'summary':str(analysis/'pose/compact_summary.json')}),flush=True)
if __name__=='__main__':main()
