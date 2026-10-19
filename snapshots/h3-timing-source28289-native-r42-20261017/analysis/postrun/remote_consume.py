"""Read-only producer intake, one fixed source28289 Native result. All inference is already complete."""
import argparse,fcntl,os,shutil,subprocess,sys,time
from pathlib import Path
from contract import *
P=read(HERE/'PROTOCOL.json');ROOT=Path(P['root_remote']);ARC=HERE/'captured/batch';OLD=Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')

def bound():
 b=read(HERE/'BINDING.json');owner=check_binding(ROOT,b,P)
 proc=Path('/proc')/str(owner['pid'])
 if proc.exists():
  stat=(proc/'stat').read_text().split(') ',1)[1].split();require(proc.stat().st_uid==b['external_identity']['uid'] and stat[19]==b['external_identity']['start_ticks'],'owner PID changed')
  if stat[0]!='Z':require(hashlib.sha256((proc/'cmdline').read_bytes()).hexdigest()==b['external_identity']['cmdline_sha256'],'owner command changed')
 return owner

def inventory():
 rels={'processes/service.json','deploy_manifest.json','configs/queue.json','configs/runtime.json','configs/runtime_provenance.json'}
 for case in P['cases']:
  run=case['run_id'];g=read(ROOT/'configs/graphs'/f'{run}.json');h=read(ROOT/'logs'/f'{run}_history.json');j=read(ROOT/'logs'/f'{run}_job.json');require(h['status']['completed'] is True and h['status']['status_str']=='success' and j['status']=='success','all planned Native jobs must complete')
  rels.update((f'logs/{run}_history.json',f'logs/{run}_job.json',f'configs/graphs/{run}.json',f'audit/{run}_conditioning.json',f'audit/{run}_noise.json',f'audit/router/{run}.json',f'audit/x0/{run}/manifest.json'))
  m=read(ROOT/'audit/x0'/run/'manifest.json');names=[f'x0_step{i:03d}.pt' for i in range(20)]+['sampler_final.pt'];require(m['status']=='complete' and [r['file'] for r in m['captures']+[m['final_sampler_result']]]==names and sorted(x.name for x in (ROOT/'audit/x0'/run).glob('*.pt'))==sorted(names),'21 chosen inventory')
  rels.update(f'audit/x0/{run}/'+x for x in names);n=read(ROOT/'audit'/f'{run}_noise.json');rels.add('audit/'+n['pair_id']+'_noise.pt');shared='audit/'+g['5']['inputs']['run_id']+'_conditioning.json';rels.add(shared)
  def visit(v):
   if isinstance(v,dict):
    if 'tensor_file' in v and {'shape','dtype','sha256'}<=set(v):rels.add('audit/'+v['tensor_file'])
    for x in v.values():visit(x)
   elif isinstance(v,list):
    for x in v:visit(x)
  visit(read(ROOT/shared));rels.add(relative(ROOT,output_file(ROOT,h,run)))
 for rel in read(ROOT/'deploy_manifest.json')['files']:
  if rel.startswith('inputs/'):
   rels.add(rel)
   if not rel.endswith('_provenance.json'):rels.add(rel.replace('inputs/','input/',1))
 return [safe(ROOT,x) for x in sorted(rels)]

