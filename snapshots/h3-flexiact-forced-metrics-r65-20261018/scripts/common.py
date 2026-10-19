import contextlib,fcntl,hashlib,importlib.util,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('fitness','one_leg');METHODS=('native','forced');INDICES=list(range(0,147,3));METRIC=ROOT/'runtime/official_metric'
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

def frozen(root,manifest,expected):
 root=Path(root);require(sha(root/manifest)==expected,'frozen manifest changed')
 for name,row in read(root/manifest)['files'].items():require(sha(root/name)==(row['sha256'] if isinstance(row,dict) else row),'frozen file changed: '+name)
 return expected

def verify_runtime():
 snapshot=read(ROOT/'CONSUMER_FREEZE.json')
 for name,digest in snapshot['files'].items():require(sha(ROOT/name)==digest,'consumer static artifact changed: '+name)
 c=read(ROOT/'configs/contract.json');frozen(METRIC,'RUNTIME_FREEZE.json',c['official_runtime_freeze_sha256']);frozen(ROOT/'runtime/physical','FREEZE.json',c['physical_freeze_sha256'])
 require(sha(ROOT/'runtime/release/release49.py')==c['release49_sha256'],'release sampler changed')
 for entry in c['historical_cache_reference_only']:require(sha(ROOT/entry['file'])==entry['sha256'],'historical source tracks changed')
 return c

def verify_gate(g,source):
 require(source in SOURCES and g.get('schema')=='r65-paired-runtime-gate-v1' and g.get('passed') is True and g.get('source_id')==source and g.get('prompt_version')=='R49_original','actual paired runtime receipt missing/invalid')
 require(g['checks'] and all(value is True for value in g['checks'].values()),'runtime check failed')
 for name in ['actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal','producer_seal']:require(g['checks'].get(name) is True,'mandatory runtime check missing')
 for method in METHODS:
  row=g['runs'][method];require(row['run_id']==f'r65_{source}_seed2026101701_{method}' and row['valid_frames']==147 and row['NFE']==20 and row['Euler_updates']==20 and row['routed_blocks']==(0 if method=='native' else 450),'paired execution differs')
  require(row['evaluation_indices']==INDICES and row['evaluation_fps']==8,'official49 map differs')
 return g

@contextlib.contextmanager
def cpu_lock():
 if str(ROOT).startswith('/data5/'):
  p=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
 elif str(ROOT).startswith('/data3/'):
  p=Path('/data3/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
 else:p=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('a') as f:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);yield str(p)
