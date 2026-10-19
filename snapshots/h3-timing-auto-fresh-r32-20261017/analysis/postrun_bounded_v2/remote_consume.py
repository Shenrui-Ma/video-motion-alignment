"""One bounded CPU phase. Producer and original consumer remain unchanged."""
import argparse,fcntl,importlib.util,json,os,shutil,subprocess,sys,time
from pathlib import Path
from indexed_contract import *
P=read(HERE/"PROTOCOL.json");ROOT=Path(P["root_remote"])

def bound():
 b=read(HERE/'BINDING.json');owner=check_binding(ROOT,b,P)
 require(b['original_binding_sha256']==P['bounded_v2']['original_binding_sha256']==sha(Path(P['bounded_v2']['remote_original_postrun'])/'BINDING.json'),'original root binding changed')
 proc=Path('/proc')/str(owner['pid'])
 if proc.exists():
  try:s=(proc/'stat').read_text().split(') ',1)[1].split();cmd=(proc/'cmdline').read_bytes();uid=proc.stat().st_uid
  except FileNotFoundError:require(not proc.exists(),'partial PID identity')
  else:
   e=b['external_identity'];require(uid==e['uid'] and s[19]==e['start_ticks'],'live PID identity changed')
   if s[0]!='Z':require(hashlib.sha256(cmd).hexdigest()==e['cmdline_sha256'],'live command changed')
 return b,owner

def case_for(run):
 a=[x for x in P['cases'] if x['run_id']==run];require(len(a)==1,'run outside postrun protocol');return a[0]

def verify_consumer_seal():
 for name,d in read(HERE/'FREEZE.json')['files'].items():require(sha(safe(HERE,name))==d,'consumer source changed '+name)

def inventory(run):
 case_for(run);h=read(ROOT/'logs'/f'{run}_history.json');j=read(ROOT/'logs'/f'{run}_job.json')
 require(h['status']['completed'] is True and h['status']['status_str']=='success' and j['status']=='success','run not successful')
 a=read(ROOT/'audit/counterfactual'/f'{run}.json');c=a['counterfactual'];require(a['status']=='complete' and len(c['measurements'])==20 and len(c['steps'])==20,'controller/callback archive incomplete')
 g=read(ROOT/'configs'/f'{run}.json');shared=g['5']['inputs']['run_id']+'_conditioning.json';noise=read(ROOT/'audit'/f'{run}_noise.json')
 rels={f'logs/{run}_history.json',f'logs/{run}_job.json',f'configs/{run}.json','configs/protocol.json','configs/queue.json','configs/input_hashes.json','configs/source.pose.json','processes/service.json','deploy_manifest.json',f'audit/{run}_conditioning.json',f'audit/{run}_noise.json',f'audit/{shared}',f'audit/counterfactual/{run}.json',f'audit/x0/{run}/manifest.json'}
 rels.add(relative(ROOT,noise['cache_file']))
 names=[f'x0_step{i:03d}.pt' for i in range(20)]+['sampler_final.pt'];m=read(ROOT/'audit/x0'/run/'manifest.json')
 require(m['status']=='complete' and [r['file'] for r in m['captures']+[m['final_sampler_result']]]==names and sorted(x.name for x in (ROOT/'audit/x0'/run).glob('*.pt'))==sorted(names),'chosen inventory differs')
 rels.update(f'audit/x0/{run}/'+n for n in names)
 expected={Path(r['file']).name for r in c['branches']+c['inputs']}|{'sampler_final_raw.pt'};folder=ROOT/'audit/counterfactual'/f'{run}_snapshots'
 require({x.name for x in folder.iterdir()}==expected,'raw endpoint/input unique inventory differs')
 rels.update(str(x.relative_to(ROOT)) for x in folder.iterdir())
 dirs=set()
 for m in c['measurements']:
  path=Path(m['request_file']).parent;relative(ROOT,path/'request.json');require(path.parent==ROOT/'audit/observations' and path.name not in dirs,'observation outside/duplicate')
  dirs.add(path.name);require(read(path/'request.json')['run_id']==run,'observation belongs to another run')
  for f in path.rglob('*'):
   if f.is_file():rels.add(relative(ROOT,f))
 def visit(v):
  if isinstance(v,dict):
   if 'tensor_file' in v and {'shape','dtype','sha256'}<=set(v):rels.add('audit/'+v['tensor_file'])
   for z in v.values():visit(z)
  elif isinstance(v,list):
   for z in v:visit(z)
 visit(read(ROOT/'audit'/shared))
 for n in read(ROOT/'configs/input_hashes.json'):
  rels.add('inputs/'+n);rels.add('input/'+n)
 rels.add(relative(ROOT,output_file(ROOT,h,run)))
 paths=[safe(ROOT,r) for r in sorted(rels)];require(all(p.is_file() for p in paths),'completed inventory missing file');return paths

