"""Three fixed-guidance outputs bound to actual same-host P1 Native parents."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('human2animal_1__game_man_4',)
VALID={SOURCES[0]:147}
GEOMETRY={'width':1152,'height':768,'frames':158,'fps':24}
SHAPES={'video':(1,24,47,48,72),'audio':(1,32,2,263)}
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)
def run_id(source):require(source in SOURCES,'unknown source');return 'r101_'+source+'_seed2026101701_forced'
def geometry(case):require(case['source_id'] in SOURCES,'unknown source');return dict(GEOMETRY)
def latent_shapes(case):geometry(case);return dict(SHAPES)
def routing_layout(case):
 geometry(case);valid=VALID[case['source_id']];sizes=[(1,4,4,4,4)[i%5] for i in range(47)];cursor=0;stop=0
 for i,n in enumerate(sizes):
  if cursor<valid:stop=i+1
  cursor+=n
 return {'latent_interval_half_open':[0,stop],'position_bin_coverage_inclusive':[0,sum(sizes[:stop])-1],'pixel_interval_inclusive':[0,valid-1],'total_latent_bins':47,'pure_pad_bins':list(range(stop,47)),'frame_rows':864}
def expected_graph(root,case):
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);source=case['source_id'];run=run_id(source);g=copy.deepcopy(read(root/case['parent_graph']))
 for node,key,suf in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/suf)
 shared='r101_'+source+'_shared';g['5']['inputs']['run_id']=shared;g['51']['inputs']['source_run_id']=shared
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']='r101_'+source+'_seed2026101701';g['14']['inputs']['filename_prefix']=run
 g['50']['inputs'].update(mode='mass_preserve',alpha=1.,radius=0,time_offset=0,start_frame=0,end_frame=VALID[source]-1,block_start=0,block_end=50,step_start=6,step_end=15)
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');bindings=read(root/'configs/parent_bindings.json');order=[run_id(x) for x in SOURCES]
 require(s['source_ids']==list(SOURCES) and s['arms']==['forced'] and s['case_order']==order and len(s['cases'])==1,'single fixed output changed')
 require(read(root/'configs/queue.json')=={'jobs':order,'finalize':True},'fixed registry order changed')
 require(s['cases']==read(root/'design/CASE_DEFINITIONS.json'),'case definition changed');jobs={}
 for case,source in zip(s['cases'],SOURCES):
  run=run_id(source);b=bindings[source];parent=root/case['parent_graph'];g=read(parent)
  require(case['run_id']==run and case['source_id']==source and case['parent_run']==b['run_id'] and case['arm']=='forced' and case['seed']==2026101701,'case identity changed')
  require(case['geometry']==GEOMETRY and case['valid_frame_count']==VALID[source] and case['reference_video_count']==1 and case['reference_image_count']==1 and case['evaluation_crop_xywh']==[0,0,1152,768],'case geometry/modalities changed')
  require(case['prompt']==g['5']['inputs']['prompt']==(root/'configs/prompts'/f'{source}.txt').read_text() and sha(parent)==case['parent_graph_sha256']==b['graph']['sha256'],'actual parent graph/P1 changed')
  for rel,digest in b['local_snapshot_hashes'].items():require(sha(root/'design'/source/rel)==digest,'actual parent snapshot changed: '+rel)
  gate=read(root/'design'/source/'PARENT_ACTUAL_GATE.json');require(gate['passed'] is True and all(gate['checks'].values()),'parent actual gate failed')
  graph=root/'configs/graphs'/f'{run}.json';require(read(graph)==expected_graph(root,case),'graph changed outside registered routing and run paths')
  jobs[run]={'case':case,'source_id':source,'seed':2026101701,'arm':'forced','graph_sha256':sha(graph)}
 return jobs,order

def validate_job(run,root=ROOT):
 root=Path(root);jobs,_=registry(root);require(run in jobs,'unregistered run');row=jobs[run]
 for key in ('video','portrait','provenance'):
  name=row['case'][key];p=root/'inputs'/name;require(Path(name).name==name and not p.is_symlink() and sha(p)==row['case'][key+'_sha256'],'original input changed: '+key)
 return row

def audit_dir(value):
 p=Path(value);require(p.is_absolute() and p.resolve()==Path(read(ROOT/'configs/runtime.json')['remote_root'])/'audit','audit root differs');return p

def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
 row=validate_job(run_id);remote=Path(read(ROOT/'configs/runtime.json')['remote_root']);require(Path(audit_dir)==remote/'audit/router','router audit differs')
 require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==('mass_preserve',1.,0,0,0,VALID[row['source_id']]-1,0,50,6,15),'fixed route differs')

def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True)
 for key in ('video','portrait'):
  p=folder/case[key]
  if not p.exists():
   with (root/'inputs'/case[key]).open('rb') as before,p.open('xb') as after:shutil.copyfileobj(before,after)
  require(not p.is_symlink() and sha(p)==case[key+'_sha256'],'loader input changed')
 return row