def snapshot():
 owner=bound();controller=read(ROOT/'logs/controller_state.json') if (ROOT/'logs/controller_state.json').exists() else {};states=[]
 for c in P['cases']:
  run=c['run_id'];hp=ROOT/'logs'/f'{run}_history.json';jp=ROOT/'logs'/f'{run}_job.json';h=read(hp) if hp.exists() else {};j=read(jp) if jp.exists() else {}
  if h.get('status',{}).get('status_str')=='error' or j.get('status') in ('error','unknown_missing','submission_uncertain'):return {'status':'failed','run':run,'history':h.get('status'),'job':j.get('status')}
  states.append(h.get('status',{}).get('completed') is True and h.get('status',{}).get('status_str')=='success' and j.get('status')=='success')
 if not all(states):return {'status':'failed' if controller.get('status')=='failed' else 'pending','job_success':states,'controller':controller}
 ps=inventory();token=canonical_sha([{'rel':relative(ROOT,p),'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'json_sha':sha(p) if p.suffix=='.json' else None} for p in ps]);return {'status':'success_files_present','token':token,'owner':owner,'files':len(ps)}

def online_pending():
 for root in map(Path,P['online_priority_roots']):
  for d in (root/'audit/observations').glob('step*'):
   if (d/'request.json').exists() and (d/'native.json').exists() and not (d/'pose_complete.json').exists() and not (d/'response.json').exists():return True
 return False

def locked():
 if online_pending():raise BlockingIOError('online pose priority')
 f=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if online_pending():f.close();raise BlockingIOError('online pose priority')
 return f

def checked_archive():
 owner=bound();verify_archive_anchor(ARC,'batch',owner);verify_producer_sources(ROOT,P['producer_manifest_sha256']);return owner

def archive(token):
 with locked():
  owner=bound();require(snapshot()['token']==token,'completion token changed');require(not ARC.exists(),'partial archive requires explicit review')
  for rel,r in read(ROOT/'deploy_manifest.json')['files'].items():require(sha(safe(ROOT,rel))==r['sha256'],'sealed producer changed '+rel)
  files=inventory();inv={relative(ROOT,p):{'sha256':sha(p),'bytes':p.stat().st_size} for p in files};ARC.mkdir(parents=True)
  for p in files:
   dest=safe(ARC,relative(ROOT,p));dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);require(sha(dest)==sha(p)==inv[relative(ROOT,p)]['sha256'],'archive changed during copy')
  save(ARC/'FILE_INVENTORY.json',inv);save(ARC/'ADMIN_ADMISSION_AT_ARCHIVE.json',read(ROOT/'configs/admission.json'))
  with (ARC/'verify.log').open('x') as log:
   proc=subprocess.run([sys.executable,str(ROOT/'scripts/verify_batch.py'),'--output',str(ARC/'RUNTIME_GATE.json')],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'),timeout=480)
  require(proc.returncode==0 and read(ARC/'RUNTIME_GATE.json')['passed'] is True,'fixed batch runtime gate failed')
  gate={'passed':True,'run_id':'batch','runs':[x['run_id'] for x in P['cases']],'owner':owner,'file_inventory_sha256':sha(ARC/'FILE_INVENTORY.json'),'runtime_gate_sha256':sha(ARC/'RUNTIME_GATE.json'),'cleanup_claim':False,'CPU_final_pending':True};save(ARC/'RUN_GATE.json',gate);verify_source_archive(ROOT,ARC,owner,'batch');verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True);save(HERE/'archive_receipts/batch.json',{'run_id':'batch','owner':owner,'run_gate_sha256':sha(ARC/'RUN_GATE.json'),'inventory_sha256':sha(ARC/'FILE_INVENTORY.json')});return gate

def source_pose(sourcevideo):
 from scan_current_pose import valid_pose
 folder=ARC/'source_pose'/sourcevideo.stem;inventory=folder/'SOURCE_FILES.json'
 if folder.exists():
  require(inventory.exists(),'partial source pose needs review');files=read(inventory)
  require({str(x.relative_to(folder)) for x in folder.rglob('*') if x.is_file()}==set(files)|{'SOURCE_FILES.json'},'source pose inventory differs')
  for rel,d in files.items():require(sha(safe(folder,rel))==d,'source pose changed')
 else:
  folder.mkdir(parents=True);cmd=[sys.executable,str(OLD/'scripts/pose_probe.py'),'--video',str(sourcevideo),'--output-dir',str(folder),'--threads','4','--stride','1']
  with (folder/'pose.log').open('x') as log:proc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4'),timeout=240)
  require(proc.returncode==0,'source pose technical failure')
  save(inventory,{str(x.relative_to(folder)):sha(x) for x in folder.rglob('*') if x.is_file()})
 pose=folder/(sourcevideo.stem+'.pose.json');raw=valid_pose(pose);require(raw['video']['sha256']==sha(sourcevideo),'source pose input hash');return pose

def evaluate_case(case):
 from evaluate import fixed_metrics,common_regions,media_and_pixels
 import timing_metrics as metrics
 from scan_current_pose import observe,valid_pose
 start=time.monotonic();run=case['run_id'];dest=ARC/'final'/run;require(not dest.exists(),'partial case evaluation requires review');dest.mkdir(parents=True)
 for path,d in P['frozen_external'].items():require(sha(path)==d,'frozen metric/model changed '+path)
 h=read(ARC/'logs'/f'{run}_history.json');video=output_file(ARC,h,run);g=read(ARC/'configs/graphs'/f'{run}.json');sourcevideo=ARC/'input'/g['22']['inputs']['file'];deps=verify_phase_dependencies(ROOT,ARC,{relative(ARC,video),relative(ARC,sourcevideo),f'configs/graphs/{run}.json',f'logs/{run}_history.json',f'logs/{run}_job.json',f'audit/router/{run}.json'});source=source_pose(sourcevideo)
 cmd=[sys.executable,str(OLD/'scripts/pose_probe.py'),'--video',str(video),'--output-dir',str(dest/'pose'),'--threads','4','--stride','1']
 for f in P['fixed_visual_frames']:cmd+=['--overlay-frame',str(f)]
 with (dest/'pose.log').open('x') as log:proc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4'),timeout=240)
 require(proc.returncode==0,'technical pose failure');pose=dest/'pose'/(video.stem+'.pose.json');raw=valid_pose(pose);require(raw['video']['sha256']==sha(video) and raw['provenance']==read(source)['provenance'],'pose input/model/provenance changed')
 poses={'Native':pose};fixed=fixed_metrics(source,poses,case['windows'],P['thresholds'],metrics);save(dest/'FIXED_WINDOWS.json',{'window_scope':case['window_scope'],'results':fixed})
 scan=observe(source,pose,19);save(dest/'NATIVE_WHOLE_SCAN.json',scan);summary_scan=observer_summary(scan)
 regions={'whole_clip':list(range(141))};regions.update({f'pregeneration_source_{a}_{b}':list(range(a,b+1)) for a,b in case['windows']})
 for length in (16,32):
  for a in sorted(set(range(0,141-length+1,4))|{141-length}):regions[f'scan_{a}_{a+length-1}']=list(range(a,a+length))
 for confidence in P['thresholds']:save(dest/f'COMMON_{confidence}.json',common_regions(source,poses,regions,confidence,metrics))
 media_and_pixels({'SOURCE':sourcevideo,'Native':video},dest/'media',P['fixed_visual_frames'],P['fixed_clip_inclusive'])
 from presentation import render_layout
 render_layout({'SOURCE':sourcevideo,'Native':video},dest/'presentation',P,P['presentation']['layouts']['source_native'])
 router=read(ARC/'audit/router'/f'{run}.json');job=read(ARC/'logs'/f'{run}_job.json');summary={'passed':True,'run_id':run,'seed':case['seed'],'NFE':20,'actual_routed_blocks':router['routed_calls'],'video':str(video),'video_sha256':sha(video),'pose':str(pose),'pose_sha256':sha(pose),'source_pose':str(source),'source_pose_sha256':sha(source),'phase_dependency_hashes':deps,'scan_summary':summary_scan,'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'chosen20_capture_seconds':sum(x['capture_seconds'] for x in read(ARC/'audit/x0'/run/'manifest.json')['captures']),'final_capture_cost':'included in total job wall; no isolated timing claim','CPU_seconds':time.monotonic()-start,'quality_review':'pending identity/background/shape/limb/ghosting inspection; arm pose alone does not establish exact hand shape, character identity or appearance','scope':P['scope'],'all_UNKNOWN_retained':True};save(dest/'SUMMARY.json',summary);return summary

def cross_source_summary():
 summaries=[read(ARC/'final'/case['run_id']/'SUMMARY.json') for case in P['cases']]
 require([x['run_id'] for x in summaries]==[x['run_id'] for x in P['cases']],'case order differs')
 require(len({x['source_pose_sha256'] for x in summaries})==len(P['cases']),'each planned source requires its actual pose')
 folder=ARC/'batch_summary';require(not folder.exists(),'partial summary needs review');folder.mkdir()
 save(folder/'SUMMARY.json',{'passed':True,'cases':summaries,'sources':[x['source_id'] for x in P['cases']],'fixed_seed':2026101701,'all_outcomes_retained':True,'pooled_motion_metric':False,'scan_rows_not_independent_trials':True,'quality_review':'pending independent fixed frames and continuous video review','scope':P['scope']})

def validate_final():
 owner=checked_archive();verify_source_archive(ROOT,ARC,owner,'batch');verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True);done=read(ARC/'CPU_COMPLETE.json');require(done['passed'] is True and done['runs']==[x['run_id'] for x in P['cases']],'wrong completion')
 inv=read(ARC/'FILE_INVENTORY.json');derived=read(ARC/'DERIVED_FILES.json');allowed={'FILE_INVENTORY.json','DERIVED_FILES.json'}|({'ADMIN_RELEASE_ACCEPTANCE.json'} if (ARC/'ADMIN_RELEASE_ACCEPTANCE.json').exists() else set());require(set(done['derived_outputs'])|{'CPU_COMPLETE.json'}==set(derived),'derived manifest omitted output')
 require({str(p.relative_to(ARC)) for p in ARC.rglob('*') if p.is_file()}==set(inv)|set(derived)|allowed,'exact final inventory')
 for rel,d in derived.items():require(sha(safe(ARC,rel))==d,'derived output changed '+rel)
 return done

def status():
 if not ARC.exists():return {'phase':'archive'}
 checked_archive()
 if (ARC/'CPU_COMPLETE.json').exists():
  done=read(ARC/'CPU_COMPLETE.json');receipt=read(HERE/'final_receipt.json');require(done['passed'] is True and sha(ARC/'CPU_COMPLETE.json')==receipt['complete_sha256'] and sha(ARC/'DERIVED_FILES.json')==receipt['derived_sha256'],'completed receipt changed');return {'phase':'complete','result':done}
 for c in P['cases']:
  p=ARC/'final'/c['run_id']/'CASE_FILES.json'
  if not p.exists():return {'phase':'case','run':c['run_id']}
  files=read(p);folder=p.parent;require({x.name for x in folder.iterdir()} >= {'SUMMARY.json','CASE_FILES.json'},'case incomplete')
  require({str(x.relative_to(folder)) for x in folder.rglob('*') if x.is_file()}==set(files)|{'CASE_FILES.json'},'case exact inventory')
  for rel,d in files.items():require(sha(safe(folder,rel))==d,'case result changed')
 return {'phase':'finalize'}

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['snapshot','archive','status','case','finalize']);p.add_argument('--token');p.add_argument('--run');a=p.parse_args()
 for rel,d in read(HERE/'FREEZE.json')['files'].items():require(sha(HERE/rel)==d,'consumer changed')
 if a.mode=='snapshot':result=snapshot()
 elif a.mode=='archive':result=archive(a.token)
 else:
  with locked():
   if a.mode=='status':result=status()
   elif a.mode=='case':
    checked_archive();cases=[x for x in P['cases'] if x['run_id']==a.run];require(len(cases)==1,'case outside fixed protocol');result=evaluate_case(cases[0]);dest=ARC/'final'/a.run;save(dest/'CASE_FILES.json',{str(x.relative_to(dest)):sha(x) for x in dest.rglob('*') if x.is_file()})
   else:
    require(status()['phase']=='finalize','not all cases complete');owner=checked_archive();verify_source_archive(ROOT,ARC,owner,'batch');verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True);cross_source_summary();original=read(ARC/'FILE_INVENTORY.json');paths=sorted(str(x.relative_to(ARC)) for x in ARC.rglob('*') if x.is_file() and str(x.relative_to(ARC)) not in original and x.name!='ADMIN_RELEASE_ACCEPTANCE.json');result={'passed':True,'runs':[x['run_id'] for x in P['cases']],'derived_outputs':paths,'no_GPU':True,'cleanup_claim':False};save(ARC/'CPU_COMPLETE.json',result);save(ARC/'DERIVED_FILES.json',{rel:sha(ARC/rel) for rel in paths+['CPU_COMPLETE.json']});validate_final();save(HERE/'final_receipt.json',{'complete_sha256':sha(ARC/'CPU_COMPLETE.json'),'derived_sha256':sha(ARC/'DERIVED_FILES.json')})
 print(json.dumps(result,allow_nan=False))
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY');raise SystemExit(75)
