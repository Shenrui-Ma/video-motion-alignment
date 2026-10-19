"""Frozen five-case automatic archive and original-sample release; CPU only."""
import argparse,fcntl,os,shutil,subprocess,sys,time
from pathlib import Path
from contract import *
P=read(HERE/'PROTOCOL.json');ROOT=Path(P['root_remote']);ARC=HERE/'captured/batch'

def bound():
 b=read(HERE/'BINDING.json');owner=check_binding(ROOT,b,P)
 proc=Path('/proc')/str(owner['pid'])
 if proc.exists():
  stat=(proc/'stat').read_text().split(') ',1)[1].split();require(proc.stat().st_uid==b['external_identity']['uid'] and stat[19]==b['external_identity']['start_ticks'],'owner PID changed')
  if stat[0]!='Z':require(hashlib.sha256((proc/'cmdline').read_bytes()).hexdigest()==b['external_identity']['cmdline_sha256'],'owner command changed')
 return owner

def inventory(cases=None):
 cases=P['cases'] if cases is None else cases
 rels={'processes/service.json','deploy_manifest.json','configs/queue.json','configs/protocol.json','configs/scientific_contract.json','configs/engineering_revision_v2.json','audit/known_endpoint_158_split_gate.json','audit/resource_admission_v2.json'}
 for name in ('audit/FULL_PREFLIGHT_v4.json','audit/CPU_DEPLOYMENT_v4.json'):
  if (ROOT/name).is_file():rels.add(name)
 for case in cases:
  run=case['run_id'];g=read(ROOT/'configs/graphs'/f'{run}.json');h=read(ROOT/'logs'/f'{run}_history.json');j=read(ROOT/'logs'/f'{run}_job.json');require(h['status']['completed'] is True and h['status']['status_str']=='success' and j['status']=='success','all planned automatic jobs must complete')
  rels.update((f'logs/{run}_history.json',f'logs/{run}_job.json',f'configs/graphs/{run}.json',f'audit/{run}_conditioning.json',f'audit/{run}_noise.json',f'audit/counterfactual/{run}.json',f'audit/x0/{run}/manifest.json'))
  m=read(ROOT/'audit/x0'/run/'manifest.json');names=[f'x0_step{i:03d}.pt' for i in range(20)]+['sampler_final.pt'];require(m['status']=='complete' and [r['file'] for r in m['captures']+[m['final_sampler_result']]]==names and sorted(x.name for x in (ROOT/'audit/x0'/run).glob('*.pt'))==sorted(names),'21 chosen inventory')
  rels.update(f'audit/x0/{run}/'+x for x in names);n=read(ROOT/'audit'/f'{run}_noise.json');rels.add(relative(ROOT,n['cache_file']));shared='audit/'+g['5']['inputs']['run_id']+'_conditioning.json';rels.add(shared)
  a=read(ROOT/'audit/counterfactual'/f'{run}.json');c=a['counterfactual'];require(a['status']=='complete' and len(c['steps'])==len(c['measurements'])==20,'automatic archive incomplete')
  expected={Path(r['file']).name for r in c['branches']+c['inputs']}|{'sampler_final_raw.pt'};folder=ROOT/'audit/counterfactual'/f'{run}_snapshots'
  require({x.name for x in folder.iterdir()}==expected,'raw endpoint/input unique inventory differs');rels.update(relative(ROOT,x) for x in folder.iterdir())
  dirs=set()
  for observation in c['measurements']:
   path=Path(observation['request_file']).parent;relative(ROOT,path/'request.json');require(path.parent==ROOT/'audit/observations' and path.name not in dirs,'observation outside/duplicate')
   dirs.add(path.name);require(read(path/'request.json')['run_id']==run,'observation belongs to another run');rels.update(relative(ROOT,f) for f in path.rglob('*') if f.is_file())
  producer_case=[x for x in read(ROOT/'configs/protocol.json')['cases'] if x['run_id']==run];require(len(producer_case)==1,'producer case binding');source_pose=producer_case[0]['source_pose_path'];rels.add(relative(ROOT,ROOT/source_pose))
  def visit(v):
   if isinstance(v,dict):
    if 'tensor_file' in v and {'shape','dtype','sha256'}<=set(v):rels.add('audit/'+v['tensor_file'])
    for x in v.values():visit(x)
   elif isinstance(v,list):
    for x in v:visit(x)
  visit(read(ROOT/shared));rels.add(relative(ROOT,output_file(ROOT,h,run)))
 for rel in read(ROOT/'deploy_manifest.json')['files']:
  if rel.startswith(('inputs/','configs/')):
   rels.add(rel)
 for case in cases:
  for key in ('video','portrait'):rels.add('input/'+case[key])
 return [safe(ROOT,x) for x in sorted(rels)]

