from pathlib import Path
import subprocess,shlex,json,hashlib,sys,time
D=Path(__file__).parent
HOSTS={'host41_fixed_budget':('H3_HOST_PRIMARY','/data4/research-user/h3_runs/benchmark_schedule_20261022','/data3/research-user/ComfyUI/.venv/bin/python',8672,7,'GPU-REPLACE-WITH-DEVICE-UUID',37500),'host81_fixed_budget':('H3_HOST_RTX4090','/data/research-user/h3_inference_20261023/run_uniform_energy','/data/research-user/h3_inference_20261023/env/bin/python',8679,5,'GPU-REPLACE-WITH-DEVICE-UUID',22500),'host9_fixed_budget':('H3_HOST_SECONDARY','/home/research-user/h3_runs/adaptive_role5_20261023','/home/research-user/miniconda3/envs/comfyui/bin/python',8678,1,'GPU-REPLACE-WITH-DEVICE-UUID',33792)}
def activate(owner):
 host,R,py,port,index,gpu,minimum=HOSTS[owner];out=D/owner;assert json.loads((out/'CPU_READY.json').read_text())['status']=='CPU_READY'
 probe='''from pathlib import Path
import sys,json,torch
r=Path(ROOT);sys.path.insert(0,str(r/'custom_nodes'));from H3TemporalGainFieldFixedBudget.frozen import load_frozen
core=load_frozen().core
for dt in [torch.float16,torch.bfloat16]:
 q=torch.randn(1,2,16,32,device='cuda',dtype=dt);o,l=core.flash_attention_lse(q,q,q);assert torch.isfinite(o).all() and torch.isfinite(l).all()
torch.cuda.synchronize();print(json.dumps({'status':'passed','gpu_flash':True}))
'''.replace('ROOT',repr(R))
 env='CUDA_VISIBLE_DEVICES='+gpu+' '
 if host=='H3_HOST_RTX4090':env+='PYTHONPATH=/data/research-user/h3_inference_20261023/runtime_deps '
 p=subprocess.run(['ssh',host,env+shlex.quote(py)+' -'],input=probe.encode(),capture_output=True);assert p.returncode==0,p.stderr.decode();(out/'GPU_READY.json').write_bytes(p.stdout)
 code='''from pathlib import Path
import sys,json,time,hashlib,fcntl,subprocess,os,socket
r=Path(ROOT);x=json.load(sys.stdin);sys.path.insert(0,str(r/'scripts'));import fixed_budget_helpers as g
d=r/'innovation_handoff/fixed_budget_20261023'
with (d/'activation.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);assert not (d/'TARGET_RECEIPT.json').exists();snap=g.snapshot(r);assert snap['worker']['state']=='exited' and snap['service']['state'] in ('exited','missing_record');assert not any(snap['locks'].values()) and not snap['port_listening'];assert snap['worker_status']['event']=='finished' and snap['worker_status']['cleanup_code']==0 and snap['worker_status']['queue_exit_code']==0
 policy=g.read(r/'shared_gpu_authorization.json');gpu=x['gpu'];procs=[]
 for line in subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True).splitlines():
  uuid,pid,mem=[y.strip() for y in line.split(',')]
  if uuid==gpu:
   p=Path('/proc')/pid;procs.append({'pid':int(pid),'uid':p.stat().st_uid,'start_ticks':(p/'stat').read_text().rsplit(')',1)[1].split()[19],'memory_mib':mem})
 rows=subprocess.check_output(['nvidia-smi','--query-gpu=uuid,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True);row=next(a.split(',') for a in rows.splitlines() if a.startswith(gpu));free=int(row[1]);assert row[2].strip().isdigit() and free>=x['minimum']
 for name,h in x['assets'].items():assert hashlib.sha256((r/name).read_bytes()).hexdigest()==h,name
 service=r/'scripts/manage_service.py';change=x['service'];assert hashlib.sha256(service.read_bytes()).hexdigest()==change['before_sha256'];staged=r/'scripts/fixed_budget_service.staged.py';assert hashlib.sha256(staged.read_bytes()).hexdigest()==change['after_sha256']
 jobs=x['manifest']['jobs'];ids={j['id'] for j in jobs};assert not ids&set(snap['states']);assert not ids&{j['id'] for j in snap['manifest']['jobs']};assert all(j['max_attempts']==1 for j in jobs)
 (d/'service_before.py').write_bytes(service.read_bytes());tmp=service.with_suffix('.fixed_budget.tmp');tmp.write_bytes(staged.read_bytes());os.replace(tmp,service)
 g.atomic(d/'planned_jobs.json',x['manifest']);g.atomic(d/'base_manifest.json',snap['manifest']);manifest=snap['manifest'];manifest['jobs'].append(jobs[0]);g.atomic(r/'jobs.json',manifest)
 rec={'status':'unique_owner','owner':x['owner'],'target_host':x['host'],'target_root':str(r),'port':x['port'],'job_ids':[j['id'] for j in jobs],'base_job_count':len(manifest['jobs'])-1,'first_only_until_audit':len(jobs)>1,'scientific_ready_sha256':'5b32848ead9252fee90b9dfbd484e9c339853016cba2e0c31f711d1c26d43e95','source_unchanged':True,'assets':x['assets'],'policy':policy,'gpu':gpu,'free_mib':free,'other_processes':procs,'previous_worker':snap['worker'],'previous_service':snap['service'],'time':time.time()};g.launch_owned_worker(r,d/'TARGET_RECEIPT.json',rec)
 with (d/'guard.log').open('ab') as log:p=subprocess.Popen(['python3','-u',str(r/'scripts/fixed_budget_guard.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 pth=Path('/proc')/str(p.pid);g.atomic(d/'GUARD.json',{'pid':p.pid,'uid':pth.stat().st_uid,'start_ticks':(pth/'stat').read_text().rsplit(')',1)[1].split()[19],'time':time.time()});sys.stdout.buffer.write((d/'TARGET_RECEIPT.json').read_bytes())
'''.replace('ROOT',repr(R))
 x={'assets':json.loads((out/'ASSETS.json').read_text()),'manifest':json.loads((out/'jobs.json').read_text()),'service':json.loads((out/'SERVICE_CHANGE.json').read_text()),'owner':owner,'host':host,'gpu':gpu,'minimum':minimum,'port':port}
 p=subprocess.run(['ssh',host,shlex.join(['python3','-c',code])],input=json.dumps(x),capture_output=True,text=True);assert p.returncode==0,p.stderr;(out/'TARGET_RECEIPT.json').write_text(p.stdout);r=json.loads(p.stdout);print(owner,r['worker'],flush=True)
for owner in sys.argv[1:]:activate(owner)
