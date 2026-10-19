"""One bounded CPU phase. Producer/service/queue are read-only."""
import argparse,fcntl,os,shutil,subprocess,sys,time
from pathlib import Path
from contract import *
P=read(HERE/'PROTOCOL.json');ROOT=Path(P['root_remote']);RUN=P['cases'][0]['run_id'];ARC=Path(P['recovery']['archive_root'])

def bound():
 b=read(HERE/'BINDING.json');owner=check_binding(ROOT,b,P);proc=Path('/proc')/str(owner['pid'])
 if proc.exists():
  try:stat=(proc/'stat').read_text().split(') ',1)[1].split();cmd=(proc/'cmdline').read_bytes();uid=proc.stat().st_uid
  except FileNotFoundError:require(not proc.exists(),'partial live identity')
  else:
   e=b['external_identity'];require(uid==e['uid'] and stat[19]==e['start_ticks'],'owner PID reused')
   if stat[0]!='Z':require(hashlib.sha256(cmd).hexdigest()==e['cmdline_sha256'],'owner command changed')
 return owner

def check_seal():
 for rel,d in read(HERE/'FREEZE.json')['files'].items():require(sha(safe(HERE,rel))==d,'consumer seal differs '+rel)

def online_pending():
 for root in P['online_priority_roots']:
  for d in (Path(root)/'audit/observations').glob('step*'):
   if (d/'request.json').exists() and (d/'native.json').exists() and not (d/'pose_complete.json').exists() and not (d/'response.json').exists():return True
 return False

def locked():
 if online_pending():raise BlockingIOError('online observer priority')
 f=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if online_pending():f.close();raise BlockingIOError('online observer priority')
 return f

def inventory():
 h=read(ROOT/'logs'/f'{RUN}_history.json');j=read(ROOT/'logs'/f'{RUN}_job.json');require(h['status']['completed'] is True and h['status']['status_str']=='success' and j['status']=='success','actual producer incomplete')
 g=read(ROOT/'configs/graphs'/f'{RUN}.json');a=read(ROOT/'audit/counterfactual'/f'{RUN}.json');c=a['counterfactual'];require(a['status']=='complete' and len(c['steps'])==20 and len(c['branches'])==21 and c['measurements']==[],'fixed run incomplete')
 rels={'processes/service.json','deploy_manifest.json','configs/queue.json','configs/runtime_provenance.json',f'logs/{RUN}_history.json',f'logs/{RUN}_job.json',f'audit/{RUN}_conditioning.json',f'audit/{RUN}_noise.json',f'audit/counterfactual/{RUN}.json',f'audit/x0/{RUN}/manifest.json'}
 for rel in read(ROOT/'deploy_manifest.json')['files']:
  if rel.startswith(('configs/','inputs/','design/')) or rel=='PROTOCOL.json':rels.add(rel)
 for name in read(ROOT/'configs/input_hashes.json'):rels.add('input/'+name)
 shared=f"audit/{g['5']['inputs']['run_id']}_conditioning.json";rels.add(shared)
 def visit(v):
  if isinstance(v,dict):
   if 'tensor_file' in v and {'shape','dtype','sha256'}<=set(v):rels.add('audit/'+v['tensor_file'])
   for z in v.values():visit(z)
  elif isinstance(v,list):
   for z in v:visit(z)
 visit(read(ROOT/shared));n=read(ROOT/'audit'/f'{RUN}_noise.json');rels.add(relative(ROOT,n['cache_file']))
 xfolder=ROOT/'audit/x0'/RUN;names=[f'x0_step{i:03d}.pt' for i in range(20)]+['sampler_final.pt'];m=read(xfolder/'manifest.json')
 require(m['status']=='complete' and [r['file'] for r in m['captures']+[m['final_sampler_result']]]==names and sorted(f.name for f in xfolder.glob('*.pt'))==sorted(names),'chosen exact21 inventory')
 rels.update(f'audit/x0/{RUN}/'+v for v in names)
 folder=ROOT/'audit/counterfactual'/f'{RUN}_snapshots';expected={Path(r['file']).name for r in c['branches']+c['inputs']}|{'sampler_final_raw.pt'}
 require({f.name for f in folder.iterdir()}==expected and len(expected)==23,'raw exact23 inventory')
 rels.update(relative(ROOT,f) for f in folder.iterdir());rels.add(relative(ROOT,output_file(ROOT,h,RUN)))
 files=[safe(ROOT,rel) for rel in sorted(rels)];require(all(f.is_file() for f in files),'completed file missing');return files

