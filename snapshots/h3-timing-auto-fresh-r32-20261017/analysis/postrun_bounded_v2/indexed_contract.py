"""Small dependency indexes; copied from audited R27 recovery helpers."""
from contract import *

def stat_inventory(root,arc,inventory):
 records=[]
 for rel in sorted(inventory):
  for kind,base in (('archive',arc),('source',root)):
   if kind=='source' and rel=='configs/queue.json':continue
   p=safe(base,rel);s=p.stat();require(p.is_file(),'stat inventory missing file')
   records.append([kind,rel,s.st_size,s.st_mtime_ns])
 return canonical_sha(records)

def index_measurement(root,arc,run,index,measurement,inventory):
 m=measurement;require(m['physical_index']==index and m['status']=='complete','measurement order/status')
 reqrel=relative(root,m['request_file']);resrel=relative(root,m['response_file'])
 request=read(safe(arc,reqrel));response=read(safe(arc,resrel))
 require(request['run_id']==run and request['physical_index']==index and response['physical_index']==index,'request/run/index binding')
 require(sha(safe(arc,reqrel))==m['request_sha256']==response['request_sha256'],'request SHA differs')
 require(sha(safe(arc,resrel))==m['response_sha256'],'response SHA differs')
 deps={'configs/source.pose.json',reqrel,resrel,relative(root,request['endpoint_file'])}
 for key in ('decode','pose','observer'):
  rel=relative(root,response[key]['file']);deps.add(rel)
  require(sha(safe(arc,rel))==response[key]['sha256'],'response dependency SHA '+key)
 observer=numeric_observer(read(safe(arc,relative(root,response['observer']['file']))))
 require(observer==numeric_observer(m['observer']),'measurement/observer numeric mismatch')
 pose=safe(arc,relative(root,response['pose']['file']));source=safe(arc,'configs/source.pose.json')
 require(observer['physical_index']==index and observer['source_pose_sha256']==sha(source) and observer['edited_pose_sha256']==sha(pose),'observer source identity')
 require(request['endpoint_file_sha256']==response['endpoint_file_sha256']==inventory[relative(root,request['endpoint_file'])]['sha256'],'Native endpoint SHA binding')
 expected={'index':index,'scan_sha256':canonical_sha(observer),'source_pose_sha256':sha(source),'pose_sha256':sha(pose),'producer_observer_sha256':canonical_sha(observer),'summary':observer_summary(observer)}
 return {'run_id':run,'index':index,'dependencies':{n:inventory[n] for n in sorted(deps)},'source':'configs/source.pose.json','pose':relative(root,response['pose']['file']),'expected_replay':expected}

def check_index(path,want,run,index,inventory):
 require(sha(path)==want,'recovery index changed');d=read(path)
 require(d['run_id']==run and type(d['index']) is int and d['index']==index,'index identity')
 require(d['dependencies'] and all(inventory.get(n)==v for n,v in d['dependencies'].items()),'index dependencies diverge from original inventory')
 require(d['source']=='configs/source.pose.json' and d['source'] in d['dependencies'] and d['pose'] in d['dependencies'],'index source/pose dependency absent')
 require(d['expected_replay']['index']==index,'expected index differs');return d

def verify_data_dependencies(root,arc,deps):
 for rel,want in deps.items():
  for base in (root,arc):
   p=safe(base,rel);require(p.stat().st_size==want['bytes'] and sha(p)==want['sha256'],'phase dependency differs '+rel)
 return {k:v['sha256'] for k,v in deps.items()}

def validate_partial_inventory(arc,inventory):
 allowed=set(inventory)|{'FILE_INVENTORY.json','RUN_GATE.json','RUNTIME_GATE.json','DECISION_LEDGER.json','verify.log','ADMIN_ADMISSION_AT_ARCHIVE.json'}
 if (arc/'ADMIN_RELEASE_ACCEPTANCE.json').exists():allowed.add('ADMIN_RELEASE_ACCEPTANCE.json')
 replays={str(p.relative_to(arc)) for p in (arc/'observer_replay').glob('*.json')}
 require(replays<={f'observer_replay/{i:03d}.json' for i in range(20)},'unexpected replay index')
 require({str(p.relative_to(arc)) for p in arc.rglob('*') if p.is_file()}==allowed|replays,'partial original/derived inventory differs')
 return replays
