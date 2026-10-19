"""CPU archive and scoring-view export for five fixed IVEBench P1 prompt-adaptation Native tasks."""
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

def inventory():
 rels={'processes/service.json','deploy_manifest.json','configs/queue.json','configs/runtime.json','configs/scientific_contract.json'}
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
  if rel.startswith(('inputs/','configs/','design/')):
   rels.add(rel)
 for case in P['cases']:
  rels.update('inputs/'+name for name in (case['video'],case['provenance'],case['original_source'],case['source_id']+'_prompt.txt'))
  rels.add('input/'+case['video'])
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
 f=Path(P['consumer']['CPU_lock']).open('a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
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
  require(proc.returncode==0,'fixed batch runtime validator failed')
  check_runtime_gate(read(ARC/'RUNTIME_GATE.json'),P)
  gate={'passed':True,'run_id':'batch','runs':[x['run_id'] for x in P['cases']],'owner':owner,'file_inventory_sha256':sha(ARC/'FILE_INVENTORY.json'),'runtime_gate_sha256':sha(ARC/'RUNTIME_GATE.json'),'cleanup_claim':False,'CPU_final_pending':True,'consumer_freeze_sha256':sha(HERE/'FREEZE.json')};save(ARC/'RUN_GATE.json',gate);verify_source_archive(ROOT,ARC,owner,'batch');verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True);save(HERE/'archive_receipts/batch.json',{'run_id':'batch','owner':owner,'run_gate_sha256':sha(ARC/'RUN_GATE.json'),'inventory_sha256':sha(ARC/'FILE_INVENTORY.json')});return gate

def file_record(path):return {'file':str(path),'sha256':sha(path)}


def evaluate_case(case):
 start=time.monotonic();run=case['run_id'];dest=ARC/'final'/run;require(not dest.exists(),'partial case release requires review');dest.mkdir(parents=True)
 h=read(ARC/'logs'/f'{run}_history.json');video=output_file(ARC,h,run);source=ARC/'inputs'/case['original_source'];prepared=ARC/'inputs'/case['video'];provenance_path=ARC/'inputs'/case['provenance']
 rels={relative(ARC,video),relative(ARC,source),relative(ARC,prepared),relative(ARC,provenance_path),f'configs/graphs/{run}.json',f'logs/{run}_history.json',f'logs/{run}_job.json',f'audit/router/{run}.json',f'audit/x0/{run}/manifest.json'}
 deps=verify_phase_dependencies(ROOT,ARC,rels)
 import release_prefix
 provenance=read(provenance_path);require(sha(source)==provenance['source_sha256'] and sha(prepared)==case['video_sha256'] and sha(provenance_path)==case['provenance_sha256'],'source/prepared/provenance binding differs')
 count=case['valid_frame_count'];require(count==provenance['effective_frame_count'],'valid prefix differs')
 published_record=source_score_binding(case,read(HERE/'SOURCE_SCORE_BINDINGS.json'))
 published=Path(published_record['files']['source_score.mp4']['remote_file'])
 source_release=release_prefix.reuse_source(prepared,source,provenance_path,published,dest/'source_score.mp4')
 require(sha(dest/'source_score.mp4')==published_record['files']['source_score.mp4']['sha256'],'reused P0 score bytes changed')
 edited_release=release_prefix.edited_view(video,count,dest/'edited_score.mp4')
 router=read(ARC/'audit/router'/f'{run}.json');job=read(ARC/'logs'/f'{run}_job.json')
 generation={'schema':'r57-P1-native-generation-record-v1','run_id':run,'source_id':case['source_id'],'method':P['method_name'],'prompt_version':'P1','prompt_attribution':P['prompt_attribution'],'original_task':case['original_task'],'prompt':case['prompt'],'seed':case['seed'],'geometry':case['geometry'],'source_prepared_video':file_record(prepared),'source_provenance':file_record(provenance_path),'full_video':file_record(video),'graph':file_record(ARC/'configs/graphs'/f'{run}.json'),'job':file_record(ARC/'logs'/f'{run}_job.json'),'history':file_record(ARC/'logs'/f'{run}_history.json'),'producer_manifest_sha256':P['producer_manifest_sha256'],'runtime_gate_sha256':sha(ARC/'RUNTIME_GATE.json'),'NFE':20,'routed_calls':router['routed_calls']}
 save(dest/'GENERATION_RECORD.json',generation)
 metric={'pair_id':case['source_id'],'source_original':file_record(source),'source_prepared_video':file_record(prepared),'source_score_video':file_record(dest/'source_score.mp4'),'source_preparation_record':file_record(provenance_path),'score_frame_indices':list(range(count)),'input_to_original_frame':provenance['input_to_original_frame'],'edited':{P['method_name']:{'score_video':file_record(dest/'edited_score.mp4'),'full_video':file_record(video),'generation_record':file_record(dest/'GENERATION_RECORD.json'),'release_record':file_record(dest/'edited_score.mapping.json')}}}
 save(dest/'METRIC_INPUTS.json',metric)
 summary={'passed':True,'run_id':run,'source_id':case['source_id'],'source_video_sha256':sha(prepared),'original_source_sha256':sha(source),'seed':case['seed'],'NFE':20,'actual_routed_blocks':router['routed_calls'],'video':str(video),'video_sha256':sha(video),'phase_dependency_hashes':deps,'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'chosen20_capture_seconds':sum(x['capture_seconds'] for x in read(ARC/'audit/x0'/run/'manifest.json')['captures']),'CPU_seconds':time.monotonic()-start,'scope':P['scope'],'runtime_cost_evidence':read(ARC/'RUNTIME_GATE.json')['runs'][run],'actual_reference_equal_P0':read(ARC/'RUNTIME_GATE.json')['checks'][run+'_actual_reference_equal_P0'],'actual_initial_AV_noise_equal_P0':read(ARC/'RUNTIME_GATE.json')['checks'][run+'_actual_initial_AV_noise_equal_P0'],'score_frame_indices':list(range(count)),'decoded_frame_md5_equal':source_release['decoded_pixel_mapping_exact'] and edited_release['decoded_pixel_mapping_exact'],'padding_evaluated':False,'metric_inputs_sha256':sha(dest/'METRIC_INPUTS.json'),'metrics_computed':False};check_case_summary(summary,case);save(dest/'SUMMARY.json',summary);return summary


def cross_source_summary():
 summaries=[read(ARC/'final'/case['run_id']/'SUMMARY.json') for case in P['cases']]
 require([x['run_id'] for x in summaries]==[x['run_id'] for x in P['cases']],'case order differs')
 for summary,case in zip(summaries,P['cases']):check_case_summary(summary,case)
 require(len({x['original_source_sha256'] for x in summaries})==5,'five original sources required')
 folder=ARC/'batch_summary';require(not folder.exists(),'partial summary needs review');folder.mkdir()
 save(folder/'SUMMARY.json',{'passed':True,'cases':summaries,'sources':[x['source_id'] for x in P['cases']],'fixed_seed':2026101701,'all_outcomes_retained':True,'pilot_pair_denominator':5,'metrics_computed':False,'scope':P['scope']})
 save(folder/'METRIC_MANIFEST.json',{'schema':P['metrics_manifest_schema'],'selection_sha256':P['selection_sha256'],'methods':[P['method_name']],'pairs':[read(ARC/'final'/case['run_id']/'METRIC_INPUTS.json') for case in P['cases']],'protocol_sha256':sha(HERE/'PROTOCOL.json'),'consumer_freeze_sha256':sha(HERE/'FREEZE.json')})

def validate_final():
 owner=checked_archive();verify_source_archive(ROOT,ARC,owner,'batch');verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True);done=read(ARC/'CPU_COMPLETE.json');require(done['passed'] is True and done['runs']==[x['run_id'] for x in P['cases']],'wrong completion')
 inv=read(ARC/'FILE_INVENTORY.json');derived=read(ARC/'DERIVED_FILES.json');allowed={'FILE_INVENTORY.json','DERIVED_FILES.json'}|({'ADMIN_RELEASE_ACCEPTANCE.json'} if (ARC/'ADMIN_RELEASE_ACCEPTANCE.json').exists() else set());require(set(done['derived_outputs'])|{'CPU_COMPLETE.json'}==set(derived),'derived manifest omitted output')
 require({str(p.relative_to(ARC)) for p in ARC.rglob('*') if p.is_file()}==set(inv)|set(derived)|allowed,'exact final inventory')
 for rel,d in derived.items():require(sha(safe(ARC,rel))==d,'derived output changed '+rel)
 return done

