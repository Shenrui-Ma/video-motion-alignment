"""Two same-host operators, with a recorded historical Native reference."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('long_0174',)
ARMS=('fixed_one_bin','matched_one_bin')
SEED=2026101701
PAIR_ID='r115_long_0174_seed2026101701'
SHARED_ID='r115_long_0174_shared'
RUNS=tuple(PAIR_ID+'_'+a for a in ARMS)
GEOMETRY={'width':1312,'height':736,'frames':158,'fps':24}
SHAPES={'video':(1,24,47,46,82),'audio':(1,32,2,263)}
VALID=145
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def run_id(arm):
 require(arm in ARMS,'unknown spatial arm');return PAIR_ID+'_'+arm
def geometry(case):return dict(GEOMETRY)
def latent_shapes(case):return dict(SHAPES)
def routing_layout(case):
 return {'latent_interval_half_open':[0,43],'position_bin_coverage_inclusive':[0,144],'pixel_interval_inclusive':[0,144],'total_latent_bins':47,'pure_pad_bins':[43,44,45,46],'frame_rows':943}
def expected_graph(root,case):
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);g=copy.deepcopy(read(root/case['parent_graph']));run=run_id(case['arm'])
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/suffix)
 g['5']['inputs']['run_id']=SHARED_ID;g['51']['inputs']['source_run_id']=SHARED_ID
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']=PAIR_ID;g['14']['inputs']['filename_prefix']=run
 g['50']['inputs'].update(mode=case['arm'],alpha=1.,radius=0,time_offset=0,start_frame=0,end_frame=144,block_start=0,block_end=50,step_start=6,step_end=15)
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');cases=read(root/'design/CASE_DEFINITIONS.json')
 require(s['cases']==cases and s['arms']==list(ARMS) and s['case_order']==list(RUNS) and s['seeds']==[SEED],'scientific registry changed')
 require(read(root/'configs/queue.json')=={'jobs':list(RUNS),'finalize':True},'queue changed')
 require(len(cases)==2,'two new runs required');jobs={}
 for arm,c in zip(ARMS,cases):
  require(c['run_id']==run_id(arm) and c['arm']==arm and c['seed']==SEED and c['source_id']=='long_0174','run/arm/seed changed')
  require(c['geometry']==GEOMETRY and c['valid_frame_count']==VALID and c['evaluation_crop_xywh']==[16,8,1280,720],'geometry changed')
  require(c['reference_image_count']==0 and c['reference_video_count']==1,'modality changed')
  require(c['prompt']==(root/'configs/prompts/long_0174.txt').read_text()==read(root/c['parent_graph'])['5']['inputs']['prompt'],'prompt changed')
  require(sha(root/c['parent_graph'])==c['parent_graph_sha256'],'original graph changed')
  f=root/'configs/graphs'/(c['run_id']+'.json');require(read(f)==expected_graph(root,c),'graph changed beyond registered run/path/operator')
  jobs[c['run_id']]={'case':c,'source_id':'long_0174','arm':arm,'seed':SEED,'graph_sha256':sha(f)}
 return jobs,list(RUNS)
def validate_job(run,root=ROOT):
 root=Path(root);jobs,_=registry(root);require(run in jobs,'unknown run');row=jobs[run]
 for k in ('video','provenance'):
  c=row['case'];p=root/'inputs'/c[k];require(Path(c[k]).name==c[k] and not p.is_symlink() and sha(p)==c[k+'_sha256'],'input changed: '+k)
 return row
def audit_dir(value):
 p=Path(value);remote=Path(read(ROOT/'configs/runtime.json')['remote_root']);require(p.is_absolute() and p.resolve()==remote/'audit','audit root changed');return p
def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);c=row['case'];folder=root/'input';folder.mkdir(exist_ok=True);p=folder/c['video']
 if not p.exists():
  with (root/'inputs'/c['video']).open('rb') as before,p.open('xb') as after:shutil.copyfileobj(before,after)
 require(not p.is_symlink() and sha(p)==c['video_sha256'],'loader input changed');return row

def correspondence_configuration(run,root=ROOT):
 root=Path(root);row=validate_job(run,root);remote=Path(read(root/'configs/runtime.json')['remote_root'])
 m=str(remote/'audit/x0'/run/'manifest.json')
 conf={'root':str(remote/'audit/correspondence_banks'/run),'valid_bins':43,'spatial_grid':[23,41],'prefix_manifest':m,'paired_prefix_manifest':m}
 # First operator verifies its own files; second must match the actual first trajectory.
 if row['arm']=='matched_one_bin':
  conf['paired_root']=str(remote/'audit/correspondence_banks'/RUNS[0]);conf['paired_prefix_manifest']=str(remote/'audit/x0'/RUNS[0]/'manifest.json')
 return conf

def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
 row=validate_job(run_id);remote=Path(read(ROOT/'configs/runtime.json')['remote_root']);require(Path(audit_dir)==remote/'audit/router','router directory changed')
 require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==(row['arm'],1.,0,0,0,144,0,50,6,15),'operator changed')
 root_gpu_review()
def root_gpu_review(root=ROOT):
 root=Path(root);r=read(root/'audit/GPU_DEPLOYMENT_REVIEW.json')
 require(r.get('approved') is True and r.get('reviewer')=='root' and r.get('scope')=='r115-two-arm-host9-gpu-execution' and r.get('producer_seal_sha256')==sha(root/'deploy_manifest.json'),'root GPU review absent/stale')
 return r