def snapshot():
 raise ValueError('retry2 uses four incremental releases plus external chest; batch snapshot disabled')
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
   proc=subprocess.run([sys.executable,str(ROOT/'scripts/verify_completed.py'),'--allow-resident','--output',str(ARC/'RUNTIME_GATE.json')],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'),timeout=720)
  require(proc.returncode==0 and read(ARC/'RUNTIME_GATE.json')['status']=='pass','fixed batch runtime gate failed')
  gate={'passed':True,'run_id':'batch','runs':[x['run_id'] for x in P['cases']],'owner':owner,'file_inventory_sha256':sha(ARC/'FILE_INVENTORY.json'),'runtime_gate_sha256':sha(ARC/'RUNTIME_GATE.json'),'cleanup_claim':False,'CPU_final_pending':True,'consumer_freeze_sha256':sha(HERE/'FREEZE.json')};save(ARC/'RUN_GATE.json',gate);verify_source_archive(ROOT,ARC,owner,'batch');verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True);save(HERE/'archive_receipts/batch.json',{'run_id':'batch','owner':owner,'run_gate_sha256':sha(ARC/'RUN_GATE.json'),'inventory_sha256':sha(ARC/'FILE_INVENTORY.json')});return gate

def replay_case_observations(case,dest,arc=None):
 archive=ARC if arc is None else arc
 run=case['run_id'];producer_case=[x for x in read(archive/'configs/protocol.json')['cases'] if x['run_id']==run];require(len(producer_case)==1,'replay producer case');producer_case=producer_case[0]
 sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'extensions'))
 from scan_current_pose import observe
 from H3AutomaticWindowRouter.geometry import Geometry
 geometry=Geometry.from_case(producer_case)
 require(geometry.frames==158 and geometry.valid_frames==147,'replay public observation domain')
 source_rel=relative(ROOT,ROOT/producer_case['source_pose_path']);source=archive/source_rel
 require(sha(source)==producer_case['source_pose_sha256'],'replay frozen source pose')
 audit=read(archive/'audit/counterfactual'/f'{run}.json');ledger=decision_ledger(audit);save(dest/'DECISION_LEDGER.json',ledger);records=[]
 for i,m in enumerate(audit['counterfactual']['measurements']):
  require(m['physical_index']==i and m['status']=='complete','replay order')
  response=read(safe(archive,relative(ROOT,m['response_file'])));pose=safe(archive,relative(ROOT,response['pose']['file']))
  rels={source_rel,f'audit/counterfactual/{run}.json',relative(ROOT,m['request_file']),relative(ROOT,m['response_file'])}
  rels.update(relative(ROOT,response[key]['file']) for key in ('decode','pose','observer'))
  checked=verify_phase_dependencies(ROOT,archive,rels);require(sha(pose)==response['pose']['sha256'],'replay pose SHA')
  result=observe(source,pose,i,geometry);require(numeric_observer(result)==numeric_observer(m['observer']),'independent current pose scan differs')
  row={'passed':True,'index':i,'all_numeric_values_equal':True,'scan_sha256':canonical_sha(numeric_observer(result)),'producer_observer_sha256':canonical_sha(numeric_observer(m['observer'])),'source_pose_sha256':sha(source),'pose_sha256':sha(pose),'summary':observer_summary(result),'verified_dependencies':checked}
  save(dest/'observer_replay'/f'{i:03d}.json',row);records.append(row)
 require(len(records)==20,'twenty independent replays required')
 return ledger,records

