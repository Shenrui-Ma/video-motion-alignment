"""Singleton online execution; original R73 prompt, graph and source stay bound."""
import copy,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUN='r144_long_0039_seed2026101701_visible_only'
SOURCES=('long_0039',)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for v in iter(lambda:f.read(1048576),b''):h.update(v)
 return h.hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)
REMOTE=Path(read(ROOT/'configs/runtime.json')['remote_root'])
def expected_graph(root=ROOT):
 root=Path(root);g=copy.deepcopy(read(root/'configs/PARENT_GRAPH.json'));remote=Path(read(root/'configs/runtime.json')['remote_root'])
 for node,key,folder in [('5','audit_dir','audit'),('6','audit_dir','audit'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=str(remote/folder)
 for node in ('6','51','52'):g[node]['inputs']['run_id']=RUN
 g['14']['inputs']['filename_prefix']=RUN
 g['50']={'class_type':'H3AutomaticWindowRouter','inputs':{'model':['41',0],'positive':['51',0],'run_id':RUN,'audit_dir':str(remote/'audit/counterfactual')}}
 return g

def registry(root=ROOT):
 root=Path(root);p=read(root/'configs/protocol.json');s=read(root/'configs/scientific_contract.json');q=read(root/'configs/queue.json')
 require(p['arms']==['visible_only'] and len(p['cases'])==1 and s['cases']==p['cases'] and s['case_order']==[RUN],'singleton visible-only registry differs')
 require(q=={'jobs':[RUN],'finalize':True},'queue differs')
 c=p['cases'][0];g=read(root/'configs/PARENT_GRAPH.json');require(c['source_id']=='long_0039' and c['run_id']==RUN and c['seed']==2026101701,'identity differs')
 require(c['geometry']=={'width': 1312, 'height': 736, 'frames': 107, 'fps': 24} and c['valid_frame_count']==106,'geometry differs')
 require(c['arm']=='visible_only' and c['prompt']==g['5']['inputs']['prompt']==(root/'configs/prompts/long_0039.txt').read_text(),'original P1 prompt differs')
 require(c['parent_graph_sha256']==sha(root/'configs/PARENT_GRAPH.json'),'original graph differs')
 bounds=p['person_selection']['selected_bbox_center_x_fraction']; require(bounds is None or (len(bounds)==2 and 0<=bounds[0]<bounds[1]<=1),'invalid source-specified identity bounds')
 graph=root/'configs/graphs'/(RUN+'.json');require(read(graph)==expected_graph(root),'graph differs outside authorized observer/run/path changes')
 return {RUN:{'case':c,'arm':c['arm'],'source_id':c['source_id'],'seed':c['seed'],'graph_sha256':sha(graph)}},[RUN]

def validate_job(run,root=ROOT):
 root=Path(root);jobs,_=registry(root);require(run in jobs,'unregistered online job')
 for name,digest in read(root/'configs/input_hashes.json').items():require(sha(root/'inputs'/name)==digest,'source input differs: '+name)
 return jobs[run]

def audit_dir(value):
 p=Path(value);require(p.is_absolute() and p.resolve()==REMOTE/'audit','audit root differs');return p

def prepare_loader_inputs(run,root=ROOT):
 root=Path(root);row=validate_job(run,root);c=row['case'];target=root/'input'/c['video'];target.parent.mkdir(exist_ok=True)
 if not target.exists():
  with (root/'inputs'/c['video']).open('rb') as f,target.open('xb') as o:shutil.copyfileobj(f,o)
 require(not target.is_symlink() and sha(target)==c['video_sha256'],'loader source differs')
 return row
