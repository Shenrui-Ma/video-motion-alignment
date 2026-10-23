from pathlib import Path
import json,subprocess,shlex,hashlib,io,tarfile
D=Path(__file__).parent;E=D.parent.parent;R='/home/research-user/h3_runs/adaptive_role5_20261023';S='/home/research-user/h3_runs/benchmark_schedule_20261022_host9a';out=D;xs=json.loads((D/'PRECHECK.json').read_text())['jobs'];jobs=[];files={}
def ssh(h,c,x=None):return subprocess.check_output(['ssh',h,shlex.join(['python3','-c',c])],input=None if x is None else json.dumps(x).encode())
for x in xs:
 original=x['graph'];g=json.loads(json.dumps(original).replace(S,R));assert json.loads(json.dumps(g).replace(R,S))==original;raw=(json.dumps(g,indent=2)+'\n').encode();j=json.loads(json.dumps(x['job']).replace(S,R));j['max_attempts']=1;j['metadata'].update(producer_host='host9_extension_0185',source_job_id=j['id'],graph_sha256=hashlib.sha256(raw).hexdigest(),extension_release='followon_0185_20261023');jobs.append(j);files[j['graph']]=raw
files['scripts/extension_followon0185_pair.py']=(E/'supervision/extension_three_20261023/extension_guard.py').read_text().replace('extension_three_20261023','extension_followon_0185_20261023').encode()
files['scripts/extension_followon0185_wait.py']=b'''from pathlib import Path
import sys,time,fcntl,subprocess,os,json
r=Path(__file__).resolve().parents[1];sys.path.insert(0,str(r/'scripts'));import extension_helpers as g
d=r/'innovation_handoff/extension_followon_0185_20261023'
with (d/'wait.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 while True:
  prior=g.read(r/'innovation_handoff/extension_three_20261023/RESULT.json',{});s=g.snapshot(r)
  if prior.get('status')=='audit_or_execution_failure':g.atomic(d/'PROGRESS.json',{'status':'blocked_by_prior_failure'});sys.exit(1)
  if prior.get('status')=='passed' and s['worker']['state']=='exited' and s['service']['state']=='exited' and not any(s['locks'].values()) and not s['port_listening']:
   with (d/'activation.lock').open('a') as a:
    fcntl.flock(a,fcntl.LOCK_EX|fcntl.LOCK_NB);jobs=g.read(d/'planned_jobs.json')['jobs'];ids={j['id'] for j in jobs};assert not ids&set(s['states']);assert not ids&{j['id'] for j in s['manifest']['jobs']};s['manifest']['jobs'].append(jobs[0]);g.atomic(r/'jobs.json',s['manifest']);g.launch_owned_worker(r,d/'FIRST_STARTED.json',{'status':'prior_pair_complete','time':time.time()})
   break
  g.atomic(d/'PROGRESS.json',{'status':'waiting_prior_pair','time':time.time()});time.sleep(30)
os.execvp('python3',['python3','-u',str(r/'scripts/extension_followon0185_pair.py')])
'''
b=io.BytesIO()
with tarfile.open(fileobj=b,mode='w') as t:
 for n,raw in files.items():ti=tarfile.TarInfo(n);ti.size=len(raw);t.addfile(ti,io.BytesIO(raw))
subprocess.run(['ssh','H3_HOST_SECONDARY','tar -xf - -C '+R],input=b.getvalue(),check=True)
src=xs[0]['job']['metadata']['source_video'];dst=R+'/input/'+Path(src).name
exists=json.loads(ssh('H3_HOST_SECONDARY','from pathlib import Path;import hashlib,json;p=Path('+repr(dst)+');print(json.dumps({"exists":p.exists(),"sha":hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None}))'))
if exists['exists']:assert exists['sha']==xs[0]['source_sha256']
else:
 ssh('H3_HOST_SECONDARY','from pathlib import Path;import shutil,hashlib;s=Path('+repr(src)+');d=Path('+repr(dst)+');tmp=d.with_suffix(d.suffix+".partial0185");shutil.copyfile(s,tmp);assert hashlib.sha256(tmp.read_bytes()).hexdigest()=='+repr(xs[0]['source_sha256'])+';tmp.replace(d)')
