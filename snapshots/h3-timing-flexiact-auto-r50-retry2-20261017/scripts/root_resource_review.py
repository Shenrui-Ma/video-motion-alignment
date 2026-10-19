"""CPU/NVML-only root admission; no service, torch, decoder or inference launch."""
import argparse,json,os,socket,subprocess,time
from pathlib import Path
import service
from observer_import import t
from recovery_contract import sha,read,require

def inspect():
 main=service.main_memory_profile();decoder=t.decoder_memory_profile();processes=service.compute_processes();owned=[];public=[]
 for row in processes:
  uid=service.proc_uid(row['pid']);require(uid is not None,'compute ownership temporarily unavailable')
  public.append(dict(row,uid=uid))
  if uid==os.getuid():
   identity=service.external_identity(row['pid']);require(identity is not None,'own compute identity unavailable');owned.append({'pid':row['pid'],'identity':identity,'gpu_uuid':row['gpu_uuid']})
 planned={service.GPU,t.DECODER_UUID};require(len(planned|{r['gpu_uuid'] for r in owned})<=2,'more than two owned GPU cards would be used')
 # Explicit root review is required for existing own jobs, so this convenience
 # command admits only the empty-own-job case used by this recovery.
 require(not owned,'existing own compute must be explicitly reviewed by root')
 devices={}
 for uuid,required in [(service.GPU,main['required_free_bytes']),(t.DECODER_UUID,decoder['required_free_bytes'])]:
  q=subprocess.run(['nvidia-smi','--id='+uuid,'--query-gpu=uuid,memory.free,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10,check=True)
  rows=[r.split(',') for r in q.stdout.splitlines() if r.strip()];require(len(rows)==1 and len(rows[0])==3 and rows[0][0].strip()==uuid and not q.stderr.strip(),'GPU query invalid')
  free,temp=map(float,rows[0][1:]);require(free>=0 and 0<=temp<85,'GPU health invalid')
  devices[uuid]={'free_bytes':int(free*1024**2),'required_bytes':required,'temperature_c':temp,'ready':free*1024**2>=required}
 with socket.socket() as sock:sock.bind(('127.0.0.1',service.PORT))
 mem=dict(x.split(':',1) for x in Path('/proc/meminfo').read_text().splitlines());ram=int(mem['MemAvailable'].split()[0])*1024
 return {'schema':'r50-retry2-current-resource-review-v1','observed_unix':time.time(),'devices':devices,'processes':public,'owned_processes':owned,'port':service.PORT,'host_available_bytes':ram,'main_required_free_bytes':main['required_free_bytes'],'ready':all(v['ready'] for v in devices.values()) and ram>=20*1024**3}

def main():
 p=argparse.ArgumentParser();p.add_argument('--approve',action='store_true');a=p.parse_args()
 from preflight import check
 check(metadata_only=True)
 v=inspect();out=service.RUN/'audit/recovery'/('resource_'+str(time.time_ns())+'.json');service.write_json(out,v)
 print(json.dumps(v),flush=True)
 if a.approve:
  require(v['ready'],'actual current resource gate not ready')
  receipt=dict(v,root_approved=True,producer_manifest_sha256=sha(service.RUN/'deploy_manifest.json'),protocol_sha256=sha(service.RUN/'configs/protocol.json'),scope='four_new_cases_external_chest_fixed5')
  target=service.RUN/'audit/ROOT_RECOVERY_APPROVAL.json';require(not target.exists(),'root approval already exists')
  service.write_json(target,receipt)
  admission=read(service.RUN/'configs/admission.json');admission.update(permitted_compute_processes=[],root_live_review_required=False);service.write_json(service.RUN/'configs/admission.json',admission)
if __name__=='__main__':main()
