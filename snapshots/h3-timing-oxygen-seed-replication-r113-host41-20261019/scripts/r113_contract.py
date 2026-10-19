"""Two predeclared fresh seed pairs with the original R73 fixed temporal route."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('short_0252',)
SEEDS=(2026101702,2026101703)
ARMS=('native','fixed')
PAIR_KEYS=tuple(f'short_0252_seed{s}' for s in SEEDS)
RUNS=tuple(f'r113_{p}_{a}' for p in PAIR_KEYS for a in ARMS)
SHARED_ID='r113_short_0252_shared'
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
def pair_id(seed):
 require(seed in SEEDS,'unregistered seed')
 return f'r113_short_0252_seed{seed}'
def geometry(case):return case['geometry']
def latent_shapes(case):return SHAPES

def expected_graph(root,case):
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);g=copy.deepcopy(read(root/case['parent_graph']))
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/suffix)
 g['5']['inputs']['run_id']=SHARED_ID;g['51']['inputs']['source_run_id']=SHARED_ID
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=case['run_id']
 g['6']['inputs']['pair_id']=pair_id(case['seed']);g['6']['inputs']['noise_seed']=case['seed'];g['14']['inputs']['filename_prefix']=case['run_id']
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json')
 require(s['case_order']==list(RUNS) and len(s['cases'])==4 and s['arms']==list(ARMS) and s['seeds']==list(SEEDS) and s['source_ids']==list(SOURCES) and s['pair_keys']==list(PAIR_KEYS),'two-seed registry differs')
 require(read(root/'configs/queue.json')=={'jobs':list(RUNS),'finalize':True},'all four fresh runs must finalize')
 d=read(root/'design/INTERFACE_BINDINGS.json');jobs={}
 for index,(run,case) in enumerate(zip(RUNS,s['cases'])):
  seed,arm=SEEDS[index//2],ARMS[index%2]
  require(case['run_id']==run and case['source_id']==SOURCES[0] and case['pair_key']==PAIR_KEYS[index//2] and case['seed']==seed and case['geometry']==GEOMETRY and case['valid_frame_count']==VALID and case['arm']==arm and case['sampler_function']=='sample_euler','seed/arm/geometry/run changed')
  require(case['prompt']==d['source_task']['prompt'] and case['prompt_sha256']==hashlib.sha256(case['prompt'].encode()).hexdigest(),'original P1 prompt changed')
  template=d['task_templates'][arm]
  require(case['parent_graph']==template['local_file'] and sha(root/case['parent_graph'])==case['parent_graph_sha256']==template['sha256'],'original R73 Native/fixed graph changed')
  for key in ('video','provenance'):require(case[key]==d['source_task'][key] and case[key+'_sha256']==d['source_task'][key+'_sha256'],'original source binding differs')
  require(case['reference_image_count']==0 and case['reference_video_count']==1 and case['evaluation_crop_xywh']==[16,8,1280,720],'reference/crop differs')
  graph=root/'configs/graphs'/(run+'.json');require(read(graph)==expected_graph(root,case),'graph changed beyond seed/run/path')
  jobs[run]={'case':case,'source_id':SOURCES[0],'pair_key':case['pair_key'],'motion_source_id':SOURCES[0],'seed':seed,'arm':arm,'graph_sha256':sha(graph)}
 return jobs,list(RUNS)

def validate_job(run,root=ROOT):
 root=Path(root);jobs,_=registry(root);require(run in jobs,'unknown run');row=jobs[run]
 for key in ('video','provenance'):
  case=row['case'];p=root/'inputs'/case[key];require(Path(case[key]).name==case[key] and not p.is_symlink() and sha(p)==case[key+'_sha256'],'input changed: '+key)
 return row

def audit_dir(value):
 p=Path(value);require(p.is_absolute() and p.resolve()==REMOTE/'audit','audit root differs');return p

def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
 row=validate_job(run_id);require(Path(audit_dir)==REMOTE/'audit/router','router audit differs')
 expected_mode='native' if row['arm']=='native' else 'mass_preserve'
 require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==(expected_mode,1.,0,0,0,97,0,50,6,15),'registered fixed route differs')

def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True)
 path=folder/case['video']
 if not path.exists():
  with (root/'inputs'/case['video']).open('rb') as before,path.open('xb') as after:shutil.copyfileobj(before,after)
 require(not path.is_symlink() and sha(path)==case['video_sha256'],'loader input changed')
 return row

def root_gpu_review(root=ROOT):
 root=Path(root);review=read(root/'audit/GPU_DEPLOYMENT_REVIEW.json')
 require(review.get('approved') is True and review.get('reviewer')=='root' and review.get('scope')=='r113-two-seed-gpu-execution' and review.get('producer_seal_sha256')==sha(root/'deploy_manifest.json'),'root review for this producer seal is required')
 return review
