"""Frozen manual physical span with prior fixed schedule single run; no implicit GPU grant or continuation."""
import copy,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REMOTE=Path('/data5/researcher/h3_runs/timing_manual_source51310_r41_20261017')
RUN_ID='r41_source51310_seed2026101701_manual56to127_6to14';SEED=2026101701
SHARED='r41_source_51310_shared';PAIR=RUN_ID+'_noise'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def safe(v):
 if not isinstance(v,str) or not re.fullmatch(r'[a-z0-9_]+',v):raise ValueError('unsafe identifier')
 return v
def expected_graph(root=ROOT):
 root=Path(root);g=copy.deepcopy(read(root/'configs/parent_graph.json'));remote=str(REMOTE)
 g['5']['inputs'].update(audit_dir=remote+'/audit',run_id=SHARED)
 g['6']['inputs'].update(audit_dir=remote+'/audit',run_id=RUN_ID,pair_id=PAIR)
 g['14']['inputs']['filename_prefix']=RUN_ID
 g['50']={'class_type':'H3StaticWindowRouter','inputs':{'model':['41',0],'positive':['51',0],'run_id':RUN_ID,'audit_dir':remote+'/audit/counterfactual'}}
 g['51']['inputs'].update(source_audit_dir=remote+'/audit',source_run_id=SHARED,run_id=RUN_ID)
 g['52']['inputs'].update(run_id=RUN_ID,output_dir=remote+'/audit/x0')
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');q=read(root/'configs/queue.json');r=read(root/'configs/job_registry.json')['jobs']
 if s['run_id']!=RUN_ID or s['seed']!=SEED or s['arm']!='static_manual_span' or list(r)!=[RUN_ID] or set(q)!={'jobs','finalize'} or q['jobs']!=[RUN_ID] or type(q['finalize']) is not bool:raise ValueError('fixed one-run scope changed')
 row=r[RUN_ID]
 if row['seed']!=SEED or row['arm']!='static_manual_span' or row['case']!={'source_id':'51310'}:raise ValueError('case binding changed')
 return r,[RUN_ID]
def validate_job(run,root=ROOT):
 root=Path(root);jobs,_=registry(root)
 if run not in jobs:raise ValueError('unregistered R41 job')
 row=jobs[run];p=root/'configs/graphs'/f'{safe(run)}.json'
 if p.is_symlink() or sha(p)!=row['graph_sha256'] or read(p)!=expected_graph(root):raise ValueError('graph differs from actual R38 Native parent transform')
 for name,d in read(root/'configs/input_hashes.json').items():
  p=root/'inputs'/name
  if Path(name).name!=name or p.is_symlink() or sha(p)!=d:raise ValueError('input binding differs')
 for name,d in read(root/'configs/evidence_hashes.json').items():
  if sha(root/name)!=d:raise ValueError('parent/design evidence changed '+name)
 return row

def audit_dir(value):
 p=Path(value)
 if not p.is_absolute() or p.resolve()!=(REMOTE/'audit').resolve():raise ValueError('audit root differs')
 return p

def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);g=expected_graph(root);target=root/'input';target.mkdir(exist_ok=True)
 for name in (g['21']['inputs']['image'],g['22']['inputs']['file']):
  src=root/'inputs'/name;dst=target/name
  if dst.is_symlink():raise ValueError('loader symlink')
  if not dst.exists():
   with src.open('rb') as a,dst.open('xb') as b:shutil.copyfileobj(a,b)
  if sha(dst)!=read(root/'configs/input_hashes.json')[name]:raise ValueError('actual input differs')
 return row
