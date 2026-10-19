"""One actual-parent fixed-schedule control; no new numerical operator."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('short_0358',)
ARMS=('extended',)
RUN_ID='r97_short_0358_seed2026101701_extended'
GEOMETRY={'width':1312,'height':736,'frames':107,'fps':24}
SHAPES={'video':(1,24,32,46,82),'audio':(1,32,2,178)}
def read(path):return json.loads(Path(path).read_text())
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)
REMOTE=Path(read(ROOT/'configs/runtime.json')['remote_root'])
def geometry(case):
 require(case['source_id']=='short_0358','unregistered source');return dict(GEOMETRY)
def latent_shapes(case):geometry(case);return dict(SHAPES)
def routing_layout(case):
 geometry(case);sizes=[(1,4,4,4,4)[i%5] for i in range(32)];cursor=0;stop=0
 for i,n in enumerate(sizes):
  if cursor<105:stop=i+1
  cursor+=n
 return {'latent_interval_half_open':[0,stop],'position_bin_coverage_inclusive':[0,sum(sizes[:stop])-1],'pixel_interval_inclusive':[0,104],'total_latent_bins':32,'pure_pad_bins':list(range(stop,32)),'frame_rows':943}
def expected_graph(root,case):
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);g=copy.deepcopy(read(root/'design/R89_ACTUAL/forced_graph.json'))
 for node,key,suf in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/suf)
 g['5']['inputs']['run_id']='r97_short_0358_shared';g['51']['inputs']['source_run_id']='r97_short_0358_shared'
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=RUN_ID
 g['6']['inputs']['pair_id']='r97_short_0358_seed2026101701';g['14']['inputs']['filename_prefix']=RUN_ID
 g['50']['inputs']['step_end']=20
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');b=read(root/'configs/parent_bindings.json')
 require(s['case_order']==[RUN_ID] and s['arms']==['extended'] and len(s['cases'])==1 and s['source_ids']==list(SOURCES),'single output registry changed')
 require(read(root/'configs/queue.json')=={'jobs':[RUN_ID],'finalize':True},'single output must finalize')
 require(sha(root/'design/CASE_DEFINITION.json')==b['definition_sha256'],'case definition changed')
 case=s['cases'][0];require(case==read(root/'design/CASE_DEFINITION.json'),'case differs from frozen actual parent definition')
 require(case['run_id']==RUN_ID and case['source_id']=='short_0358' and case['seed']==2026101701 and case['arm']=='extended' and case['geometry']==GEOMETRY and case['valid_frame_count']==105 and case['prompt_version']=='P1-local-v1','case identity/geometry changed')
 require(case['reference_video_count']==1 and case['reference_image_count']==0,'reference modalities changed')
 parent=root/'design/R89_ACTUAL/forced_graph.json';p=read(parent)
 require(sha(parent)==b['parent_graph_sha256']==case['parent_graph_sha256'],'actual fixed graph changed')
 require(case['prompt']==p['5']['inputs']['prompt']==(root/'configs/prompts/short_0358.txt').read_text(),'actual P1 text differs')
 for rel,digest in b['parent_records'].items():require(sha(root/'design/R89_ACTUAL'/rel)==digest,'frozen parent record changed: '+rel)
 require(sha(root/'design/R89_ACTUAL/PAIR_RUNTIME_GATE.json')==b['parent_gate_sha256']=='963d11b3e95861cf55801ad037140794fbaa58159f0b5522eebdfcdccccc924c','actual parent gate changed')
 gate=read(root/'design/R89_ACTUAL/PAIR_RUNTIME_GATE.json');require(gate['passed'] is True and all(gate['checks'].values()),'parent gate not passed')
 require(sha(root/'design/EVENT_REVIEW.json')==b['event_review_sha256']==s['evaluation']['event_review_sha256'] and s['evaluation']['manual_boundaries_used_for_guidance'] is False,'evaluation-only review changed')
 graph=root/'configs/graphs'/(RUN_ID+'.json');require(read(graph)==expected_graph(root,case),'graph differs outside step_end/run/path updates')
 return {RUN_ID:{'case':case,'source_id':'short_0358','seed':2026101701,'arm':'extended','graph_sha256':sha(graph)}},[RUN_ID]
def validate_job(run,root=ROOT):
 root=Path(root);jobs,_=registry(root);require(run in jobs,'unregistered run');row=jobs[run]
 for key in ('video','provenance'):
  name=row['case'][key];p=root/'inputs'/name
  require(Path(name).name==name and not p.is_symlink() and sha(p)==row['case'][key+'_sha256'],'input changed: '+key)
 return row
def audit_dir(value):
 p=Path(value);require(p.is_absolute() and p.resolve()==REMOTE/'audit','audit root differs');return p
def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
 validate_job(run_id);require(Path(audit_dir)==REMOTE/'audit/router','router audit differs')
 require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==('mass_preserve',1.,0,0,0,104,0,50,6,20),'extended route differs')
def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True);path=folder/case['video']
 if not path.exists():
  with (root/'inputs'/case['video']).open('rb') as before,path.open('xb') as after:shutil.copyfileobj(before,after)
 require(not path.is_symlink() and sha(path)==case['video_sha256'],'loader source changed');return row