def evaluate_case(case,arc=None,runtime_gate_name='RUNTIME_GATE.json'):
 archive=ARC if arc is None else arc
 start=time.monotonic();run=case['run_id'];dest=archive/'final'/run;require(not dest.exists(),'partial case release requires review');
 if arc is None and reuse_incremental_case(case,dest):return read(dest/'SUMMARY.json')
 dest.mkdir(parents=True)
 h=read(archive/'logs'/f'{run}_history.json');video=output_file(archive,h,run);source=archive/'inputs'/f"source_{case['source_id']}_original.mp4";prepared=archive/'inputs'/case['video'];portrait=archive/'inputs'/case['portrait']
 rels={relative(archive,video),relative(archive,source),relative(archive,prepared),relative(archive,portrait),f"inputs/{case['provenance']}",f'configs/graphs/{run}.json',f'logs/{run}_history.json',f'logs/{run}_job.json',f'audit/counterfactual/{run}.json',f'audit/x0/{run}/manifest.json'}
 deps=verify_phase_dependencies(ROOT,archive,rels)
 sys.path.insert(0,str(ROOT/'scripts'));import release49
 require(sha(Path(release49.__file__))==P['release49_sha256'],'release49 implementation differs')
 release=release49.run(video,dest/'edited49_8fps.mp4')
 provenance=read(archive/'inputs'/case['provenance']);require(sha(source)==provenance['source_original_sha256'] and sha(prepared)==case['video_sha256'] and sha(portrait)==case['portrait_sha256'],'original-source/prepared/target binding differs')
 metric={'status':'ready_for_separate_metric_lane','run_id':run,'source_id':case['source_id'],'official_pair_id':provenance['official_pair']['stable_id'],'original_source':str(source),'original_source_sha256':sha(source),'edited49':release['destination'],'edited49_sha256':release['destination_sha256'],'full158_output':str(video),'full158_output_sha256':sha(video),'target_image':str(portrait),'target_sha256':sha(portrait),'source_frames':49,'source_fps':8,'source_size':[720,480],'output_frames':49,'output_fps':8,'output_size':[1152,768],'physical_seconds':P['score_seconds'],'source_indices':list(range(49)),'full_output_indices':P['score_output_indices'],'padding_evaluated':False,'official_caption_in_inference':False,'prompt':case['prompt'],'score_computed':False}
 save(dest/'METRIC_INPUTS.json',metric)
 router=read(archive/'audit/counterfactual'/f'{run}.json');job=read(archive/'logs'/f'{run}_job.json');ledger,replays=replay_case_observations(case,dest,archive)
 runtime=[x for x in read(archive/runtime_gate_name)['cases'] if x['run']==run];require(len(runtime)==1,'runtime case denominator')
 summary={'passed':True,'run_id':run,'source_id':case['source_id'],'identity':case['identity'],'portrait_sha256':case['portrait_sha256'],'source_video_sha256':sha(prepared),'original_source_sha256':sha(source),'seed':case['seed'],'NFE':ledger['NFE'],'active_denoising_indices':ledger['active_indices'],'actual_routed_blocks':router['routed_calls'],'observations_replayed':len(replays),'video':str(video),'video_sha256':sha(video),'phase_dependency_hashes':deps,'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'chosen20_capture_seconds':sum(x['capture_seconds'] for x in read(archive/'audit/x0'/run/'manifest.json')['captures']),'CPU_seconds':time.monotonic()-start,'scope':P['scope'],'runtime_cost_evidence':runtime[0],'score_output_indices':P['score_output_indices'],'decoded_frame_md5_equal':release['decoded_frame_md5_equal'],'padding_evaluated':False,'metric_inputs_sha256':sha(dest/'METRIC_INPUTS.json'),'metrics_computed':False};check_case_summary(summary,case);save(dest/'SUMMARY.json',summary);return summary

def cross_source_summary():
 summaries=[read(ARC/'final'/case['run_id']/'SUMMARY.json') for case in P['cases']]
 require([x['run_id'] for x in summaries]==[x['run_id'] for x in P['cases']],'case order differs')
 for summary,case in zip(summaries,P['cases']):check_case_summary(summary,case)
 require(len({x['original_source_sha256'] for x in summaries})==5,'five original sources required')
 folder=ARC/'batch_summary';require(not folder.exists(),'partial summary needs review');folder.mkdir()
 save(folder/'SUMMARY.json',{'passed':True,'cases':summaries,'sources':[x['source_id'] for x in P['cases']],'fixed_seed':2026101701,'all_outcomes_retained':True,'pilot_pair_denominator':5,'metrics_computed':False,'scope':P['scope']})
 save(folder/'METRIC_MANIFEST.json',{'pilot_pair_denominator':5,'fixed_order':[x['run_id'] for x in P['cases']],'pairs':[read(ARC/'final'/case['run_id']/'METRIC_INPUTS.json') for case in P['cases']],'protocol_sha256':sha(HERE/'PROTOCOL.json'),'consumer_freeze_sha256':sha(HERE/'FREEZE.json')})

def validate_final():
 owner=checked_archive();verify_source_archive(ROOT,ARC,owner,'batch');verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True);done=read(ARC/'CPU_COMPLETE.json');require(done['passed'] is True and done['runs']==[x['run_id'] for x in P['cases']],'wrong completion')
 inv=read(ARC/'FILE_INVENTORY.json');derived=read(ARC/'DERIVED_FILES.json');allowed={'FILE_INVENTORY.json','DERIVED_FILES.json'}|({'ADMIN_RELEASE_ACCEPTANCE.json'} if (ARC/'ADMIN_RELEASE_ACCEPTANCE.json').exists() else set());require(set(done['derived_outputs'])|{'CPU_COMPLETE.json'}==set(derived),'derived manifest omitted output')
 require({str(p.relative_to(ARC)) for p in ARC.rglob('*') if p.is_file()}==set(inv)|set(derived)|allowed,'exact final inventory')
 for rel,d in derived.items():require(sha(safe(ARC,rel))==d,'derived output changed '+rel)
 return done

