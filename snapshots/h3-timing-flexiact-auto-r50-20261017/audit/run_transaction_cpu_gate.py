"""One bounded synthetic-model transaction using actual CPU Comfy Euler/wrappers."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
attempt = int(sys.argv[1])
case = sys.argv[2]
if case not in ('off', 'restart'):
    raise ValueError('requires one transaction case')
remote = '/data5/researcher/h3_runs/r50_transaction_cpu_stage_attempt' + str(attempt)
log = root / 'audit' / f'actual_comfy_transaction_attempt{attempt}.log'
if log.exists():
    raise FileExistsError(log)
start = time.monotonic()
lock_path = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
with lock_path.open('a') as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.write_text('Mac CPU busy; no computation or remote stage\n')
        raise SystemExit(75)
    files = {}
    for folder in ('scripts', 'extensions', 'tests', 'configs'):
        for p in (root / folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc':
                files[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = root / 'audit' / f'transaction_stage_attempt{attempt}.json'
    manifest.write_text(json.dumps({'remote': remote, 'case': case, 'files': files}, indent=2) + '\n')
    subprocess.run(['ssh', 'H3_SERVER_A', 'mkdir -p ' + shlex.quote(remote + '/audit')], check=True, timeout=30)
    for folder in ('scripts', 'extensions', 'tests', 'configs'):
        subprocess.run(['rsync', '-a', '--exclude=__pycache__', '--exclude=*.pyc', str(root / folder),
                        'H3_SERVER_A:' + remote + '/'], check=True, timeout=30)
    subprocess.run(['rsync', '-a', str(manifest), 'H3_SERVER_A:' + remote + '/stage_manifest.json'], check=True, timeout=30)
    code = r'''
import fcntl,hashlib,json,os,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1])
def pending():
 for task in Path('/data5/researcher/h3_runs').glob('timing_auto_*'):
  for d in (task/'audit/observations').glob('step*'):
   if not (d/'request.json').is_file() or not (d/'native.json').is_file() or (d/'pose_complete.json').exists() or (d/'response.json').exists():continue
   r=json.loads((d/'request.json').read_text());parent=r['parent'];p=Path('/proc')/str(parent['pid'])
   try:
    stat=(p/'stat').read_text();tail=stat[stat.rindex(')')+2:].split()
    if tail[0]!='Z' and p.stat().st_uid==parent['uid'] and str(parent['start_ticks'])==tail[19] and hashlib.sha256((p/'cmdline').read_bytes()).hexdigest()==parent['cmdline_sha256']:return True
   except (FileNotFoundError,ProcessLookupError):pass
 return False
if pending():raise SystemExit(75)
handle=open('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock','a')
try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(75)
if pending():raise SystemExit(75)
manifest=json.loads((root/'stage_manifest.json').read_text())
for rel,digest in manifest['files'].items():
 if hashlib.sha256((root/rel).read_bytes()).hexdigest()!=digest:raise ValueError('stage mismatch '+rel)
temp=root/'tmp';temp.mkdir(exist_ok=False)
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH='/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps',TMPDIR=str(temp),TMP=str(temp),TEMP=str(temp))
print(json.dumps({'CPU_environment':{k:env[k] for k in ('CUDA_VISIBLE_DEVICES','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','TMPDIR','TMP','TEMP')}}),flush=True)
command=['/home/researcher/miniconda3/envs/comfyui/bin/python',str(root/'tests/real_comfy_transaction_smoke.py'),'--core','/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI','--case',manifest['case']]
raise SystemExit(subprocess.run(command,env=env,timeout=180).returncode)
'''
    result = subprocess.run(['ssh', 'H3_SERVER_A', 'python3 -c ' + shlex.quote(code) + ' ' + shlex.quote(remote)],
                            capture_output=True, text=True, timeout=220)
    log.write_text(result.stdout + '\nSTDERR\n' + result.stderr)
    record = {'returncode': result.returncode, 'case': case, 'wall_seconds': time.monotonic()-start,
              'remote': remote, 'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()}
    (root/'audit'/f'actual_comfy_transaction_attempt{attempt}.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record))
    raise SystemExit(result.returncode)
