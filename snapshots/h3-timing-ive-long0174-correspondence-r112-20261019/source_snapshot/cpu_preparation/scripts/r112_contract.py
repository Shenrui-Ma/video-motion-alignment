"""CPU-prepared two-arm contract; actual execution requires a separate review."""
import copy
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('long_0174',)
ARMS=('fixed_one_bin','matched_one_bin')
GEOMETRY={'width':1312,'height':736,'frames':158,'fps':24}
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)
def run_id(arm):
    require(arm in ARMS,'unregistered spatial arm')
    return 'r112_long_0174_seed2026101701_'+arm
def geometry(case):
    require(case['source_id']=='long_0174','unregistered source')
    return dict(GEOMETRY)

def expected_graph(root,case):
    root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);run=run_id(case['arm'])
    graph=copy.deepcopy(read(root/case['parent_graph']))
    for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:
        graph[node]['inputs'][key]=str(remote/suffix)
    shared='r112_long_0174_shared';graph['5']['inputs']['run_id']=shared;graph['51']['inputs']['source_run_id']=shared
    for node in ('6','50','51','52'):graph[node]['inputs']['run_id']=run
    graph['6']['inputs']['pair_id']='r112_long_0174_seed2026101701';graph['14']['inputs']['filename_prefix']=run
    graph['50']['inputs'].update(mode=case['arm'],alpha=1.,radius=0,time_offset=0,start_frame=0,end_frame=144,block_start=0,block_end=50,step_start=6,step_end=15)
    return graph

def registry(root=ROOT):
    root=Path(root);scientific=read(root/'configs/scientific_contract.json');cases=read(root/'design/CASE_DEFINITIONS.json');order=[run_id(a) for a in ARMS]
    require(scientific['cases']==cases and scientific['arms']==list(ARMS) and scientific['case_order']==order,'registered two-arm comparison changed')
    require(read(root/'configs/queue.json')=={'jobs':order,'finalize':True},'queue differs')
    require(len(cases)==2,'two cases required');jobs={};bindings=read(root/'configs/parent_bindings.json')['long_0174']
    for arm,case in zip(ARMS,cases):
        require(case['arm']==arm and case['run_id']==run_id(arm) and case['seed']==2026101701,'arm/seed/run mismatch')
        require(case['geometry']==GEOMETRY and case['valid_frame_count']==145 and case['evaluation_crop_xywh']==[16,8,1280,720],'geometry changed')
        require(case['reference_image_count']==0 and case['reference_video_count']==1,'modalities changed')
        require(case['prompt']==(root/'configs/prompts/long_0174.txt').read_text()==read(root/case['parent_graph'])['5']['inputs']['prompt'],'prompt changed')
        require(sha(root/case['parent_graph'])==case['parent_graph_sha256']==bindings['graph']['sha256'],'parent graph changed')
        for rel,digest in bindings['local_snapshot_hashes'].items():require(sha(root/'design/long_0174'/rel)==digest,'parent evidence changed: '+rel)
        run=run_id(arm);file=root/'configs/graphs'/f'{run}.json'
        require(read(file)==expected_graph(root,case),'graph changed beyond registered operator/run paths')
        jobs[run]={'case':case,'source_id':'long_0174','seed':2026101701,'arm':arm,'graph_sha256':sha(file)}
    return jobs,order

def validate_job(run,root=ROOT):
    root=Path(root);jobs,_=registry(root);require(run in jobs,'unregistered job');row=jobs[run]
    for key in ('video','provenance'):
        name=row['case'][key];file=root/'inputs'/name
        require(Path(name).name==name and not file.is_symlink() and sha(file)==row['case'][key+'_sha256'],'source input differs')
    return row

def audit_dir(value):
    root=Path(read(ROOT/'configs/runtime.json')['remote_root'])
    require(Path(value).is_absolute() and Path(value).resolve()==root/'audit','audit directory differs')
    return Path(value)

def correspondence_configuration(run,root=ROOT):
    root=Path(root);jobs,_=registry(root);require(run in jobs,'unregistered bank job');remote=Path(read(root/'configs/runtime.json')['remote_root'])
    config={'root':str(remote/'audit/correspondence_banks'/run),'valid_bins':43,'spatial_grid':[23,41],
            'prefix_manifest':str(remote/'audit/x0'/run/'manifest.json')}
    bindings=read(root/'configs/parent_bindings.json')['long_0174']
    config['paired_prefix_manifest']=str(Path(bindings['first_six_predictions'][0]['file']).parent/'manifest.json')
    if jobs[run]['arm']=='matched_one_bin':
        config['paired_root']=str(remote/'audit/correspondence_banks'/run_id('fixed_one_bin'))
        config['paired_prefix_manifest']=str(remote/'audit/x0'/run_id('fixed_one_bin')/'manifest.json')
    return config

def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
    row=validate_job(run_id);remote=Path(read(ROOT/'configs/runtime.json')['remote_root'])
    require(Path(audit_dir)==remote/'audit/router','router output path differs')
    require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==(row['arm'],1.,0,0,0,144,0,50,6,15),'registered intervention changed')
    review=ROOT/'audit/GPU_DEPLOYMENT_REVIEW.json'
    require(review.exists(),'R112 CPU preparation awaits root deployment review')
    approval=read(review)
    require(approval.get('approved') is True and approval.get('scope')=='r112-two-arm-gpu-execution' and approval.get('producer_seal_sha256')==sha(ROOT/'CPU_PREPARATION_SEAL.json'),'root GPU review absent/stale')
    for rel,meta in read(ROOT/'CPU_PREPARATION_SEAL.json')['files'].items():
        file=ROOT/rel
        require(not file.is_symlink() and sha(file)==meta['sha256'],'reviewed producer changed: '+rel)

if __name__=='__main__':
    jobs,order=registry()
    for run in order:validate_job(run)
    print(json.dumps({'registered_runs':order,'source_and_graphs_verified':True,'GPU_started':False},indent=2))
