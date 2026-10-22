"""One IVE source with approved minimal prompt envelope and paired guidance."""
import copy, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('short_0177',)
ARMS = ('native', 'forced')
SOURCE_LENGTHS = {'short_0177': (73, 60)}
PROMPTS = {'short_0177': 'subject_definitions:\n<Video 1> is the source video for the target video edit and supplies its composition, camera, and temporal structure.\nSource caption: A tiger is resting on a rock and yawning widely, showing its sharp teeth and tongue.\n<Subject 1> is the tiger in <Video 1>.\n<Subject 2> is the rock in <Video 1>.\n<Subject 3> is the remaining source scene in <Video 1>.\n\nsummary:\n[video editing] The target video is an edited version of <Video 1>.\nReplace the tiger with a lion\n\nretention_analysis:\n<Subject 1> (appears in [Shot 1]): partially_preserved - Apply the edit requested in the summary; preserve its other source properties and actions.\n<Subject 2> (appears in [Shot 1]): fully_preserved - Preserve this source object, including its appearance and motion.\n<Subject 3> (appears in [Shot 1]): fully_preserved - Preserve the remaining source scene and objects.\n<Video 1> (composition, camera, and temporal structure): fully_preserved - Preserve the source framing, camera motion, cuts, and action timing.\n\ndetailed_description:\n[Shot 1] A lion is resting on a rock and yawning widely, showing its sharp teeth and tongue.\nThe edited subject is <Subject 1>; the source rock is <Subject 2>, and the remaining setting is <Subject 3>, as shown in <Video 1>.\n\noverall_soundscape:\nThe benchmark specifies no audio edit.\n\nnon_diegetic_music:\nThe benchmark specifies no music edit.'}
ROUTER = {'mode':'mass_preserve','alpha':1.0,'blocks':[0,50],'steps':[6,15],
          'physical_frames':'[0,valid_frame_count-1] per source',
          'query_support':'all spatial queries in each position bin overlapping valid physical time; pure-pad bins remain native',
          'native_mask_parameters':'same as forced; mode native'}

def read(path): return json.loads(Path(path).read_text())
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()
def require(ok,message):
    if not ok: raise ValueError(message)

REMOTE = Path(read(ROOT/'configs/runtime.json')['remote_root'])

def geometry(case): return {'width':1312,'height':736,'frames':73,'fps':24}
def latent_shapes(case): return {'video':(1,24,22,46,82),'audio':(1,32,2,122)}
def routing_layout(case):
    valid=SOURCE_LENGTHS[case['source_id']][1]
    sizes=[(1,4,4,4,4)[i%5] for i in range(22)];cursor=0;stop=0
    for i,n in enumerate(sizes):
        if cursor<valid:stop=i+1
        cursor+=n
    return {'latent_interval_half_open':[0,stop],
            'position_bin_coverage_inclusive':[0,sum(sizes[:stop])-1],
            'pixel_interval_inclusive':[0,valid-1],'total_latent_bins':22,
            'pure_pad_bins':list(range(stop,22)),'frame_rows':943}

def expected_graph(root,case):
    root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root'])
    g=copy.deepcopy(read(root/case['parent_graph']));run=case['run_id'];source=case['source_id']
    for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:
        g[node]['inputs'][key]=str(remote/suffix)
    shared='r123_'+source+'_shared';g['5']['inputs'].update(run_id=shared,prompt=case['prompt'])
    g['51']['inputs']['source_run_id']=shared
    for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
    g['6']['inputs'].update(pair_id='r123_'+source+'_seed2026101701',noise_seed=2026101701)
    g['14']['inputs']['filename_prefix']=run
    g['50']['inputs'].update(mode='native' if case['arm']=='native' else 'mass_preserve',
                            alpha=1.,radius=0,time_offset=0,start_frame=0,
                            end_frame=case['valid_frame_count']-1,
                            block_start=0,block_end=50,step_start=6,step_end=15)
    return g

def registry(root=ROOT):
    root=Path(root);s=read(root/'configs/scientific_contract.json')
    order=['r123_'+source+'_seed2026101701_'+arm for source in SOURCES for arm in ARMS]
    require(s['case_order']==order and len(s['cases'])==2 and s['source_ids']==list(SOURCES) and s['arms']==list(ARMS),'one-source registry changed')
    require(read(root/'configs/queue.json')=={'jobs':order,'finalize':True},'queue changed')
    frozen=root/'design/SOURCE_DEFINITIONS.json'
    require(sha(frozen)==s['source_definitions_sha256'],'source definitions changed')
    definitions=read(frozen);jobs={}
    for i,(case,run) in enumerate(zip(s['cases'],order)):
        source=SOURCES[i//2];arm=ARMS[i%2];d=definitions[source]
        require(case['run_id']==run and case['source_id']==source and case['arm']==arm and case['seed']==2026101701,'source/arm/seed changed')
        require(case['geometry']==geometry(case) and case['valid_frame_count']==SOURCE_LENGTHS[source][1],'geometry changed')
        require(case['evaluation_crop_xywh']==[16,8,1280,720] and case['evaluation_indices']==list(range(case['valid_frame_count'])),'evaluation includes padding or altered crop')
        require(case['reference_video_count']==1 and case['reference_image_count']==0,'reference scope changed')
        require(case['original_task']==d['original_task'],'official task record changed')
        prompt=root/'configs/prompts'/(source+'.txt')
        require(case['prompt_version']==s['prompt_version']=='official_context_ir_with_benchmark_captions_and_subject_binding','prompt label changed')
        require(prompt.read_text()==case['prompt']==PROMPTS[source] and case['prompt'].split('\n\nretention_analysis:')[0].splitlines()[-1]==case['original_task']['edit_prompt'],'official edit_prompt must be verbatim')
        require(sha(prompt)==case['prompt_sha256'],'prompt digest changed')
        for key in ('video','provenance','original_source'):
            require(case[key]==d[key] and case[key+'_sha256']==d[key+'_sha256'],'source media binding changed')
        require(case['parent_graph']==d['parent_graph'] and case['parent_graph_sha256']==d['parent_graph_sha256']==sha(root/case['parent_graph']),'source graph changed')
        graph=root/'configs/graphs'/(run+'.json')
        require(read(graph)==expected_graph(root,case),'graph differs outside official prompt/admin/guidance mode')
        jobs[run]={'case':case,'source_id':source,'seed':case['seed'],'arm':arm,'graph_sha256':sha(graph)}
    return jobs,order

def validate_job(run,root=ROOT):
    root=Path(root);jobs,_=registry(root);require(run in jobs,'unknown run');row=jobs[run]
    for key in ('video','provenance','original_source'):
        case=row['case'];name=case[key];p=root/'inputs'/name
        require(Path(name).name==name and not p.is_symlink() and sha(p)==case[key+'_sha256'],'input changed: '+key)
    return row

def audit_dir(value):
    p=Path(value);require(p.is_absolute() and p.resolve()==REMOTE/'audit','audit root differs');return p

def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
    row=validate_job(run_id)
    require(Path(audit_dir)==REMOTE/'audit/router','router audit differs')
    require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==('mass_preserve' if row['arm']=='forced' else 'native',1.,0,0,0,row['case']['valid_frame_count']-1,0,50,6,15),'fixed route changed')

def prepare_loader_inputs(run,root=ROOT):
    import shutil
    root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True);p=folder/case['video']
    if not p.exists():
        with (root/'inputs'/case['video']).open('rb') as src,p.open('xb') as dst:shutil.copyfileobj(src,dst)
    require(not p.is_symlink() and sha(p)==case['video_sha256'],'loader source changed')
    return row
