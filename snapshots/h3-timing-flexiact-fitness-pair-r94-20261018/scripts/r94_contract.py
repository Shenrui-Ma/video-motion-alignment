"""One official Flex pair; each Native/forced pair has identical prompt and actual caches."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PAIR_KEYS=('fitness__game_man_5',)
SOURCES=PAIR_KEYS;ARMS=('native','forced')
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
 root=Path(root);a=read(root/'configs/prompt_ancestry.json');p=root/'design/PAIR_DEFINITIONS.json';require(sha(p)==a['pair_definitions_sha256'],'frozen pair definitions changed')
 d=read(p);require(tuple(p['pair_key'] for p in d['pairs'])==PAIR_KEYS,'fixed single pair changed')
 require(sha(root/'design/SELECTED_PAIRS.json')==d['selection_sha256'],'candidate selection changed')
 require(sha(root/'design/P1_TEMPLATE.txt')==a['p1_template_sha256'] and sha(root/'design/official_ref-en.txt')==a['official_guide_sha256'],'P1 template/guide changed')
 return d['pairs']
def prompt_values(root=ROOT,pair=PAIR_KEYS[0]):
 root=Path(root);p=next(x for x in definitions(root) if x['pair_key']==pair);f=root/p['prompt_file'];require(sha(f)==p['prompt_sha256'],'frozen P1 prompt changed');value=f.read_text()
 require(value==p['prompt'],'prompt value differs')
 if p['prompt_version']=='P1':require((root/'design/P1_TEMPLATE.txt').read_text().format(**p['p1_fields'])==value,'P1 fields differ')
 else:
  require(p['prompt_version']=='P0' and pair=='one_leg__movie_man_9','unsupported prompt protocol');a=p['p0_ancestry']
  require(sha(root/a['prompt_file'])==a['prompt_sha256']==p['prompt_sha256'] and sha(root/a['graph_file'])==a['graph_sha256'] and sha(root/a['case_file'])==a['case_sha256'],'R72 P0 ancestry changed')
  require((root/a['prompt_file']).read_text()==value==read(root/a['graph_file'])['5']['inputs']['prompt']==read(root/a['case_file'])['prompt'],'exact R72 P0 differs')
 return value
def expected_graph(root,case):
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);g=copy.deepcopy(read(root/case['parent_graph']));run=case['run_id'];pair=case['pair_key'];forced=case['arm']=='forced'
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/suffix)
 shared='r94_'+pair+'_shared';g['5']['inputs'].update(run_id=shared,prompt=case['prompt']);g['51']['inputs']['source_run_id']=shared
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']='r94_'+pair+'_seed2026101701';g['14']['inputs']['filename_prefix']=run
 g['21']['inputs']['image']=case['portrait'];g['22']['inputs']['file']=case['video']
 g['50']['inputs'].update(mode='mass_preserve' if forced else 'native',alpha=1.,radius=0,time_offset=0,start_frame=0,end_frame=146,block_start=0,block_end=50,step_start=6 if forced else 0,step_end=15 if forced else 20)
 return g
def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');order=['r94_'+p+'_seed2026101701_'+a for p in PAIR_KEYS for a in ARMS]
 require(s['case_order']==order and len(s['cases'])==2 and s['arms']==list(ARMS) and s['source_ids']==s['pair_keys']==list(PAIR_KEYS),'fixed single paired registry changed')
 q=read(root/'configs/queue.json');require(set(q)=={'jobs','finalize'} and q['jobs']==order and type(q['finalize']) is bool,'paired queue changed')
 defs=definitions(root);jobs={}
 for i,(case,run) in enumerate(zip(s['cases'],order)):
  p=defs[i//2];pair=PAIR_KEYS[i//2];arm=ARMS[i%2];prompt=prompt_values(root,pair)
  require(case['run_id']==run and case['source_id']==case['pair_key']==pair and case['arm']==arm and case['prompt_version']==p['prompt_version'] and case['seed']==2026101701 and case['geometry']==GEOMETRY,'pair/seed/arm/geometry changed')
  expected={'motion_source_id':p['motion_source_id'],'original_pair_id':p['original_pair_id'],'group':p['group'],'source_is_new_motion_content':False,'identity':p['identity'],'video':p['source']['video'],'portrait':p['portrait'],'provenance':p['source']['provenance'],'video_sha256':p['source']['video_sha256'],'portrait_sha256':p['portrait_sha256'],'provenance_sha256':p['source']['provenance_sha256'],'prompt':prompt,'prompt_file':p['prompt_file'],'prompt_sha256':p['prompt_sha256'],'reference_image_expected':p['reference_image_expected'],'valid_frame_count':147,'evaluation_indices':list(range(0,147,3)),'evaluation_crop_xywh':[0,0,1152,768]}
  require(all(case.get(k)==v for k,v in expected.items()),'frozen pair input or prompt changed: '+pair)
  parent=root/case['parent_graph'];require(case['parent_graph']=='configs/parent_graphs/r72_fitness__game_man_5_seed2026101701_p1.json' and sha(parent)==case['parent_graph_sha256'],'parent graph changed')
  graph=root/'configs/graphs'/(run+'.json');require(read(graph)==expected_graph(root,case),'graph numerical inputs changed')
  jobs[run]={'case':case,'source_id':pair,'pair_key':pair,'motion_source_id':p['motion_source_id'],'seed':case['seed'],'arm':arm,'graph_sha256':sha(graph)}
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
 row=validate_job(run_id);forced=row['arm']=='forced';require(Path(audit_dir)==REMOTE/'audit/router','router audit differs')
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
