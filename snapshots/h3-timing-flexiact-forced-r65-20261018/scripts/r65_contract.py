"""Two original FlexiAct development pairs, same-host Native followed by fixed-ON; twenty Euler predictions."""
import copy,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('fitness','one_leg')
ARMS=('native','forced');GEOMETRY={'width':1152,'height':768,'frames':158,'fps':24}
SHAPES={'video':(1,24,47,48,72),'audio':(1,32,2,263)}
def read(path):return json.loads(Path(path).read_text())
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
REMOTE=Path(read(ROOT/'configs/runtime.json')['remote_root'])
def require(ok,message):
 if not ok:raise ValueError(message)
def expected_graph(root,case):
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);g=copy.deepcopy(read(root/case['parent_graph']));run=case['run_id'];source=case['source_id']
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/suffix)
 shared='r65_'+source+'_shared';g['5']['inputs']['run_id']=shared;g['51']['inputs']['source_run_id']=shared
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']='r65_'+source+'_seed2026101701'
 g['14']['inputs']['filename_prefix']=run
 g['50']['inputs'].update(mode='native' if case['arm']=='native' else 'mass_preserve',alpha=1.,radius=0,time_offset=0,start_frame=0,end_frame=146,block_start=0,block_end=50,step_start=0 if case['arm']=='native' else 6,step_end=20 if case['arm']=='native' else 15)
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');order=['r65_'+source+'_seed2026101701_'+arm for source in SOURCES for arm in ARMS]
 require(s['case_order']==order and len(s['cases'])==4 and s['arms']==list(ARMS) and s['source_ids']==list(SOURCES),'fixed two paired case registry changed')
 q=read(root/'configs/queue.json');require(set(q)=={'jobs','finalize'} and q['jobs']==order and type(q['finalize']) is bool,'fixed paired queue changed')
 jobs={}
 for case,run in zip(s['cases'],order):
  require(case['run_id']==run and case['prompt_version']=='R49_original' and case['seed']==2026101701 and case['geometry']==GEOMETRY,'source/seed/original-prompt/geometry changed')
  parent=root/case['parent_graph'];require(sha(parent)==case['parent_graph_sha256'],'R49 graph changed')
  require(read(parent)['5']['inputs']['prompt']==case['prompt'],'original R49 prompt changed')
  graph=root/'configs/graphs'/(run+'.json');require(read(graph)==expected_graph(root,case),'graph numerical inputs changed')
  jobs[run]={'case':case,'source_id':case['source_id'],'seed':case['seed'],'arm':case['arm'],'graph_sha256':sha(graph)}
 return jobs,order

def validate_job(run,root=ROOT):
 root=Path(root);jobs,_=registry(root);require(run in jobs,'unknown run');row=jobs[run]
 for key in ('video','portrait','provenance'):
  case=row['case'];name=case[key];p=root/'inputs'/name
  require(Path(name).name==name and not p.is_symlink() and sha(p)==case[key+'_sha256'],'input changed: '+key)
 return row

def audit_dir(value):
 p=Path(value);require(p.is_absolute() and p.resolve()==REMOTE/'audit','audit root differs');return p

def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
 row=validate_job(run_id);forced=row['arm']=='forced'
 require(Path(audit_dir)==REMOTE/'audit/router','router audit differs')
 require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==('mass_preserve' if forced else 'native',1.,0,0,0,146,0,50,6 if forced else 0,15 if forced else 20),'fixed route parameters differ')

def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True)
 for key in ('video','portrait'):
  path=folder/case[key]
  if not path.exists():
   with (root/'inputs'/case[key]).open('rb') as before,path.open('xb') as after:shutil.copyfileobj(before,after)
  require(not path.is_symlink() and sha(path)==case[key+'_sha256'],'loader source changed')
 return row
