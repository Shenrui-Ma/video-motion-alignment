import contextlib,fcntl,hashlib,importlib.util,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PAIR_KEYS=('chest__game_man_5', 'chest__movie_man_7', 'crouch__movie_man_5', 'crouch__movie_man_9', 'rotate__game_man_1', 'rotate__game_man_4')
SOURCES=PAIR_KEYS;MOTIONS=('chest','crouch','rotate');METHODS=('native','forced');INDICES=list(range(0,147,3));METRIC=ROOT/'runtime/official_metric'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(1048576),b''):h.update(c)
 return h.hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def save(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def bound(p):return {'file':str(Path(p).resolve()),'sha256':sha(p)}
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
def pair_info(key):
 require(key in PAIR_KEYS,'unknown action+target pair');rows=read(ROOT/'configs/contract.json')['pairs'];return next(x for x in rows if x['pair_key']==key)
def source_item(action):
 require(action in MOTIONS,'unknown motion source');return next(x for x in read(METRIC/'SOURCE_INPUTS.json')['inputs'] if x['id']==f'human/{action}/000')
def frozen(root,manifest,expected):
 root=Path(root);require(sha(root/manifest)==expected,'frozen manifest changed')
 for name,row in read(root/manifest)['files'].items():require(sha(root/name)==(row['sha256'] if isinstance(row,dict) else row),'frozen file changed: '+name)
 return expected

def verify_runtime():
 for name,digest in read(ROOT/'CONSUMER_FREEZE.json')['files'].items():require(sha(ROOT/name)==digest,'consumer static artifact changed: '+name)
 c=read(ROOT/'configs/contract.json');frozen(METRIC,'RUNTIME_FREEZE.json',c['official_runtime_freeze_sha256'])
 require(sha(ROOT/'runtime/release/release49.py')==c['release49_sha256'],'release sampler changed')
 require(sha(ROOT/'configs/producer_scientific_contract.json')==c['producer_contract_sha256'],'producer contract changed')
 require([x['pair_key'] for x in c['pairs']]==list(PAIR_KEYS),'fixed pair order changed')
 return c

def verify_gate(g,pair):
 p=pair_info(pair)
 require(g.get('schema')=='r74-paired-runtime-gate-v1' and g.get('passed') is True and g.get('source_id')==g.get('pair_key')==pair and g.get('prompt_version')=='P1','actual paired runtime receipt missing/invalid')
 require(all(g.get(k)==p[k] for k in ['motion_source_id','original_pair_id','group']),'pair/motion/group binding differs')
 require(g['checks'] and all(value is True for value in g['checks'].values()),'runtime check failed')
 for name in ['actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal','producer_seal','native_reference_geometry','forced_reference_geometry']:require(g['checks'].get(name) is True,'mandatory runtime check missing')
 for method in METHODS:
  row=g['runs'][method];require(row['run_id']==f'r74_{pair}_seed2026101701_{method}' and row['valid_frames']==147 and row['NFE']==20 and row['Euler_updates']==20 and row['routed_blocks']==(0 if method=='native' else 450),'paired execution differs')
  require(row['evaluation_indices']==INDICES and row['evaluation_fps']==8,'official49 map differs')
 return g

@contextlib.contextmanager
def cpu_lock():
 if str(ROOT).startswith('/data5/'):p=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
 elif str(ROOT).startswith('/data3/'):p=Path('/data3/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
 else:p=ROOT/'audit/cpu_consumer.lock'
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('a') as f:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);yield str(p)
