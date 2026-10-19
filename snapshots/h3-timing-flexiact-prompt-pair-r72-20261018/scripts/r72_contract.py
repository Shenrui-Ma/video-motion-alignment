"""Two fixed official FlexiAct identity pairs, fresh Native P0/P1 on one service."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PAIR_KEYS=('fitness__game_man_5','one_leg__movie_man_9');SOURCES=PAIR_KEYS;ARMS=('p0','p1')
GEOMETRY={'width':1152,'height':768,'frames':158,'fps':24}
SHAPES={'video':(1,24,47,48,72),'audio':(1,32,2,263)}
def read(path):return json.loads(Path(path).read_text())
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)
REMOTE=Path(read(ROOT/'configs/runtime.json')['remote_root'])

def definitions(root=ROOT):
 root=Path(root);a=read(root/'configs/prompt_ancestry.json');path=root/'design/PAIR_DEFINITIONS.json'
 require(sha(path)==a['pair_definitions_sha256'],'frozen pair definitions changed')
 d=read(path);require(tuple(p['pair_key'] for p in d['pairs'])==PAIR_KEYS,'fixed two pairs changed')
 require(sha(root/'design/FIXED_8_CANDIDATES.json')==d['selection_sha256'],'candidate selection changed')
 require(sha(root/'design/P1_TEMPLATE.txt')==a['p1_template_sha256'] and sha(root/'design/official_ref-en.txt')==a['official_guide_sha256'],'prompt template/guide changed')
 return d['pairs']

def prompt_values(root=ROOT,pair=PAIR_KEYS[0]):
 root=Path(root);p=next(x for x in definitions(root) if x['pair_key']==pair);values={}
 for arm in ARMS:
  f=root/p['prompt_files'][arm];require(sha(f)==p['prompt_sha256'][arm],'frozen prompt changed');values[arm]=f.read_text()
 require((root/'design/P1_TEMPLATE.txt').read_text().format(**p['p1_fields'])==values['p1'],'frozen P1 fields changed')
 require(read(root/'configs/parent_graphs/r66_fitness_native_template.json')['5']['inputs']['prompt']==values['p0'],'original Flex P0 changed')
 return values

def expected_graph(root,case):
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);g=copy.deepcopy(read(root/case['parent_graph']));run=case['run_id'];pair=case['pair_key']
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/suffix)
 g['5']['inputs'].update(run_id=case['reference_cache_id'],prompt=case['prompt']);g['51']['inputs']['source_run_id']=case['reference_cache_id']
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']='r72_'+pair+'_seed2026101701';g['14']['inputs']['filename_prefix']=run
 g['21']['inputs']['image']=case['portrait'];g['22']['inputs']['file']=case['video']
 g['50']['inputs'].update(mode='native',alpha=1.,radius=0,time_offset=0,start_frame=0,end_frame=146,block_start=0,block_end=50,step_start=0,step_end=20)
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');order=['r72_'+pair+'_seed2026101701_'+arm for pair in PAIR_KEYS for arm in ARMS]
 require(s['case_order']==order and len(s['cases'])==4 and s['arms']==list(ARMS) and s['source_ids']==s['pair_keys']==list(PAIR_KEYS),'fixed prompt pairs changed')
 q=read(root/'configs/queue.json');require(set(q)=={'jobs','finalize'} and q['jobs']==order and type(q['finalize']) is bool,'paired queue changed')
 defs=definitions(root);jobs={}
 for i,(case,run) in enumerate(zip(s['cases'],order)):
  pair=PAIR_KEYS[i//2];arm=ARMS[i%2];d=defs[i//2];prompts=prompt_values(root,pair)
  require(case['run_id']==run and case['source_id']==case['pair_key']==pair and case['arm']==arm and case['prompt_version']==arm.upper() and case['seed']==2026101701 and case['geometry']==GEOMETRY,'pair/seed/arm/geometry changed')
  require(case['reference_cache_id']=='r72_'+pair+'_'+arm+'_shared','independent text cache identity changed')
  require(case['prompt']==prompts[arm] and case['prompt_sha256']==sha(root/case['prompt_file']),'prompt changed')
  expected={'motion_source_id':d['motion_source_id'],'identity':d['identity'],'reference_image_expected':d['reference_image_expected'],'reference_video_count':1,'reference_image_count':1,'valid_frame_count':147,'evaluation_indices':list(range(0,147,3)),'evaluation_crop_xywh':[0,0,1152,768]}
  require(all(case[k]==v for k,v in expected.items()),'reference/input scope changed')
  parent=root/case['parent_graph'];require(sha(parent)==case['parent_graph_sha256'],'original graph changed')
  graph=root/'configs/graphs'/(run+'.json');require(read(graph)==expected_graph(root,case),'graph numerical inputs changed')
  jobs[run]={'case':case,'source_id':pair,'pair_key':pair,'motion_source_id':d['motion_source_id'],'seed':case['seed'],'arm':arm,'graph_sha256':sha(graph)}
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
 validate_job(run_id);require(Path(audit_dir)==REMOTE/'audit/router','router audit differs')
 require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==('native',1.,0,0,0,146,0,50,0,20),'Native route parameters differ')

def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True)
 for key in ('video','portrait'):
  path=folder/case[key]
  if not path.exists():
   with (root/'inputs'/case[key]).open('rb') as before,path.open('xb') as after:shutil.copyfileobj(before,after)
  require(not path.is_symlink() and sha(path)==case[key+'_sha256'],'loader source changed')
 return row

def prompt_pair_condition_checks(p0,p1):
 return {key+'_equal':p0[key]==p1[key] for key in ('input_video','native_vae_calls','qwen_presentation','target_latent_shapes')}