def snapshot():
 owner=bound();hp=ROOT/'logs'/f'{RUN}_history.json';jp=ROOT/'logs'/f'{RUN}_job.json';h=read(hp) if hp.exists() else {};j=read(jp) if jp.exists() else {};state=read(ROOT/'logs/controller_state.json') if (ROOT/'logs/controller_state.json').exists() else {};cleanup=read(ROOT/'processes/cleanup.json') if (ROOT/'processes/cleanup.json').exists() else {}
 terminal=state.get('status') in ('failed','all_queued_jobs_complete') or cleanup.get('service_record')==owner and cleanup.get('process_absent') is True
 if h.get('status',{}).get('status_str')=='error' or j.get('status') in ('error','unknown_missing','submission_uncertain'):return {'status':'producer_failed','run':RUN,'scientific_result':False,'job_status':j.get('status')}
 if not(h.get('status',{}).get('completed') is True and h['status']['status_str']=='success' and j.get('status')=='success'):return {'status':'producer_failed' if terminal else 'pending','reason':'incomplete_after_terminal' if terminal else 'awaiting_actual_success'}
 files=inventory();token=canonical_sha([{'rel':relative(ROOT,p),'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'json_sha':sha(p) if p.suffix=='.json' else None} for p in files]);return {'status':'success_files_present','token':token,'files':len(files)}

def archive(token):
 owner=bound();require(snapshot()['token']==token,'stable files changed');require(not ARC.exists(),'partial archive requires explicit review');verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True)
 files=inventory();inv={relative(ROOT,f):{'bytes':f.stat().st_size,'sha256':sha(f)} for f in files};ARC.mkdir(parents=True)
 for f in files:
  rel=relative(ROOT,f);dest=safe(ARC,rel);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest);require(sha(dest)==inv[rel]['sha256']==sha(f),'copy changed '+rel)
 save(ARC/'FILE_INVENTORY.json',inv);save(ARC/'ADMIN_ADMISSION_AT_ARCHIVE.json',read(ROOT/'configs/admission.json'))
 with (ARC/'verify.log').open('x') as log:
  cmd=[sys.executable,str(ROOT/'scripts/verify_completed.py'),'--allow-resident','--output',str(ARC/'RUNTIME_GATE.json')]
  proc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'),timeout=600)
 require(proc.returncode==0 and read(ARC/'RUNTIME_GATE.json')['status']=='pass','actual producer verification failed')
 gate={'passed':True,'run_id':RUN,'owner':owner,'file_inventory_sha256':sha(ARC/'FILE_INVENTORY.json'),'runtime_gate_sha256':sha(ARC/'RUNTIME_GATE.json'),'runtime':read(ARC/'RUNTIME_GATE.json'),'cleanup_claim':False,'final_outcome_pending':True};save(ARC/'RUN_GATE.json',gate);verify_source_archive(ROOT,ARC,owner,RUN);verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True)
 save(HERE/'archive_receipts'/f'{RUN}.json',{'run_id':RUN,'owner':owner,'run_gate_sha256':sha(ARC/'RUN_GATE.json'),'inventory_sha256':sha(ARC/'FILE_INVENTORY.json')});return gate

def checked(full=False):
 owner=bound();verify_archive_anchor(ARC,RUN,owner)
 if full:verify_source_archive(ROOT,ARC,owner,RUN)
 return owner

