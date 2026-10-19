"""Validate only the actual R96 Native receipt and its media evidence."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('long_0047','long_0123','long_0167','long_0173','long_0174')
REQUIRED_CHECKS=('producer_seal','actual_runtime_device','native_history','native_service','native_shared_conditions','native_actual_execution_counts','native_actual_layout','native_sampled_finite','native_actual_noise_cache')
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
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);require(not p.exists(),'receipt exists: '+str(p))
 temp=p.with_name(p.name+'.tmp.'+str(os.getpid()));temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.link(temp,p);temp.unlink()
def config():return read(ROOT/'configs/contract.json')
def info(source):
 require(source in SOURCES,'source not registered');return next(x for x in config()['sources'] if x['source_id']==source)
def validate_static():
 c=config();require(c['source_order']==list(SOURCES),'fixed source denominator changed')
 for name,digest in read(ROOT/'CONSUMER_FREEZE.json')['files'].items():require(sha(ROOT/name)==digest,'consumer static file changed: '+name)
 for row in c['sources']:
  for k in ('source','provenance'):require(sha(ROOT/row[k]['file'])==row[k]['sha256'],'source input changed')
 return c

def safe_path(path,subdir=None):
 p=Path(path);root=Path(config()['producer_remote']);base=root/subdir if subdir else root
 require(p.is_absolute() and '..' not in p.parts and p.is_relative_to(base),'remote path outside expected root');return p

def verify_gate(g,source,owner):
 c=config();p=info(source)
 require(g.get('schema')=='r96-native-runtime-gate-v1' and g.get('passed') is True,'Native gate not passed')
 require(g.get('source_id')==source and g.get('prompt_version')==p['prompt_version'],'source/prompt differs')
 require(set(g.get('runs',{}))=={'native'},'Native-only receipt required')
 checks=g.get('checks');require(isinstance(checks,dict) and all(x is True for x in checks.values()),'failed actual check')
 require(all(checks.get(x) is True for x in REQUIRED_CHECKS),'required actual check missing')
 require(g.get('runtime_profile_sha256')==c['producer_runtime_sha256'],'runtime hash differs')
 require(g.get('runtime_profile')==read(ROOT/'configs/producer_runtime.json'),'runtime content differs')
 require(g.get('service_owner')=={'pid':owner['pid'],'identity':owner['identity']},'Native service generation differs')
 verify_run(g['runs']['native'],p,'native')
 return g

def verify_run(r,p,mode):
 require(mode in ('native','forced'),'unknown execution mode')
 run_id=p['run_id'] if mode=='native' else p['forced_run_id']
 graph_sha=p['graph_sha256'] if mode=='native' else p['forced_graph_sha256']
 require(r.get('run_id')==run_id,'run differs')
 require(r.get('NFE')==20 and r.get('Euler_updates')==20 and r.get('routed_blocks')==(0 if mode=='native' else 450),'execution differs')
 require(r.get('valid_frames')==p['valid_frames'] and r.get('evaluation_crop_xywh')==p['crop_xywh'],'physical interval/crop differs')
 v=r['video'];safe_path(v['file'],'output');s=v['properties'];geom=p['geometry']
 require((s['width'],s['height'],int(s['nb_read_frames']))==(geom['width'],geom['height'],geom['frames']) and s['avg_frame_rate']=='24/1','output geometry differs')
 artifacts=r.get('binding_artifacts',{});require(isinstance(artifacts,dict) and artifacts,'actual binding artifacts missing')
 for rel,digest in artifacts.items():
  require(not Path(rel).is_absolute() and '..' not in Path(rel).parts and len(digest)==64,'unsafe artifact')
 required={f'configs/graphs/{run_id}.json':graph_sha,f'logs/{run_id}_job.json':r['job_sha256'],f'logs/{run_id}_history.json':r['history_sha256']}
 require(all(artifacts.get(k)==v for k,v in required.items()),'graph/job/history bindings differ')
 return r

def verify_small_evidence(path,source,owner,g,mode="native"):
 require(mode in ("native","forced"),"unknown execution mode")
 p=info(source);run_id=p['run_id'] if mode=='native' else p['forced_run_id'];graph_sha=p['graph_sha256'] if mode=='native' else p['forced_graph_sha256'];job=read(path/f'{mode}_job.json');history=read(path/f'{mode}_history.json');graph=read(path/f'{mode}_graph.json');r=g['runs'][mode]
 require(job.get('status')=='success' and job.get('name')==run_id,'actual job incomplete')
 require(job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'],'job generation differs')
 require(job['graph_sha256']==graph_sha==sha(path/f'{mode}_graph.json'),'job graph differs')
 require(history['status']['completed'] is True and history['status']['status_str']=='success' and history['prompt'][1]==job['prompt_id'] and history['prompt'][2]==graph,'history is not exact successful graph')
 images=history['outputs']['14']['images'];require(len(images)==1 and images[0].get('type')=='output','actual output not single video')
 entry=images[0];relative=Path(entry.get('subfolder',''))/entry['filename'];require(not relative.is_absolute() and '..' not in relative.parts,'unsafe history output')
 require(str(Path(config()['producer_remote'])/'output'/relative)==r['video']['file'],'history video path differs')
 require(sha(path/f'{mode}.mp4')==r['video']['sha256'],'actual video SHA differs')

def verify_intake(source):
 dest=ROOT/'incoming'/source;receipt=read(dest/'COLLECTION.json');binding=read(ROOT/'audit/EXECUTION_BINDING.json')
 require(receipt['source_id']==source and receipt['execution_binding_sha256']==sha(ROOT/'audit/EXECUTION_BINDING.json'),'intake binding changed')
 for name,digest in receipt['files'].items():
  require(Path(name).name==name,'unsafe intake path');require(sha(dest/name)==digest,'intake file changed')
 g=verify_gate(read(dest/'NATIVE_RUNTIME_GATE.json'),source,binding['owner']);verify_small_evidence(dest,source,binding['owner'],g);return g
