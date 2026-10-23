from pathlib import Path
import json,hashlib,subprocess,shlex
D=Path(__file__).parent;E=D.parent.parent;R='/data4/research-user/h3_runs/benchmark_schedule_20261022';pre=json.loads((D/'PRECHECK.json').read_text());guard=(E/'supervision/extension_three_20261023/extension_guard.py').read_text().replace('extension_three_20261023','extension_followon_0362_20261023')
code='''from pathlib import Path
import sys,json,hashlib,time,fcntl,subprocess,ast
r=Path(ROOT);sys.path.insert(0,str(r/'scripts'));import extension_helpers as g;x=json.load(sys.stdin);d=r/'innovation_handoff/extension_followon_0362_20261023';d.mkdir(exist_ok=True)
with (d/'activation.lock').open('a') as a,(r/'innovation_handoff/drain.lock').open('a') as z,(r/'worker.lock').open('a') as w,(r/'queue_state/runner.lock').open('a') as q:
 for f in [a,z,w,q]:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert not (d/'TARGET_RECEIPT.json').exists();s=g.snapshot(r);assert s['worker']['state']=='exited' and s['service']['state']=='exited' and not s['port_listening'];assert g.read(r/'innovation_handoff/extension_followon_0318_20261023/RESULT.json')['status']=='passed'
 uuid='GPU-REPLACE-WITH-DEVICE-UUID';raw=subprocess.check_output(['nvidia-smi','-i',uuid,'--query-gpu=memory.free,temperature.gpu','--format=csv,noheader,nounits'],text=True);free,temp=map(float,raw.strip().split(','));assert free>=40000 and temp<85
 assert "GPU='"+uuid+"'" in (r/'scripts/manage_service.py').read_text();assert "else 8672" in (r/'scripts/host_worker.py').read_text()
 jobs=[]
 for row in x['pre']['jobs']:
  j=row['job'];assert j['id'] not in s['states'] and j['id'] not in {j['id'] for j in s['manifest']['jobs']};assert hashlib.sha256((r/j['graph']).read_bytes()).hexdigest()==row['graph_sha256'];assert hashlib.sha256(Path(j['metadata']['source_video']).read_bytes()).hexdigest()==row['source_sha'];j['max_attempts']=1;j['metadata'].update(producer_host='host41_extension_0362',source_job_id=j['id'],cohort='ive_real_extension');jobs.append(j)
 ids={j['id'] for j in jobs};p=r/'innovation_handoff/parked_manifest.json';before=p.read_bytes();park=json.loads(before);selected=[j for j in park['jobs'] if j['id'] in ids];assert len(selected)==2;park['jobs']=[j for j in park['jobs'] if j['id'] not in ids];g.atomic(p,park);release={'status':'released_unsubmitted','source_root':str(r),'target_root':str(r),'target_owner':'host41_extension_0362','source_jobs':selected,'job_ids':sorted(ids),'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'time':time.time()};g.atomic(d/'SOURCE_RELEASE.json',release)
 gp=r/'scripts/extension_followon0362_pair.py';ast.parse(x['guard']);gp.write_text(x['guard']);g.atomic(d/'planned_jobs.json',{'jobs':jobs});manifest=s['manifest'];manifest['jobs'].append(jobs[0]);g.atomic(r/'jobs.json',manifest);receipt={'status':'unique_owner','owner':'host41_extension_0362','gpu':7,'gpu_uuid':uuid,'job_ids':sorted(ids),'source_release_sha256':hashlib.sha256((d/'SOURCE_RELEASE.json').read_bytes()).hexdigest(),'guard_sha256':hashlib.sha256(gp.read_bytes()).hexdigest(),'free_mib':free,'temperature':temp,'time':time.time()};g.atomic(d/'TARGET_RECEIPT.json',receipt)
# Locks released before worker starts; ownership already atomic.
g.launch_owned_worker(r,d/'FIRST_STARTED.json',{'status':'prior0318_passed_and_exited','time':time.time()})
with (d/'guard.log').open('ab') as f:child=subprocess.Popen(['python3','-u',str(gp)],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)
proc=Path('/proc')/str(child.pid);rec={'pid':child.pid,'uid':proc.stat().st_uid,'start_ticks':(proc/'stat').read_text().rsplit(')',1)[1].split()[19]};g.atomic(d/'GUARD.json',rec);receipt['guard']=rec;receipt['worker']=g.read(r/'worker_pid.json');g.atomic(d/'TARGET_RECEIPT.json',receipt);print(json.dumps({'receipt':receipt,'release':release,'jobs':jobs}))
'''.replace('ROOT',repr(R))
v=subprocess.check_output(['ssh','-o','ConnectTimeout=20','H3_HOST_CONFIGURE_LOCALLY',shlex.join(['python3','-c',code])],input=json.dumps({'pre':pre,'guard':guard}).encode(),timeout=60);out=json.loads(v)
for key,name in [('receipt','TARGET_RECEIPT.json'),('release','SOURCE_RELEASE.json')]: (D/name).write_text(json.dumps(out[key],indent=2))
(D/'jobs.json').write_text(json.dumps({'jobs':out['jobs']},indent=2));print(json.dumps(out['receipt']))
