"""Two immutable R26-derived global-Full controls; no continuation or arbitrary window."""
import copy,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REMOTE=Path('/data5/researcher/h3_runs/timing_global_full_r29_20261017')
SEEDS=(2026101701,);ARMS=('global_full_6to14',)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def safe(v):
 if not isinstance(v,str) or not re.fullmatch(r'[a-z0-9_]+',v):raise ValueError('unsafe R29 identifier')
 return v

def expected_graph(root,case):
 root=Path(root);g=copy.deepcopy(read(root/case['parent_graph']));oldroot=case['parent_root'];run=case['run_id']
 for node in g.values():
  for k,v in node['inputs'].items():
   if isinstance(v,str):node['inputs'][k]=v.replace(oldroot,str(REMOTE)).replace('r26_','r29_')
 for k in ('6','50','51','52'):g[k]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']=f'r29_source_{case["source_id"]}_seed2026101701';g['14']['inputs']['filename_prefix']=run
 g['50']['inputs'].update(mode='mass_preserve',step_start=6,step_end=15,start_frame=0,end_frame=140)
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');queue=read(root/'configs/queue.json');reg=read(root/'configs/job_registry.json')['jobs'];cases=s['cases']
 if s['case_order']!=['40372','51304'] or [c['source_id'] for c in cases]!=s['case_order']:raise ValueError('fixed source order differs')
 wanted=[f'r29_source_{sid}_seed2026101701_global_full_6to14' for sid in s['case_order']]
 if list(reg)!=wanted or set(queue)!={'jobs','finalize'} or queue['jobs']!=wanted or type(queue['finalize']) is not bool:raise ValueError('queue differs from frozen two-job contract')
 jobs={}
 for case,run in zip(cases,wanted):
  if case['run_id']!=run or case['seed']!=2026101701 or reg[run]['seed']!=2026101701 or reg[run]['arm']!='global_full_6to14' or reg[run]['source_id']!=case['source_id']:raise ValueError('case/seed/arm differs')
  if sha(root/case['parent_graph'])!=case['parent_graph_sha256']:raise ValueError('parent graph changed')
  for e in case['evidence'].values():
   if sha(root/e['file'])!=e['sha256']:raise ValueError('historical evidence changed')
  jobs[run]=dict(reg[run],case=case)
 return jobs,wanted

def job_record(run,root=ROOT):
 jobs,_=registry(root)
 if run not in jobs:raise ValueError('unregistered run')
 return jobs[run]

def validate_job(run,root=ROOT):
 root=Path(root);row=job_record(run,root);p=root/'configs/graphs'/f'{safe(run)}.json';case=row['case']
 if p.is_symlink() or sha(p)!=row['graph_sha256'] or read(p)!=expected_graph(root,case):raise ValueError('graph differs from actual R26 parent transformation')
 for k in ('video','portrait','provenance'):
  name=case[k]
  if Path(name).name!=name:raise ValueError('input filename must be a basename')
  p=root/'inputs'/name
  if p.is_symlink() or sha(p)!=case[k+'_sha256']:raise ValueError('input differs: '+k)
 return row

def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
 validate_job(run_id)
 if Path(audit_dir)!=REMOTE/'audit/router' or (mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)!=('mass_preserve',1.0,0,0,0,140,0,50,6,15):raise ValueError('Full operator/support/schedule differs')

def audit_dir(value):
 p=Path(value)
 if not p.is_absolute() or p.resolve()!=(REMOTE/'audit').resolve():raise ValueError('audit root differs')
 return p

def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);target=root/'input';target.mkdir(exist_ok=True)
 for k in ('video','portrait'):
  case=row['case'];src=root/'inputs'/case[k];dst=target/case[k]
  if dst.is_symlink():raise ValueError('loader input symlink')
  if not dst.exists():
   with src.open('rb') as a,dst.open('xb') as b:shutil.copyfileobj(a,b)
  if sha(dst)!=case[k+'_sha256']:raise ValueError('actual loader input differs')
 return row
