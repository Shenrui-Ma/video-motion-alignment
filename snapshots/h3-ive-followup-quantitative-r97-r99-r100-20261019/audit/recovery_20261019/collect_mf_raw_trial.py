"""Collect a completed short MF attempt and verify release, bytes and score binding."""
from pathlib import Path
import hashlib,json,shlex,subprocess,sys,tarfile
root=Path(sys.argv[1]).resolve();cfg=json.loads((root/'configs/RUNTIME.json').read_text());case=next((root/'cases').iterdir()).name;remote=cfg['remote_root'];attempt='actual_'+case+'_capacity_attempt4'
code='REMOTE='+repr(remote)+'\nCASE='+repr(case)+'\nATTEMPT='+repr(attempt)+'\n'+'''
from pathlib import Path
import json,hashlib,tarfile,subprocess,time
r=Path(REMOTE);c=r/'cases'/CASE;b=r/'audit'/ATTEMPT
complete=json.loads((b/'COMPLETE.json').read_text());assert complete['passed'] is True
nv={int(x.strip()) for x in subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).splitlines() if x.strip()}
release=[]
for p in b.glob('*/RELEASED.json'):
 d=json.loads(p.read_text());assert d['process_absent'] and d['own_cuda_absent'] and d['returncode']==0
 assert not Path('/proc/'+str(d['pid'])).exists() and d['pid'] not in nv
 release.append({'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'pid':d['pid']})
assert release
launch=json.loads((r/'audit/SLOT_CAPACITY4_LAUNCH.json').read_text());pid=launch['identity']['pid'];assert not Path('/proc/'+str(pid)).exists() and pid not in nv
receipt={'passed':True,'wrapper_identity':launch['identity'],'wrapper_absent':True,'trackers':release,'all_own_allocations_absent':True,'unix':time.time()}
(r/'audit/SLOT_RELEASE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+chr(10))
files=[]
for p in [b,c/'controls',c/'tracks',c/'results',c/'preflight']:
 if p.exists():files.extend(x for x in p.rglob('*') if x.is_file())
files.extend([r/'audit/SLOT_RELEASE_RECEIPT.json',r/'audit/SLOT_CAPACITY4_LAUNCH.json',r/'audit/PASSIVE_DEPLOYMENT.json',c/'INPUTS.json',c/'SPEC.json'])
manifest={str(x.relative_to(r)):hashlib.sha256(x.read_bytes()).hexdigest() for x in files};(r/'audit/RETURN_SHA.json').write_text(json.dumps(manifest,indent=2))
with tarfile.open(r/'audit/CAPACITY_RESULTS.tar.gz','w:gz') as t:
 for x in files:t.add(x,arcname=str(x.relative_to(r)))
 t.add(r/'audit/RETURN_SHA.json',arcname='audit/RETURN_SHA.json')
print(json.dumps({'passed':True,'files':len(files),'release':receipt}))
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','H3_SERVER_B','python3 -c '+shlex.quote(code)],capture_output=True,text=True)
(root/'audit/COLLECT_RESPONSE.json').write_text(json.dumps({'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr},indent=2)+'\n');assert p.returncode==0,p.stderr.replace('No such file or directory','ABSENT')
archive=root/'CAPACITY_RESULTS.tar.gz';subprocess.run(['scp','-q','-o','BatchMode=yes','-o','ConnectTimeout=10','H3_SERVER_B:'+remote+'/audit/CAPACITY_RESULTS.tar.gz',str(archive)],check=True)
dest=root/'actual_host41';dest.mkdir(exist_ok=False)
with tarfile.open(archive) as t:t.extractall(dest,filter='data')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for rel,h in json.loads((dest/'audit/RETURN_SHA.json').read_text()).items():assert sha(dest/rel)==h
c=dest/'cases'/case;spec=json.loads((c/'SPEC.json').read_text());scores={k:json.loads((c/'results'/(k+'.json')).read_text()) for k in spec['targets']}
for s in scores.values():assert s['case_inputs_sha256']==sha(c/'INPUTS.json')
tracks={}
for p in (dest/'audit'/attempt).glob('*/RESOURCE_OBSERVATIONS.json'):
 d=json.loads(p.read_text());initial=json.loads((p.parent/'PREFLIGHT.json').read_text())['cgroup']['snapshot'];final=d['final_snapshot'];old={r['path']:r for r in initial['ancestors']}
 deltas={r['path']:{k:r['events'].get(k,0)-old[r['path']]['events'].get(k,0) for k in ('oom','oom_kill','oom_group_kill')} for r in final['ancestors'] if r['path'] in old}
 maxrss=json.loads((c/'controls'/p.parent.name/'PROCESS_USAGE.json').read_text())['maxrss_kib']
 tracks[p.parent.name]={'maxrss_kib':maxrss,'oom_event_deltas':deltas,'samples':len(d['samples'])}
receipt=dest/'audit/SLOT_RELEASE_RECEIPT.json'
result={'case':case,'benchmark':'IVEBench','valid_frames':next(iter(scores.values()))['valid_frames'],'fps':24,'scores':{k:v['motion_fidelity'] for k,v in scores.items()},'resources':tracks,'release_receipt':{'file':str(receipt),'sha256':sha(receipt)},'input_sha256':sha(c/'INPUTS.json'),'scope':'Official MF; task acceptance and event timing remain separate.'}
(root/'RESULT_VERIFIED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