def env():
 e=os.environ.copy();e.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4');return e

def launch(cmd,log,timeout=480):
 with Path(log).open('x') as f:return subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,env=env(),timeout=timeout)

def runtime_imports():
 os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'extensions'))
 import torch
 torch.set_num_threads(1);require(not torch.cuda.is_initialized(),'CUDA initialized')
 from H3X0Readout.core import tensor_signature
 return torch,tensor_signature

def condition_checks(arc,case,audit):
 torch,signature=runtime_imports();run=case['run_id'];from H3AutomaticWindowRouter.pair_gate import condition_audit_matches
 tag='bad' if case['seed']==2026101311 else 'normal'
 oldcond=read(ROOT/(case.get('parent_conditioning') or f'configs/{tag}_conditioning.json'));oldnoise=read(ROOT/(case.get('parent_noise') or f'configs/{tag}_noise.json'));oldcap=read(ROOT/(case.get('parent_captures') or f'configs/{tag}_captures.json'))
 actual=read(arc/'audit'/f'{run}_conditioning.json');condition_audit_matches(actual,oldcond)
 require(actual['run_id']==run,'condition run')
 n=read(arc/'audit'/f'{run}_noise.json');require(n['signature']==oldnoise['signature'] and n['actual_noise_streams']==oldnoise['actual_noise_streams'] and n['run_id']==run,'actual old noise differs')
 val=torch.load(safe(arc,relative(ROOT,n['cache_file'])),map_location='cpu',weights_only=True);sig=[{k:signature(x)[k] for k in ('shape','dtype','sha256')} for x in val['tensors']]
 require(len(sig)==2 and val['signature']==n['signature'] and val['hashes']==sig==n['actual_noise_streams'],'noise bytes differ')
 for name,want in read(ROOT/'configs/input_hashes.json').items():require(sha(arc/'inputs'/name)==sha(arc/'input'/name)==want,'actual loader input differs')
 graph=read(arc/'configs'/f'{run}.json');shared=read(arc/'audit'/(graph['5']['inputs']['run_id']+'_conditioning.json'));seen=set();blobs=[]
 def visit(v):
  if isinstance(v,dict):
   if 'tensor_file' in v and {'shape','dtype','sha256'}<=set(v) and v['tensor_file'] not in seen:
    seen.add(v['tensor_file']);p=safe(arc/'audit',v['tensor_file']);value=torch.load(p,map_location='cpu',weights_only=True);require({k:signature(value)[k] for k in ('shape','dtype','sha256')}=={k:v[k] for k in ('shape','dtype','sha256')},'condition actual tensor differs');blobs.append({'file':str(p),'sha256':sha(p)})
   for x in v.values():visit(x)
  elif isinstance(v,list):
   for x in v:visit(x)
 visit(shared)
 c=audit['counterfactual'];branches={(r['physical_index'],r['branch']):r for r in c['branches']};prefix=[];first=min(c['full_physical_indices'],default=None)
 for old in oldcap['captures']:
  i=old['step_zero_based']
  if first is not None and i>first:continue
  row=branches[i,'native'];new=torch.load(safe(arc,relative(ROOT,row['file'])),map_location='cpu',weights_only=True);oldpath=Path(case['parent_root'])/'audit/x0'/case['parent_run']/old['file'];saved=torch.load(oldpath,map_location='cpu',weights_only=True)
  require(all(signature(saved[k])==old[k] and torch.equal(saved[k],new[k]) for k in ('video','audio')),'independent prefix tensor mismatch')
  prefix.append({'index':i,'old_file':str(oldpath),'old_sha256':sha(oldpath),'independent_tensor_equal':True})
 require([r['physical_index'] for r in c['inputs']]==[6,10,14],'pre-forward input inventory')
 for r in c['inputs']:
  p=safe(arc,relative(ROOT,r['file']));v=torch.load(p,map_location='cpu',weights_only=True)
  require(sha(p)==r['file_sha256'] and signature(v['packed'])==r['packed_signature']==branches[r['physical_index'],'native']['same_input'],'actual raw packed input differs')
  require(v['metadata']=={k:x for k,x in r.items() if k not in ('file','file_sha256','archive_seconds')},'raw input metadata differs')
 return {'clean_condition_exact':True,'two_stream_noise_actual_exact':True,'tensor_blobs':blobs,'independent_prefix_replays':prefix,'raw_inputs':[6,10,14],'historical_postaugmentation':'not archived historically; not independently compared','runtime_guard_scope':'current condition/RNG/residency invariants were asserted live; postrun hashes cannot reproduce historical RNG state'}

