from pathlib import Path
import json,subprocess,shlex,hashlib,time,sys
D=Path(__file__).parent;S='/home/research-user/h3_runs/benchmark_schedule_20261022_host9a'
HOSTS={'host41_extension':('H3_HOST_PRIMARY','/data4/research-user/h3_runs/benchmark_schedule_20261022'),'host81_extension':('H3_HOST_RTX4090','/data/research-user/h3_inference_20261023/run_uniform_energy'),'host9_extension':('H3_HOST_SECONDARY','/home/research-user/h3_runs/adaptive_role5_20261023')}
def ssh(h,c,x=None):return subprocess.check_output(['ssh',h,shlex.join(['python3','-c',c])],input=None if x is None else json.dumps(x).encode())
def activate(owner):
 h,r=HOSTS[owner];o=D/owner;assert json.loads((o/'PREPARED.json').read_text())['status']=='prepared';jobs=json.loads((o/'jobs.json').read_text());ids=[j['id'] for j in jobs['jobs']];assert len(ids)==2
 # Source mutation only withdraws never-submitted jobs, while preserving every other parked entry.
 c='''from pathlib import Path
import json,sys,hashlib,fcntl,time,os,socket
r=Path(ROOT);x=json.load(sys.stdin);d=r/'innovation_handoff/extension_three_20261023';d.mkdir(exist_ok=True)
with (r/'innovation_handoff/drain.lock').open('a') as lock,(r/'worker.lock').open('a') as wl,(r/'queue_state/runner.lock').open('a') as ql:
 for l in [lock,wl,ql]:fcntl.flock(l,fcntl.LOCK_EX|fcntl.LOCK_NB)
 states=json.loads((r/'queue_state/state.json').read_text())['jobs'];manifest=json.loads((r/'jobs.json').read_text());assert not set(x['ids'])&set(states);assert not set(x['ids'])&{j['id'] for j in manifest['jobs']}
 p=r/'innovation_handoff/parked_manifest.json';raw=p.read_bytes();parked=json.loads(raw);selected=[j for j in parked['jobs'] if j['id'] in x['ids']];assert {j['id'] for j in selected}==set(x['ids']);assert len(selected)==2
 recpath=d/(x['owner']+'.SOURCE_RELEASE.json');assert not recpath.exists();before=hashlib.sha256(raw).hexdigest();new={**parked,'jobs':[j for j in parked['jobs'] if j['id'] not in x['ids']]};text=json.dumps(new,ensure_ascii=False,indent=2).encode();temp=p.with_suffix('.extension.tmp');temp.write_bytes(text);temp.replace(p)
 rec={'status':'released_unsubmitted','source_root':str(r),'source_host':'H3_HOST_SECONDARY','target_owner':x['owner'],'target_host':x['host'],'target_root':x['root'],'job_ids':x['ids'],'source_jobs':selected,'before_parked_sha':before,'after_parked_sha':hashlib.sha256(text).hexdigest(),'states_absent':True,'manifest_absent':True,'time':time.time()};recpath.write_text(json.dumps(rec,indent=2));sys.stdout.buffer.write(recpath.read_bytes())
'''.replace('ROOT',repr(S))
 release=ssh('H3_HOST_SECONDARY',c,{'ids':ids,'owner':owner,'host':h,'root':r});(o/'SOURCE_RELEASE.json').write_bytes(release)
 c='''from pathlib import Path
import sys,json,hashlib,fcntl,time,subprocess
r=Path(ROOT);x=json.load(sys.stdin);sys.path.insert(0,str(r/'scripts'));import extension_helpers as g;d=r/'innovation_handoff/extension_three_20261023'
with (d/'activation.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);assert not (d/'TARGET_RECEIPT.json').exists();s=g.snapshot(r);assert s['worker']['state']=='exited' and s['service']['state']=='exited';assert not any(s['locks'].values()) and not s['port_listening'];assert s['worker_status']['event']=='finished' and s['worker_status']['cleanup_code']==s['worker_status']['queue_exit_code']==0
 jobs=x['manifest']['jobs'];ids={j['id'] for j in jobs};assert not ids&set(s['states']);assert not ids&{j['id'] for j in s['manifest']['jobs']}
 for n,h in x['assets'].items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h,n
 assert g.read(d/'planned_jobs.json')==x['manifest'];assert g.read(d/'base_manifest.json')==s['manifest'];assert x['release']['status']=='released_unsubmitted' and set(x['release']['job_ids'])==ids
 policy=g.read(r/'shared_gpu_authorization.json');g.atomic(d/'SOURCE_RELEASE_COPY.json',x['release']);m=s['manifest'];m['jobs'].append(jobs[0]);g.atomic(r/'jobs.json',m)
 rec={'status':'unique_owner','owner':x['owner'],'target_root':str(r),'target_host':x['host'],'job_ids':[j['id'] for j in jobs],'source_release_sha256':x['release_sha'],'policy':policy,'first_only_until_native_audit':True,'previous_worker':s['worker'],'previous_service':s['service'],'assets':x['assets'],'time':time.time()};g.launch_owned_worker(r,d/'TARGET_RECEIPT.json',rec)
 with (d/'guard.log').open('ab') as log:p=subprocess.Popen(['python3','-u',str(r/'scripts/extension_guard.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 proc=Path('/proc')/str(p.pid);g.atomic(d/'GUARD.json',{'pid':p.pid,'uid':proc.stat().st_uid,'start_ticks':(proc/'stat').read_text().rsplit(')',1)[1].split()[19]});sys.stdout.buffer.write((d/'TARGET_RECEIPT.json').read_bytes())
'''.replace('ROOT',repr(r))
 v=ssh(h,c,{'manifest':jobs,'release':json.loads(release),'release_sha':hashlib.sha256(release).hexdigest(),'assets':json.loads((o/'ASSETS.json').read_text()),'owner':owner,'host':h});(o/'TARGET_RECEIPT.json').write_bytes(v);print(owner,json.loads(v)['worker'],flush=True)
for owner in sys.argv[1:]:activate(owner)
