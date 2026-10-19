"""Frozen single-case, two independent lane bindings. No model/process work."""
import copy
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
REMOTE_BASE=Path('/data5/researcher/h3_runs/timing_reverse_reference_r25_20261017')
ARMS=('reverse_block','reverse_same')
SEED=2026101311
SHARED='r25_source05_sam_shared'
PAIR='r25_source05_sam_2026101311'

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def safe(v):
    if not isinstance(v,str) or not re.fullmatch(r'[a-z0-9_]+',v):raise ValueError('unsafe identifier')
    return v
def run_name(arm):
    if arm not in ARMS:raise ValueError('unregistered scientific arm')
    return 'r25_s05_'+arm+'_6to14'

def expected_graph(root,arm):
    root=Path(root);runtime=read(root/'configs/runtime.json');remote=Path(runtime['remote_root'])
    if runtime['arm']!=arm or remote!=REMOTE_BASE/arm:raise ValueError('wrong exact lane root/arm')
    g=copy.deepcopy(read(root/'configs/parent_graph.json'));run=run_name(arm)
    g['5']['inputs'].update(audit_dir=str(remote/'audit'),run_id=SHARED)
    g['6']['inputs'].update(audit_dir=str(remote/'audit'),run_id=run,pair_id=PAIR)
    g['14']['inputs']['filename_prefix']=run
    g['50']={'class_type':'H3ReverseReferenceRouter','inputs':{'model':['41',0],'positive':['51',0],
        'mode':arm,'run_id':run,'audit_dir':str(remote/'audit/router')}}
    g['51']['inputs'].update(source_audit_dir=str(remote/'audit'),source_run_id=SHARED,run_id=run)
    g['52']['inputs'].update(run_id=run,output_dir=str(remote/'audit/x0'))
    return g

def registry(root=ROOT):
    root=Path(root);record=read(root/'configs/job_registry.json');plan=read(root/'configs/queue.json')
    arm=read(root/'configs/runtime.json')['arm'];run=run_name(arm)
    if record.get('root_preparation_only') is not True or list(record['jobs'])!=[run]:raise ValueError('exact one-job scientific registry required')
    if (set(plan)!={'jobs','finalize'} or plan['jobs']!=[run] or type(plan['finalize']) is not bool):raise ValueError('only administrative finalize may change; no unreviewed continuation')
    row=record['jobs'][run]
    if row['arm']!=arm or row['seed']!=SEED:raise ValueError('registered arm/seed changed')
    return record['jobs'],[run]

def validate_job(run,root=ROOT):
    root=Path(root);jobs,_=registry(root)
    if run not in jobs:raise ValueError('run absent from this lane')
    row=jobs[run];p=root/'configs/graphs'/f'{safe(run)}.json'
    if p.is_symlink() or sha(p)!=row['graph_sha256'] or read(p)!=expected_graph(root,row['arm']):raise ValueError('actual scientific graph changed')
    for name,digest in read(root/'configs/input_hashes.json').items():
        p=root/'inputs'/name
        if Path(name).name!=name or p.is_symlink() or sha(p)!=digest:raise ValueError('immutable input changed')
    return row

def validate_router(mode,run_id,audit_path):
    row=validate_job(run_id);remote=Path(read(ROOT/'configs/runtime.json')['remote_root'])
    if mode!=row['arm'] or Path(audit_path)!=remote/'audit/router':raise ValueError('router scope/path differs from reviewed run')

def audit_dir(value):
    root=Path(read(ROOT/'configs/runtime.json')['remote_root'])/'audit'
    if not Path(value).is_absolute() or Path(value).resolve()!=root.resolve():raise ValueError('audit path must equal actual lane audit root')
    return root

def prepare_loader_inputs(run,root=ROOT):
    import shutil
    root=Path(root);row=validate_job(run,root);g=expected_graph(root,row['arm']);target=root/'input';target.mkdir(exist_ok=True)
    for name in (g['21']['inputs']['image'],g['22']['inputs']['file']):
        src=root/'inputs'/name;dst=target/name
        if dst.is_symlink():raise ValueError('loader symlink refused')
        if not dst.exists():
            with src.open('rb') as a,dst.open('xb') as b:shutil.copyfileobj(a,b)
        if sha(dst)!=read(root/'configs/input_hashes.json')[name]:raise ValueError('actual loader input mismatch')
    return row
