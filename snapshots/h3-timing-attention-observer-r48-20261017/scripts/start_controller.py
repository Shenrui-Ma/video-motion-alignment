"""Root starts queue after exact service identity has been registered by its peer."""
import argparse,json,subprocess,os,fcntl
from contextlib import contextmanager
from pathlib import Path
import service,job
from preflight import check
import urllib.request

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
  with urllib.request.urlopen(f'http://127.0.0.1:{service.PORT}/object_info/H3AttentionStateProbe',timeout=10) as response:
   if 'H3AttentionStateProbe' not in json.load(response):raise ValueError('service not ready')
  gate=json.loads((root/'processes/cuda_gate_ready.json').read_text());go=json.loads((root/'processes/cuda_gate_go.json').read_text())
  if gate!=go or gate['pid']!=owner['pid'] or gate['identity']!=service.external_identity(owner['pid']):raise ValueError('CUDA gate owner differs')
  job.require_generation(job.active_service(),owner)
  env=dict(os.environ,LC_ALL='C',LANG='C',PYTHONDONTWRITEBYTECODE='1')
  with (root/'logs/controller.log').open('ab',buffering=0) as log:
   child=subprocess.Popen(['python3','-u',str(root/'scripts/run_queue.py'),'--expected-pid',str(owner['pid']),'--expected-start-ticks',str(owner['identity']['start_ticks'])],cwd=root/'scripts',stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=env)
  record={'pid':child.pid,'identity':service.identity(child.pid),'role':'controller','service_pid':owner['pid'],'service_identity':owner['identity']}
  service.write_json(registry,record);print(json.dumps(record),flush=True)
if __name__=='__main__':main()
