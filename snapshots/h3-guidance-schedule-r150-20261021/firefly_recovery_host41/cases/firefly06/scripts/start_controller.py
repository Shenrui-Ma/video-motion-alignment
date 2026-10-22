"""Root starts queue after exact service identity has been registered by its peer."""
import argparse,json,subprocess,os,fcntl
from contextlib import contextmanager
from pathlib import Path
import service,job
from preflight import check
import urllib.request
from r132_contract import registry, read

def check_http_schema(root, port):
 required={node["class_type"] for name in registry(root)[1] for node in read(Path(root)/"configs/graphs"/(name+".json")).values()}
 with urllib.request.urlopen(f"http://127.0.0.1:{port}/object_info",timeout=10) as response:
  info=json.load(response)
 missing=required-set(info)
 if missing:raise ValueError("actual HTTP node types missing: "+repr(sorted(missing)))
 return {"passed":True,"required":sorted(required)}

def admit(expected_pid,expected_start_ticks,owner,controller=None):
 if owner['pid']!=expected_pid or str(owner['identity']['start_ticks'])!=str(expected_start_ticks):raise ValueError('stale controller-start service generation')
 if controller is not None:raise ValueError('controller registry already exists; do not duplicate')

@contextmanager
def controller_start_lock(root):
 with (Path(root)/'processes/controller_start.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  yield

def main():
 p=argparse.ArgumentParser();p.add_argument('--pid',required=True,type=int);p.add_argument('--start-ticks',required=True);a=p.parse_args()
 root=service.RUN
 with controller_start_lock(root):
  owner=json.loads((root/'processes/service.json').read_text());registry=root/'processes/controller.json'
  admit(a.pid,a.start_ticks,owner,json.loads(registry.read_text()) if registry.exists() else None)
  service.assert_owned(owner);check(root,live=True)
  check_http_schema(root,service.PORT)
  gate=json.loads((root/'processes/cuda_gate_ready.json').read_text());go=json.loads((root/'processes/cuda_gate_go.json').read_text())
  if gate!=go or gate['pid']!=owner['pid'] or gate['identity']!=service.external_identity(owner['pid']):raise ValueError('CUDA gate owner differs')
  job.require_generation(job.active_service(),owner)
  env=dict(os.environ,LC_ALL='C',LANG='C',PYTHONDONTWRITEBYTECODE='1')
  with (root/'logs/controller.log').open('ab',buffering=0) as log:
   command=['python3','-u',str(root/'scripts/run_queue.py'),'--expected-pid',str(owner['pid']),'--expected-start-ticks',str(owner['identity']['start_ticks'])]
   child=subprocess.Popen(command,cwd=root/'scripts',stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=env)
  record={'pid':child.pid,'identity':service.bind_child(child,command),'role':'controller','service_pid':owner['pid'],'service_identity':owner['identity']}
  service.write_json(registry,record);print(json.dumps(record),flush=True)
if __name__=='__main__':main()
