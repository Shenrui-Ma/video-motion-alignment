"""Bounded CPU-only orchestration of an already authorized actual R65 pair.

No producer edits, tracker invocation, service control, or GPU scheduling.
All processing delegates to the frozen, existing consumer scripts.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent / "one_leg"
AUDIT.mkdir(exist_ok=True)
SOURCE = 'one_leg'
HOST41 = 'H3_SERVER_B'
HOST9 = 'H3_SERVER_A'
PRODUCER = '/data3/researcher/h3_runs/timing_flexiact_forced_r65_20261018'
REMOTE41 = '/data3/researcher/h3_runs/flexiact_forced_metrics_r65_20261018'
REMOTE9 = '/data5/researcher/h3_runs/flexiact_forced_metrics_r65_20261018'
PY41 = '/data3/researcher/ComfyUI/.venv/bin/python'
PY9 = '/home/researcher/miniconda3/envs/comfyui/bin/python'
PYLOCAL = '/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'
ENV = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1')

def event(name, **fields):
    row = dict(event=name, unix=time.time(), **fields)
    with (AUDIT/'events.jsonl').open('a') as f:
        f.write(json.dumps(row, ensure_ascii=False)+'\n')
    print(json.dumps(row, ensure_ascii=False), flush=True)

def run(command, timeout=600, lock_retry=False, label='command'):
    deadline = time.monotonic()+1800
    while True:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=timeout, env=ENV)
        with (AUDIT/(label+'.log')).open('a') as f:
            f.write(result.stdout+result.stderr)
        if result.returncode == 0:
            return result.stdout
        lock_busy = 'BlockingIOError: [Errno 11]' in result.stderr or result.returncode == 75
        if lock_retry and lock_busy and time.monotonic() < deadline:
            time.sleep(20)
            continue
        raise RuntimeError(f'{label} exited {result.returncode}; see {label}.log')

def remote(host, code, **kwargs):
    return run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',host,
                'python3 -c '+shlex.quote(code)], **kwargs)

def remote_script(host, root, python, script, args=(), lock=False, label='script'):
    code = ('import os,subprocess,sys; os.chdir('+repr(root)+'); '
            'sys.exit(subprocess.call('+repr([python,script,*args])+
            ',env=dict(os.environ,CUDA_VISIBLE_DEVICES="",PYTHONDONTWRITEBYTECODE="1")))')
    return remote(host,code,timeout=900,lock_retry=lock,label=label)

def transfer_out(host, remote_root, relative_paths, label):
    remote_archive=remote_root+'/audit/consumer_execution_20261018/'+SOURCE+'_'+label+'.tar'
    code='''import tarfile,hashlib,json
from pathlib import Path
root=Path(ROOT)
out=Path(ARCHIVE)
out.parent.mkdir(parents=True,exist_ok=True)
with tarfile.open(out,'x') as t:
 for name in NAMES:t.add(root/name,arcname=name,recursive=True)
print(json.dumps({'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'bytes':out.stat().st_size}))
'''.replace('ROOT',repr(remote_root)).replace('ARCHIVE',repr(remote_archive)).replace('NAMES',repr(relative_paths))
    proof=json.loads(remote(host,code,label=label+'_pack'))
    local=AUDIT/(label+'.tar')
    run(['scp','-o','BatchMode=yes',host+':'+remote_archive,str(local)],label=label+'_scp')
    if hashlib.sha256(local.read_bytes()).hexdigest()!=proof['sha256']:
        raise ValueError('transferred archive SHA differs')
    with tarfile.open(local) as t:
        for m in t.getmembers():
            p=Path(m.name)
            if p.is_absolute() or '..' in p.parts or not(m.isfile() or m.isdir()):
                raise ValueError('unsafe archive member')
            if not any(p==Path(n) or Path(n) in p.parents for n in relative_paths):
                raise ValueError('unexpected archive member')
        for n in relative_paths:
            if (ROOT/n).exists():raise ValueError('preserve existing artifact: '+n)
        t.extractall(ROOT,filter='data')
    event(label, **proof)
    return local

def main():
    event('waiting_for_actual_one_leg_pair')
    deadline=time.monotonic()+4*3600
    previous=None
    while time.monotonic()<deadline:
        code='''import json
from pathlib import Path
r=Path(ROOT)
out={}
for m in ('native','forced'):
 p=r/'logs'/('r65_one_leg_seed2026101701_'+m+'_job.json')
 out[m]=json.loads(p.read_text()).get('status') if p.exists() else 'PENDING'
print(json.dumps(out))
'''.replace('ROOT',repr(PRODUCER))
        states=json.loads(remote(HOST41,code,label='status'))
        if states!=previous:event('actual_job_status',states=states);previous=states
        if any(s in ('error','failed','submission_uncertain','unknown_missing') for s in states.values()):
            raise RuntimeError('producer failed; preserve actual evidence')
        if all(s=='success' for s in states.values()):break
        time.sleep(30)
    else:raise TimeoutError('four-hour actual-pair wait expired')
    lock='/data3/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock'
    code=f'''import fcntl,os,subprocess,sys
f=open({lock!r},'a')
try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:sys.exit(75)
os.chdir({PRODUCER!r})
sys.exit(subprocess.call({[PY41,'analysis/postrun/verify_pair.py','--source',SOURCE]!r},env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')))
'''
    remote(HOST41,code,timeout=900,lock_retry=True,label='pair_runtime_gate')
    event('actual_pair_runtime_gate_passed')
    remote_script(HOST41,REMOTE41,PY41,'scripts/collect_pair.py',('--producer-root',PRODUCER,'--source',SOURCE),label='collect_pair')
    remote_script(HOST41,REMOTE41,PY41,'scripts/prepare_pair.py',('--source',SOURCE),lock=True,label='prepare_pair')
    event('metric_inputs_ready_on_host41')
    archive=transfer_out(HOST41,REMOTE41,['incoming/one_leg','prepared/one_leg'],'actual_pair')
    remote9archive=REMOTE9+'/audit/consumer_execution_20261018_one_leg_actual_pair.tar'
    run(['scp','-o','BatchMode=yes',str(archive),HOST9+':'+remote9archive],label='send_cpu_pair')
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    code=f'''import tarfile,hashlib
from pathlib import Path
r=Path({REMOTE9!r}); p=Path({remote9archive!r})
assert hashlib.sha256(p.read_bytes()).hexdigest()=={digest!r}
assert not (r/'incoming/one_leg').exists()
with tarfile.open(p) as t:
 members=[m for m in t.getmembers() if m.name=='incoming/one_leg' or m.name.startswith('incoming/one_leg/')]
 assert all(not Path(m.name).is_absolute() and '..' not in Path(m.name).parts and (m.isfile() or m.isdir()) for m in members)
 t.extractall(r,members=members)
print('actual incoming SHA verified and installed')
'''
    remote(HOST9,code,label='install_cpu_pair')
    for method in ('native','forced'):
        remote_script(HOST9,REMOTE9,PY9,'scripts/run_pose.py',('--source',SOURCE,'--method',method),lock=True,label='pose_'+method)
        event('pose_complete',method=method)
    remote_script(HOST9,REMOTE9,PY9,'scripts/evaluate_physical.py',('--source',SOURCE),lock=True,label='physical')
    transfer_out(HOST9,REMOTE9,['poses/one_leg','scores/physical/one_leg.json'],'physical_results')
    run([PYLOCAL,str(ROOT/'audit/consumer_execution_20261018/render_caption_overlay.py'),'--source',SOURCE],timeout=600,lock_retry=True,label='render_triptychs')
    event('cpu_and_media_complete',physical=str(ROOT/'scores/physical/one_leg.json'),showcase=str(ROOT/'showcase'))

if __name__=='__main__':
    try:main()
    except BaseException as exc:
        event('FAILED',error=repr(exc))
        raise
