import hashlib,json,os
from pathlib import Path

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def read(path):return json.loads(Path(path).read_text())
def write_new(path,value):
 with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def clean(value):
 if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k!='tensor_file'}
 if isinstance(value,list):return [clean(v) for v in value]
 return value

def select_largest(cases,parent_root):
 rows=[]
 for case in cases:
  run=case['parent_run'];path=Path(parent_root)/'audit'/(run+'_conditioning.json');record=read(path)
  segments=record['packed_layout']['segments'];refs=[v for v in segments if v[2]=='ref_img'];targets=[v for v in segments if v[2]=='video']
  require(len(refs)==len(targets)==1 and refs[0][1]-refs[0][0]==27*943,'actual single-video27bin layout differs')
  rows.append({'source_id':case['source_id'],'run':run,'seq_len':record['packed_layout']['seq_len'],'conditioning_file':str(path),'conditioning_sha256':sha(path)})
 require(len(rows)==5,'five metadata cases required')
 selected=sorted(rows,key=lambda r:(-r['seq_len'],r['source_id']))[0]
 return selected,rows

def probe_graph(parent,run_root,config_path):
 import copy
 g=copy.deepcopy(parent);root=Path(run_root);run_id='capacity_native_full_reserve8'
 g['5']['inputs'].update(audit_dir=str(root/'audit'),run_id='capacity_shared')
 g['6']['inputs'].update(audit_dir=str(root/'audit'),run_id=run_id,pair_id='capacity_pair')
 g['50']['inputs'].update(audit_dir=str(root/'audit/router'),run_id=run_id)
 g['51']['inputs'].update(source_audit_dir=str(root/'audit'),source_run_id='capacity_shared',run_id=run_id)
 g['52']={'class_type':'H3MainCapacityProbe','inputs':{'model':['50',0],'config_file':str(config_path)}}
 g['14']['inputs']['filename_prefix']='UNREACHABLE_capacity_probe_no_video'
 return g

def successful_capacity(report):
 require(report.get('status')=='capacity_measured_controlled_stop','capacity probe did not finish')
 require(report.get('inference_complete') is False and report.get('model_forward_calls')==2,'capacity scope differs')
 require(report.get('native_exact') is True and report.get('condition_exact') is True and report.get('noise_exact') is True,'Native source equality failed')
 require([r['branch'] for r in report['forwards']]==['native','full27'],'wrong forward inventory')
 for row in report['forwards']:
  require(row['completed_blocks']==50 and row['routed_blocks']==(50 if row['branch']=='full27' else 0),'actual routing scope differs')
  for key in ('allocated_bytes','reserved_bytes','driver_free_bytes','driver_total_bytes'):
   require(type(row['before'][key]) is int and type(row['after'][key]) is int,'allocator evidence absent')
  require(row['peak_allocated_bytes']>=row['after']['allocated_bytes'] and row['peak_reserved_bytes']>=row['after']['reserved_bytes'],'allocator peak invalid')
 return True
