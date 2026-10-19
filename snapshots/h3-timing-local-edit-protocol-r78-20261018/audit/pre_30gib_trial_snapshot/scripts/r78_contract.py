"""One frozen source, fresh P0/P1 Native prompt comparison on the same service."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('short_0370',);ARMS=('p0','p1')
GEOMETRY={'width':1312,'height':736,'frames':90,'fps':24}
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
def prompt_values(root=ROOT):
 root=Path(root);binding=read(root/'configs/prompt_ancestry.json');values={}
 for arm in ARMS:
  b=binding[arm];p=root/b['file'];require(sha(p)==b['sha256'],'ancestor graph changed')
  value=read(p)['5']['inputs']['prompt'];file=root/'configs/prompts'/(arm+'.txt')
  require(file.read_text()==value and sha(file)==b['prompt_sha256'],'frozen prompt changed')
  values[arm]=value
 for key in ('template','metadata'):
  b=binding[key];require(sha(root/b['file'])==b['sha256'],'local-edit preregistration binding changed')
 template=(root/binding['template']['file']).read_text();metadata=read(root/binding['metadata']['file'])
 row=next(x for x in metadata['pairs'] if x['pair_id']=='short_0370')
 require(template.format(**row)==values['p1'] and row['edit_prompt']==values['p0'],'P1-local-v1 template/P0 relation changed')
 return values

def expected_graph(root,case):
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);g=copy.deepcopy(read(root/case['parent_graph']));run=case['run_id']
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/suffix)
 g['5']['inputs'].update(run_id=case['reference_cache_id'],prompt=case['prompt']);g['51']['inputs']['source_run_id']=case['reference_cache_id']
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']='r78_short_0370_seed2026101701'
 g['14']['inputs']['filename_prefix']=run
 g['50']['inputs'].update(mode='native',alpha=1.,radius=0,time_offset=0,start_frame=0,end_frame=89,block_start=0,block_end=50,step_start=0,step_end=20)
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');order=['r78_short_0370_seed2026101701_'+arm for arm in ARMS];prompts=prompt_values(root)
 require(s['case_order']==order and len(s['cases'])==2 and s['arms']==list(ARMS) and s['source_ids']==list(SOURCES),'fixed prompt pair changed')
 q=read(root/'configs/queue.json');require(set(q)=={'jobs','finalize'} and q['jobs']==order and type(q['finalize']) is bool,'paired queue changed')
 jobs={}
 for case,arm,run in zip(s['cases'],ARMS,order):
  require(case['run_id']==run and case['source_id']=='short_0370' and case['arm']==arm and case['prompt_version']==arm.upper() and case['seed']==2026101701 and case['geometry']==GEOMETRY,'source/seed/arm/geometry changed')
  require(case['reference_cache_id']=='r78_short_0370_'+arm+'_shared','independent text cache identity changed')
  require(case['prompt']==prompts[arm] and case['prompt_sha256']==sha(root/case['prompt_file']),'prompt changed')
  require(case['reference_video_count']==1 and case['reference_image_count']==0 and case['valid_frame_count']==89,'input scope changed')
  parent=root/case['parent_graph'];require(sha(parent)==case['parent_graph_sha256'],'original parent graph changed')
  require(read(parent)['5']['inputs']['prompt']==prompts['p0']==case['original_task']['edit_prompt'],'original edit task changed')
  graph=root/'configs/graphs'/(run+'.json');require(read(graph)==expected_graph(root,case),'graph numerical inputs changed')
  jobs[run]={'case':case,'source_id':case['source_id'],'seed':case['seed'],'arm':arm,'graph_sha256':sha(graph)}
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
 validate_job(run_id)
 require(Path(audit_dir)==REMOTE/'audit/router','router audit differs')
 require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==('native',1.,0,0,0,89,0,50,0,20),'Native route parameters differ')

def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True);path=folder/case['video']
 if not path.exists():
  with (root/'inputs'/case['video']).open('rb') as before,path.open('xb') as after:shutil.copyfileobj(before,after)
 require(not path.is_symlink() and sha(path)==case['video_sha256'],'loader source changed');return row

def prompt_pair_condition_checks(p0,p1):
 # qwen_presentation is pre-encoder sampled RGB + timestamp metadata, not joint embeddings.
 keys=('input_video','native_vae_calls','qwen_presentation','target_latent_shapes')
 return {key+'_equal':p0[key]==p1[key] for key in keys}
