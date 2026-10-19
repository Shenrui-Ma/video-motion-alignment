"""Launch a frozen producer, binding exact live peer identities before CUDA."""
import argparse,importlib,json,os,shutil,subprocess,sys,time
from pathlib import Path

def read(p):return json.loads(p.read_text())
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--attempt',required=True);p.add_argument('--peer',action='append',default=[]);p.add_argument('--resume',action='store_true');a=p.parse_args()
 root=a.root;sys.path.insert(0,str(root/'scripts'));import service
 assert service.RUN==root
 audit=root/'audit'/a.attempt;audit.mkdir(exist_ok=False)
 peers=[]
 for folder in a.peer:
  path=Path(folder);owner=read(path/'processes/service.json')
  assert service.current_identity(owner['pid'])==owner['identity']
  peers.append((path,owner,service.external_identity(owner['pid'])))
 owned=[r for r in service.compute_processes() if service.proc_uid(r['pid'])==os.getuid()]
 assert all(r['pid'] in [o['pid'] for _,o,_ in peers] for r in owned),owned
 before={}
 for name in ['service.json','controller.json','supervisor.json','watchdog.json','cuda_gate_ready.json','cuda_gate_go.json']:
  q=root/'processes'/name
  if q.exists():
   d=read(q)
   if 'pid' in d:assert service.current_identity(d['pid']) is None,(name,d['pid'])
   before[name]=d;shutil.copy2(q,audit/('prior_'+name))
 if before:
  assert a.resume,'existing registry requires explicit recovery'
  for name in ['controller.json','cuda_gate_ready.json','cuda_gate_go.json']:
   q=root/'processes'/name
   if q.exists():q.unlink() # originals preserved above, all exact owners absent
 admission=read(root/'configs/admission.json');admission.update(ready_for_launch=True,scope='own_user_video_jobs',existing_comfy_port=None,permitted_compute_processes=[{'pid':o['pid'],'identity':i} for _,o,i in peers]);service.write_json(root/'configs/admission.json',admission)
 env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
 if not (root/'audit/ROOT_FIRST_PAIR_APPROVAL.json').exists():
  subprocess.run([service.PYTHON,'scripts/execution_gate.py','approve-first-pair','--root-admitted','--free-mib','40960'],cwd=root,env=env,check=True)
 with (audit/'launch.log').open('x') as log:
  subprocess.run([service.PYTHON,'-u','scripts/launch_remote.py','--service-only'],cwd=root,env=env,stdout=log,stderr=log,check=True,timeout=720)
 owner=read(root/'processes/service.json');ready=read(root/'processes/cuda_gate_ready.json');service.assert_owned(owner)
 assert ready['pid']==owner['pid'] and ready['identity']==service.external_identity(owner['pid'])
 assert ready['supervisor']['identity']==service.external_identity(ready['supervisor']['pid'])
 for path,peer,identity in peers:
  assert service.current_identity(peer['pid'])==peer['identity']
  adm=read(path/'configs/admission.json');adm['permitted_compute_processes']=[r for r in adm['permitted_compute_processes'] if Path('/proc',str(r['pid'])).exists()]
  assert all(r['pid']!=owner['pid'] for r in adm['permitted_compute_processes'])
  adm['permitted_compute_processes'].append({'pid':owner['pid'],'identity':ready['identity']});service.write_json(path/'configs/admission.json',adm)
 service.write_json(root/'processes/cuda_gate_go.json',ready)
 deadline=time.monotonic()+180
 while True:
  service.assert_owned(owner)
  try:queue=service.queue_at(service.PORT);break
  except OSError:
   assert time.monotonic()<deadline;time.sleep(1)
 assert not queue['queue_running'] and not queue['queue_pending']
 if a.resume:
  command=[service.PYTHON,'-u',str(Path(__file__).with_name('continue_queue.py')),'--root',str(root),'--pid',str(owner['pid']),'--start-ticks',owner['identity']['start_ticks']]
  with (audit/'continuation.log').open('x') as log:
   child=subprocess.Popen(command,cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
  record={'pid':child.pid,'identity':service.bind_child(child,command),'role':'controller','service_pid':owner['pid'],'service_identity':owner['identity']}
  service.write_json(root/'processes/controller.json',record)
 else:subprocess.run([service.PYTHON,'scripts/start_controller.py','--pid',str(owner['pid']),'--start-ticks',owner['identity']['start_ticks']],cwd=root,env=env,check=True)
 service.write_json(audit/'STARTED.json',{'owner':owner,'controller':read(root/'processes/controller.json'),'peers':[o for _,o,_ in peers],'unix':time.time(),'resume':a.resume})
 print(json.dumps({'started':str(root),'pid':owner['pid'],'start_ticks':owner['identity']['start_ticks'],'port':service.PORT}),flush=True)
if __name__=='__main__':main()
