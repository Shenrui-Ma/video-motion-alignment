"""Five P0 tasks, same-host Native followed by fixed-ON; twenty Euler predictions."""
import copy,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('short_0210','short_0230','short_0263','short_0352','short_0370')
ARMS=('native','forced');GEOMETRY={'width':1312,'height':736,'frames':90,'fps':24}
SHAPES={'video':(1,24,27,46,82),'audio':(1,32,2,150)}
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
 shared='r63_'+source+'_shared';g['5']['inputs']['run_id']=shared;g['51']['inputs']['source_run_id']=shared
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']='r63_'+source+'_seed2026101701'
 g['14']['inputs']['filename_prefix']=run
 g['50']['inputs'].update(mode='native' if case['arm']=='native' else 'mass_preserve',alpha=1.,radius=0,time_offset=0,start_frame=0,end_frame=89,block_start=0,block_end=50,step_start=0 if case['arm']=='native' else 6,step_end=20 if case['arm']=='native' else 15)
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');order=['r63_'+source+'_seed2026101701_'+arm for source in SOURCES for arm in ARMS]
 require(s['case_order']==order and len(s['cases'])==10 and s['arms']==list(ARMS) and s['source_ids']==list(SOURCES),'fixed five paired case registry changed')
 q=read(root/'configs/queue.json');require(set(q)=={'jobs','finalize'} and q['jobs']==order and type(q['finalize']) is bool,'fixed paired queue changed')
 jobs={}
 for case,run in zip(s['cases'],order):
  require(case['run_id']==run and case['prompt_version']=='P0' and case['seed']==2026101701 and case['geometry']==GEOMETRY,'source/seed/P0/geometry changed')
  parent=root/case['parent_graph'];require(sha(parent)==case['parent_graph_sha256'],'R54 P0 graph changed')
  require(read(parent)['5']['inputs']['prompt']==case['prompt']==case['original_task']['edit_prompt'],'original P0 edit prompt changed')
  graph=root/'configs/graphs'/(run+'.json');require(read(graph)==expected_graph(root,case),'graph numerical inputs changed')
  jobs[run]={'case':case,'source_id':case['source_id'],'seed':case['seed'],'arm':case['arm'],'graph_sha256':sha(graph)}
 return jobs,order

def validate_job(run,root=ROOT):
 root=Path(root);jobs,_=registry(root);require(run in jobs,'unknown run');row=jobs[run]
 for key in ('video','provenance'):
  case=row['case'];name=case[key];p=root/'inputs'/name
  require(Path(name).name==name and not p.is_symlink() and sha(p)==case[key+'_sha256'],'input changed: '+key)
 return row

def audit_dir(value):
 p=Path(value);require(p.is_absolute() and p.resolve()==REMOTE/'audit','audit root differs');return p

def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
 row=validate_job(run_id);forced=row['arm']=='forced'
 require(Path(audit_dir)==REMOTE/'audit/router','router audit differs')
 require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==('mass_preserve' if forced else 'native',1.,0,0,0,89,0,50,6 if forced else 0,15 if forced else 20),'fixed route parameters differ')

def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True);path=folder/case['video']
 if not path.exists():
  with (root/'inputs'/case['video']).open('rb') as before,path.open('xb') as after:shutil.copyfileobj(before,after)
 require(not path.is_symlink() and sha(path)==case['video_sha256'],'loader source changed');return row