# The source queue is inactive; hold both locks while removing exactly the unsubmitted pair.
code='''from pathlib import Path
import json,sys,fcntl,hashlib,time
r=Path(ROOT);x=json.load(sys.stdin);d=r/'innovation_handoff/extension_three_20261023';ids=set(x['ids'])
with (r/'innovation_handoff/drain.lock').open('a') as l,(r/'worker.lock').open('a') as w,(r/'queue_state/runner.lock').open('a') as q:
 for f in [l,w,q]:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert not ids&set(json.loads((r/'queue_state/state.json').read_text())['jobs']);assert not ids&{j['id'] for j in json.loads((r/'jobs.json').read_text())['jobs']};p=r/'innovation_handoff/parked_manifest.json';raw=p.read_bytes();v=json.loads(raw);selected=[j for j in v['jobs'] if j['id'] in ids];assert len(selected)==2;v['jobs']=[j for j in v['jobs'] if j['id'] not in ids];after=json.dumps(v,ensure_ascii=False,indent=2).encode();t=p.with_suffix('.followon.tmp');t.write_bytes(after);t.replace(p);receipt={'status':'released_unsubmitted','job_ids':sorted(ids),'source_jobs':selected,'target_host':'H3_HOST_SECONDARY','target_root':TARGET,'target_owner':'host9_extension_0185','before_sha':hashlib.sha256(raw).hexdigest(),'after_sha':hashlib.sha256(after).hexdigest(),'time':time.time()};p=d/'host9_followon0185.SOURCE_RELEASE.json';assert not p.exists();p.write_text(json.dumps(receipt,indent=2));sys.stdout.buffer.write(p.read_bytes())
'''.replace('ROOT',repr(S)).replace('TARGET',repr(R));release=ssh('H3_HOST_SECONDARY',code,{'ids':[j['id'] for j in jobs]});(out/'SOURCE_RELEASE.json').write_bytes(release)
code='''from pathlib import Path
import json,sys,hashlib,time,subprocess,os
r=Path(ROOT);x=json.load(sys.stdin);sys.path.insert(0,str(r/'scripts'));import extension_helpers as g;d=r/'innovation_handoff/extension_followon_0185_20261023';d.mkdir(exist_ok=True);assert not (d/'TARGET_RECEIPT.json').exists()
for n,h in x['assets'].items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h
policy=g.read(r/'shared_gpu_authorization.json');assert policy['torch_allocator_cap_gib']==26 and policy['reserve_vram_gib']==6 and policy['minimum_free_mib']==33792;states=g.read(r/'queue_state/state.json')['jobs'];ids={j['id'] for j in x['manifest']['jobs']};assert not ids&set(states);assert not ids&{j['id'] for j in g.read(r/'jobs.json')['jobs']};g.atomic(d/'planned_jobs.json',x['manifest']);(d/'SOURCE_RELEASE_COPY.json').write_bytes(bytes.fromhex(x['release_hex']));assert hashlib.sha256((d/'SOURCE_RELEASE_COPY.json').read_bytes()).hexdigest()==x['release_sha'];rec={'status':'unique_owner_waiting_prior_pair','job_ids':sorted(ids),'source_release_sha256':x['release_sha'],'target_root':str(r),'owner':'host9_extension_0185','assets':x['assets'],'time':time.time()};g.atomic(d/'TARGET_RECEIPT.json',rec)
with (d/'guard.log').open('ab') as f:p=subprocess.Popen(['python3','-u',str(r/'scripts/extension_followon0185_wait.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)
proc=Path('/proc')/str(p.pid);g.atomic(d/'GUARD.json',{'pid':p.pid,'uid':proc.stat().st_uid,'start_ticks':(proc/'stat').read_text().rsplit(')',1)[1].split()[19]});rec['guard']=g.read(d/'GUARD.json');g.atomic(d/'TARGET_RECEIPT.json',rec);print(json.dumps(rec))
'''.replace('ROOT',repr(R));assets={n:hashlib.sha256(b).hexdigest() for n,b in files.items()};v=ssh('H3_HOST_SECONDARY',code,{'manifest':{'jobs':jobs},'release':json.loads(release),'release_hex':release.hex(),'release_sha':hashlib.sha256(release).hexdigest(),'assets':assets});(out/'TARGET_RECEIPT.json').write_bytes(v);(out/'jobs.json').write_text(json.dumps({'jobs':jobs},indent=2));print(v.decode())
