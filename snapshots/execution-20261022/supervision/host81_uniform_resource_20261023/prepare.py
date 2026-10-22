from pathlib import Path
import subprocess,shlex,json,hashlib,io,tarfile,time
D=Path(__file__).parent;OLD='/data/research-user/h3_inference_20261023/run';R='/data/research-user/h3_inference_20261023/run_uniform_energy';UUID='GPU-REPLACE-WITH-DEVICE-UUID'
def read(p):return subprocess.check_output(['ssh','H3_HOST_RTX4090',shlex.join(['python3','-c','from pathlib import Path;import sys;sys.stdout.buffer.write(Path('+repr(p)+').read_bytes())'])])
probe=read('/data/research-user/h3_inference_20261023/uniform_resource_probe.json');(D/'GPU_PROBE.json').write_bytes(probe);p=json.loads(probe);assert p['status']=='tiny_gpu_probe_passed';assert all(next(row for row in s['processes'] if row['pid']==62100)['memory_mib']==1706 for s in p['snapshots'])
files={}
for name in ['manage_service.py','host_worker.py','compatibility_bootstrap.py','allocator_memory_budget.py','int8_row_chunking.py','memory_peak.py','backend_dispatch_audit.py']:
 raw=read(OLD+'/scripts/'+name);text=raw.decode()
 if name=='manage_service.py':
  text=text.replace('PORT=8676','PORT=8679');start=text.index(" rows=subprocess.check_output(['nvidia-smi','--query-compute-apps");end=text.index(' # The user',start)
  text=text[:start]+" policy=json.loads((ROOT/'shared_gpu_authorization.json').read_text())\n assert policy['allow_shared'] is True and policy['gpu_uuid']==GPU\n memory_rows=subprocess.check_output(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True,timeout=20)\n free=next(float(row.split(',')[1]) for row in memory_rows.splitlines() if row.split(',')[0].strip()==GPU)\n from budget_admission import admit_before_context\n if not admit_before_context(free,policy['minimum_free_mib']):raise RuntimeError('Shared GPU below validated admission budget')\n"+text[end:]
 if name=='host_worker.py':text=text.replace('port=8676','port=8679')
 compile(text,name,'exec');files['scripts/'+name]=text.encode()
files['queue/durable_comfy_queue.py']=read(OLD+'/queue/durable_comfy_queue.py');files['scripts/budget_admission.py']=(D/'budget_admission.py').read_bytes()
bootstrap='''"""Task-only allocator cap; shared GPU external headroom retained."""
import json,runpy,sys,subprocess,os
from pathlib import Path
import torch
from budget_admission import admit_after_context
root=Path(__file__).resolve().parents[1];policy=json.loads((root/'shared_gpu_authorization.json').read_text());cap=int(policy['torch_allocator_cap_gib']*1024**3)
free,total=torch.cuda.mem_get_info(0);reserved=torch.cuda.memory_reserved(0)
assert admit_after_context(free,reserved,cap,policy['post_context_external_headroom_mib']),'Physical headroom changed after CUDA initialization'
torch.cuda.set_per_process_memory_fraction(cap/total,0)
print(json.dumps({'torch_allocator_cap_bytes':cap,'free_at_start':free,'total_bytes':total,'comfy_reserve_inside_cap_gib':6,'post_context_external_headroom_mib':policy['post_context_external_headroom_mib'],'mode':'shared_cpu_weight_offload'}),flush=True)
from allocator_memory_budget import install
install(torch,cap)
from memory_peak import install as install_peak
install_peak(torch,root,cap)
sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')
''';compile(bootstrap,'budget_bootstrap.py','exec');files['scripts/budget_bootstrap.py']=bootstrap.encode()
policy={'allow_shared':True,'gpu_uuid':UUID,'minimum_free_mib':22500,'torch_allocator_cap_gib':19.5,'reserve_vram_gib':6,'comfy_reserve_inside_allocator_cap':True,'post_context_external_headroom_mib':1536,'maximum_own_video_processes':1,'maximum_attempts':1,'deployment_status':'prepared_no_jobs_wait_scientific_ready','reason':'Measured .81 nonallocator context468MiB; source107frame maxreserved19.06055GiB; first real run capacity verification required'}
files['shared_gpu_authorization.json']=json.dumps(policy,indent=2).encode();files['gpu.json']=json.dumps({'index':5,'gpu_uuid':UUID}).encode()
code="from pathlib import Path;r=Path("+repr(R)+");r.mkdir(exist_ok=True);assert not (r/'jobs.json').exists();[(r/n).mkdir(exist_ok=True) for n in ['scripts','queue','logs','custom_nodes','graphs','queue_state','output','temp','user','input','innovation_handoff']]"
subprocess.run(['ssh','H3_HOST_RTX4090',shlex.join(['python3','-c',code])],check=True)
buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w') as t:
 for n,v in files.items():i=tarfile.TarInfo(n);i.size=len(v);i.mtime=int(time.time());t.addfile(i,io.BytesIO(v))
subprocess.run(['ssh','H3_HOST_RTX4090','tar -xf - -C '+R],input=buf.getvalue(),check=True)
code='''from pathlib import Path
import sys,json,hashlib,socket
r=Path(ROOT);old=Path(OLD);assets=json.load(sys.stdin)
for n,h in assets.items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h,n
for p in (old/'custom_nodes').iterdir():
 dest=r/'custom_nodes'/p.name
 if p.is_dir() and not dest.exists():dest.symlink_to(p.resolve())
for name in ['innovation_cache','input']:
 if name=='input':
  for p in (old/name).iterdir():
   dest=r/name/p.name
   if p.is_file() and not dest.exists():dest.symlink_to(p.resolve())
 else:
  dest=r/name
  if not dest.exists():dest.symlink_to((old/name).resolve())
assert not (r/'jobs.json').exists() and not (r/'worker_pid.json').exists()
with socket.socket() as s:assert s.connect_ex(('127.0.0.1',8679))!=0
print(json.dumps({'status':'prepared_no_jobs','root':str(r),'files':len(assets),'no_worker':True,'port_available':8679}))
'''.replace('ROOT',repr(R)).replace('OLD',repr(OLD))
a={n:hashlib.sha256(v).hexdigest() for n,v in files.items()};x=subprocess.check_output(['ssh','H3_HOST_RTX4090',shlex.join(['python3','-c',code])],input=json.dumps(a).encode());(D/'PREPARED.json').write_bytes(x);(D/'ASSETS.json').write_text(json.dumps(a,indent=2));(D/'policy.json').write_text(json.dumps(policy,indent=2));print(x.decode())
