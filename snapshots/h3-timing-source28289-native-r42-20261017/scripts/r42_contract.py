"""One immutable new source with one fixed Native seed; no interventions or continuation."""
import copy,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REMOTE=Path('/data5/researcher/h3_runs/timing_source28289_native_r42_20261017')
SOURCES=('28289',);SEEDS=(2026101701,);ARMS=('native',)
PROMPT='Replace the person in the reference video with the man from the reference image, Elon Musk. He wears a plain gray long-sleeve shirt and dark trousers. Preserve the original hand gestures, body motions and their exact timing, the sequence of body poses, the camera movement, and the green background of the reference video.'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def safe(v):
 if not isinstance(v,str) or not re.fullmatch(r'[a-z0-9_]+',v):raise ValueError('unsafe R42 identifier')
 return v

def expected_graph(root,case):
 root=Path(root);g=copy.deepcopy(read(root/case['parent_graph']));run=case['run_id']
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(REMOTE/suffix)
 g['5']['inputs']['prompt']=PROMPT
 g['21']['inputs']['image']=case['portrait'];g['22']['inputs']['file']=case['video'];shared='r42_source_'+case['source_id']+'_shared'
 g['5']['inputs']['run_id']=shared;g['51']['inputs']['source_run_id']=shared
 for k in ('6','50','51','52'):g[k]['inputs']['run_id']=run
 g['6']['inputs'].update(pair_id=f'r42_source_{case["source_id"]}_seed{case["seed"]}',noise_seed=case['seed']);g['14']['inputs']['filename_prefix']=run
 g['50']['inputs'].update(mode='native',step_start=0,step_end=20,start_frame=0,end_frame=140)
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');queue=read(root/'configs/queue.json');reg=read(root/'configs/job_registry.json')['jobs'];cases=s['cases'];wanted=[f'r42_source_{source}_seed2026101701_native' for source in SOURCES]
 if s['source_ids']!=list(SOURCES) or s['seeds']!=list(SEEDS) or s['arms']!=['native'] or len(cases)!=1 or s['case_order']!=wanted:raise ValueError('fixed source/seed order differs')
 if list(reg)!=wanted or set(queue)!={'jobs','finalize'} or queue['jobs']!=wanted or type(queue['finalize']) is not bool:raise ValueError('queue differs from frozen one-source/one-seed contract')
 jobs={}
 for case,run,source in zip(cases,wanted,SOURCES):
  seed=2026101701
  if case['run_id']!=run or case['seed']!=seed or case['source_id']!=source or case['identity']!='Elon Musk' or case['prompt']!=PROMPT or reg[run]['seed']!=seed or reg[run]['arm']!='native' or reg[run]['source_id']!=source:raise ValueError('case/seed/arm differs')
  if sha(root/case['parent_graph'])!=case['parent_graph_sha256']:raise ValueError('parent graph changed')
  jobs[run]=dict(reg[run],case=case)
 return jobs,wanted

def job_record(run,root=ROOT):
 jobs,_=registry(root)
 if run not in jobs:raise ValueError('unregistered run')
 return jobs[run]

def validate_job(run,root=ROOT):
 root=Path(root);row=job_record(run,root);p=root/'configs/graphs'/f'{safe(run)}.json';case=row['case']
 if p.is_symlink() or sha(p)!=row['graph_sha256'] or read(p)!=expected_graph(root,case):raise ValueError('graph differs from actual R38 parent transformation')
 for k in ('video','portrait','provenance'):
  name=case[k]
  if Path(name).name!=name:raise ValueError('input filename must be a basename')
  p=root/'inputs'/name
  if p.is_symlink() or sha(p)!=case[k+'_sha256']:raise ValueError('input differs: '+k)
 return row

def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
 validate_job(run_id)
 if Path(audit_dir)!=REMOTE/'audit/router' or (mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)!=('native',1.0,0,0,0,140,0,50,0,20):raise ValueError('Native contract differs')

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
