"""Five fixed IVEBench parent graph transformations; actual execution closure is separate."""
import json,hashlib,shutil
from pathlib import Path
from prepare_graphs import derive
ROOT=Path(__file__).resolve().parents[1]
REMOTE=Path('/data3/researcher/h3_runs/timing_ivebench_auto_r55_20261017')
SOURCES=('short_0210','short_0230','short_0263','short_0352','short_0370')
def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def cases(root=ROOT):
 rows=read(Path(root)/'configs/protocol.json')['cases']
 if [x['source_id'] for x in rows]!=list(SOURCES):raise ValueError('fixed five-case order changed')
 return rows
def registry(root=ROOT):
 rows=cases(root);names=[c['run_id'] for c in rows];queue=read(Path(root)/'configs/queue.json')
 if set(queue)!={'jobs','finalize'} or queue['jobs']!=names or type(queue['finalize']) is not bool:raise ValueError('queue differs')
 return {c['run_id']:{'source_id':c['source_id'],'seed':c['seed'],'arm':'auto','case':c,'graph_sha256':sha(Path(root)/'configs/graphs'/(c['run_id']+'.json'))} for c in rows},names

def audit_dir(value):
 p=Path(value)
 if not p.is_absolute() or p.is_symlink() or p.resolve()!=REMOTE/'audit':raise ValueError('audit root outside frozen R55')
 return p.resolve()
audit_root=audit_dir

def validate_job(run,root=ROOT,inputs=True):
 root=Path(root);found=[c for c in cases(root) if c['run_id']==run]
 if len(found)!=1:raise ValueError('unknown case')
 case=found[0];parent=root/case['parent_graph']
 if sha(parent)!=case['parent_graph_sha256']:raise ValueError('parent graph differs')
 path=root/'configs/graphs'/(run+'.json')
 if path.is_symlink() or read(path)!=derive(read(parent),case):raise ValueError('graph differs from frozen parent transformation')
 if case['prompt']!=case['original_task']['edit_prompt'] or case['reference_image_count']!=0 or case['reference_video_count']!=1:raise ValueError('original task changed')
 if inputs:
  for key in ('video','provenance'):
   name=case[key];p=root/'inputs'/name
   if Path(name).name!=name or p.is_symlink() or sha(p)!=case[key+'_sha256']:raise ValueError('input differs')
 return {'case':case,'graph_sha256':sha(path)}
def prepare_loader_inputs(run,root=ROOT):
 root=Path(root);row=validate_job(run,root);case=row['case'];folder=root/'input';folder.mkdir(exist_ok=True)
 src=root/'inputs'/case['video'];dst=folder/case['video']
 if dst.is_symlink():raise ValueError('loader symlink')
 if not dst.exists():
  with src.open('rb') as a,dst.open('xb') as b:shutil.copyfileobj(a,b)
 if sha(dst)!=case['video_sha256']:raise ValueError('loader input differs')
 return row