def status():
 if not ARC.exists():return {'phase':'archive'}
 owner=checked_archive();cleanup=ROOT/'processes/cleanup.json'
 if not cleanup.exists():return {'phase':'awaiting_root_release'}
 receipt=read(cleanup)
 require(receipt.get('service_record')==owner and all(receipt.get(k) is True for k in ('process_absent','own_compute_absent','child_compute_absent')),'root exact release receipt differs')
 if (ARC/'CPU_COMPLETE.json').exists():
  done=read(ARC/'CPU_COMPLETE.json');receipt=read(HERE/'final_receipt.json');require(done['passed'] is True and sha(ARC/'CPU_COMPLETE.json')==receipt['complete_sha256'] and sha(ARC/'DERIVED_FILES.json')==receipt['derived_sha256'],'completed receipt changed');return {'phase':'complete','result':done}
 for c in P['cases']:
  p=ARC/'final'/c['run_id']/'CASE_FILES.json'
  if not p.exists():return {'phase':'case','run':c['run_id']}
  files=read(p);folder=p.parent;require({x.name for x in folder.iterdir()} >= {'SUMMARY.json','CASE_FILES.json'},'case incomplete');check_case_summary(read(folder/'SUMMARY.json'),c)
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
    checked_archive();cases=[x for x in P['cases'] if x['run_id']==a.run];require(len(cases)==1,'case outside fixed protocol');result=evaluate_case(cases[0]);dest=ARC/'final'/a.run;save(dest/'CASE_FILES.json',{str(x.relative_to(dest)):sha(x) for x in dest.rglob('*') if x.is_file() and x.name!='CASE_FILES.json'})
   else:
    require(status()['phase']=='finalize','not all cases complete');owner=checked_archive();verify_source_archive(ROOT,ARC,owner,'batch');verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True);cross_source_summary();original=read(ARC/'FILE_INVENTORY.json');paths=sorted(str(x.relative_to(ARC)) for x in ARC.rglob('*') if x.is_file() and str(x.relative_to(ARC)) not in original and x.name!='ADMIN_RELEASE_ACCEPTANCE.json');result={'passed':True,'runs':[x['run_id'] for x in P['cases']],'derived_outputs':paths,'no_GPU':True,'cleanup_claim':False};save(ARC/'CPU_COMPLETE.json',result);save(ARC/'DERIVED_FILES.json',{rel:sha(ARC/rel) for rel in paths+['CPU_COMPLETE.json']});validate_final();save(HERE/'final_receipt.json',{'complete_sha256':sha(ARC/'CPU_COMPLETE.json'),'derived_sha256':sha(ARC/'DERIVED_FILES.json')})
 print(json.dumps(result,allow_nan=False))


def reuse_incremental_case(case,destination):
 """Reuse a verified partial case only after the complete five-case archive exists."""
 src=HERE/'completed_cases'/case['run_id'];receipt=src/'CASE_READY.json'
 if not receipt.exists():return False
 ready=read(receipt);require(ready.get('partial_batch') is True and ready.get('planned_denominator')==5 and ready.get('run_id')==case['run_id'],'incremental case identity')
 require(sha(src/'FILE_INVENTORY.json')==ready['file_inventory_sha256'] and sha(src/'CASE_RUNTIME_GATE.json')==ready['runtime_gate_sha256'],'incremental proof changed')
 original=read(src/'FILE_INVENTORY.json');full=read(ARC/'FILE_INVENTORY.json')
 require(all(rel in full and row==full[rel] for rel,row in original.items()),'incremental and complete case inputs differ')
 final=src/'final'/case['run_id'];files=read(final/'CASE_FILES.json');require(sha(final/'CASE_FILES.json')==ready['case_files_sha256'],'incremental final inventory changed')
 for rel,digest in files.items():require(sha(safe(final,rel))==digest,'incremental output changed')
 require({str(x.relative_to(final)) for x in final.rglob('*') if x.is_file()}==set(files)|{'CASE_FILES.json'},'incremental final inventory differs')
 check_case_summary(read(final/'SUMMARY.json'),case)
 shutil.copytree(final,destination)
 save(destination/'REUSED_INCREMENTAL.json',{'source_case_ready':str(receipt),'source_case_ready_sha256':sha(receipt),'full_batch_gate_sha256':sha(ARC/'RUN_GATE.json'),'fixed_denominator':5,'all_original_dependencies_equal':True,'encoded_score_bytes_reused':True})
 return True

if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY');raise SystemExit(75)
