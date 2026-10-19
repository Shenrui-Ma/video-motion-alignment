"""R94 media-only contract and actual evidence validation, adapted from R74."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PAIRS=('fitness__game_man_5',)
METHODS=('native','forced');INDICES=list(range(0,147,3))
def require(ok,message):
 if not ok:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def bound(p):return {'file':str(Path(p).resolve()),'sha256':sha(p)}
def save(p,value,replace=False):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if not replace:require(not p.exists(),'receipt already exists: '+str(p))
 tmp=p.with_name(p.name+'.tmp.'+str(os.getpid()));tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(p)
def config():return read(ROOT/'configs/contract.json')
def pair_info(pair):
 require(pair in PAIRS,'unknown pair');return next(x for x in config()['pairs'] if x['pair_key']==pair)
def validate_static():
 c=config();require(c['pair_order']==list(PAIRS),'fixed single pair differs')
 require(sha(ROOT/'configs/producer_scientific_contract.json')==c['producer_contract_sha256'],'scientific contract changed')
 for name,digest in read(ROOT/'CONSUMER_FREEZE.json')['files'].items():require(sha(ROOT/name)==digest,'consumer static file changed: '+name)
 return c

def verify_gate(g,pair):
 p=pair_info(pair);require(g.get('schema')=='r94-paired-runtime-gate-v1' and g.get('passed') is True,'actual pair gate is not passed')
 require(g.get('source_id')==g.get('pair_key')==pair,'pair key differs')
 for k in ['motion_source_id','original_pair_id','group','prompt_version']:require(g.get(k)==p[k],'gate '+k+' differs')
 checks=g.get('checks');require(isinstance(checks,dict) and checks and all(v is True for v in checks.values()),'actual gate check missing/failed')
 for k in ['actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal','producer_seal','actual_runtime_device','native_service','forced_service','native_reference_geometry','forced_reference_geometry']:
  require(checks.get(k) is True,'mandatory check missing: '+k)
 require(g['runtime_profile_sha256']==config()['producer_runtime_sha256'],'actual runtime profile differs')
 for arm in METHODS:
  r=g['runs'][arm];require(r['run_id']==p['runs'][arm]['run_id'],'run ID differs')
  require(r['valid_frames']==147 and r['NFE']==20 and r['Euler_updates']==20 and r['routed_blocks']==(0 if arm=='native' else 450),'execution count differs')
  require(r['evaluation_indices']==INDICES and r['evaluation_fps']==8 and r['evaluation_crop_xywh']==[0,0,1152,768],'physical frame mapping differs')
  props=r['video']['properties'];require(props['width']==1152 and props['height']==768 and int(props['nb_read_frames'])==158 and props['avg_frame_rate']=='24/1','output properties differ')
 require(set(g.get('runs',{}))==set(METHODS),'exact fresh pair required')
 require(g.get('runtime_profile')==read(ROOT/'configs/producer_runtime.json'),'actual runtime content differs')
 for arm in METHODS:
  for suffix in ['history','shared_conditions','actual_execution_counts','actual_layout','sampled_finite','actual_noise_cache']:
   require(checks.get(arm+'_'+suffix) is True,'mandatory actual check missing: '+arm+'_'+suffix)
 prefix=g.get('prefix_tensor_comparison');require(isinstance(prefix,list) and len(prefix)==6,'six actual prefix comparisons required')
 require([x.get('step_zero_based') for x in prefix]==list(range(6)) and all(x.get(k) is True for x in prefix for k in ['video','audio']),'actual prefix tensors differ')
 return g

def safe_output(path):
 root=Path(config()['producer_remote']);p=Path(path)
 require(p.is_absolute() and '..' not in p.parts and p.is_relative_to(root/'output'),'output outside producer root');return p

def verify_job(job,arm,pair,owner,gate):
 expected=pair_info(pair)['runs'][arm]
 require(job.get('status')=='success' and job.get('name')==expected['run_id'],'actual job incomplete/different')
 require(job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'],'job service generation differs from root STARTED')
 require(job['graph_sha256']==expected['graph_sha256'],'actual graph changed')

def verify_intake(pair):
 path=ROOT/'incoming'/pair;receipt=read(path/'COLLECTION.json')
 require(receipt['pair']==pair and receipt['execution_binding_sha256']==sha(ROOT/'audit/EXECUTION_BINDING.json'),'intake execution binding differs')
 for name,digest in receipt['files'].items():require(sha(path/name)==digest,'intake changed: '+name)
 g=verify_gate(read(path/'PAIR_RUNTIME_GATE.json'),pair)
 for arm in METHODS:
  require(sha(path/(arm+'.mp4'))==g['runs'][arm]['video']['sha256'],'intake output differs')
  verify_small_evidence(path,arm,pair,read(ROOT/'audit/EXECUTION_BINDING.json')['owner'],g)
 return g


def verify_small_evidence(path,arm,pair,owner,g):
 p=pair_info(pair);job=read(path/(arm+'_job.json'));history=read(path/(arm+'_history.json'));graph=read(path/(arm+'_graph.json'))
 verify_job(job,arm,pair,owner,g)
 require(sha(path/(arm+'_graph.json'))==p['runs'][arm]['graph_sha256'],'actual graph file differs')
 require(history['status']['completed'] is True and history['status']['status_str']=='success' and history['prompt'][1]==job['prompt_id'] and history['prompt'][2]==graph,'history graph/output not exact successful execution')
 images=history['outputs']['14']['images'];require(len(images)==1 and images[0].get('type')=='output','single actual output required')
 entry=images[0];relative=Path(entry.get('subfolder',''))/entry['filename'];require(not relative.is_absolute() and '..' not in relative.parts,'unsafe output')
 require(str(Path(config()['producer_remote'])/'output'/relative)==g['runs'][arm]['video']['file'],'actual history output differs')
 require(sha(path/(arm+'.mp4'))==g['runs'][arm]['video']['sha256'],'actual video differs')
