"""Read-only media consumer, with actual Native execution and historical-input binding."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REQUIRED_CHECKS=('producer_seal','same_host_numerical_runtime','actual_runtime_device','actual_history','actual_service_generation','actual_condition_snapshot','all_conditions_equal_actual_Native','pre_DiT_condition_gate','actual_parent_eight_condition_tensors','actual20NFE20Euler450routes','valid_physical_support','actual_reference_geometry','sampled_finite','same_sampler_grid_and_initial_packed_noise','AV_prediction_prefix_0_5_bitwise_equal','actual_raw_AV_noise_equal_Native','output_geometry')
def require(ok,message):
 if not ok:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def bound(p):return {'file':str(Path(p).resolve()),'sha256':sha(p)}
def config():return read(ROOT/'configs/contract.json')
def save(p,value,replace=False):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if not replace:require(not p.exists(),'receipt already exists: '+str(p))
 t=p.with_name(p.name+'.tmp.'+str(os.getpid()));t.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');t.replace(p)
def parent():return read(ROOT/'configs/parent_bindings.json')[config()['source_id']]
def validate_static():
 c=config()
 for rel,digest in read(ROOT/'CONSUMER_FREEZE.json')['files'].items():require(sha(ROOT/rel)==digest,'consumer file changed: '+rel)
 for row in c['media'].values():require(sha(row['file'])==row['sha256'],'parent media changed')
 b=parent()
 for name,digest in b['local_snapshot_hashes'].items():require(sha(ROOT/'configs/parent'/name)==digest,'parent snapshot changed')
 gate=read(ROOT/'configs/parent/PARENT_ACTUAL_GATE.json');require(gate['passed'] is True and all(v is True for v in gate['checks'].values()),'actual R98 Native gate failed')
 require(gate['run_id']==b['run_id']==c['parent_run_id'] and gate['video']['sha256']==c['media']['native']['sha256']==b['native_video']['sha256'],'parent Native differs')
 require((gate['valid_frames'],gate['NFE'],gate['routed_blocks'])==(147,20,0),'parent counts differ')
 graph=read(ROOT/'configs/parent/PARENT_GRAPH.json');hist=read(ROOT/'configs/parent/PARENT_HISTORY.json');job=read(ROOT/'configs/parent/PARENT_JOB.json')
 require(hist['status']['completed'] is True and hist['status']['status_str']=='success' and hist['prompt'][2]==graph and hist['prompt'][1]==job['prompt_id'] and job['status']=='success','parent history differs')
 return c

def verify_gate(g):
 c=config();b=parent();require(g.get('schema')=='r101-historical-native-paired-runtime-gate-v1' and g.get('passed') is True,'actual paired gate pending/failed')
 require(g.get('source_id')==c['source_id'] and g.get('prompt_version')=='actual-parent-P1-verbatim','actual source/prompt differs')
 checks=g.get('checks',{});require(checks and all(v is True for v in checks.values()) and all(checks.get(k) is True for k in REQUIRED_CHECKS),'mandatory actual checks missing/failed')
 require(g['runtime_profile_sha256']==c['producer_runtime_sha256'] and g['runtime_profile']==read(ROOT/'configs/producer_runtime.json'),'actual runtime differs')
 require((g['valid_frames'],g['total_frames'],g['fps'],g['evaluation_crop_xywh'])==(147,158,24,[0,0,1152,768]),'timeline or crop differs')
 n=g['runs']['native'];f=g['runs']['forced']
 require(n['run_id']==b['run_id'] and n['parent_root']==b['producer_remote'] and n['video']==b['native_video'] and n['historical_parent'] is True,'actual paired Native differs')
 require(f['run_id']==c['run_id'],'forced run differs')
 for r,routes in [(n,0),(f,450)]:
  require((r['valid_frames'],r['NFE'],r['Euler_updates'],r['routed_blocks'])==(147,20,20,routes),'actual frame/count/route differs')
  p=r['video']['properties'];require((p['width'],p['height'],int(p['nb_read_frames']),p['avg_frame_rate'])==(1152,768,158,'24/1'),'actual video geometry differs')
 proof=g['parent_evidence'][c['source_id']];require(proof['passed'] is True and proof['large_files_verified'] is True and proof['parent_run']==b['run_id'] and proof['frozen_gate_raw_sha256']==b['gate']['sha256'],'parent verification missing')
 require(g['first_allowed_prediction_divergence_index']==6,'prefix divergence index changed')
 rows=g['prefix_tensor_comparison'];require(len(rows)==6,'six actual prefix comparisons required')
 for ix,row in enumerate(rows):
  require(row['step_zero_based']==ix and row['model_call_one_based']==ix+1 and row['video'] is True and row['audio'] is True and row['parent_file_sha256']==b['first_six_predictions'][ix]['sha256'],'actual AV prefix mismatch')
  require(len(row['current_file_sha256'])==64,'current prefix hash absent')
 blobs=g['parent_condition_tensor_files'];require(len(blobs)==8 and {x['file']:x['sha256'] for x in blobs}=={x['file']:x['gate_file_sha256'] for x in b['condition_tensors']},'eight actual parent conditions differ')
 safe_output(f['video']['file']);return g

def safe_output(path):
 p=Path(path);r=Path(config()['producer_remote']);require(p.is_absolute() and '..' not in p.parts and p.is_relative_to(r/'output'),'output outside producer');return p

def verify_small_evidence(path,owner,g):
 c=config();path=Path(path);job=read(path/'job.json');hist=read(path/'history.json');graph=read(path/'graph.json')
 require(job.get('name')==c['run_id'] and job.get('status')=='success','job incomplete/different')
 require(job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'],'job generation differs')
 require(job['graph_sha256']==c['graph_sha256']==sha(path/'graph.json') and graph==read(ROOT/'configs/producer_graph.json'),'actual graph differs')
 require(hist['status']['completed'] is True and hist['status']['status_str']=='success' and hist['prompt'][1]==job['prompt_id'] and hist['prompt'][2]==graph,'actual history is not the bound successful graph')
 images=hist['outputs']['14']['images'];require(len(images)==1 and images[0].get('type')=='output','single output required');entry=images[0]
 rel=Path(entry.get('subfolder',''))/entry['filename'];require(not rel.is_absolute() and '..' not in rel.parts,'unsafe history output')
 require(str(Path(c['producer_remote'])/'output'/rel)==g['runs']['forced']['video']['file'],'history output differs')
 require(sha(path/'forced.mp4')==g['runs']['forced']['video']['sha256'],'output bytes differ')

def verify_intake():
 c=validate_static();path=ROOT/'incoming';receipt=read(path/'COLLECTION.json');binding=read(ROOT/'audit/EXECUTION_BINDING.json')
 require(receipt['execution_binding_sha256']==sha(ROOT/'audit/EXECUTION_BINDING.json'),'intake attempt changed')
 for name,digest in receipt['files'].items():require(sha(path/name)==digest,'intake file changed: '+name)
 gate=verify_gate(read(path/'PAIR_RUNTIME_GATE.json'));verify_small_evidence(path,binding['owner'],gate);return gate
