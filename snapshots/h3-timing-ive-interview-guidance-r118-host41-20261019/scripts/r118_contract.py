"""One fixed-guidance output with recorded R96 Native provenance."""
import copy, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('long_0047',)
VALID={'long_0047':97}
GEOMETRY={'width':1312,'height':736,'frames':107,'fps':24}
SHAPES={'video':(1,24,32,46,82),'audio':(1,32,2,178)}
ROUTER={'mode':'mass_preserve','alpha':1.,'blocks':[0,50],'steps':[6,15],'physical_frames':'0..96 inclusive','routed_calls':450}
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)
def run_id(source):require(source in SOURCES,'unknown source');return 'r118_'+source+'_seed2026101701_forced'
def geometry(case):require(case['source_id'] in SOURCES,'unknown source');return dict(GEOMETRY)
def latent_shapes(case):geometry(case);return dict(SHAPES)
def routing_layout(case):
 geometry(case)
 return {'latent_interval_half_open':[0,29],'position_bin_coverage_inclusive':[0,97],'pixel_interval_inclusive':[0,96],'total_latent_bins':32,'pure_pad_bins':[29,30,31],'frame_rows':943}
def verify_historical_native(root=ROOT):
 root=Path(root);b=read(root/'configs/parent_bindings.json')['long_0047']
 for rel,digest in b['evidence_files'].items():require(sha(root/rel)==digest,'historical evidence changed: '+rel)
 d=root/'design/historical_native';gate=read(d/'NATIVE_RUNTIME_GATE.json');g=read(d/'native_graph.json');job=read(d/'native_job.json');history=read(d/'native_history.json');collection=read(d/'COLLECTION.json')
 require(gate['passed'] is True and all(gate['checks'].values()),'historical Native gate failed')
 require(gate['runs']['native']['run_id']==b['run_id'] and gate['runs']['native']['video']['sha256']==b['video']['sha256']==collection['files']['native.mp4'],'historical Native media identity differs')
 require(history['status']['status_str']=='success' and history['status']['completed'] is True and history['prompt'][2]==g and history['prompt'][1]==job['prompt_id'] and job['status']=='success','historical Native history failed')
 require(job['service_pid']==gate['service_owner']['pid'] and job['service_identity']==gate['service_owner']['identity'],'historical Native service differs')
 require(sha(d/'native_graph.json')==b['graph_sha256'] and sha(d/'NATIVE_RUNTIME_GATE.json')==collection['gate_sha256'],'historical graph/gate binding differs')
 return {'passed':True,'run_id':b['run_id'],'video':b['video'],'gate_sha256':sha(d/'NATIVE_RUNTIME_GATE.json'),'runtime':b['runtime'],'comparison_scope':'Historical Native reused; runtime differences recorded without additional environment experiment.'}
def definitions(root=ROOT):
 root=Path(root);b=read(root/'configs/parent_bindings.json')['long_0047'];p=root/'design/CASE_DEFINITION.json'
 require(sha(p)==b['definition_sha256'],'case definition changed');return [read(p)]
def expected_graph(root,case):
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);g=copy.deepcopy(read(root/case['parent_graph']));run=run_id(case['source_id']);shared='r118_long_0047_shared'
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/suffix)
 g['5']['inputs']['run_id']=shared;g['51']['inputs']['source_run_id']=shared
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']='r118_long_0047_seed2026101701';g['14']['inputs']['filename_prefix']=run;g['50']['inputs']['mode']='mass_preserve'
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');order=[run_id(SOURCES[0])];b=read(root/'configs/parent_bindings.json')['long_0047']
 require(s['source_ids']==list(SOURCES) and s['arms']==['forced'] and s['case_order']==order and s['cases']==definitions(root),'single guided registry changed')
 require(read(root/'configs/queue.json')=={'jobs':order,'finalize':True},'queue changed')
 require(s['evaluation']['rules_sha256']==sha(root/'design/SOURCE_REVIEW_PLAN.json')==b['source_plan_sha256'],'source event plan changed')
 verify_historical_native(root);case=s['cases'][0];run=order[0];parent=root/case['parent_graph'];g=read(parent)
 require(case['source_id']==SOURCES[0] and case['run_id']==run and case['arm']=='forced' and case['seed']==2026101701 and case['parent_run']==b['run_id'],'identity changed')
 require(case['geometry']==GEOMETRY and case['valid_frame_count']==97 and case['evaluation_indices']==list(range(97)) and case['evaluation_crop_xywh']==[16,8,1280,720],'evaluation geometry changed')
 require(case['reference_video_count']==1 and case['reference_image_count']==0,'reference count changed')
 require(case['prompt']==g['5']['inputs']['prompt']==(root/'configs/prompts/long_0047.txt').read_text() and sha(root/'configs/prompts/long_0047.txt')==b['prompt_sha256'],'R96 prompt changed')
 require(sha(parent)==b['graph_sha256']==case['parent_graph_sha256'],'R96 graph changed')
 graph=root/'configs/graphs'/(run+'.json');require(read(graph)==expected_graph(root,case),'graph changed outside routing mode and run paths')
 return {run:{'case':case,'source_id':SOURCES[0],'seed':2026101701,'arm':'forced','graph_sha256':sha(graph)}},order

def validate_job(run,root=ROOT):
 root=Path(root);jobs,_=registry(root);require(run in jobs,'unregistered run');row=jobs[run]
 for key in ('video','provenance'):
  name=row['case'][key];path=root/'inputs'/name
  require(Path(name).name==name and not path.is_symlink() and sha(path)==row['case'][key+'_sha256'],'input changed: '+key)
 return row

def audit_dir(value):
 p=Path(value);require(p.is_absolute() and p.resolve()==Path(read(ROOT/'configs/runtime.json')['remote_root'])/'audit','audit root changed');return p

def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
 validate_job(run_id);remote=Path(read(ROOT/'configs/runtime.json')['remote_root'])
 require(Path(audit_dir)==remote/'audit/router','router audit changed')
 require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==('mass_preserve',1.,0,0,0,96,0,50,6,15),'fixed routing changed')

def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True);target=folder/case['video']
 if not target.exists():
  with (root/'inputs'/case['video']).open('rb') as a,target.open('xb') as b:shutil.copyfileobj(a,b)
 require(not target.is_symlink() and sha(target)==case['video_sha256'],'loader input changed');return row
