"""One bounded CPU recovery phase; all producer scientific files are read-only."""
import argparse,fcntl,os,sys,time
from recovery_contract import *
P=read(HERE/'PROTOCOL.json');ROOT=Path(P['root_remote']);LEGACY=Path(P['recovery']['remote_original_postrun'])

def case_for(run):
 rows=[x for x in P['cases'] if x['run_id']==run];require(len(rows)==1,'unknown run');return rows[0]
def archive_for(run):case_for(run);return LEGACY/'captured'/run
def anchors_for(run):case_for(run);return HERE/'anchors'/run
def bound():
 b=read(HERE/'BINDING.json');owner=check_binding(ROOT,b,P)
 require(b['recovery_of_binding_sha256']==sha(LEGACY/'BINDING.json'),'legacy root binding changed')
 return owner

def seal():
 for n,v in read(HERE/'FREEZE.json')['files'].items():require(sha(safe(HERE,n))==v,'recovery source changed '+n)

def pending_online():
 for root in P['recovery']['online_priority_roots']:
  for d in (Path(root)/'audit/observations').glob('step*'):
   if (d/'request.json').exists() and (d/'native.json').exists() and not (d/'pose_complete.json').exists() and not (d/'response.json').exists():return True
 return False

def locked():
 if pending_online():raise BlockingIOError('online pose priority')
 f=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a')
 try:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  if pending_online():raise BlockingIOError('online pose priority')
  return f
 except BaseException:f.close();raise

def metadata(run,owner):
 arc=archive_for(run);expected=P['recovery']['legacy_runs'][run]
 for n,want in expected.items():require(sha(arc/n)==want,'legacy receipt changed '+n)
 gate=read(arc/'RUN_GATE.json');require(gate['passed'] is True and gate['owner']==owner and gate['run_id']==run,'legacy completed archive gate')
 h=read(ROOT/'logs'/f'{run}_history.json');job=read(ROOT/'logs'/f'{run}_job.json');graph=read(ROOT/'configs'/f'{run}.json')
 require(h['status']['completed'] is True and h['status']['status_str']=='success' and job['status']=='success','producer not successful')
 require(job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'] and h['prompt'][1]==job['prompt_id'] and h['prompt'][2]==graph,'history/owner binding differs')
 require(job['graph_sha256']==sha(ROOT/'configs'/f'{run}.json'),'submitted graph bytes differ')
 return arc

def adopted(run,stat_check=True):
 owner=bound();arc=metadata(run,owner);a=anchors_for(run);receipt=read(a/'RECEIPT.json');verify_receipt(receipt,P,run,owner,arc);inv=read(arc/'FILE_INVENTORY.json')
 if stat_check:require(stat_inventory(ROOT,arc,inv)==receipt['stat_inventory_sha256'],'source/archive stat changed; full review required')
 return arc,a,receipt,inv,owner

def index_for(a,receipt,inv,run,index):return check_index(a/f'{index:03d}.json',receipt['index_sha256'][f'{index:03d}'],run,index,inv)

def status(run):
 owner=bound();arc=metadata(run,owner);a=anchors_for(run)
 if not a.exists():return {'phase':'adopt','run':run,'content_integrity':'not rerun at status'}
 require((a/'RECEIPT.json').exists(),'partial adoption preserved; explicit recovery required')
 arc,a,receipt,inv,owner=adopted(run)
 if (arc/'CPU_COMPLETE.json').exists():
  final=read(HERE/'final_receipts'/f'{run}.json')
  require(final['completion_sha256']==sha(arc/'CPU_COMPLETE.json') and final['derived_inventory_sha256']==sha(arc/'DERIVED_FILES.json') and final['original_inventory_sha256']==sha(arc/'FILE_INVENTORY.json'),'final receipt changed')
  return {'phase':'complete','run':run,'content_integrity':'full verification occurred at final; status uses anchors/stat'}
 for i in range(20):
  p=arc/'observer_replay'/f'{i:03d}.json'
  if not p.exists():return {'phase':'observation','index':i,'run':run}
  old=receipt['preserved_replay_sha256'].get(f'{i:03d}')
  if old is not None:require(sha(p)==old,'preexisting numerical replay changed')
  else:
   phase=read(HERE/'phase_receipts'/run/f'{i:03d}.json')
   require(phase['run_id']==run and phase['index']==i and phase['result_sha256']==sha(p) and phase['index_sha256']==receipt['index_sha256'][f'{i:03d}'],'new phase receipt changed')
 return {'phase':'final','run':run}

def adopt(run):
 started=time.monotonic();owner=bound();arc=metadata(run,owner);a=anchors_for(run);require(not a.exists(),'adoption already/partially exists; preserve evidence')
 verify_source_archive(ROOT,arc,owner,run);verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True)
 inv=read(arc/'FILE_INVENTORY.json');validate_partial_inventory(arc,inv);audit=read(arc/'audit/counterfactual'/f'{run}.json');measurements=audit['counterfactual']['measurements'];require(len(measurements)==20,'20 measurements required');a.mkdir(parents=True)
 hashes={};preserved={}
 for i,m in enumerate(measurements):
  d=index_measurement(ROOT,arc,run,i,m,inv);verify_data_dependencies(ROOT,arc,d['dependencies']);save(a/f'{i:03d}.json',d);hashes[f'{i:03d}']=sha(a/f'{i:03d}.json')
  old=preserve_or_validate(arc/'observer_replay'/f'{i:03d}.json',d['expected_replay'])
  if old is not None:preserved[f'{i:03d}']=old
 verify_source_archive(ROOT,arc,owner,run)
 receipt={'run_id':run,'owner':owner,'protocol_sha256':sha(HERE/'PROTOCOL.json'),'legacy_anchors':P['recovery']['legacy_runs'][run],'index_sha256':hashes,'preserved_replay_sha256':preserved,'stat_inventory_sha256':stat_inventory(ROOT,arc,inv),'full_original_integrity_verified':True,'seconds':time.monotonic()-started}
 save(a/'RECEIPT.json',receipt);return {'status':'adopted','run':run,'existing_replays_preserved':sorted(preserved),'seconds':receipt['seconds'],'no_numerical_result_changed':True}

