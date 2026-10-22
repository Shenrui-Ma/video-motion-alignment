"""Seven fixed R83 tasks; imports perform no GPU operations."""
import contextlib,fcntl,hashlib,json,os,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime'
SELECTION=ROOT/'configs/INPUT_PLAN.json'
PAIRS=('short_0131','short_0268','short_0343','short_0274','short_0085','short_0358','short_0178')
METHODS=('native','forced')

def require(ok,message):
    if not ok:raise ValueError(message)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def read(path):return json.loads(Path(path).read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def replace(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex)
    save(temp,value);os.replace(temp,path)
def bound(path):
    path=Path(path).resolve();return {'file':str(path),'sha256':sha(path)}
def entry(source):
    require(source in PAIRS,'unregistered source')
    plan=read(SELECTION)
    require(plan['source_selection_sha256']==sha(ROOT/'configs/SELECTED_7_MANIFEST.json'),'source selection changed')
    require(tuple(x['pair_id'] for x in plan['pairs'])==PAIRS,'fixed seven sources changed')
    return next(x for x in plan['pairs'] if x['pair_id']==source)
def run_id(source,method):
    entry(source);require(method in METHODS,'unregistered method')
    return f'r83_{source}_seed2026101701_{method}'
def verify_runtime(inputs=True):
    for rel,digest in read(ROOT/'configs/NUMERICAL_INHERITANCE.json')['files'].items():require(sha(ROOT/rel)==digest,'numerical source changed: '+rel)
    if inputs:
        for name,digest in read(ROOT/'configs/producer_input_hashes.json').items():require(sha(ROOT/'inputs'/name)==digest,'input changed: '+name)
    if (ROOT/'CONSUMER_FREEZE.json').exists():
        for rel,digest in read(ROOT/'CONSUMER_FREEZE.json')['files'].items():require(sha(ROOT/rel)==digest,'consumer source changed: '+rel)
    return sha(ROOT/'configs/NUMERICAL_INHERITANCE.json')
@contextlib.contextmanager
def cpu_lock():
    if str(ROOT).startswith('/data3/'):
        path=Path('/data3/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
    else:path=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:fcntl.flock(f,fcntl.LOCK_UN)
def source_row(source):
    row=read(ROOT/'prepared'/source/'SOURCE_INPUTS.json')
    names={'source_original':f'inputs/{source}_original.mp4','source_prepared_video':f'inputs/{source}_video.mp4','source_preparation_record':f'inputs/{source}_provenance.json','source_score_video':f'prepared/{source}/source_score.mp4'}
    for role,relative in names.items():
        path=ROOT/relative;require(sha(path)==row[role]['sha256'],'portable source changed: '+role);row[role]['file']=str(path)
    return row
