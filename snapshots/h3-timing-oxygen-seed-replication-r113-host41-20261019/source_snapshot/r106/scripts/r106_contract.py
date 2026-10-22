"""Two fresh Native edits on an identical ManualSigmas grid; only solver changes."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=PAIR_KEYS=('short_0252',)
ARMS=('euler','res_multistep')
RUNS=tuple('r106_short_0252_seed2026101701_'+a for a in ARMS)
PAIR_ID='r106_short_0252_seed2026101701'
SHARED_ID='r106_short_0252_shared'
GEOMETRY={'width':1312,'height':736,'frames':107,'fps':24}
SHAPES={'video':(1,24,32,46,82),'audio':(1,32,2,178)}
VALID=98

def read(path):return json.loads(Path(path).read_text())
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)
REMOTE=Path(read(ROOT/'configs/runtime.json')['remote_root'])
def geometry(case):return case['geometry']
def latent_shapes(case):return SHAPES

def expected_graph(root,case):
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);g=copy.deepcopy(read(root/case['parent_graph']))
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/suffix)
 g['5']['inputs']['run_id']=SHARED_ID;g['51']['inputs']['source_run_id']=SHARED_ID
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=case['run_id']
 g['6']['inputs']['pair_id']=PAIR_ID;g['14']['inputs']['filename_prefix']=case['run_id'];g['8']['inputs']['sampler_name']=case['arm']
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');require(s['case_order']==list(RUNS) and len(s['cases'])==2 and s['arms']==list(ARMS) and s['source_ids']==s['pair_keys']==list(SOURCES),'two-solver registry differs')
 require(read(root/'configs/queue.json')=={'jobs':list(RUNS),'finalize':True},'two Native edits must finalize')
 d=read(root/'design/INTERFACE_BINDINGS.json');jobs={}
 for arm,run,case in zip(ARMS,RUNS,s['cases']):
  require(case['run_id']==run and case['source_id']==case['pair_key']==SOURCES[0] and case['seed']==2026101701 and case['geometry']==GEOMETRY and case['valid_frame_count']==VALID and case['arm']==arm and case['sampler_function']=='sample_'+arm,'solver/geometry/seed/run changed')
  require(case['prompt']==d['source_task']['prompt'] and case['prompt_sha256']==hashlib.sha256(case['prompt'].encode()).hexdigest(),'original P1 prompt changed')
  require(sha(root/case['parent_graph'])==case['parent_graph_sha256']==d['task_template']['sha256'],'actual R73 graph changed')
  for key in ('video','provenance'):require(case[key]==d['source_task'][key] and case[key+'_sha256']==d['source_task'][key+'_sha256'],'original source binding differs')
  require(case['reference_image_count']==0 and case['reference_video_count']==1 and case['evaluation_crop_xywh']==[16,8,1280,720],'reference/crop differs')
  graph=root/'configs/graphs'/(run+'.json');require(read(graph)==expected_graph(root,case),'graph changed beyond solver/run/path')
  jobs[run]={'case':case,'source_id':SOURCES[0],'pair_key':SOURCES[0],'motion_source_id':SOURCES[0],'seed':2026101701,'arm':arm,'graph_sha256':sha(graph)}
 return jobs,list(RUNS)

def validate_job(run,root=ROOT):
 root=Path(root);jobs,_=registry(root);require(run in jobs,'unknown run');row=jobs[run]
 for key in ('video','provenance'):
  case=row['case'];p=root/'inputs'/case[key];require(Path(case[key]).name==case[key] and not p.is_symlink() and sha(p)==case[key+'_sha256'],'input changed: '+key)
 return row

def audit_dir(value):
 p=Path(value);require(p.is_absolute() and p.resolve()==REMOTE/'audit','audit root differs');return p

def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
 validate_job(run_id);require(Path(audit_dir)==REMOTE/'audit/router','router audit differs')
 require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==('native',1.,0,0,0,97,0,50,6,15),'Native-only router parameters differ')

def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True)
 path=folder/case['video']
 if not path.exists():
  with (root/'inputs'/case['video']).open('rb') as before,path.open('xb') as after:shutil.copyfileobj(before,after)
 require(not path.is_symlink() and sha(path)==case['video_sha256'],'loader input changed')
 return row
