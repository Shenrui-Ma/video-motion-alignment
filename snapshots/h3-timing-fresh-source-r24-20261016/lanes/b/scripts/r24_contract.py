"""Pure R24 case/graph/queue binding; no model/network/process operations."""
import copy,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REMOTE_BASE=Path('/data5/researcher/h3_runs/timing_fresh_source_r24_20261016')
SEEDS=(2026101610,2026101611)
ARMS=('native','full_6to14')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def safe(v):
 if not isinstance(v,str) or not re.fullmatch(r'[a-z0-9_]+',v):raise ValueError('unsafe R24 identifier')
 return v

def case_check(case):
 safe(case['case_id'])
 for key in ('video','portrait','provenance'):
  if not isinstance(case[key],str) or Path(case[key]).name!=case[key]:raise ValueError('case asset must be a filename')
  if not re.fullmatch('[0-9a-f]{64}',case[key+'_sha256']):raise ValueError('missing immutable asset SHA')
 a,b=case['primary_window_inclusive']
 if type(a) is not int or type(b) is not int or not 0<=a<=b<141:raise ValueError('event RGB window outside141frames')
 if not isinstance(case['prompt'],str) or not case['prompt'].strip() or '__' in case['prompt']:raise ValueError('unbound prompt')
 if case.get('new_to_study_attestation') is not True:raise ValueError('source selection attestation missing')
 return case

def run_name(case,seed,arm):
 case_check(case)
 if seed not in SEEDS or arm not in ARMS:raise ValueError('unregistered seed/arm')
 return f'r24_{case["case_id"]}_seed{seed}_{arm}'

def expected_graph(root,case,seed,arm):
 root=Path(root);case_check(case);run=run_name(case,seed,arm)
 runtime=read(root/'configs/runtime.json');remote=Path(runtime['remote_root'])
 if remote not in (REMOTE_BASE/'a',REMOTE_BASE/'b'):raise ValueError('wrong isolated remote lane')
 g=copy.deepcopy(read(root/'configs/graph_template.json'))
 shared='r24_'+case['case_id']+'_shared';pair=f'r24_{case["case_id"]}_seed{seed}'
 g['5']['inputs'].update(prompt=case['prompt'],audit_dir=str(remote/'audit'),run_id=shared)
 g['6']['inputs'].update(noise_seed=seed,audit_dir=str(remote/'audit'),run_id=run,pair_id=pair)
 g['21']['inputs']['image']=case['portrait'];g['22']['inputs']['file']=case['video']
 g['14']['inputs']['filename_prefix']=run
 a,b=case['primary_window_inclusive']
 g['50']['inputs'].update(mode='native' if arm=='native' else 'mass_preserve',start_frame=a,end_frame=b,run_id=run,audit_dir=str(remote/'audit/router'))
 g['51']['inputs'].update(source_audit_dir=str(remote/'audit'),source_run_id=shared,run_id=run)
 g['52']['inputs'].update(run_id=run,output_dir=str(remote/'audit/x0'))
 return g

def registry(root=ROOT):
 root=Path(root);base=read(root/'configs/job_registry.json');plan=read(root/'configs/queue.json')
 batches=[base]
 for entry in plan.get('approved_continuations',[]):
  rel=Path(entry['file']);p=root/rel
  if rel.is_absolute() or '..' in rel.parts or not str(rel).startswith('configs/approved_continuations/') or p.is_symlink() or sha(p)!=entry['sha256']:raise ValueError('unbound continuation manifest')
  batch=read(p)
  if batch.get('root_approved') is not True:raise ValueError('continuation requires root approval')
  batches.append(batch)
 jobs={};order=[];case_ids=set()
 for batch in batches:
  case=case_check(batch['case']);cid=case['case_id']
  if cid in case_ids:raise ValueError('case id must be unique per batch; never reuse old cached run')
  case_ids.add(cid)
  wanted=[run_name(case,s,a) for s in SEEDS for a in ARMS]
  if list(batch['jobs'])!=wanted:raise ValueError('batch order must be seed1610 native/full then1611 native/full')
  for run,row in batch['jobs'].items():
   if run in jobs:raise ValueError('duplicate registered run')
   jobs[run]=dict(row,case=case);order.append(run)
 if plan.get('jobs')!=order or len(order)!=len(set(order)):raise ValueError('queue must equal complete approved batch order')
 if type(plan.get('finalize')) is not bool:raise ValueError('explicit finalize boolean required')
 return jobs,order

def job_record(run,root=ROOT):
 jobs,_=registry(root)
 if run not in jobs:raise ValueError('run absent from approved queue')
 row=jobs[run]
 if run!=run_name(row['case'],row['seed'],row['arm']):raise ValueError('run/seed/source identity mismatch')
 return row

def validate_job(run,root=ROOT):
 root=Path(root);row=job_record(run,root);p=root/'configs/graphs'/f'{safe(run)}.json'
 if p.is_symlink() or sha(p)!=row['graph_sha256'] or read(p)!=expected_graph(root,row['case'],row['seed'],row['arm']):raise ValueError('bound graph changed')
 for key in ('video','portrait','provenance'):
  p=root/'inputs'/row['case'][key]
  if p.is_symlink() or sha(p)!=row['case'][key+'_sha256']:raise ValueError('bound source asset changed: '+key)
 return row

def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
 row=validate_job(run_id);rt=read(ROOT/'configs/runtime.json');remote=Path(rt['remote_root'])
 want='native' if row['arm']=='native' else 'mass_preserve'
 if Path(audit_dir)!=remote/'audit/router' or (mode,alpha,radius,time_offset,block_start,block_end,step_start,step_end)!=(want,1.0,0,0,0,50,6,15) or [start_frame,end_frame]!=row['case']['primary_window_inclusive']:raise ValueError('router differs from frozen per-source contract')

def audit_dir(value):
 root=Path(read(ROOT/'configs/runtime.json')['remote_root'])/'audit'
 if not Path(value).is_absolute() or Path(value).resolve()!=root.resolve():raise ValueError('audit path must equal actual lane audit root')
 return root


def prepare_loader_inputs(run,root=ROOT):
 """Copy once, then verify actual loader files before every prompt submission."""
 import shutil
 root=Path(root);row=validate_job(run,root);target=root/'input';target.mkdir(exist_ok=True)
 for key in ('video','portrait'):
  name=row['case'][key];src=root/'inputs'/name;dst=target/name
  if dst.is_symlink():raise ValueError('loader input symlink rejected')
  if not dst.exists():
   with src.open('rb') as a,dst.open('xb') as b:shutil.copyfileobj(a,b)
  if sha(dst)!=row['case'][key+'_sha256']:raise ValueError('actual loader input changed: '+key)
 return row