def status():
 require(ARC.is_dir(),'registered original archive missing; never rerun archive');from recovery import check_legacy;check_legacy(P)
 checked()
 if (ARC/'CPU_COMPLETE.json').exists():
  receipt=read(HERE/'final_receipts'/f'{RUN}.json');require(receipt['completion_sha256']==sha(ARC/'CPU_COMPLETE.json') and receipt['derived_sha256']==sha(ARC/'DERIVED_FILES.json'),'final receipt changed');return {'phase':'complete'}
 for phase in PHASES:
  folder=phase_folder(ARC,phase)
  if folder.exists():
   if phase=='pose' and not (folder/'COMPLETE.json').exists():return {'phase':'recover_pose'}
   receipt=read(HERE/'phase_receipts'/f'{RUN}_{phase}.json');require(receipt['result_sha256']==sha(folder/'COMPLETE.json') and receipt['inventory_sha256']==sha(ARC/'FILE_INVENTORY.json'),'phase anchor changed');continue
  if phase=='compare' and not (HERE/'AUTO_PARENT_BINDING.json').exists():return {'phase':'waiting_parent','reason':'actual R27 normal final binding pending'}
  return {'phase':phase}
 return {'phase':'finalize'}

def analyse(phase):
 checked();verify_producer_sources(ROOT,P['producer_manifest_sha256']);import outcome
 result=outcome.execute(phase,ROOT,ARC,P);verify_producer_sources(ROOT,P['producer_manifest_sha256']);receipt=seal_phase(ARC,phase,result)
 save(HERE/'phase_receipts'/f'{RUN}_{phase}.json',{'result_sha256':sha(phase_folder(ARC,phase)/'COMPLETE.json'),'inventory_sha256':sha(ARC/'FILE_INVENTORY.json')});return {'phase':phase,'passed':True,'summary':result}

def finalize():
 require(status()['phase']=='finalize','analysis phases incomplete');owner=checked(full=True);verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True)
 for phase in PHASES:validate_phase(ARC,phase)
 validate_auto_parent(read(HERE/'AUTO_PARENT_BINDING.json'),P)
 original=read(ARC/'FILE_INVENTORY.json');paths=sorted(str(f.relative_to(ARC)) for f in ARC.rglob('*') if f.is_file() and str(f.relative_to(ARC)) not in original and f.name not in ('ADMIN_RELEASE_ACCEPTANCE.json','FILE_INVENTORY.json'))
 done={'passed':True,'run_id':RUN,'phases':list(PHASES),'no_GPU':True,'owner':owner,'derived_outputs':paths,'manual_quality_review':'pending blinded fixed frames/full141 comparison','scope':P['scope']};save(ARC/'CPU_COMPLETE.json',done);save(ARC/'DERIVED_FILES.json',{rel:sha(ARC/rel) for rel in paths+['CPU_COMPLETE.json']});validate_delivery(ARC);verify_source_archive(ROOT,ARC,owner,RUN);verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True);save(HERE/'final_receipts'/f'{RUN}.json',{'completion_sha256':sha(ARC/'CPU_COMPLETE.json'),'derived_sha256':sha(ARC/'DERIVED_FILES.json')});return done

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['snapshot','status','archive','recover_pose',*PHASES,'finalize']);p.add_argument('--token');a=p.parse_args();check_seal()
 if a.mode=='snapshot':result=snapshot()
 else:
  with locked():
   if a.mode=='status':result=status()
   elif a.mode=='archive':result=archive(a.token)
   elif a.mode=='finalize':result=finalize()
   elif a.mode=='recover_pose':
    require(status()['phase']=='recover_pose','wrong recovery stage');from recovery import recover_pose;result=recover_pose(ROOT,ARC,P,checked(full=True))
   else:require(status()['phase']==a.mode,'wrong next phase');result=analyse(a.mode)
 print(json.dumps(result,allow_nan=False))
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY');raise SystemExit(75)
