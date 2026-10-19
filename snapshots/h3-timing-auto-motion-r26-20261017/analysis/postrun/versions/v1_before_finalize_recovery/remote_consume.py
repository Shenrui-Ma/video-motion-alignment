"""Completed-run CPU audit/archival/pose while sibling GPU jobs may continue.
No Comfy HTTP calls, process control, GPU initialization, or producer mutations.
"""
import argparse,fcntl,hashlib,importlib.util,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
BASE=Path('/data5/researcher/h3_runs/timing_auto_motion_r26_20261017')
HERE=BASE/'analysis/postrun'; OLD=Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
HASHES={'scripts/pose_probe.py':'04c6dd432ddf102300a4cd065f4de8b9c2bc0661ce1abb06d994330b32ae693f','scripts/timing_metrics.py':'eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e'}
VISUAL_FRAMES=[0,35,70,105,140]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');t.replace(p)
def require(v,msg):
 if not v:raise ValueError(msg)
def safe(root,rel):
 p=Path(rel);require(not p.is_absolute() and '..' not in p.parts,'unsafe relative path');x=root/p;require(not x.is_symlink() and x.resolve().is_relative_to(root.resolve()),'unsafe/symlink path');return x

def bind(lane,binding):
 b=read(binding)['lanes'][lane];root=BASE/lane;require(str(root)==b['remote_root'],'wrong remote root')
 mp=safe(root,b['manifest_file']);require(sha(mp)==b['manifest_sha256'],'manifest binding')
 owner=read(root/'processes/service.json');require(owner['pid']==b['service_pid'] and owner['identity']==b['service_identity'],'service generation changed')
 proc=Path('/proc')/str(owner['pid'])
 if proc.exists():
  try:
   fields=(proc/'stat').read_text().split(') ',1)[1].split();cmd=(proc/'cmdline').read_bytes();uid=proc.stat().st_uid
  except FileNotFoundError:
   if proc.exists():raise
  else:
   require(uid==b['external_identity']['uid'] and fields[19]==b['external_identity']['start_ticks'],'live identity replaced')
   if fields[0]!='Z':require(hashlib.sha256(cmd).hexdigest()==b['external_identity']['cmdline_sha256'],'live command replaced')
 return root,b,owner

def output_file(root,h,run):
 rows=h.get('outputs',{}).get('14',{}).get('images',[]);require(len(rows)==1,'exactly one final video')
 x=rows[0];require(x['type']=='output' and x.get('subfolder','')=='' and re.fullmatch(re.escape(run)+r'_\d+_\.mp4',x['filename']),'output path/run mismatch')
 return safe(root,'output/'+x['filename'])

def inventory(root,run):
 h=read(root/'logs'/f'{run}_history.json');j=read(root/'logs'/f'{run}_job.json');require(h['status']['completed'] is True and h['status']['status_str']=='success' and j['status']=='success','run not successful')
 c=read(root/'audit'/f'{run}_conditioning.json');n=read(root/'audit'/f'{run}_noise.json');m=read(root/'audit/x0'/run/'manifest.json');require(m['status']=='complete','capture incomplete')
 expected=[f'x0_step{i:03d}.pt' for i in range(20)]+['sampler_final.pt']
 require([x['file'] for x in m['captures']+[m['final_sampler_result']]]==expected,'original manifest PT inventory mismatch')
 require(sorted(x.name for x in (root/'audit/x0'/run).glob('*.pt'))==sorted(expected),'original run PT directory has missing/extra files')
 sys.path.insert(0,str(root/'scripts'));import r26_contract as rc;case=rc.job_record(run,root)['case'];shared=f'r26_{case["case_id"]}_shared_conditioning.json'
 rels={f'logs/{run}_history.json',f'logs/{run}_job.json',f'configs/graphs/{run}.json','configs/queue.json','configs/native_screen.json','configs/native_material_manifest.json','configs/native_source_selection_manifest.json',f'audit/{run}_conditioning.json',f'audit/{run}_noise.json',f'audit/router/{run}.json',f'audit/x0/{run}/manifest.json',f'audit/{shared}',f'audit/{n["pair_id"]}_noise.pt','configs/job_registry.json','configs/runtime.json'}
 for k in ('video','portrait','provenance'):rels.add('inputs/'+case[k])
 for continuation in read(root/'configs/queue.json').get('approved_continuations',[]):rels.add(continuation['file'])
 for x in m['captures']+[m['final_sampler_result']]:rels.add(f'audit/x0/{run}/'+x['file'])
 def visit(v):
  if isinstance(v,dict):
   if 'tensor_file' in v and {'shape','dtype','sha256'}<=set(v):rels.add('audit/'+v['tensor_file'])
   for x in v.values():visit(x)
  elif isinstance(v,list):
   for x in v:visit(x)
 visit(read(root/'audit'/shared));rels.add(str(output_file(root,h,run).relative_to(root)))
 paths=[safe(root,x) for x in sorted(rels)];require(all(p.is_file() for p in paths),'completed run file missing');return paths

