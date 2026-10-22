"""One animal color edit, same-host Native then conditional fixed guidance;20 Euler predictions."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('short_0235',)
ARMS=('native','forced')
SOURCE_LENGTHS={'short_0235': (90, 90)}
ROUTER={'mode':'mass_preserve','alpha':1.0,'blocks':[0,50],'steps':[6,15],'physical_frames':'[0,valid_frame_count-1] per source','query_support':'all spatial queries in each position bin overlapping valid physical time; pure-pad bins remain native','native_mask_parameters':'same as forced; mode native'}
def read(path):return json.loads(Path(path).read_text())
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
REMOTE=Path(read(ROOT/'configs/runtime.json')['remote_root'])
def require(ok,message):
 if not ok:raise ValueError(message)
def geometry(case):return dict(width=1312,height=736,frames=SOURCE_LENGTHS[case['source_id']][0],fps=24)
def latent_shapes(case):
 # Exact pinned nodes_minimax_h3.temporal_shape: duration=T/24, audio_t=round(duration*40).
 g=geometry(case);t=g['frames'];return {'video':(1,24,((t-5)//17)*5+2,g['height']//16,g['width']//16),'audio':(1,32,2,round(t/24*40))}
def routing_layout(case):
 t=latent_shapes(case)['video'][2];sizes=[(1,4,4,4,4)[i%5] for i in range(t)];valid=SOURCE_LENGTHS[case['source_id']][1]
 cursor=0;stop=0
 for i,n in enumerate(sizes):
  if cursor<valid:stop=i+1
  cursor+=n
 return {'latent_interval_half_open':[0,stop],'position_bin_coverage_inclusive':[0,sum(sizes[:stop])-1],'pixel_interval_inclusive':[0,valid-1],'total_latent_bins':t,'pure_pad_bins':list(range(stop,t)),'frame_rows':(g:=geometry(case))['height']//32*(g['width']//32)}
def expected_graph(root,case):
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);g=copy.deepcopy(read(root/case['parent_graph']));run=case['run_id'];source=case['source_id'];geom=geometry(case)
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/suffix)
 shared='r136_'+source+'_shared';g['5']['inputs']['run_id']=shared;g['51']['inputs']['source_run_id']=shared
 g['5']['inputs']['prompt']=case['prompt'];g['22']['inputs']['file']=case['video']
 for node in ('5','52'):
  g[node]['inputs'].update(width=geom['width'],height=geom['height'],length=geom['frames'])
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']='r136_'+source+'_seed2026101701';g['14']['inputs']['filename_prefix']=run
 g['50']['inputs'].update(mode='native' if case['arm']=='native' else 'mass_preserve',alpha=1.,radius=0,time_offset=0,start_frame=0,end_frame=case['valid_frame_count']-1,block_start=0,block_end=50,step_start=6,step_end=15)
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');order=['r136_'+source+'_seed2026101701_'+arm for source in SOURCES for arm in ARMS]
 require(s['case_order']==order and len(s['cases'])==2 and s['arms']==list(ARMS) and s['source_ids']==list(SOURCES),'fixed single-source Native-first registry changed')
 q=read(root/'configs/queue.json');require(set(q)=={'jobs','finalize'} and q['jobs']==order and type(q['finalize']) is bool,'fixed paired queue changed')
 for name,digest in read(root/'configs/source_selection_hashes.json').items():require(sha(root/'configs/source_selection'/name)==digest,'frozen source evidence changed')
 selected={x['source_id']:x for x in read(root/'configs/source_selection/SELECTED_SOURCE_MANIFEST.json')['pairs']};prepared={x['pair_id']:x for x in read(root/'PREPARED_INPUTS_MANIFEST.json')['pairs']}
 require(sha(root/'design/INPUT_PLAN.json')==s['input_plan_sha256'] and sha(root/'PREPARED_INPUTS_MANIFEST.json')==s['prepared_input_manifest_sha256'],'input plan/manifest changed')
 require(sha(root/'design/PROPOSAL.json')==s['root_proposal_sha256'] and sha(root/'design/REFERENCE_EVENT_REVIEW_PLAN.json')==s['root_event_review_sha256'],'root source/prompt/review plan changed')
 require(sha(root/'configs/source_selection/SELECTED_SOURCE_MANIFEST.json')==s['source_selection_sha256'],'source selection changed')
 proposal={x['source_id']:x for x in read(root/'design/PROPOSAL.json')['cases']};jobs={}
 for i,(case,run) in enumerate(zip(s['cases'],order)):
  source=SOURCES[i//2];arm=ARMS[i%2];original=selected[source];inputs=prepared[source];promptfile=root/'configs/prompts'/(source+'.txt');frozen=root/'design'/(source+'_actual_prompt.txt')
  require(case['run_id']==run and case['source_id']==source and case['arm']==arm and case['prompt_version']=='IVEBench-edit-with-generic-retention-v1' and case['seed']==2026101701 and case['geometry']==geometry(case) and case['valid_frame_count']==SOURCE_LENGTHS[source][1],'source/arm/seed/prompt/geometry changed')
  require(case['reference_video_count']==1 and case['reference_image_count']==0,'reference scope changed')
  require(sha(promptfile)==sha(frozen)==proposal[source]['prompt_sha256']==s['prompt_sha256'][source]==case['prompt_sha256'],'official prompt bytes changed')
  require(case['prompt']==promptfile.read_text() and case['original_task']==proposal[source]['official_task']==original['official_task'],'prompt or original task changed')
  require(case['prompt'] == (root/'design/GENERIC_RETENTION_TEMPLATE.txt').read_text() and proposal[source]['official_task']['edit_prompt'] in case['prompt'] and all(proposal[source]['official_task'][k] not in case['prompt'] for k in ('source_prompt','target_prompt')),'generic retention template or original edit differs')
  for key in ('video','provenance'):require(case[key+'_sha256']==inputs['files'][key]['sha256'],'frozen input binding changed')
  require(case['evaluation_crop_xywh']==[16,8,1280,720] and case['clip']==original['clip'],'evaluation temporal/spatial scope changed')
  parent=root/case['parent_graph'];require(sha(parent)==case['parent_graph_sha256'],'R88 numerical graph template changed')
  graph=root/'configs/graphs'/(run+'.json');require(read(graph)==expected_graph(root,case),'graph numerical inputs changed')
  jobs[run]={'case':case,'source_id':source,'seed':case['seed'],'arm':arm,'graph_sha256':sha(graph)}
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
 require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==('mass_preserve' if forced else 'native',1.,0,0,0,row['case']['valid_frame_count']-1,0,50,6,15),'fixed route parameters differ')

def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True);path=folder/case['video']
 if not path.exists():
  with (root/'inputs'/case['video']).open('rb') as before,path.open('xb') as after:shutil.copyfileobj(before,after)
 require(not path.is_symlink() and sha(path)==case['video_sha256'],'loader source changed');return row
