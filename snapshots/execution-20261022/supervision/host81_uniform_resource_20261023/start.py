from pathlib import Path
import subprocess,json,shlex,hashlib
D=Path(__file__).parent;R='/data/research-user/h3_inference_20261023/run_uniform_energy';H='H3_HOST_RTX4090'
def ssh(c,b=None,python='python3'):return subprocess.check_output(['ssh',H,shlex.join([python,'-c',c])],input=b)
raw=(D/'sequence_guard.py').read_bytes();ssh('from pathlib import Path;import sys;Path('+repr(R+'/scripts/sequence_guard.py')+').write_bytes(sys.stdin.buffer.read())',raw)
assets=json.loads((D/'DEPLOY_ASSETS.json').read_text());assets['scripts/sequence_guard.py']=hashlib.sha256(raw).hexdigest();(D/'DEPLOY_ASSETS.json').write_text(json.dumps(assets,indent=2))
code='''from pathlib import Path
import sys,torch,json
r=Path(ROOT);sys.path.insert(0,str(r/'custom_nodes'));from H3TemporalGainFieldUniformEnergy.frozen import load_frozen
core=load_frozen().core
for dtype in (torch.float16,torch.bfloat16):
 q=torch.randn(1,2,16,32,device='cuda',dtype=dtype);o,l=core.flash_attention_lse(q,q,q);assert torch.isfinite(o).all() and torch.isfinite(l).all()
torch.cuda.synchronize();print(json.dumps({'status':'passed','torch':torch.__version__,'tiny_flash':True}))
'''.replace('ROOT',repr(R))
probe=subprocess.run(['ssh',H,'CUDA_VISIBLE_DEVICES=GPU-REPLACE-WITH-DEVICE-UUID PYTHONPATH=/data/research-user/h3_inference_20261023/runtime_deps /data/research-user/h3_inference_20261023/env/bin/python -'],input=code.encode(),capture_output=True);assert probe.returncode==0,probe.stderr.decode();(D/'DEPLOY_GPU_READY.json').write_bytes(probe.stdout)
code='''from pathlib import Path
import sys,json,hashlib,fcntl,socket,subprocess,time,os
r=Path(ROOT);x=json.load(sys.stdin);sys.path.insert(0,str(r/'scripts'));import runtime_helpers as g
d=r/'innovation_handoff/uniform_energy';d.mkdir(exist_ok=True)
with (d/'activation.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);assert not (d/'TARGET_RECEIPT.json').exists();assert not (r/'jobs.json').exists();assert not g.read(r/'queue_state/state.json',{'jobs':{}})['jobs']
 for f,h in x['assets'].items():assert hashlib.sha256((r/f).read_bytes()).hexdigest()==h,f
 assert g.identity(g.read(r/'worker_pid.json'),str(r/'scripts/host_worker.py'))['state'] in ('exited','missing_record');assert g.identity(g.read(r/'service.json'),str(r))['state'] in ('exited','missing_record');assert not g.locked(r/'worker.lock') and not g.locked(r/'queue_state/runner.lock')
 with socket.socket() as s:assert s.connect_ex(('127.0.0.1',8679))!=0
 rows=subprocess.check_output(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True);free=next(float(a.split(',')[1]) for a in rows.splitlines() if a.startswith('GPU-REPLACE-WITH-DEVICE-UUID'));assert free>=22500
 jobs=x['manifest']['jobs'];assert len(jobs)==2 and '0358' in jobs[0]['id']
 for j in jobs:assert j['max_attempts']==1 and hashlib.sha256((r/j['graph']).read_bytes()).hexdigest()==j['metadata']['graph_sha256']
 g.atomic(d/'planned_jobs.json',x['manifest']);g.atomic(r/'jobs.json',{'jobs':[jobs[0]],'planned_count':1})
 rec={'status':'unique_owner','job_ids':[j['id'] for j in jobs],'target_host':'H3_HOST_RTX4090','owner':'host81_uniform','target_root':str(r),'port':8679,'policy':g.read(r/'shared_gpu_authorization.json'),'first_only_until_audit':True,'new_independent_pilots_never_submitted_elsewhere':True,'ready_sha256':x['ready_sha256'],'assets':x['assets'],'physical_free_mib':free,'time':time.time()};g.launch_owned_worker(r,d/'TARGET_RECEIPT.json',rec)
 with (d/'guard.log').open('ab') as log:p=subprocess.Popen(['python3','-u',str(r/'scripts/sequence_guard.py')],stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True)
 q=Path('/proc')/str(p.pid);g.atomic(d/'GUARD.json',{'pid':p.pid,'uid':q.stat().st_uid,'start_ticks':(q/'stat').read_text().rsplit(')',1)[1].split()[19],'time':time.time()});sys.stdout.buffer.write((d/'TARGET_RECEIPT.json').read_bytes())
'''.replace('ROOT',repr(R))
x=ssh(code,json.dumps({'manifest':json.loads((D/'jobs.json').read_text()),'assets':assets,'ready_sha256':'f494b28d02b2ca6f01712910e124c2c46ed1ac92397db5d867385615404a7423'}).encode());(D/'TARGET_RECEIPT.json').write_bytes(x);print(x.decode())
