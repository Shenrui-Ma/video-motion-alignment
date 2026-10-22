"""R87 media-only contract and actual evidence validation, adapted from R74."""
import hashlib,json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PAIRS=('short_0131','short_0268','short_0343','short_0274','short_0085','short_0358','short_0178')
METHODS=('native','forced')
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
 c=config();require(c['pair_order']==list(PAIRS),'fixed seven source order differs')
 require(sha(ROOT/'configs/producer_scientific_contract.json')==c['producer_contract_sha256'],'scientific contract changed')
 for name,digest in read(ROOT/'CONSUMER_FREEZE.json')['files'].items():require(sha(ROOT/name)==digest,'consumer static file changed: '+name)
 return c

def verify_gate(g,pair):
 p=pair_info(pair);require(g.get('schema')=='r87-paired-runtime-gate-v1' and g.get('passed') is True,'actual pair gate is not passed')
 require(g.get('source_id')==pair,'source key differs');require(g.get('prompt_version')==p['prompt_version'],'prompt version differs')
 checks=g.get('checks');require(isinstance(checks,dict) and checks and all(v is True for v in checks.values()),'actual gate check missing/failed')
 for k in ['actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal','producer_seal','actual_runtime_device','native_service','forced_service','native_actual_layout','forced_actual_layout','native_actual_execution_counts','forced_actual_execution_counts']:
  require(checks.get(k) is True,'mandatory check missing: '+k)
 require(g['runtime_profile_sha256']==config()['producer_runtime_sha256'],'actual runtime profile differs')
 for arm in METHODS:
  r=g['runs'][arm];require(r['run_id']==p['runs'][arm]['run_id'],'run ID differs')
  require(r['valid_frames']==p['valid_frames'] and r['NFE']==20 and r['Euler_updates']==20 and r['routed_blocks']==(0 if arm=='native' else 450),'execution count differs')
  require(r['evaluation_crop_xywh']==p['evaluation_crop_xywh'],'physical crop differs')
  props=r['video']['properties'];require(props['width']==1312 and props['height']==736 and int(props['nb_read_frames'])==p['geometry']['frames'] and props['avg_frame_rate']=='24/1','output properties differ')
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
 for arm in METHODS:require(sha(path/(arm+'.mp4'))==g['runs'][arm]['video']['sha256'],'intake output differs')
 return g
