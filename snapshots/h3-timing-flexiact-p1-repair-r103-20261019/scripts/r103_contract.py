"""Two original Flex tasks: P1 Native acceptance, then optional matched fixed guidance."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=PAIR_KEYS=('human2animal_2__game_man_4','chest__game_girl_1')
ARMS=('native','forced');GEOMETRY={'width':1152,'height':768,'frames':158,'fps':24}
SHAPES={'video':(1,24,47,48,72),'audio':(1,32,2,263)}
ROUTER={'mode':'mass_preserve','alpha':1.0,'blocks':[0,50],'steps':[6,15],'physical_frames':'[0,valid_frame_count-1] per source','query_support':'all spatial queries in each position bin overlapping valid physical time; pure-pad bins remain native','native_mask_parameters':'same as forced; mode native'}
def read(path):return json.loads(Path(path).read_text())
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)
REMOTE=Path(read(ROOT/'configs/runtime.json')['remote_root'])
def geometry(case):return dict(GEOMETRY)
def latent_shapes(case):return dict(SHAPES)
def routing_layout(case):return {'latent_interval_half_open':[0,44],'position_bin_coverage_inclusive':[0,148],'pixel_interval_inclusive':[0,146],'total_latent_bins':47,'pure_pad_bins':[44,45,46],'frame_rows':864}
def definitions(root=ROOT):
 root=Path(root);p=root/'design/PAIR_DEFINITIONS.json';a=read(root/'configs/prompt_ancestry.json')
 require(sha(p)==a['pair_definitions_sha256'],'frozen definitions changed')
 d=read(p);require(tuple(x['pair_key'] for x in d['pairs'])==SOURCES,'two task order changed')
 require(sha(root/'design/EVIDENCE.json')==d['design_evidence_sha256'] and sha(root/'design/ACCEPTANCE.json')==d['acceptance_sha256'],'source evidence or acceptance changed')
 require(sha(root/'design/OFFICIAL_REF_EN.txt')==a['official_guide_sha256'],'official guide changed')
 return d['pairs']
def expected_graph(root,case):
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);g=copy.deepcopy(read(root/case['parent_graph']));run=case['run_id'];key=case['pair_key']
 for node,field,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][field]=str(remote/suffix)
 shared='r103_'+key+'_shared';g['5']['inputs'].update(prompt=case['prompt'],run_id=shared);g['51']['inputs']['source_run_id']=shared
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']='r103_'+key+'_seed2026101701';g['14']['inputs']['filename_prefix']=run
 g['21']['inputs']['image']=case['portrait'];g['22']['inputs']['file']=case['video']
 g['50']['inputs'].update(mode='mass_preserve' if case['arm']=='forced' else 'native',alpha=1.,radius=0,time_offset=0,start_frame=0,end_frame=146,block_start=0,block_end=50,step_start=6,step_end=15)
 return g
def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');order=['r103_'+key+'_seed2026101701_'+arm for key in SOURCES for arm in ARMS]
 require(s['case_order']==order and len(s['cases'])==4 and s['source_ids']==s['pair_keys']==list(SOURCES) and s['arms']==list(ARMS),'two paired registry changed')
 require(read(root/'configs/queue.json')=={'jobs':order,'finalize':True},'fixed Native-first queue changed')
 require(s['prepared_input_manifest_sha256']==sha(root/'PREPARED_INPUTS_MANIFEST.json') and s['pair_definitions_sha256']==sha(root/'design/PAIR_DEFINITIONS.json'),'input bindings changed')
 defs=definitions(root);jobs={}
 for i,(case,run) in enumerate(zip(s['cases'],order)):
  p=defs[i//2];key=SOURCES[i//2];arm=ARMS[i%2];prompt=root/p['prompt_file']
  require(sha(prompt)==p['prompt_sha256'] and prompt.read_text()==p['prompt'],'P1 prompt changed')
  require(case['run_id']==run and case['source_id']==case['pair_key']==key and case['arm']==arm and case['seed']==2026101701 and case['geometry']==GEOMETRY and case['prompt_version']=='P1-reference-v1','case geometry/seed/arm changed')
  for k in ('motion_source_id','original_pair_id','group','identity','portrait','portrait_sha256','reference_image_expected','prompt','prompt_file','prompt_sha256','prompt_version','source_is_new_motion_content'):
   require(case[k]==p[k],'case definition changed: '+k)
  for k in ('video','video_sha256','provenance','provenance_sha256'):require(case[k]==p['source'][k],'original source binding changed: '+k)
  require(case['reference_image_count']==case['reference_video_count']==1 and case['valid_frame_count']==147 and case['evaluation_indices']==list(range(0,147,3)) and case['evaluation_crop_xywh']==[0,0,1152,768],'reference count or physical time policy changed')
  require(case['parent_graph']=='configs/parent_graphs/r66_native_template.json' and sha(root/case['parent_graph'])==case['parent_graph_sha256'],'parent numerical graph changed')
  graph=root/'configs/graphs'/(run+'.json');require(read(graph)==expected_graph(root,case),'numerical graph changed')
  jobs[run]={'case':case,'source_id':key,'pair_key':key,'motion_source_id':p['motion_source_id'],'seed':case['seed'],'arm':arm,'graph_sha256':sha(graph)}
 return jobs,order
def validate_job(run,root=ROOT):
 root=Path(root);jobs,_=registry(root);require(run in jobs,'unregistered job');row=jobs[run]
 for key in ('video','portrait','provenance'):
  c=row['case'];p=root/'inputs'/c[key];require(Path(c[key]).name==c[key] and not p.is_symlink() and sha(p)==c[key+'_sha256'],'input changed: '+key)
 prov=read(root/'inputs'/row['case']['provenance']);require(prov['input_to_original']==[i//3 for i in range(147)]+[48]*11,'original49@8 mapping changed')
 return row
def audit_dir(value):
 p=Path(value);require(p.is_absolute() and p.resolve()==REMOTE/'audit','audit root differs');return p
def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
 row=validate_job(run_id);require(Path(audit_dir)==REMOTE/'audit/router','router audit differs')
 require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==('mass_preserve' if row['arm']=='forced' else 'native',1.,0,0,0,146,0,50,6,15),'fixed route parameters changed')
def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);c=row['case'];folder=root/'input';folder.mkdir(exist_ok=True)
 for key in ('video','portrait'):
  p=folder/c[key]
  if not p.exists():
   with (root/'inputs'/c[key]).open('rb') as a,p.open('xb') as b:shutil.copyfileobj(a,b)
  require(not p.is_symlink() and sha(p)==c[key+'_sha256'],'loader source changed')
 return row
