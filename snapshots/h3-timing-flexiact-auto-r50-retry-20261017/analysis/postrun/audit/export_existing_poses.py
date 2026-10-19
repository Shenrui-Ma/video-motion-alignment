"""Export existing committed/observed first-case poses; no GPU or recomputation."""
from pathlib import Path
import hashlib,io,json,sys,tarfile,time
root=Path(sys.argv[1]);read=lambda p:json.loads(p.read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
case=read(root/'configs/protocol.json')['cases'];assert len(case)==5;case=case[0];run=case['run_id']
source=root/case['source_pose_path'];sraw=source.read_bytes();assert sha(sraw)==case['source_pose_sha256']
cf=root/'audit/counterfactual'/(run+'.json');craw=cf.read_bytes();c=json.loads(craw).get('counterfactual',{});decisions={x['physical_index']:x['decision'] for x in c.get('steps',[])}
files={'source.pose.json':sraw};rows=[]
for p in sorted((root/'audit/observations').glob('step*/response.json')):
 raw=p.read_bytes();response=json.loads(raw);rp=p.parent/'request.json';rraw=rp.read_bytes();request=json.loads(rraw)
 if request['run_id']!=run:continue
 assert response['status']=='complete' and response['request_sha256']==sha(rraw)
 pose=Path(response['pose']['file']);praw=pose.read_bytes();assert pose.is_relative_to(root) and sha(praw)==response['pose']['sha256']
 index=response['physical_index'];assert request['physical_index']==index
 prefix='steps/%03d/'%index
 for name,data in [('request.json',rraw),('response.json',raw),('target.pose.json',praw)]:files[prefix+name]=data
 decision=decisions.get(index)
 if decision is not None:assert decision['response_sha256']==sha(raw)
 rows.append({'denoising_index':index,'run_id':run,'original_decision_committed':decision is not None,'original_decision':decision,
 'request':{'remote_file':str(rp),'relative_file':prefix+'request.json','sha256':sha(rraw)},
 'response':{'remote_file':str(p),'relative_file':prefix+'response.json','sha256':sha(raw)},
 'target_pose':{'remote_file':str(pose),'relative_file':prefix+'target.pose.json','sha256':sha(praw)},
 'observer':response['observer'],'endpoint_file_sha256':response['endpoint_file_sha256']})
rows.sort(key=lambda x:x['denoising_index']);assert len({r['denoising_index'] for r in rows})==len(rows)
index={'schema':'existing-observer-pose-export-v1','observed_unix':time.time(),'root_remote':str(root),'run_id':run,'case':case,
 'source_pose':{'remote_file':str(source),'relative_file':'source.pose.json','sha256':sha(sraw)},'rows':rows,
 'counterfactual_snapshot':{'remote_file':str(cf),'sha256':sha(craw),'bytes':len(craw),'snapshot_only':True},
 'scope':'Exact existing CPU pose files; original observer JSON retained remote; no new inference, no policy change.',
 'files':{name:{'sha256':sha(data),'bytes':len(data)} for name,data in files.items()}}
files['INDEX.json']=(json.dumps(index,indent=2,allow_nan=False)+'\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 for name,data in files.items():
  info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;archive.addfile(info,io.BytesIO(data))
