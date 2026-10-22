from pathlib import Path
import json,subprocess,shlex,hashlib,base64
D=Path(__file__).parent;S='/data4/research-user/h3_runs/benchmark_schedule_20261022';T='/home/research-user/h3_runs/adaptive_role5_20261023'
def ssh(h,c,b=None):return subprocess.check_output(['ssh',h,shlex.join(['python3','-c',c])],input=b)
jobs=json.loads((D/'jobs.json').read_text());assets=json.loads((D/'ASSETS.json').read_text())
code='''from pathlib import Path
import sys,json,hashlib,socket
r=Path(ROOT);x=json.load(sys.stdin);assert not (r/'jobs.json').exists();assert json.loads((r/'GPU_PROBE.json').read_text())['status']=='passed'
for f,h in x.items():assert hashlib.sha256((r/f).read_bytes()).hexdigest()==h,f
with socket.socket() as s:assert s.connect_ex(('127.0.0.1',8678))!=0
print('ready')
'''.replace('ROOT',repr(T));assert ssh('H3_HOST_SECONDARY',code,json.dumps(assets).encode()).strip()==b'ready'
code='''from pathlib import Path
import sys,json,fcntl,os,signal,time,hashlib
r=Path(ROOT);sys.path.insert(0,str(r/'scripts'));import layer_runtime_helpers as g
d=r/'innovation_handoff/role5_priority_20261023'
with (r/'innovation_handoff/activation.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if (d/'SOURCE_RELEASE.json').exists():sys.stdout.buffer.write((d/'SOURCE_RELEASE.json').read_bytes());sys.exit(0)
 req=g.read(d/'request.json');ids=[j['id'] for j in req['pilots']['jobs']];manifest=g.read(r/'jobs.json');state=g.read(r/'queue_state/state.json')['jobs'];assert len(manifest['jobs'])==67
 assert not set(ids)&set(j['id'] for j in manifest['jobs']);assert not set(ids)&set(state);assert not (d/'activation.json').exists()
 guard=g.read(d/'pid.json');assert guard['pid']==109767 and str(guard['start_ticks'])=='1465446' and guard['uid']==1004;assert g.identity(guard,str(r/'scripts/role5_boundary_guard.py'))['state']=='owned_alive'
 before=hashlib.sha256((r/'jobs.json').read_bytes()).hexdigest();req['status']='transferred_unsubmitted';req['transfer_target']=TARGET;g.atomic(d/'request.json',req)
 os.kill(guard['pid'],signal.SIGTERM)
 for _ in range(100):
  if g.identity(guard,str(r/'scripts/role5_boundary_guard.py'))['state']=='exited':break
  time.sleep(.1)
 assert g.identity(guard,str(r/'scripts/role5_boundary_guard.py'))['state']=='exited'
 assert hashlib.sha256((r/'jobs.json').read_bytes()).hexdigest()==before
 rec={'status':'released_unsubmitted','job_ids':ids,'source_root':str(r),'source_host':'H3_HOST_PRIMARY','target_host':'H3_HOST_SECONDARY','target_root':TARGET,'guard_stopped':guard,'source_manifest_count':67,'source_manifest_sha256':before,'current_worker':g.read(r/'worker_pid.json'),'current_service':g.read(r/'service.json'),'current_video_untouched':True,'time':time.time()};g.atomic(d/'SOURCE_RELEASE.json',rec);g.atomic(d/'status.json',rec);sys.stdout.buffer.write((d/'SOURCE_RELEASE.json').read_bytes())
'''.replace('ROOT',repr(S)).replace('TARGET',repr(T))
raw=ssh('H3_HOST_PRIMARY',code);json.loads(raw);(D/'SOURCE_RELEASE.json').write_bytes(raw)
code='''from pathlib import Path
import sys,json,hashlib,fcntl,socket,base64,subprocess,time,os
r=Path(ROOT);x=json.load(sys.stdin);sys.path.insert(0,str(r/'scripts'));import runtime_helpers as g
d=r/'innovation_handoff/role5_transfer';d.mkdir(exist_ok=True)
with (d/'activation.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);assert not (d/'TARGET_RECEIPT.json').exists();assert not (r/'jobs.json').exists();assert not g.read(r/'queue_state/state.json',{'jobs':{}})['jobs']
 assert g.identity(g.read(r/'worker_pid.json'),str(r/'scripts/host_worker.py'))['state'] in ('exited','missing_record');assert g.identity(g.read(r/'service.json'),str(r))['state'] in ('exited','missing_record')
 with socket.socket() as s:assert s.connect_ex(('127.0.0.1',8678))!=0
 raw=base64.b64decode(x['release']);assert hashlib.sha256(raw).hexdigest()==x['release_sha256'];(d/'SOURCE_RELEASE.json').write_bytes(raw);jobs=x['manifest']['jobs'];assert len(jobs)==2
 for j in jobs:assert j['max_attempts']==1 and hashlib.sha256((r/j['graph']).read_bytes()).hexdigest()==j['metadata']['graph_sha256']
 g.atomic(d/'planned_jobs.json',x['manifest']);g.atomic(r/'jobs.json',{'jobs':[jobs[0]],'planned_count':1})
 rec={'status':'unique_owner','job_ids':[j['id'] for j in jobs],'source_release_sha256':x['release_sha256'],'target_host':'H3_HOST_SECONDARY','target_root':str(r),'port':8678,'policy':g.read(r/'shared_gpu_authorization.json'),'first_only_until_audit':True,'time':time.time()};g.launch_owned_worker(r,d/'TARGET_RECEIPT.json',rec)
 with (d/'guard.log').open('ab') as log:p=subprocess.Popen(['python3','-u',str(r/'scripts/sequence_guard.py')],stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True)
 q=Path('/proc')/str(p.pid);g.atomic(d/'GUARD.json',{'pid':p.pid,'uid':q.stat().st_uid,'start_ticks':(q/'stat').read_text().rsplit(')',1)[1].split()[19],'time':time.time()});sys.stdout.buffer.write((d/'TARGET_RECEIPT.json').read_bytes())
'''.replace('ROOT',repr(T))
x=ssh('H3_HOST_SECONDARY',code,json.dumps({'release':base64.b64encode(raw).decode(),'release_sha256':hashlib.sha256(raw).hexdigest(),'manifest':jobs}).encode());(D/'TARGET_RECEIPT.json').write_bytes(x);print(x.decode())
