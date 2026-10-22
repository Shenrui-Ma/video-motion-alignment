import hashlib,json,os,fcntl,contextlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PAIRS=['short_0210','short_0230','short_0263','short_0352','short_0370']
RUNTIME=ROOT/'runtime';SELECTION=ROOT/'inputs/PILOT_5_MANIFEST.json'
PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def bound(p):return {'file':str(Path(p).resolve()),'sha256':sha(p)}
def verify_runtime():
 f=read(ROOT/'RUNTIME_FREEZE.json')
 for rel,row in f['files'].items():
  p=ROOT/rel
  if sha(p)!=row['sha256'] or p.stat().st_size!=row['bytes']:raise ValueError('runtime dependency differs: '+rel)
 return sha(ROOT/'RUNTIME_FREEZE.json')
@contextlib.contextmanager
def cpu_lock():
 if Path('/data5/researcher/h3_runs').exists():p=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
 else:p=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
 with p.open('a') as h:
  fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB);yield
