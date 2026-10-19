"""Bound CPU intake for the single R97 schedule control."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REQUIRED_CHECKS=('producer_seal','same_host_numerical_runtime','actual_runtime_device','actual_history','actual_service_generation','actual_condition_snapshot','all_conditions_equal_R89_fixed','historical_condition_blob_files_unchanged','actual20NFE20Euler700routes','same_actual_layout_R89_fixed','valid_physical_support','sampled_finite','same_sampler_grid_and_initial_packed_noise','AV_prediction_prefix_0_14_bitwise_equal','actual_raw_AV_noise_equal_R89_fixed','output_geometry')
def require(ok,message):
 if not ok:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def bound(p):return {'file':str(Path(p).resolve()),'sha256':sha(p)}
def save(p,value):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);require(not p.exists(),'receipt exists: '+str(p))
 temp=p.with_name(p.name+'.tmp.'+str(os.getpid()));temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.link(temp,p);temp.unlink()
def config():return read(ROOT/'configs/contract.json')
def validate_static():
 c=config()
 for name,d in read(ROOT/'CONSUMER_FREEZE.json')['files'].items():require(sha(ROOT/name)==d,'consumer file changed: '+name)
 for row in c['old_media']:require(sha(row['file'])==row['sha256'],'original R89 media changed')
 require(sha(ROOT/'configs/parent_gate.json')==read(ROOT/'configs/parent_bindings.json')['parent_gate_sha256'],'original parent gate changed')
 return c
def safe_path(path,subdir=None):
 p=Path(path);root=Path(config()['producer_remote']);base=root/subdir if subdir else root
 require(p.is_absolute() and '..' not in p.parts and p.is_relative_to(base),'remote path outside expected root');return p
def canonical_gate(g):return hashlib.sha256(json.dumps({k:v for k,v in g.items() if k!='created_unix'},sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def verify_gate(g):
 c=config();parent=read(ROOT/'configs/parent_bindings.json')
 require(g.get('schema')=='r97-schedule-control-runtime-gate-v1' and g.get('passed') is True,'control gate not passed')
 for k in ('run_id','source_id','prompt_version'):require(g.get(k)==c[k],k+' differs')
 checks=g.get('checks');require(isinstance(checks,dict) and all(x is True for x in checks.values()),'failed actual check')
 require(all(checks.get(k) is True for k in REQUIRED_CHECKS),'required actual check missing')
 require(g.get('runtime_profile_sha256')==c['producer_runtime_sha256'] and g.get('runtime_profile')==read(ROOT/'configs/producer_runtime.json'),'actual runtime differs')
 require((g.get('NFE'),g.get('Euler_updates'),g.get('routed_blocks'))==(20,20,700),'actual execution counts differ')
 require(g.get('valid_frames')==105 and g.get('evaluation_crop_xywh')==[16,8,1280,720],'valid interval/crop differs')
 require(g.get('first_allowed_prediction_divergence_index')==15,'divergence interval differs')
 v=g['video'];safe_path(v['file'],'output');p=v['properties']
 require((p['width'],p['height'],int(p['nb_read_frames']),p['avg_frame_rate'])==(1312,736,107,'24/1'),'output geometry differs')
 require(len(v['sha256'])==64,'video SHA missing')
 proof=g.get('parent_evidence',{})
 require(proof.get('passed') is True and proof.get('frozen_gate_raw_sha256')==parent['parent_gate_sha256'],'actual parent evidence differs')
 require(proof.get('gate_canonical_sha256')==canonical_gate(read(ROOT/'configs/parent_gate.json')) and proof.get('ignored_gate_field')=='top-level created_unix only','parent gate semantic binding differs')
 require(proof.get('prefix_file_hashes_verified')==15,'parent prefix was not verified')
 require(g.get('parent_fixed_video')==parent['parent_video'],'parent fixed output differs')
 rows=g.get('prefix_tensor_comparison',[]);require(len(rows)==15,'prefix count differs')
 for i,row in enumerate(rows):
  require(row.get('step_zero_based')==i and row.get('model_call_one_based')==i+1,'prefix order differs')
  require(row.get('video') is True and row.get('audio') is True,'AV prefix differs')
  require(row.get('parent_file_sha256')==parent['parent_snapshots_prefix'][i]['sha256'],'parent x0 binding differs')
  require(len(row.get('current_file_sha256',''))==64,'actual x0 binding absent')
 return g

def verify_small(path,owner,g):
 c=config();job=read(path/'extended_job.json');history=read(path/'extended_history.json');graph=read(path/'extended_graph.json')
 require(job.get('status')=='success' and job.get('name')==c['run_id'],'actual job incomplete')
 require(job.get('service_pid')==owner['pid'] and job.get('service_identity')==owner['identity'],'job generation differs')
 require(job.get('graph_sha256')==c['graph_sha256']==sha(path/'extended_graph.json'),'job graph differs')
 require(history['status']['completed'] is True and history['status']['status_str']=='success' and history['prompt'][1]==job['prompt_id'] and history['prompt'][2]==graph,'history is not exact successful graph')
 images=history['outputs']['14']['images'];require(len(images)==1 and images[0].get('type')=='output','output is not single video')
 entry=images[0];relative=Path(entry.get('subfolder',''))/entry['filename'];require(not relative.is_absolute() and '..' not in relative.parts,'unsafe history output')
 require(str(Path(c['producer_remote'])/'output'/relative)==g['video']['file'],'history output differs')
 require(sha(path/'extended.mp4')==g['video']['sha256'],'actual video SHA differs')
 router=read(path/'extended_router.json')
 require(router.get('run_id')==c['run_id'] and router.get('routed_calls')==700 and router.get('completed_forward_calls')==20 and router.get('routed_by_forward')==[0]*6+[50]*14,'actual router counts differ')
 return g

def verify_intake():
 dest=ROOT/'incoming';receipt=read(dest/'COLLECTION.json');binding=read(ROOT/'audit/EXECUTION_BINDING.json')
 require(receipt['execution_binding_sha256']==sha(ROOT/'audit/EXECUTION_BINDING.json'),'intake execution binding changed')
 for name,digest in receipt['files'].items():require(Path(name).name==name and sha(dest/name)==digest,'intake file changed')
 g=verify_gate(read(dest/'CONTROL_RUNTIME_GATE.json'));verify_small(dest,binding['owner'],g);return g
