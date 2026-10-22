from pathlib import Path
import subprocess,json,time,os,sys
UUID='GPU-REPLACE-WITH-DEVICE-UUID';R=Path('/data/research-user/h3_inference_20261023/run')
def snapshot():
 gpu=subprocess.check_output(['nvidia-smi','-i',UUID,'--query-gpu=uuid,memory.total,memory.free,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip().split(',');procs=[]
 for line in subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True).splitlines():
  uuid,pid,mem=[x.strip() for x in line.split(',')]
  if uuid!=UUID:continue
  p=Path('/proc')/pid;procs.append({'pid':int(pid),'memory_mib':int(mem),'uid':p.stat().st_uid,'start_ticks':(p/'stat').read_text().rsplit(')',1)[1].split()[19]})
 return {'time':time.time(),'gpu':[x.strip() for x in gpu],'processes':procs}
before=snapshot();assert int(before['gpu'][2])>=22500
import torch
cap=int(19.5*1024**3);total=torch.cuda.get_device_properties(0).total_memory;torch.cuda.set_per_process_memory_fraction(cap/total,0)
sys.path.insert(0,str(R/'custom_nodes'));from H3CausalLayerBudget.frozen import load_frozen
core=load_frozen().core
results=[]
for dtype in [torch.float16,torch.bfloat16]:
 q=torch.randn(1,2,16,32,device='cuda',dtype=dtype);o,lse=core.flash_attention_lse(q,q,q);m=torch.randn(128,128,device='cuda',dtype=dtype);v=m@m;torch.cuda.synchronize();assert torch.isfinite(o).all() and torch.isfinite(lse).all() and torch.isfinite(v).all();results.append(str(dtype))
checks=[]
for _ in range(4):checks.append(snapshot());time.sleep(10)
record={'status':'tiny_gpu_probe_passed','pid':os.getpid(),'before':before,'snapshots':checks,'dtypes':results,'cap_bytes':cap,'max_allocated_bytes':torch.cuda.max_memory_allocated(),'max_reserved_bytes':torch.cuda.max_memory_reserved(),'reserved_bytes':torch.cuda.memory_reserved(),'torch_version':torch.__version__,'time':time.time(),'no_video_submitted':True}
p=R.parent/'uniform_resource_probe.json';p.write_text(json.dumps(record,indent=2));print(json.dumps(record))
