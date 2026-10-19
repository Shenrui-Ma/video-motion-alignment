"""Local administrative binding only; root must have launched and recorded identities."""
import hashlib,importlib.util,json,shutil,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 frozen=read(P/'FREEZE.json')
 for name,h in frozen['files'].items():
  if sha(P/name)!=h:raise ValueError('consumer frozen file changed '+name)
 lp=ROOT/'audit/live_bindings.json';live=read(lp);selection=read(ROOT/'configs/source_selection_manifest.json')
 spec=importlib.util.spec_from_file_location('consumer_contract',ROOT/'scripts/r26_contract.py');rc=importlib.util.module_from_spec(spec);spec.loader.exec_module(rc)
 out={'created_unix':time.time(),'root_live_bindings_sha256':sha(lp),'source_selection_manifest_sha256':sha(ROOT/'configs/source_selection_manifest.json'),'lanes':{}}
 for lane in ['a','b']:
  row=live['lanes'][lane];local=ROOT/'lanes'/lane;runtime=read(local/'configs/runtime.json');jobs,order=rc.registry(local)
  if row['remote_root']!=runtime['remote_root']:raise ValueError('actual remote root differs from lane runtime')
  manifest=local/'deploy_manifest.json'
  if sha(manifest)!=row['deploy_manifest_sha256']:raise ValueError('live deployed manifest differs from local sealed copy')
  poses={}
  for run in order:
   case=jobs[run]['case'];cid=case['source_id'];s=selection['sources'][cid];dest=P/'source_poses'/f'{cid}.pose.json'
   if sha(dest)!=s['source_pose_sha256'] or read(dest)['video']['sha256']!=case['video_sha256']:raise ValueError('source pose binding')
   poses[cid]={'file':str(dest.relative_to(P)),'sha256':sha(dest),'video_sha256':case['video_sha256'],'tracking_context':'full-source state retained'}
  out['lanes'][lane]={'remote_root':row['remote_root'],'service_pid':row['service']['pid'],'service_identity':row['service']['identity'],'external_identity':row['external_identity'],'manifest_file':'deploy_manifest.json','manifest_sha256':row['deploy_manifest_sha256'],'runs':order,'source_poses':poses}
 with (P/'BINDING.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
 print(sha(P/'BINDING.json'))
if __name__=='__main__':main()
