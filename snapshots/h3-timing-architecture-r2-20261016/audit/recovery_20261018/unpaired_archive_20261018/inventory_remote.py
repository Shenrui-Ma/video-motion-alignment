"""Read-only completed single-run archive manifest; retain tensors remotely."""
from pathlib import Path
import hashlib,json,time
CASES=[('R72','timing_flexiact_prompt_pair_r72_20261018','r72_one_leg__movie_man_9_seed2026101701_p0','r72_one_leg__movie_man_9','r72_one_leg__movie_man_9_seed2026101701_p1'),('R74','timing_flexiact_official_six_r74_20261018','r74_chest__game_man_5_seed2026101701_native','r74_chest__game_man_5','r74_chest__game_man_5_seed2026101701_forced')]
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(8<<20),b''):h.update(c)
 return h.hexdigest()
def leaves(x):
 if isinstance(x,dict):
  for v in x.values():yield from leaves(v)
 elif isinstance(x,list):
  for v in x:yield from leaves(v)
 elif isinstance(x,str):yield x
out=[]
for batch,name,run,prefix,pending in CASES:
 start=time.monotonic();r=Path('/data3/researcher/h3_runs')/name
 history=read(r/'logs'/f'{run}_history.json');job=read(r/'logs'/f'{run}_job.json')
 assert history['status']['completed'] is True and history['status']['status_str']=='success' and job['status']=='success'
 hold=read(r/'audit/task_scope_review_hold_20261018/VERIFIED_HOLD.json')
 assert hold['service_and_controller_proc_absent'] and hold['service_CUDA_absent'] and hold['scientific_queue_preserved']
 image=history['outputs']['14']['images'];assert len(image)==1 and image[0]['type']=='output'
 v=r/'output'/image[0].get('subfolder','')/image[0]['filename'];assert v.resolve().is_relative_to(r/'output') and not v.is_symlink()
 paths={v,r/'logs'/f'{run}_history.json',r/'logs'/f'{run}_job.json',r/'configs/graphs'/f'{run}.json',r/'configs/scientific_contract.json',r/'configs/runtime.json',r/'configs/queue.json',r/'deploy_manifest.json'}
 paths.update((r/'audit/task_scope_review_hold_20261018').glob('*.json'))
 paths.update(q for q in (r/'audit').rglob('*.json') if prefix in str(q))
 cases=read(r/'configs/scientific_contract.json')['cases'];case=[c for c in cases if c['run_id']==run];assert len(case)==1;case=case[0]
 for key in ['video','portrait','provenance']:
  if key in case:
   q=r/'inputs'/case[key];assert q.exists()
   if key+'_sha256' in case:assert sha(q)==case[key+'_sha256']
   paths.add(q)
 seal=read(r/'deploy_manifest.json');bad=[rel for rel,b in seal['files'].items() if sha(r/rel)!=b['sha256']];assert not bad,bad
 captures=read(r/'audit/x0'/run/'manifest.json');assert captures['callback_count']==20 and len(captures['captures'])==20
 tensors=set((r/'audit/x0'/run).glob('*.pt'))
 for q in sorted(paths):
  if q.suffix!='.json':continue
  for value in leaves(read(q)):
   if not value.endswith('.pt'):continue
   pp=Path(value)
   if pp.is_absolute():found=[pp] if pp.exists() and pp.resolve().is_relative_to(r) else []
   else:found=list({a.resolve() for a in [r/'audit'/pp,r/'audit/x0'/run/pp,r/pp,q.parent/pp] if a.is_file()})
   assert len(found)==1,(q,value,found)
   tensors.add(found[0])
 def bound(q):
  s=q.stat();return {'relative':str(q.relative_to(r)),'remote_file':str(q),'sha256':sha(q),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns}
 download=[bound(q) for q in sorted(paths)];remote_only=[bound(q) for q in sorted(tensors)]
 assert not (r/'logs'/f'{pending}_job.json').exists() and not (r/'logs'/f'{pending}_history.json').exists()
 out.append({'schema':'held-unpaired-completed-run-v1','batch':batch,'remote_root':str(r),'run_id':run,'case':case,'status':'completed_single_run_unpaired','counts_as_complete_pair':False,'pending_run':pending,'pending_job_and_history_absent':True,'history_success':True,'job_success':True,'actual_x0_callbacks':captures['callback_count'],'actual_x0_capture_count':len(captures['captures']),'producer_seal_verified':True,'download_files':download,'retained_remote_tensor_files':remote_only,'download_bytes':sum(x['bytes'] for x in download),'remote_tensor_bytes':sum(x['bytes'] for x in remote_only),'remote_inventory_seconds':time.monotonic()-start,'unix':time.time(),'GPU_calls':0})
print(json.dumps(out))
