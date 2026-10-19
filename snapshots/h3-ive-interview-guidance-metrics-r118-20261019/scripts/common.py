"""Independent R118 provenance, actual execution and exact-release validation."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CHECKS=('producer_seal','actual_runtime_device','forced_history','forced_service','forced_input_pixels_match_R96_source','forced_prepared_RGB_match_R96_source','forced_initial_AV_noise_matches_R96_source','forced_shared_conditions','forced_actual_execution_counts','forced_actual_layout','forced_reference_geometry','forced_sampled_finite','forced_actual_noise_cache')
def require(ok,message):
 if not ok:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def bound(p):return {'file':str(Path(p).resolve()),'sha256':sha(p)}
def save(p,value):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def config():return read(ROOT/'configs/contract.json')
def relative(path):
 p=Path(path);require(not p.is_absolute() and '..' not in p.parts,'unsafe relative path');return p
def remote_relative(path,cfg):
 p=Path(path);root=Path(cfg['producer_remote']);require(p.is_absolute() and '..' not in p.parts and p.is_relative_to(root),'unsafe remote path');return p.relative_to(root)
def verify_static():
 c=config()
 for f,digest in read(ROOT/'CONSUMER_FREEZE.json')['files'].items():require(sha(ROOT/relative(f))==digest,'consumer changed: '+f)
 require(sha(ROOT/'configs/producer_seal.json')==c['producer_seal_sha256'],'producer seal differs')
 require(sha(ROOT/'configs/producer_runtime.json')==c['producer_runtime_sha256'],'producer runtime differs')
 require(sha(c['historical_native']['file'])==c['historical_native']['sha256'],'historical video changed')
 d=ROOT/'configs/historical_native';g=read(d/'NATIVE_RUNTIME_GATE.json');b=read(ROOT/'configs/parent_bindings.json')['long_0047'];collection=read(d/'COLLECTION.json');history=read(d/'native_history.json');job=read(d/'native_job.json')
 require(g['passed'] is True and all(x is True for x in g['checks'].values()),'historical gate failed')
 require(g['runs']['native']['video']['sha256']==collection['files']['native.mp4']==c['historical_native']['sha256'],'historical media binding differs')
 require(history['status']['completed'] is True and history['status']['status_str']=='success' and history['prompt'][2]==read(d/'native_graph.json') and history['prompt'][1]==job['prompt_id'],'historical execution differs')
 require(sha(d/'native_graph.json')==b['graph_sha256'] and sha(d/'NATIVE_RUNTIME_GATE.json')==collection['gate_sha256'],'historical gate/graph differs')
 for role in ('source','provenance'):require(sha(ROOT/c[role]['file'])==c[role]['sha256'],'input changed')
 return c

def verify_gate(g,c):
 require(g.get('schema')=='r118-historical-native-guidance-runtime-gate-v1' and g.get('passed') is True,'actual R118 gate failed')
 require(g.get('source_id')=='long_0047' and g.get('prompt_version')=='P1-local-v1','source/prompt differs')
 checks=g.get('checks',{});require(all(checks.get(x) is True for x in CHECKS) and all(x is True for x in checks.values()),'actual required check failed')
 require(set(g.get('runs',{}))=={'native','forced'} and g['runs']['native']==c['expected_historical_native'],'historical Native provenance differs')
 rt=read(ROOT/'configs/producer_runtime.json');owner=g['service_owner'];require(g['runtime_profile']==rt and g['runtime_profile_sha256']==c['producer_runtime_sha256'],'runtime differs')
 require(owner['gpu_uuid']==rt['gpu_uuid'] and owner['port']==rt['port'] and owner['identity']['uid']==rt['uid'] and str(Path(c['producer_remote'])/'scripts/service_entry.py') in owner['identity']['cmdline'],'service identity differs')
 r=g['runs']['forced'];require(r['run_id']==c['runs']['forced'] and (r['NFE'],r['Euler_updates'],r['routed_blocks'],r['valid_frames'])==(20,20,450,97),'actual new run differs')
 require(r['evaluation_crop_xywh']==[16,8,1280,720],'crop differs');v=r['video'];rel=remote_relative(v['file'],c);require(rel.parts[0]=='output','video outside output');s=v['properties'];require((s['width'],s['height'],s['avg_frame_rate'],int(s['nb_read_frames']))==(1312,736,'24/1',107),'generated geometry differs')
 required={f"configs/graphs/{c['runs']['forced']}.json":sha(ROOT/'configs/graph_forced.json'),f"logs/{c['runs']['forced']}_job.json":r['job_sha256'],f"logs/{c['runs']['forced']}_history.json":r['history_sha256']}
 for rel,digest in r['binding_artifacts'].items():relative(rel);require(len(digest)==64,'invalid artifact digest')
 require(all(r['binding_artifacts'].get(k)==v for k,v in required.items()),'actual graph/job/history binding differs')
 require(len(g['condition_tensor_files'])==6,'condition tensor binding count differs')
 return g

def verify_release(g,complete,release,started,cleanup,gate_sha,c):
 owner=g['service_owner'];require(complete.get('passed') is True and complete.get('GPU_released') is True and complete.get('jobs')==[c['runs']['forced']] and complete.get('remaining')==[],'new output incomplete')
 bound_gate=complete['gates']['long_0047'];require(bound_gate['sha256']==gate_sha and remote_relative(bound_gate['file'],c)==Path('analysis/postrun/long_0047/PAIR_RUNTIME_GATE.json'),'completion gate differs')
 require(release.get('passed') is True and release.get('process_absent') is True and release.get('CUDA_allocation_absent') is True,'release pending')
 require(release['owner']==started['owner']==owner,'service generation differs')
 require(cleanup['pid']==owner['pid'] and cleanup['process_absent'] is True and cleanup['own_compute_absent'] is True,'cleanup differs')

def verify_job(folder,g,c):
 r=g['runs']['forced'];run=c['runs']['forced'];owner=g['service_owner'];graph=read(folder/'forced_graph.json');job=read(folder/'forced_job.json');history=read(folder/'forced_history.json');router=read(folder/'forced_router.json')
 for kind,key in [('job','job_sha256'),('history','history_sha256'),('router','router_file_sha256')]:require(sha(folder/('forced_'+kind+'.json'))==r[key],'actual evidence digest differs')
 require(graph==read(ROOT/'configs/graph_forced.json'),'actual graph differs')
 require(job['status']=='success' and job['name']==run and job['graph_sha256']==sha(folder/'forced_graph.json') and job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'],'actual job differs')
 require(history['status']['completed'] is True and history['status']['status_str']=='success' and history['prompt'][1]==job['prompt_id'] and history['prompt'][2]==graph,'actual history differs')
 outputs=history['outputs']['14']['images'];require(len(outputs)==1 and outputs[0]['type']=='output','ambiguous final output');record=outputs[0];require(relative(record.get('subfolder',''))/relative(record['filename'])==remote_relative(r['video']['file'],c).relative_to('output'),'output path differs')
 expected={'run_id':run,'mode':'mass_preserve','alpha':1.,'radius':0,'time_offset':0,'block_interval_half_open':[0,50],'step_interval_half_open':[6,15],'pixel_interval_inclusive':[0,96],'completed_forward_calls':20,'routed_calls':450,'routed_by_forward':[0]*6+[50]*9+[0]*5,'routed_by_block':[9]*50}
 require(all(router.get(k)==v for k,v in expected.items()),'actual intervention schedule differs')
 require(sha(folder/'forced.mp4')==r['video']['sha256'],'generated media differs')
 for rel,digest in r['binding_artifacts'].items():
  target=folder/'evidence'/relative(rel)
  if target.exists():require(sha(target)==digest,'compact evidence differs')

def verify_collection(folder):
 c=verify_static();folder=Path(folder);receipt=read(folder/'COLLECTION.json');require(receipt['passed'] is True and receipt['consumer_freeze_sha256']==sha(ROOT/'CONSUMER_FREEZE.json'),'collection not bound')
 require(receipt['roles']==['source','native','forced'] and receipt['valid_frames']==97,'collection domain differs')
 for f,digest in receipt['files'].items():require(sha(folder/relative(f))==digest,'collected artifact changed')
 g=read(folder/'PAIR_RUNTIME_GATE.json');verify_gate(g,c);verify_job(folder,g,c);verify_release(g,read(folder/'COMPLETE.json'),read(folder/'ROOT_EXIT_RECEIPT.json'),read(folder/'STARTED.json'),read(folder/'cleanup.json'),sha(folder/'PAIR_RUNTIME_GATE.json'),c)
 require(read(folder/'service.json')==g['service_owner'],'actual service differs')
 require(sha(folder/'native.mp4')==c['historical_native']['sha256'] and sha(folder/'source.mp4')==c['source']['sha256'],'historical/source media changed')
 return receipt
