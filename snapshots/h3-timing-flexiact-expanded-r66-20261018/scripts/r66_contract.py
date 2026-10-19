"""Eight frozen action+target pairs; one Native/forced pair per cache identity."""
import copy,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PAIR_KEYS=('human2animal_1__movie_man_11','human2animal_1__game_man_4','fitness__game_man_4','one_leg__movie_man_11','human2animal_3__movie_man_11','human2animal_3__game_man_4','human2animal_2__movie_man_11','human2animal_2__game_man_4')
# Retain the inherited CLI/API spelling; every element is a pair key, not an independent motion source.
SOURCES=PAIR_KEYS
ARMS=('native','forced');GEOMETRY={'width':1152,'height':768,'frames':158,'fps':24}
SHAPES={'video':(1,24,47,48,72),'audio':(1,32,2,263)}
PREPARED_SHA='39e1f8c996605320869a789565d7eb18e36b392d33d5bf482fa0130c7d24619a'
SELECTED_SHA='8e6d23998ed289c8f4bbff6bf50daf77d4c2b5a121dc56b0660561e1f615a257'
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
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);g=copy.deepcopy(read(root/case['parent_graph']));run=case['run_id'];pair=case['pair_key']
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/suffix)
 shared='r66_'+pair+'_shared';g['5']['inputs']['run_id']=shared;g['51']['inputs']['source_run_id']=shared
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']='r66_'+pair+'_seed2026101701'
 g['14']['inputs']['filename_prefix']=run
 g['21']['inputs']['image']=case['portrait'];g['22']['inputs']['file']=case['video']
 g['50']['inputs'].update(mode='native' if case['arm']=='native' else 'mass_preserve',alpha=1.,radius=0,time_offset=0,start_frame=0,end_frame=146,block_start=0,block_end=50,step_start=0 if case['arm']=='native' else 6,step_end=20 if case['arm']=='native' else 15)
 return g

def frozen_pairs(root):
 folder=Path(root)/'configs/source_selection'
 require(sha(folder/'PREPARED_8_PAIRS.json')==PREPARED_SHA and sha(folder/'SELECTED_8_MANIFEST.json')==SELECTED_SHA,'frozen source-only selection changed')
 p=read(folder/'PREPARED_8_PAIRS.json');q=read(folder/'QUEUE_RECOMMENDATION.json');require(q['prepared_pairs_sha256']==PREPARED_SHA,'queue ancestry changed')
 rows={x['pair_id']:x for x in p['pairs']};require(len(rows)==8 and len(q['pair_order'])==8 and set(q['pair_order'])==set(rows),'pair inventory changed')
 ordered=[rows[k] for k in q['pair_order']]
 require(tuple(x['action']+'__'+Path(x['target']['official_path']).stem for x in ordered)==PAIR_KEYS,'pair priority/cache identity changed')
 return ordered

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');order=['r66_'+pair+'_seed2026101701_'+arm for pair in PAIR_KEYS for arm in ARMS]
 require(s['case_order']==order and len(s['cases'])==16 and s['arms']==list(ARMS) and s['source_ids']==s['pair_keys']==list(PAIR_KEYS),'fixed eight paired case registry changed')
 q=read(root/'configs/queue.json');require(set(q)=={'jobs','finalize'} and q['jobs']==order and type(q['finalize']) is bool,'fixed paired queue changed')
 frozen=frozen_pairs(root);shapes=read(root/'configs/source_selection/EXPECTED_SHAPES.json')['reference_images'];jobs={}
 for i,(case,run) in enumerate(zip(s['cases'],order)):
  p=frozen[i//2];pair=PAIR_KEYS[i//2];portrait=Path(p['target']['prepared_local_path']).name
  require(re.fullmatch(r'[a-z0-9_]+',pair) and case['source_id']==case['pair_key']==pair and case['arm']==ARMS[i%2],'safe pair/arm identity changed')
  require(case['run_id']==run and case['prompt_version']=='R49_original' and case['seed']==2026101701 and case['geometry']==GEOMETRY,'seed/prompt/geometry changed')
  bindings={'motion_source_id':p['action'],'original_pair_id':p['pair_id'],'group':p['group'],'source_is_new_motion_content':p['source_is_new_motion_content'],'video':Path(p['source']['video']).name,'portrait':portrait,'provenance':Path(p['source']['provenance']).name,'identity':p['target']['official_path'],'video_sha256':p['source']['video_sha256'],'portrait_sha256':p['target']['prepared_sha256'],'provenance_sha256':p['source']['provenance_sha256'],'prompt':p['prompt_exact'],'valid_frame_count':147,'evaluation_indices':list(range(0,147,3)),'evaluation_crop_xywh':[0,0,1152,768],'reference_image_expected':shapes[portrait]}
  require(all(case.get(k)==v for k,v in bindings.items()),'frozen pair input or metadata changed: '+pair)
  parent=root/case['parent_graph'];require(case['parent_graph']=='configs/parent_graphs/r65_native_graph_template.json' and sha(parent)==case['parent_graph_sha256'],'R65 graph template changed')
  require(read(parent)['5']['inputs']['prompt']==case['prompt'],'original R49 prompt changed')
  graph=root/'configs/graphs'/(run+'.json');require(read(graph)==expected_graph(root,case),'graph numerical inputs changed')
  jobs[run]={'case':case,'source_id':pair,'pair_key':pair,'motion_source_id':p['action'],'seed':case['seed'],'arm':case['arm'],'graph_sha256':sha(graph)}
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