def status():
 if not ARC.exists():return {'phase':'archive'}
 owner=checked_archive()
 cleanup_path=ROOT/'processes/cleanup.json'
 if not cleanup_path.exists():return {'phase':'await_root_release','owner':owner}
 cleanup=read(cleanup_path);require(cleanup.get('pid')==owner['pid'] and cleanup.get('service_record')==owner and cleanup.get('process_absent') is True and cleanup.get('own_compute_absent') is True,'cleanup owner or completion differs')
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
    require(status()=={'phase':'case','run':a.run},'case phase not ready');checked_archive();cases=[x for x in P['cases'] if x['run_id']==a.run];require(len(cases)==1,'case outside fixed protocol');result=evaluate_case(cases[0]);dest=ARC/'final'/a.run;save(dest/'CASE_FILES.json',{str(x.relative_to(dest)):sha(x) for x in dest.rglob('*') if x.is_file()})
   else:
    require(status()['phase']=='finalize','not all cases complete');owner=checked_archive();verify_source_archive(ROOT,ARC,owner,'batch');verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True);cross_source_summary();original=read(ARC/'FILE_INVENTORY.json');paths=sorted(str(x.relative_to(ARC)) for x in ARC.rglob('*') if x.is_file() and str(x.relative_to(ARC)) not in original and x.name!='ADMIN_RELEASE_ACCEPTANCE.json');result={'passed':True,'runs':[x['run_id'] for x in P['cases']],'derived_outputs':paths,'no_GPU':True,'cleanup_claim':False};save(ARC/'CPU_COMPLETE.json',result);save(ARC/'DERIVED_FILES.json',{rel:sha(ARC/rel) for rel in paths+['CPU_COMPLETE.json']});validate_final();save(HERE/'final_receipt.json',{'complete_sha256':sha(ARC/'CPU_COMPLETE.json'),'derived_sha256':sha(ARC/'DERIVED_FILES.json')})
 print(json.dumps(result,allow_nan=False))
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY');raise SystemExit(75)
