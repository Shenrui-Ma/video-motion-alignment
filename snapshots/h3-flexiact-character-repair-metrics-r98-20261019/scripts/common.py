"""Read-only media consumer, with actual Native execution and historical-input binding."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REQUIRED_CHECKS=('producer_seal','actual_runtime_device','historical_parent_evidence_unchanged','actual_history','actual_service_generation','actual_P1_condition_snapshot','actual_host9_input_pixels','current_clean_reference_snapshot_consistency','Qwen_physical_sampling_unchanged','actual20NFE20Euler0routes','actual_native_layout','actual_reference_geometry','sampled_finite','actual_noise_cache','raw_initial_AV_noise_matches_R66')
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
def validate_static():
 c=config()
 for rel,digest in read(ROOT/'CONSUMER_FREEZE.json')['files'].items():require(sha(ROOT/rel)==digest,'consumer file changed: '+rel)
 for row in c['media'].values():require(sha(row['file'])==row['sha256'],'historical media changed')
 gate=read(ROOT/'configs/historical/PAIR_RUNTIME_GATE.json');require(gate['passed'] and all(v is True for v in gate['checks'].values()),'historical actual gate failed')
 old=gate['runs']['native'];require(old['video']['sha256']==c['media']['old_native']['sha256'] and old['NFE']==20 and old['routed_blocks']==0 and old['valid_frames']==147,'historical Native differs')
 graph=read(ROOT/'configs/historical/native_graph.json');hist=read(ROOT/'configs/historical/native_history.json');job=read(ROOT/'configs/historical/native_job.json')
 require(hist['status']['completed'] is True and hist['status']['status_str']=='success' and hist['prompt'][2]==graph and hist['prompt'][1]==job['prompt_id'] and job['status']=='success','historical evidence differs')
 return c

def verify_gate(g):
 c=config();require(g.get('schema')=='r98-character-repair-native-runtime-gate-v1' and g.get('passed') is True,'actual Native gate pending/failed')
 require(g.get('run_id')==c['run_id'] and g.get('source_id')==c['source_id'] and g.get('prompt_version')==c['prompt_version'],'actual run differs')
 checks=g.get('checks',{});require(checks and all(v is True for v in checks.values()) and all(checks.get(k) is True for k in REQUIRED_CHECKS),'mandatory actual checks missing/failed')
 require(g['runtime_profile_sha256']==c['producer_runtime_sha256'] and g['runtime_profile']==read(ROOT/'configs/producer_runtime.json'),'actual runtime differs')
 require(g['historical_R66_gate_sha256']==sha(ROOT/'configs/historical/PAIR_RUNTIME_GATE.json'),'historical parent gate differs')
 require((g['valid_frames'],g['NFE'],g['Euler_updates'],g['routed_blocks'])==(147,20,20,0) and g['evaluation_indices']==list(range(0,147,3)),'actual frames/counts differ')
 p=g['video']['properties'];require((p['width'],p['height'],int(p['nb_read_frames']),p['avg_frame_rate'])==(1152,768,158,'24/1'),'actual video geometry differs')
 safe_output(g['video']['file']);return g

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
 require(str(Path(c['producer_remote'])/'output'/rel)==g['video']['file'],'history output differs')
 require(sha(path/'native.mp4')==g['video']['sha256'],'output bytes differ')

def verify_intake():
 c=validate_static();path=ROOT/'incoming';receipt=read(path/'COLLECTION.json');binding=read(ROOT/'audit/EXECUTION_BINDING.json')
 require(receipt['execution_binding_sha256']==sha(ROOT/'audit/EXECUTION_BINDING.json'),'intake attempt changed')
 for name,digest in receipt['files'].items():require(sha(path/name)==digest,'intake file changed: '+name)
 gate=verify_gate(read(path/'NATIVE_RUNTIME_GATE.json'));verify_small_evidence(path,binding['owner'],gate);return gate
