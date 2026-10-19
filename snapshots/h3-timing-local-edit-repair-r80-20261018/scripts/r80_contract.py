"""Two fixed development sources; official-format local editing, Native only."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('short_0230','short_0352');ARMS=('native',)
VALID={'short_0230':86,'short_0352':78}
GEOMETRY={'width':1312,'height':736,'frames':90,'fps':24}
SHAPES={'video':(1,24,27,46,82),'audio':(1,32,2,150)}
def read(path):return json.loads(Path(path).read_text())
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
REMOTE=Path(read(ROOT/'configs/runtime.json')['remote_root'])
def require(ok,message):
 if not ok:raise ValueError(message)
def expected_graph(root,case):
 root=Path(root);remote=Path(read(root/'configs/runtime.json')['remote_root']);g=copy.deepcopy(read(root/case['parent_graph']));run=case['run_id'];source=case['source_id']
 for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/suffix)
 g['5']['inputs'].update(run_id=case['reference_cache_id'],prompt=case['prompt']);g['51']['inputs']['source_run_id']=case['reference_cache_id']
 for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
 g['6']['inputs']['pair_id']='r80_'+source+'_seed2026101701';g['14']['inputs']['filename_prefix']=run
 # The original R69 Native router mask is dormant and is kept exactly.
 return g

def registry(root=ROOT):
 root=Path(root);s=read(root/'configs/scientific_contract.json');order=['r80_'+source+'_seed2026101701_native' for source in SOURCES]
 require(s['case_order']==order and len(s['cases'])==2 and s['arms']==list(ARMS) and s['source_ids']==list(SOURCES),'fixed Native repair registry changed')
 q=read(root/'configs/queue.json');require(set(q)=={'jobs','finalize'} and q['jobs']==order and q['finalize'] is True,'two-run Native queue changed')
 template=(root/'design/P1_TEMPLATE.txt').read_text();fields=read(root/'design/PROMPT_FIELDS.json')
 require(sha(root/'design/P1_TEMPLATE.txt')==s['prompt_template_sha256'] and sha(root/'design/PROMPT_FIELDS.json')==s['prompt_fields_sha256'],'prompt template/visible fields changed')
 official={x['source_id']:x['official_task'] for x in read(root/'design/OFFICIAL_TASKS.json')['sources']};jobs={}
 for case,source,run in zip(s['cases'],SOURCES,order):
  require(case['run_id']==run and case['source_id']==source and case['arm']=='native' and case['seed']==2026101701 and case['geometry']==GEOMETRY,'run/source/seed/geometry changed')
  require(case['prompt_protocol']=='P1-local-v1' and case['prompt_version']=='P1','prompt protocol changed')
  row=next(x for x in fields['rows'] if x['source_id']==source)
  require(case['prompt']==template.format(**row)==(root/case['prompt_file']).read_text() and sha(root/case['prompt_file'])==case['prompt_sha256'],'prompt changed')
  require(case['original_task']==official[source] and all(row[k]==case['original_task'][k] for k in ['source_prompt','edit_prompt','target_prompt']),'official task text changed')
  require(case['reference_video_count']==1 and case['reference_image_count']==0 and case['valid_frame_count']==VALID[source],'reference scope changed')
  require(case['reference_cache_id']=='r80_'+source+'_shared','condition cache identity changed')
  parent=root/case['parent_graph'];require(sha(parent)==case['parent_graph_sha256'] and read(parent)['5']['inputs']['prompt']==case['original_task']['edit_prompt'],'original R69 parent graph changed')
  graph=root/'configs/graphs'/(run+'.json');require(read(graph)==expected_graph(root,case),'graph numeric inputs changed')
  jobs[run]={'case':case,'source_id':source,'seed':case['seed'],'arm':'native','graph_sha256':sha(graph)}
 return jobs,order

def validate_job(run,root=ROOT):
 root=Path(root);jobs,_=registry(root);require(run in jobs,'unregistered run');row=jobs[run]
 for key in ('video','provenance'):
  case=row['case'];name=case[key];p=root/'inputs'/name
  require(Path(name).name==name and not p.is_symlink() and sha(p)==case[key+'_sha256'],'input changed: '+key)
 return row

def audit_dir(value):
 p=Path(value);require(p.is_absolute() and p.resolve()==REMOTE/'audit','audit root differs');return p

def validate_router(mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end,run_id,audit_dir):
 validate_job(run_id);require(Path(audit_dir)==REMOTE/'audit/router','router audit differs')
 require((mode,alpha,radius,time_offset,start_frame,end_frame,block_start,block_end,step_start,step_end)==('native',1.,0,0,0,89,0,50,0,20),'original Native route parameters differ')

def prepare_loader_inputs(run,root=ROOT):
 import shutil
 root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True);path=folder/case['video']
 if not path.exists():
  with (root/'inputs'/case['video']).open('rb') as before,path.open('xb') as after:shutil.copyfileobj(before,after)
 require(not path.is_symlink() and sha(path)==case['video_sha256'],'loader source changed');return row
