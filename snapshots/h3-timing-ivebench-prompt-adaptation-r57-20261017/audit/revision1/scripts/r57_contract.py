"""Five fixed P1 prompts derived from actual R54 graphs; CPU preparation and Native runtime."""
import copy,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
REMOTE=Path(read(ROOT/'configs/runtime.json')['remote_root'])
SOURCES=('short_0210','short_0230','short_0263','short_0352','short_0370')
SEEDS=(2026101701,);ARMS=('native',)
GEOMETRY={'width':1312,'height':736,'frames':90,'fps':24}
SHAPES={'video':(1,24,27,46,82),'audio':(1,32,2,150)}
BINDING=read(ROOT/'design/PILOT_5_MANIFEST.json')
TEMPLATE=(ROOT/'design/P1_TEMPLATE.txt').read_text()
PROMPTS={row['pair_id']:TEMPLATE.format(**row) for row in BINDING['pairs']}

def input_path(root,name):
    root=Path(root)
    if Path(name).name!=name:raise ValueError('unsafe input name')
    record=read(root/'configs/input_bindings.json')[name]
    staged=root/'inputs'/name
    if staged.exists():return staged
    if root.resolve()==REMOTE.resolve():raise FileNotFoundError('materialize exact archived input before runtime: '+name)
    return Path(record['local_source'])

def verify_parent_metadata(root=ROOT):
    root=Path(root);binding=read(root/'configs/parent_binding.json')
    for name,digest in binding['anchors'].items():
        if sha(root/'configs/parents/batch'/name)!=digest:raise ValueError('parent anchor changed: '+name)
    if any(read(root/'configs/parents/batch'/name).get('passed') is not True for name in ('RUN_GATE.json','RUNTIME_GATE.json')):raise ValueError('parent completed archive gates failed')
    inventory=read(root/'configs/parents/batch/FILE_INVENTORY.json')
    parent_seal=read(root/'configs/parents/batch/deploy_manifest.json')['files']
    for source,row in binding['cases'].items():
        parentrel='configs/graphs/'+row['parent_run']+'.json'
        if sha(root/row['graph'])!=row['graph_sha256'] or parent_seal[parentrel]['sha256']!=row['graph_sha256']:raise ValueError('actual parent graph binding changed')
        for rel,record in row['files'].items():
            if sha(root/record['local_metadata'])!=record['sha256'] or inventory[rel]['sha256']!=record['sha256']:raise ValueError('actual parent evidence changed: '+rel)
    for name,record in read(root/'configs/input_bindings.json').items():
        if inventory['inputs/'+name]['sha256']!=record['sha256']:raise ValueError('input parent binding differs')
        p=input_path(root,name)
        if p.is_symlink() or p.stat().st_size!=record['bytes'] or sha(p)!=record['sha256']:raise ValueError('actual input differs: '+name)
    return {'actual_parent_cases':5,'actual_input_bindings':20,'large_files_copied':False}

def safe(value):
    if not isinstance(value,str) or not re.fullmatch('[a-z0-9_]+',value):raise ValueError('unsafe identifier')
    return value

def expected_graph(root,case):
    root=Path(root);graph=copy.deepcopy(read(root/case['parent_graph']));run=case['run_id']
    for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:
        graph[node]['inputs'][key]=str(REMOTE/suffix)
    graph['5']['inputs']['prompt']=PROMPTS[case['source_id']]
    graph['22']['inputs']['file']=case['video'];shared='r57_'+case['source_id']+'_shared'
    graph['5']['inputs']['run_id']=shared;graph['51']['inputs']['source_run_id']=shared
    for key in ('6','50','51','52'):graph[key]['inputs']['run_id']=run
    graph['6']['inputs'].update(pair_id='r57_'+case['source_id']+'_seed'+str(case['seed']),noise_seed=case['seed'])
    graph['14']['inputs']['filename_prefix']=run
    graph['50']['inputs'].update(mode='native',step_start=0,step_end=20,start_frame=0,end_frame=89)
    for node in ('5','52'):graph[node]['inputs'].update(width=1312,height=736,length=90)
    return graph

def registry(root=ROOT):
    root=Path(root);science=read(root/'configs/scientific_contract.json');queue=read(root/'configs/queue.json');registered=read(root/'configs/job_registry.json')['jobs']
    expected=['r57_'+source+'_seed2026101701_native' for source in SOURCES]
    if science['source_ids']!=list(SOURCES) or science['seeds']!=list(SEEDS) or science['arms']!=list(ARMS) or science['case_order']!=expected:raise ValueError('fixed case order changed')
    if list(registered)!=expected or set(queue)!={'jobs','finalize'} or queue['jobs']!=expected or type(queue['finalize']) is not bool:raise ValueError('queue differs')
    rows=science['cases']
    if len(rows)!=5:raise ValueError('five cases required')
    jobs={}
    for case,source,run in zip(rows,SOURCES,expected):
        if (case['source_id'],case['run_id'],case['seed'],case['prompt'])!=(source,run,2026101701,PROMPTS[source]):raise ValueError('case/prompt/seed differs')
        if case.get('portrait') is not None or case['reference_video_count']!=1 or case['reference_image_count']!=0:raise ValueError('requires original video-only task')
        if sha(root/case['parent_graph'])!=case['parent_graph_sha256']:raise ValueError('parent graph differs')
        row=registered[run]
        if (row['source_id'],row['seed'],row['arm'])!=(source,case['seed'],'native'):raise ValueError('job registry differs')
        jobs[run]=dict(row,case=case)
    return jobs,expected

def validate_job(run,root=ROOT):
    root=Path(root);jobs,_=registry(root)
    if run not in jobs:raise ValueError('unknown case')
    row=jobs[run];case=row['case'];path=root/'configs/graphs'/(safe(run)+'.json')
    if path.is_symlink() or sha(path)!=row['graph_sha256'] or read(path)!=expected_graph(root,case):raise ValueError('actual graph changed')
    for key in ('video','provenance'):
        name=case[key];p=input_path(root,name)
        if Path(name).name!=name or p.is_symlink() or sha(p)!=case[key+'_sha256']:raise ValueError('input changed: '+key)
    return row

def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
    validate_job(run_id)
    if Path(audit_dir)!=REMOTE/'audit/router' or (mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)!=('native',1.,0,0,0,89,0,50,0,20):raise ValueError('Native router differs')

def audit_dir(value):
    p=Path(value)
    if not p.is_absolute() or p.resolve()!=(REMOTE/'audit').resolve():raise ValueError('audit root differs')
    return p

def prepare_loader_inputs(run,root=ROOT):
    import shutil
    root=Path(root);row=validate_job(run,root);case=row['case'];target=root/'input';target.mkdir(exist_ok=True)
    src=input_path(root,case['video']);dst=target/case['video']
    if dst.is_symlink():raise ValueError('loader input symlink')
    if not dst.exists():
        with src.open('rb') as a,dst.open('xb') as b:shutil.copyfileobj(a,b)
    if sha(dst)!=case['video_sha256']:raise ValueError('actual loader input differs')
    return row


def paired_input_checks(reference,parent_reference,noise,parent_noise):
    """Actual tensor signatures, not file names or matching random seeds alone."""
    reference_keys=('input_video','native_vae_calls','qwen_presentation','target_latent_shapes')
    return {
        'reference_equal_P0':all(reference[key]==parent_reference[key] for key in reference_keys),
        'initial_AV_noise_equal_P0':noise['signature']==parent_noise['signature'] and noise['actual_noise_streams']==parent_noise['actual_noise_streams'],
    }
