"""Ordinary R100 P1 versus exact single-sentence prompt, with unchanged visual inputs."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=PAIR_KEYS=('short_0114',)
ARMS=('native',)
RUN_ID='r110_short_0114_seed2026101701_native'
GEOMETRY={'width':1312,'height':736,'frames':107,'fps':24}
SHAPES={'video':(1,24,32,46,82),'audio':(1,32,2,178)}
P1_SHA=hashlib.sha256(b'Edit <Video 1> by changing only the basketball into a neon-lit basketball. Keep the original player, dribbling actions, camera framing, scene, and timing.').hexdigest()
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
 root=Path(root);a=read(root/'configs/parent_bindings.json');p=root/'design/CASE_DEFINITION.json'
 require(sha(p)==a['definition_sha256'],'case definition changed')
 return [read(p)]
def prompt_values(root=ROOT,pair=SOURCES[0]):
 root=Path(root);require(pair==SOURCES[0],'unexpected source');p=root/'configs/prompts/short_0114_plain.txt'
 require(sha(p)==P1_SHA==read(root/'configs/parent_bindings.json')['p1_file_sha256'],'exact short prompt bytes changed')
 return p.read_text()
def expected_graph(root,case):
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);g=copy.deepcopy(read(root/case['parent_graph']))
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/suffix)
 g['5']['inputs'].update(prompt=prompt_values(root),run_id='r110_'+SOURCES[0]+'_shared');g['51']['inputs']['source_run_id']='r110_'+SOURCES[0]+'_shared'
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=RUN_ID
 g['6']['inputs']['pair_id']='r110_'+SOURCES[0]+'_seed2026101701';g['14']['inputs']['filename_prefix']=RUN_ID
 return g
def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');require(s['case_order']==[RUN_ID] and len(s['cases'])==1 and s['arms']==['native'] and s['source_ids']==s['pair_keys']==list(SOURCES),'single Native registry changed')
 require(read(root/'configs/queue.json')=={'jobs':[RUN_ID],'finalize':True},'single Native must finalize')
 case=s['cases'][0];definition=definitions(root)[0];a=read(root/'configs/parent_bindings.json');parent=root/case['parent_graph']
 require(case['run_id']==RUN_ID and case['source_id']==case['pair_key']==SOURCES[0] and case['seed']==2026101701 and case['geometry']==GEOMETRY and case['valid_frame_count']==105 and case['arm']=='native' and case['prompt_version']=='bound-short-v1','Native geometry/seed/run changed')
 require(case['prompt']==prompt_values(root) and case['prompt_sha256']==P1_SHA,'P1 actual prompt changed')
 require(sha(parent)==case['parent_graph_sha256']==a['r100_native_graph_sha256'],'actual R100 parent graph changed')
 for key in ('video','provenance'):
  require(case[key]==definition['source'][key] and case[key+'_sha256']==definition['source'][key+'_sha256'],'original source binding differs')
 require(case['reference_image_count']==0 and case['reference_video_count']==1,'reference count changed')
 require(read(root/'design/R100_ACTUAL/PAIR_RUNTIME_GATE.json')['passed'] is True,'actual R100 Native/forced integrity pending')
 graph=root/'configs/graphs'/(RUN_ID+'.json');require(read(graph)==expected_graph(root,case),'graph differs outside allowed prompt/run/path updates')
 for name,digest in a['actual_record_sha256'].items():require(sha(root/'design/R100_ACTUAL'/name)==digest,'R100 actual evidence changed')
 validate_r109_comparator(root,read(graph))
 return {RUN_ID:{'case':case,'source_id':SOURCES[0],'pair_key':SOURCES[0],'motion_source_id':SOURCES[0],'seed':2026101701,'arm':'native','graph_sha256':sha(graph)}},[RUN_ID]

def validate_r109_comparator(root,current_graph):
 root=Path(root);binding=read(root/'configs/parent_bindings.json')['r109_comparator'];folder=root/'design/R109_ACTUAL'
 for name,digest in binding['records'].items():require(sha(folder/name)==digest,'actual R109 record changed: '+name)
 history=read(folder/'history.json');gate=read(folder/'gate.json');previous=read(folder/'graph.json')
 require(history['status']['completed'] and history['status']['status_str']=='success' and history['prompt'][2]==previous,'R109 actual graph/history differ')
 require(gate['passed'] and gate['video']['sha256']==binding['video_sha256'] and read(folder/'COMPLETE.json')['GPU_released'] and read(folder/'ROOT_EXIT_RECEIPT.json')['passed'],'R109 actual completion/release pending')
 def normalized(g):
  g=copy.deepcopy(g)
  for node,key in [('5','prompt'),('5','run_id'),('51','source_run_id'),('6','pair_id'),('14','filename_prefix')]+[(n,'run_id') for n in ('6','50','51','52')]+[(n,k) for n,k in [('5','audit_dir'),('6','audit_dir'),('50','audit_dir'),('51','source_audit_dir'),('52','output_dir')]]:g[node]['inputs'][key]='ADMIN_OR_PROMPT'
  return g
 require(normalized(previous)==normalized(current_graph),'R109 comparison changed outside prompt/admin fields')
 runtime=read(root/'configs/runtime.json');oldruntime=read(folder/'runtime.json')
 for k in ('host','core','python','dependencies','models','kj_nodes','reserve_vram','memory_mode','gpu_uuid','expected_gpu_index'):require(runtime[k]==oldruntime[k],'R109 numerical runtime differs: '+k)
 return binding
def validate_job(run,root=ROOT):
 root=Path(root);jobs,_=registry(root);require(run in jobs,'unknown run');row=jobs[run]
 for key in ('video','provenance'):
  case=row['case'];p=root/'inputs'/case[key];require(Path(case[key]).name==case[key] and not p.is_symlink() and sha(p)==case[key+'_sha256'],'input changed: '+key)
 return row
def audit_dir(value):
 p=Path(value);require(p.is_absolute() and p.resolve()==REMOTE/'audit','audit root differs');return p
def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
 validate_job(run_id);require(Path(audit_dir)==REMOTE/'audit/router','router audit differs')
 require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==('native',1.,0,0,0,104,0,50,6,15),'Native-only router parameters differ')
def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True)
 for key in ('video',):
  path=folder/case[key]
  if not path.exists():
   with (root/'inputs'/case[key]).open('rb') as before,path.open('xb') as after:shutil.copyfileobj(before,after)
  require(not path.is_symlink() and sha(path)==case[key+'_sha256'],'loader input changed')
 return row
