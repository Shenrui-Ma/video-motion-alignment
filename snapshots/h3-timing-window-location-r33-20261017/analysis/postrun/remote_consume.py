"""Read-only producer intake, one displaced single-job batch. All inference is already complete."""
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
  run=case['run_id'];g=read(ROOT/'configs/graphs'/f'{run}.json');h=read(ROOT/'logs'/f'{run}_history.json');j=read(ROOT/'logs'/f'{run}_job.json');require(h['status']['completed'] is True and h['status']['status_str']=='success' and j['status']=='success','both jobs must complete')
  rels.update((f'logs/{run}_history.json',f'logs/{run}_job.json',f'configs/graphs/{run}.json',f'audit/{run}_conditioning.json',f'audit/{run}_noise.json',f'audit/counterfactual/{run}.json',f'audit/x0/{run}/manifest.json'))
  audit=read(ROOT/'audit/counterfactual'/f'{run}.json');c=audit['counterfactual']
  for row in c['branches']+c['inputs']:rels.add(relative(ROOT,row['file']))
  rels.add(f'audit/counterfactual/{run}_snapshots/sampler_final_raw.pt')
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
  if rel.startswith(('configs/','design/','parent_evidence/')):rels.add(rel)
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
 owner=bound();gate=read(ARC/'RUN_GATE.json');require(gate['passed'] is True and gate['run_id']=='batch' and gate['owner']==owner,'batch gate identity');verify_source_archive(ROOT,ARC,owner,'batch');return owner

def archive(token):
 with locked():
  owner=bound();require(snapshot()['token']==token,'completion token changed');require(not ARC.exists(),'partial archive requires explicit review')
  for rel,r in read(ROOT/'deploy_manifest.json')['files'].items():require(sha(safe(ROOT,rel))==r['sha256'],'sealed producer changed '+rel)
  files=inventory();inv={relative(ROOT,p):{'sha256':sha(p),'bytes':p.stat().st_size} for p in files};ARC.mkdir(parents=True)
  for p in files:
   dest=safe(ARC,relative(ROOT,p));dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);require(sha(dest)==sha(p)==inv[relative(ROOT,p)]['sha256'],'archive changed during copy')
  save(ARC/'FILE_INVENTORY.json',inv);save(ARC/'ADMIN_ADMISSION_AT_ARCHIVE.json',read(ROOT/'configs/admission.json'))
  with (ARC/'verify.log').open('x') as log:
   proc=subprocess.run([sys.executable,str(ROOT/'scripts/verify_completed.py'),'--allow-resident','--output',str(ARC/'RUNTIME_GATE.json')],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'),timeout=480)
  require(proc.returncode==0 and read(ARC/'RUNTIME_GATE.json')['status']=='pass','fixed batch runtime gate failed')
  gate={'passed':True,'run_id':'batch','runs':[x['run_id'] for x in P['cases']],'owner':owner,'file_inventory_sha256':sha(ARC/'FILE_INVENTORY.json'),'runtime_gate_sha256':sha(ARC/'RUNTIME_GATE.json'),'cleanup_claim':False,'CPU_final_pending':True};save(ARC/'RUN_GATE.json',gate);verify_source_archive(ROOT,ARC,owner,'batch');return gate

def evaluate_case(case):
 from displaced_evaluate import evaluate_displaced
 return evaluate_displaced(ROOT,ARC,case,P)

def validate_final():
 checked_archive();done=read(ARC/'CPU_COMPLETE.json');require(done['passed'] is True and done['runs']==[x['run_id'] for x in P['cases']],'wrong completion')
 inv=read(ARC/'FILE_INVENTORY.json');derived=read(ARC/'DERIVED_FILES.json');allowed={'FILE_INVENTORY.json','DERIVED_FILES.json'}|({'ADMIN_RELEASE_ACCEPTANCE.json'} if (ARC/'ADMIN_RELEASE_ACCEPTANCE.json').exists() else set());require(set(done['derived_outputs'])|{'CPU_COMPLETE.json'}==set(derived),'derived manifest omitted output')
 require({str(p.relative_to(ARC)) for p in ARC.rglob('*') if p.is_file()}==set(inv)|set(derived)|allowed,'exact final inventory')
 for rel,d in derived.items():require(sha(safe(ARC,rel))==d,'derived output changed '+rel)
 return done

def status():
 if not ARC.exists():return {'phase':'archive'}
 checked_archive()
 if (ARC/'CPU_COMPLETE.json').exists():return {'phase':'complete','result':validate_final()}
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
    require(status()['phase']=='finalize','not all cases complete');checked_archive();original=read(ARC/'FILE_INVENTORY.json');paths=sorted(str(x.relative_to(ARC)) for x in ARC.rglob('*') if x.is_file() and str(x.relative_to(ARC)) not in original and x.name!='ADMIN_RELEASE_ACCEPTANCE.json');result={'passed':True,'runs':[x['run_id'] for x in P['cases']],'derived_outputs':paths,'no_GPU':True,'cleanup_claim':False};save(ARC/'CPU_COMPLETE.json',result);save(ARC/'DERIVED_FILES.json',{rel:sha(ARC/rel) for rel in paths+['CPU_COMPLETE.json']});validate_final()
 print(json.dumps(result,allow_nan=False))
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY');raise SystemExit(75)