def pending_online_observer():
 for root in P['bounded_v2']['online_priority_roots']:
  for d in (Path(root)/'audit/observations').glob('step*'):
   if (d/'request.json').exists() and (d/'native.json').exists() and not (d/'pose_complete.json').exists() and not (d/'response.json').exists():return True
 return False

def locked():
 if pending_online_observer():raise BlockingIOError('online pose priority')
 f=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a')
 try:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  if pending_online_observer():raise BlockingIOError('online pose priority')
  return f
 except BaseException:f.close();raise

def success_metadata(run,owner):
 h=read(ROOT/'logs'/f'{run}_history.json');job=read(ROOT/'logs'/f'{run}_job.json');gp=ROOT/'configs'/f'{run}.json';graph=read(gp)
 require(h['status']['completed'] is True and h['status']['status_str']=='success' and job['status']=='success','producer not successful')
 require(job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'] and h['prompt'][1]==job['prompt_id'] and h['prompt'][2]==graph,'history/submission generation differs')
 require(job['name']==run and job['graph_sha256']==sha(gp),'submitted graph bytes differ')
 return h,job

def metadata_token(run):
 """Stat-based stability only; deliberately never loads giant counterfactual JSON."""
 records=[]
 rels=[f'logs/{run}_history.json',f'logs/{run}_job.json',f'configs/{run}.json',f'audit/counterfactual/{run}.json',f'audit/{run}_conditioning.json',f'audit/{run}_noise.json','deploy_manifest.json','configs/source.pose.json']
 for rel in rels:
  p=safe(ROOT,rel);st=p.stat();records.append([rel,st.st_size,st.st_mtime_ns])
 for rel in [f'audit/x0/{run}',f'audit/counterfactual/{run}_snapshots','audit/observations']:
  folder=safe(ROOT,rel);require(folder.is_dir(),'completion folder absent')
  for p in sorted(folder.rglob('*')):
   if p.is_file():st=p.stat();records.append([relative(ROOT,p),st.st_size,st.st_mtime_ns])
 m=ROOT/'audit/x0'/run/'manifest.json';manifest=read(m)
 require(manifest['status']=='complete' and len(manifest['captures'])==20,'chosen captures not complete')
 return canonical_sha({'stat':records,'chosen_manifest_sha256':sha(m),'manifest_sha256':sha(ROOT/'deploy_manifest.json')})

def snapshot():
 _,owner=bound();out={}
 for c in P['cases']:
  run=c['run_id'];hp=ROOT/'logs'/f'{run}_history.json';jp=ROOT/'logs'/f'{run}_job.json'
  if not hp.exists() or not jp.exists():out[run]={'status':'pending'};continue
  h=read(hp);j=read(jp)
  if h.get('status',{}).get('status_str')=='error' or j.get('status') in ('error','unknown_missing','submission_uncertain'):
   out[run]={'status':'failed','reason':'technical_producer_error'};continue
  if not(h.get('status',{}).get('completed') is True and h['status'].get('status_str')=='success' and j.get('status')=='success'):
   out[run]={'status':'pending'};continue
  success_metadata(run,owner)
  try:out[run]={'status':'success_files_present','token':metadata_token(run)}
  except FileNotFoundError:out[run]={'status':'completion_files_pending'}
 return {'runs':out,'owner':owner,'metadata_only':True,'content_integrity':'not claimed; archive verifies every original byte'}

def checked_archive(run):
 _,owner=bound();success_metadata(run,owner);arc=HERE/'captured'/run;verify_archive_anchor(arc,run,owner)
 receipt=read(HERE/'archive_receipts'/f'{run}.json');require(receipt['protocol_sha256']==sha(HERE/'PROTOCOL.json'),'archive protocol differs')
 require(sorted(receipt['index_sha256'])==[f'{i:03d}' for i in range(20)],'20 index inventory')
 inv=read(arc/'FILE_INVENTORY.json')
 require(stat_inventory(ROOT,arc,inv)==receipt['stat_inventory_sha256'],'source/archive stats changed; full integrity review required')
 return arc,owner,receipt,inv

def index_for(run,index,receipt,inv):
 require(type(index) is int and 0<=index<20,'index outside20')
 return check_index(HERE/'indexes'/run/f'{index:03d}.json',receipt['index_sha256'][f'{index:03d}'],run,index,inv)

def archive(run,token):
 with locked():
  started=time.monotonic();_,owner=bound();case=case_for(run);require(snapshot()['runs'][run]['token']==token,'changed since stable snapshot');arc=HERE/'captured'/run
  require(not arc.exists(),'partial/existing archive retained; explicit recovery required')
  verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True)
  ps=inventory(run);inv={relative(ROOT,p):{'sha256':sha(p),'bytes':p.stat().st_size} for p in ps};arc.mkdir(parents=True)
  for p in ps:
   rel=relative(ROOT,p);dest=safe(arc,rel);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);require(sha(dest)==inv[rel]['sha256']==sha(p),'copy/source changed')
  save(arc/'FILE_INVENTORY.json',inv);save(arc/'ADMIN_ADMISSION_AT_ARCHIVE.json',read(ROOT/'configs/admission.json'))
  proc=launch([sys.executable,str(HERE/'verify_single.py'),'--run',run,'--allow-resident','--output',str(arc/'RUNTIME_GATE.json')],arc/'verify.log',timeout=900)
  require(proc.returncode==0 and read(arc/'RUNTIME_GATE.json')['status']=='pass','runtime verification failed')
  audit=read(arc/'audit/counterfactual'/f'{run}.json');supplement=condition_checks(arc,case,audit);save(arc/'DECISION_LEDGER.json',decision_ledger(audit))
  hashes={};measurements=audit['counterfactual']['measurements'];require(len(measurements)==20,'20 actual measurements required')
  for i,m in enumerate(measurements):
   d=index_measurement(ROOT,arc,run,i,m,inv);dest=HERE/'indexes'/run/f'{i:03d}.json';save(dest,d);hashes[f'{i:03d}']=sha(dest)
  result={'passed':True,'run_id':run,'owner':owner,'manifest_sha256':P['producer_manifest_sha256'],'file_inventory_sha256':sha(arc/'FILE_INVENTORY.json'),'runtime':read(arc/'RUNTIME_GATE.json'),'additional_checks':supplement,'ledger_sha256':sha(arc/'DECISION_LEDGER.json'),'archive_seconds':time.monotonic()-started,'numerical_observer_replay':'pending20 CPU replay phases','final_pose':'pending','cleanup_claim':False,'new_method_claim':False}
  save(arc/'RUN_GATE.json',result);verify_source_archive(ROOT,arc,owner,run);verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True)
  save(HERE/'archive_receipts'/f'{run}.json',{'run_id':run,'owner':owner,'protocol_sha256':sha(HERE/'PROTOCOL.json'),'run_gate_sha256':sha(arc/'RUN_GATE.json'),'inventory_sha256':sha(arc/'FILE_INVENTORY.json'),'index_sha256':hashes,'stat_inventory_sha256':stat_inventory(ROOT,arc,inv),'full_original_integrity_verified':True})
  return {'status':'archive_complete','run':run,'gate':str(arc/'RUN_GATE.json'),'files':len(inv),'seconds':result['archive_seconds'],'may_request_exact_owner_release':True,'cleanup_claim':False}