def runtime_imports():
 os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'extensions'))
 import torch
 torch.set_num_threads(1);require(not torch.cuda.is_initialized(),'CUDA initialized')

def observation(run,index):
 started=time.monotonic();arc,a,receipt,inv,owner=adopted(run);d=index_for(a,receipt,inv,run,index);dest=arc/'observer_replay'/f'{index:03d}.json';require(not dest.exists(),'never overwrite an existing numerical replay')
 checked=verify_data_dependencies(ROOT,arc,d['dependencies']);code=verify_producer_sources(ROOT,P['producer_manifest_sha256']);runtime_imports();from scan_current_pose import observe
 result=observe(safe(arc,d['source']),safe(arc,d['pose']),index);numeric=numeric_observer(result)
 require(canonical_sha(numeric)==d['expected_replay']['scan_sha256'],'independent numerical replay differs')
 out={'passed':True,'all_numeric_values_equal':True,**d['expected_replay'],'summary':observer_summary(result),'elapsed_seconds':time.monotonic()-started,'verified_dependencies':checked,'verified_producer_sources':code,'recovery_index_sha256':sha(a/f'{index:03d}.json')}
 validate_replay(out,d['expected_replay']);save(dest,out);save(HERE/'phase_receipts'/run/f'{index:03d}.json',{'run_id':run,'index':index,'result_sha256':sha(dest),'index_sha256':sha(a/f'{index:03d}.json')})
 return {'status':'observation_complete','run':run,'index':index,'summary_counts':out['summary']['baseline_counts'],'seconds':out['elapsed_seconds']}

def final(run):
 started=time.monotonic();arc,a,receipt,inv,owner=adopted(run);require(status(run)['phase']=='final','final only after20 replays')
 verify_source_archive(ROOT,arc,owner,run);verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True)
 audit=read(arc/'audit/counterfactual'/f'{run}.json');require(len(audit['counterfactual']['measurements'])==20,'20 final measurements')
 for i,m in enumerate(audit['counterfactual']['measurements']):
  d=index_for(a,receipt,inv,run,i);require(index_measurement(ROOT,arc,run,i,m,inv)==d,'final index differs from original actual audit');validate_replay(read(arc/'observer_replay'/f'{i:03d}.json'),d['expected_replay'])
 runtime_imports();import evaluate
 result=evaluate.evaluate(ROOT,arc,case_for(run),P)
 verify_source_archive(ROOT,arc,owner,run);verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True)
 result.update(passed=True,run_id=run,owner=owner,no_GPU=True,cleanup_claim=False,observer_replay_indices=list(range(20)));result['derived_outputs']=sorted(str(p.relative_to(arc)) for p in (arc/'final').rglob('*') if p.is_file());save(arc/'CPU_COMPLETE.json',result)
 generated={str(p.relative_to(arc)):sha(p) for p in arc.rglob('*') if p.is_file() and str(p.relative_to(arc)) not in inv and p.name not in ('DERIVED_FILES.json','ADMIN_RELEASE_ACCEPTANCE.json')};save(arc/'DERIVED_FILES.json',generated);validate_complete_inventory(arc)
 save(HERE/'final_receipts'/f'{run}.json',{'completion_sha256':sha(arc/'CPU_COMPLETE.json'),'derived_inventory_sha256':sha(arc/'DERIVED_FILES.json'),'original_inventory_sha256':sha(arc/'FILE_INVENTORY.json')})
 return {'status':'final_complete','run':run,'seconds':time.monotonic()-started,'completion_file':str(arc/'CPU_COMPLETE.json'),'all20_observations_replayed':True}

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['status','snapshot','adopt','observation','final']);p.add_argument('--run');p.add_argument('--index',type=int);args=p.parse_args();seal()
 if args.mode=='snapshot':result={'runs':{c['run_id']:status(c['run_id']) for c in P['cases']},'metadata_only':True}
 elif args.mode=='status':result=status(args.run)
 else:
  with locked():result=adopt(args.run) if args.mode=='adopt' else observation(args.run,args.index) if args.mode=='observation' else final(args.run)
 print(json.dumps(result,allow_nan=False))
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY');raise SystemExit(75)