def snapshot(lane,binding):
 root,b,owner=bind(lane,binding);result={'lane':lane,'service_pid':owner['pid'],'time':time.time(),'runs':{}}
 controller=read(root/'logs/controller_state.json') if (root/'logs/controller_state.json').exists() else {}
 terminal=controller.get('status') in ('failed','final_close','bounded_idle_expired')
 cleanup=read(root/'processes/cleanup.json') if (root/'processes/cleanup.json').exists() else {}
 exact_cleanup=cleanup.get('service_record')==owner and cleanup.get('process_absent') is True and cleanup.get('own_compute_absent') is True
 terminal=terminal or exact_cleanup
 for run in b['runs']:
  hp=root/'logs'/f'{run}_history.json';jp=root/'logs'/f'{run}_job.json'
  h=read(hp) if hp.exists() else {};j=read(jp) if jp.exists() else {}
  if h.get('status',{}).get('status_str')=='error' or j.get('status') in ('error','unknown_missing','submission_uncertain'):
   result['runs'][run]={'status':'failed','reason':'producer_failed_or_uncertain','history_status':h.get('status'),'job_status':j.get('status')};continue
  if not(h.get('status',{}).get('completed') and h['status'].get('status_str')=='success' and j.get('status')=='success'):
   result['runs'][run]={'status':'failed' if terminal else 'pending','reason':('unsubmitted_after_terminal' if not jp.exists() else 'incomplete_after_terminal') if terminal else 'awaiting_success','controller_status':controller.get('status'),'exact_cleanup':exact_cleanup};continue
  try:
   ps=inventory(root,run);rows=[{'path':str(p.relative_to(root)),'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'json_sha256':sha(p) if p.suffix=='.json' else None} for p in ps]
   result['runs'][run]={'status':'success_files_present','stability_token':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),'file_count':len(rows)}
  except (FileNotFoundError,KeyError) as e:result['runs'][run]={'status':'failed' if terminal else 'completion_files_pending','reason':'completed_files_missing_after_terminal' if terminal else 'awaiting_complete_files','error':str(e)}
 result['batch_ready']=(controller.get('completed')==b['runs'] and controller.get('current') is None and controller.get('status') in ('resident_hold','final_close','bounded_idle_expired'));result['producer_terminal']=terminal
 return result

def load_runtime(root):
 os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['OMP_NUM_THREADS']='1';sys.path.insert(0,str(root/'scripts'))
 import torch
 torch.set_num_threads(1);require(not torch.cuda.is_initialized(),'CUDA initialized')
 import verify_batch as vb
 import r26_contract as rc
 return torch,vb,rc

def locked():
 lock=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);return lock