def observation(run,index):
 with locked():
  started=time.monotonic();arc,owner,receipt,inv=checked_archive(run);d=index_for(run,index,receipt,inv);dest=arc/'observer_replay'/f'{index:03d}.json';require(not dest.exists(),'never overwrite replay')
  checked=verify_data_dependencies(ROOT,arc,d['dependencies']);code=verify_producer_sources(ROOT,P['producer_manifest_sha256']);runtime_imports();from scan_current_pose import observe
  result=observe(safe(arc,d['source']),safe(arc,d['pose']),index);require(canonical_sha(numeric_observer(result))==d['expected_replay']['scan_sha256'],'independent replay differs')
  out={'passed':True,'all_numeric_values_equal':True,**d['expected_replay'],'summary':observer_summary(result),'elapsed_seconds':time.monotonic()-started,'verified_dependencies':checked,'verified_producer_sources':code};validate_replay(out,d['expected_replay']);save(dest,out)
  save(HERE/'phase_receipts'/run/f'{index:03d}.json',{'run_id':run,'index':index,'result_sha256':sha(dest),'index_sha256':receipt['index_sha256'][f'{index:03d}']})
  return {'status':'observation_complete','run':run,'index':index,'seconds':out['elapsed_seconds'],'summary_counts':out['summary']['baseline_counts']}