def capture_and_audit(lane,run,binding,token):
 lock=locked();started=time.time();root,b,owner=bind(lane,binding);require(run in b['runs'],'run not bound')
 require(snapshot(lane,binding)['runs'][run]['stability_token']==token,'changed after stable observation')
 manifest=read(safe(root,b['manifest_file']));
 for rel,entry in manifest['files'].items():require(sha(safe(root,rel))==entry['sha256'],'deployed file changed '+rel)
 torch,vb,rc=load_runtime(root);row=rc.validate_job(run,root);case=row['case'];seed=row['seed'];full=row['arm']=='full_6to14';arc=HERE/'captured'/run
 if (arc/'CPU_COMPLETE.json').exists():
  done=read(arc/'CPU_COMPLETE.json');require(done['passed'] and done['run_id']==run and read(arc/'RUN_GATE.json')['passed'],'invalid existing completion')
  require(all(sha(safe(arc,k))==v['sha256']==sha(safe(root,k)) for k,v in read(arc/'FILE_INVENTORY.json').items()),'existing completed archive/source changed')
  return done
 require(not arc.exists(),'incomplete archive already exists; inspect, never overwrite')
 paths=inventory(root,run);before={str(p.relative_to(root)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in paths}
 arc.mkdir(parents=True)
 for p in paths:
  rel=str(p.relative_to(root));dst=safe(arc,rel);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);require(sha(dst)==before[rel]['sha256']==sha(p),'copy/source mutation '+rel)
 save(arc/'FILE_INVENTORY.json',before)
 h=read(arc/'logs'/f'{run}_history.json');j=read(arc/'logs'/f'{run}_job.json');g=read(arc/'configs/graphs'/f'{run}.json');grid=torch.tensor([float(x) for x in g['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist()
 checks={};checks['history_graph']=(h['status']['completed'] is True and h['status']['status_str']=='success' and h['prompt'][2]==g and h['prompt'][1]==j['prompt_id']);checks['service']=(j['status']=='success' and j['service_pid']==owner['pid'] and j['service_identity']==owner['identity'] and j['graph_sha256']==row['graph_sha256'])
 c=read(arc/'audit'/f'{run}_conditioning.json');n=read(arc/'audit'/f'{run}_noise.json');shared=arc/'audit'/f'r26_{case["case_id"]}_shared_conditioning.json';checks['actual_shared_condition']=(c['run_id']==run and c['pair_snapshot']['verified'] is True and c['pair_snapshot']['source_manifest_sha256']==sha(shared))
 blobs=[];seen=set()
 def visit(v):
  if isinstance(v,dict):
   if 'tensor_file' in v and {'shape','dtype','sha256'}<=set(v) and v['tensor_file'] not in seen:seen.add(v['tensor_file']);blobs.append(vb.inspect_blob(arc/'audit',v))
   for x in v.values():visit(x)
  elif isinstance(v,list):
   for x in v:visit(x)
 visit(read(shared));router=read(arc/'audit/router'/f'{run}.json')
 expect={'run_id':run,'mode':'mass_preserve' if full else 'native','alpha':1.,'radius':0,'time_offset':0,'block_interval_half_open':[0,50],'step_interval_half_open':[0,20],'pixel_interval_inclusive':case['primary_window_inclusive'],'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,'routed_calls':450 if full else 0,'calls_by_forward':[50]*20,'calls_by_block':[20]*50,'routed_by_forward':vb.expected_routing(full),'routed_by_block':[9 if full else 0]*50,'sample_sigmas':grid,'expected_sampling_steps':20}
 checks['20_actual_forwards']=all(router.get(k)==v for k,v in expect.items());seq=c['packed_layout']['seq_len'];plan=router['validated_layout'];checks['actual_layout']=(router['first_attention']['qkv_shape']==[1,56,seq,128] and router['first_attention']['heads']==56 and plan['seq_len']==seq and [list(x) for x in plan['segments']]==c['packed_layout']['segments'] and plan['pixel_interval_inclusive']==case['primary_window_inclusive'] and plan['frame_rows']==943)
 checks['native_only']=(row['arm']=='native' and seed==2026101701);checks['actual_embedding_stored']='tensor_file' in read(shared)['conditioning_embedding']
 checks['finite_router']=all(x.get('sampled_finite',True) for x in router['forward_summaries']);m,files,prefix=vb.inspect_capture(arc/'audit/x0'/run,run,grid,seed)
 cache=arc/'audit'/f'{n["pair_id"]}_noise.pt';saved=torch.load(cache,map_location='cpu',weights_only=True);actual=[{k:vb.signature(t)[k] for k in ('shape','dtype','sha256')} for t in saved['tensors']]
 checks['actual_noise']=(n['run_id']==run and n['pair_id']==f'r26_{case["case_id"]}_seed{seed}' and n['signature']['seed']==seed and len(actual)==2 and saved['signature']==n['signature'] and saved['hashes']==actual==n['actual_noise_streams'])
 checks['copied_files_post_audit']=all(sha(safe(arc,k))==v['sha256']==sha(safe(root,k)) for k,v in before.items())
 result={'passed':all(checks.values()),'checks':checks,'run_id':run,'lane':lane,'case':case,'seed':seed,'arm':row['arm'],'owner':owner,'manifest_sha256':b['manifest_sha256'],'file_inventory_sha256':sha(arc/'FILE_INVENTORY.json'),'snapshot_files':files,'condition_tensor_files':blobs,'NFE':20,'callbacks':20,'Euler_updates':20,'Euler_evidence':'Frozen actual20Euler graph+20callbacks+1000blocks','job_wall_seconds':j['observed_unix']-j['submitted_unix'],'capture_wrapper_seconds':m['finished_unix']-m['created_unix'],'copy_snapshot_seconds':sum(x['capture_seconds'] for x in m['captures']),'execution_cached_events':[x for x in h['status'].get('messages',[]) if x[0]=='execution_cached'],'integrity_seconds':time.time()-started,'service_cleanup_required':False,'service_cleanup_claim':False}
 save(arc/'RUN_GATE.json',result);require(result['passed'],'actual run gate failed')
 for rel,d in HASHES.items():require(sha(OLD/rel)==d,'frozen evaluation changed '+rel)
 source_binding=b['source_poses'][case['source_id']];source=safe(HERE,source_binding['file']);require(sha(source)==source_binding['sha256'] and read(source)['video']['sha256']==case['video_sha256'],'source pose binding')
 video=output_file(arc,h,run);pose_dir=arc/'pose';env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4')
 cmd=[sys.executable,str(OLD/'scripts/pose_probe.py'),'--video',str(video),'--output-dir',str(pose_dir),'--threads','4']
 for f in VISUAL_FRAMES:cmd+=['--overlay-frame',str(f)]
 with (arc/'pose_extract.log').open('w') as log:subprocess.run(cmd,env=env,check=True,stdout=log,stderr=subprocess.STDOUT)
 pp=pose_dir/(video.stem+'.pose.json');praw=read(pp);require(praw['video']['sha256']==sha(video) and praw['statistics']['processed_frames']==141 and praw['video']['fps']==24 and [x['frame'] for x in praw['frames']]==list(range(141)),'pose video binding');sprov=read(source)['provenance']
 for k in ('detector_sha256','pose_sha256','detector_code_sha256','pose_code_sha256','script_sha256'):require(praw['provenance'][k]==sprov[k],'pose model/code provenance '+k)
 scan=arc/'scan';cmd=[sys.executable,str(HERE/'scan_native.py'),'--source',str(source),'--target',str(pp),'--output',str(scan),'--run',run]
 with (arc/'scan.log').open('x') as log:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
 scan_result=read(scan/'RESULTS.json');require(len(scan_result['windows'])==186,'expected all186 overlapping part windows')
 require(all(sha(safe(arc,k))==v['sha256']==sha(safe(root,k)) for k,v in before.items()),'post-consumption source/archive changed')
 done={'passed':True,'run_id':run,'arc':str(arc),'video':str(video),'video_sha256':sha(video),'pose':str(pp),'pose_sha256':sha(pp),'source_pose_sha256':sha(source),'elapsed_seconds':time.time()-started,'pose_seconds':praw['statistics']['elapsed_s'],'all_UNKNOWN_retained':True,'scan_summary':scan_result['summary'],'scan_result_sha256':sha(scan/'RESULTS.json'),'no_GPU':True,'model_device':praw['provenance']['device'],'providers':praw['provenance']['providers']};save(arc/'CPU_COMPLETE.json',done);return done


def batch(lane,binding):
 lock=locked();root,b,owner=bind(lane,binding);torch,vb,rc=load_runtime(root)
 for run in b['runs']:require(read(HERE/'captured'/run/'CPU_COMPLETE.json')['passed'],'run consumer incomplete')
 result=vb.verify(root,HERE/f'BATCH_{lane}.json');require(result['passed'],'actual lane batch gate')
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['snapshot','consume','batch']);p.add_argument('--lane',choices=['a','b'],required=True);p.add_argument('--binding',required=True);p.add_argument('--run');p.add_argument('--token');a=p.parse_args()
 try:
  if a.mode=='snapshot':r=snapshot(a.lane,a.binding)
  elif a.mode=='consume':r=capture_and_audit(a.lane,a.run,a.binding,a.token)
  else:r=batch(a.lane,a.binding)
  print(json.dumps(r,allow_nan=False))
 except BlockingIOError:print('CPU_LOCK_BUSY');raise SystemExit(75)
if __name__=='__main__':main()