def status(run):
 case_for(run);arc=HERE/'captured'/run
 if not arc.exists():bound();return {'phase':'archive','run':run}
 require((arc/'RUN_GATE.json').exists() and (HERE/'archive_receipts'/f'{run}.json').exists(),'partial archive retained; explicit recovery required')
 arc,owner,receipt,inv=checked_archive(run)
 if (arc/'CPU_COMPLETE.json').exists():
  f=read(HERE/'final_receipts'/f'{run}.json');require(f['completion_sha256']==sha(arc/'CPU_COMPLETE.json') and f['derived_inventory_sha256']==sha(arc/'DERIVED_FILES.json') and f['original_inventory_sha256']==sha(arc/'FILE_INVENTORY.json'),'final receipt differs')
  return {'phase':'complete','run':run,'content_integrity':'full final gate then small anchors/stat at status'}
 for i in range(20):
  dest=arc/'observer_replay'/f'{i:03d}.json'
  if not dest.exists():return {'phase':'observation','index':i,'run':run}
  d=index_for(run,i,receipt,inv);r=read(HERE/'phase_receipts'/run/f'{i:03d}.json');require(r=={'run_id':run,'index':i,'result_sha256':sha(dest),'index_sha256':receipt['index_sha256'][f'{i:03d}']},'phase receipt differs');validate_replay(read(dest),d['expected_replay'])
 return {'phase':'final','run':run}

def final(run):
 with locked():
  started=time.monotonic();arc,owner,receipt,inv=checked_archive(run);require(status(run)['phase']=='final','final requires20 replays')
  verify_source_archive(ROOT,arc,owner,run);verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True);validate_partial_inventory(arc,inv)
  audit=read(arc/'audit/counterfactual'/f'{run}.json');require(len(audit['counterfactual']['measurements'])==20,'20 actual measurements')
  for i,m in enumerate(audit['counterfactual']['measurements']):
   d=index_for(run,i,receipt,inv);require(index_measurement(ROOT,arc,run,i,m,inv)==d,'indexed audit differs');validate_replay(read(arc/'observer_replay'/f'{i:03d}.json'),d['expected_replay'])
  runtime_imports();import evaluate
  result=evaluate.evaluate(ROOT,arc,case_for(run),P)
  verify_source_archive(ROOT,arc,owner,run);verify_producer_sources(ROOT,P['producer_manifest_sha256'],all_files=True)
  result.update(passed=True,run_id=run,owner=owner,no_GPU=True,cleanup_claim=False,observer_replay_indices=list(range(20)));result['derived_outputs']=sorted(str(p.relative_to(arc)) for p in (arc/'final').rglob('*') if p.is_file());save(arc/'CPU_COMPLETE.json',result)
  generated={str(p.relative_to(arc)):sha(p) for p in arc.rglob('*') if p.is_file() and str(p.relative_to(arc)) not in inv and p.name not in ('DERIVED_FILES.json','ADMIN_RELEASE_ACCEPTANCE.json')};save(arc/'DERIVED_FILES.json',generated);validate_complete_inventory(arc)
  save(HERE/'final_receipts'/f'{run}.json',{'completion_sha256':sha(arc/'CPU_COMPLETE.json'),'derived_inventory_sha256':sha(arc/'DERIVED_FILES.json'),'original_inventory_sha256':sha(arc/'FILE_INVENTORY.json')})
  return {'status':'final_complete','run':run,'seconds':time.monotonic()-started,'completion_file':str(arc/'CPU_COMPLETE.json')}

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['snapshot','archive','observation','final','status']);p.add_argument('--run');p.add_argument('--token');p.add_argument('--index',type=int);a=p.parse_args();verify_consumer_seal()
 if a.mode=='snapshot':r=snapshot()
 elif a.mode=='archive':r=archive(a.run,a.token)
 elif a.mode=='observation':r=observation(a.run,a.index)
 elif a.mode=='final':r=final(a.run)
 else:r=status(a.run)
 print(json.dumps(r,allow_nan=False))
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY');raise SystemExit(75)
