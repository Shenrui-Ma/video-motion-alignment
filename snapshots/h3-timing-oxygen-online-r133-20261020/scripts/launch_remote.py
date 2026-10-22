"""Create one root-gated service. Root wrapper owns all lifecycle decisions."""
import json,os,subprocess,time
from pathlib import Path
import service,preflight
from r86_contract import registry,prepare_loader_inputs

def created_owner(supervisor_pid,supervisor_identity):
 p=service.RUN/f'processes/supervisor_{supervisor_pid}.json'
 if not p.exists():return None
 r=json.loads(p.read_text());owner=r.get('service_record')
 if r.get('pid')!=supervisor_pid or r.get('identity')!=supervisor_identity or owner is None:return None
 current=service.RUN/'processes/service.json'
 if not current.exists():return None
 c=json.loads(current.read_text())
 return owner if c.get('pid')==owner['pid'] and c.get('identity')==owner['identity'] else None

def launch():
 root=service.RUN;preflight.check(root,live=True)
 for name in ('custom_nodes','input','output','temp','user','logs','processes','audit','analysis'):(root/name).mkdir(exist_ok=True)
 for name in ('H3EventAudit','H3PairAudit','H3TemporalRouter','H3X0Readout','H3AutomaticWindowRouter'):
  target=root/'extensions'/name;link=root/'custom_nodes'/name
  if not link.exists():link.symlink_to(target,target_is_directory=True)
  if link.resolve()!=target.resolve():raise ValueError('custom node alias differs')
 kj=root/'custom_nodes/ComfyUI-KJNodes'
 if not kj.exists():kj.symlink_to(service.RUNTIME['kj_nodes'],target_is_directory=True)
 if kj.resolve()!=Path(service.RUNTIME['kj_nodes']).resolve():raise ValueError('KJ alias differs')
 for run in registry()[1]:prepare_loader_inputs(run)
 env=dict(os.environ,LC_ALL='C',LANG='C',PYTHONDONTWRITEBYTECODE='1')
 command=['python3','-u',str(root/'scripts/supervise_service.py')]
 with (root/'logs/supervisor.log').open('ab',buffering=0) as log:p=subprocess.Popen(command,cwd=root/'scripts',env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 ident=service.bind_child(p,command);owner=None
 try:
  deadline=time.monotonic()+660
  while time.monotonic()<deadline:
   if p.poll() is not None or service.current_identity(p.pid)!=ident:raise RuntimeError('supervisor exited before ready')
   owner=created_owner(p.pid,ident);ready=root/'processes/cuda_gate_ready.json'
   if owner is not None and ready.exists():
    gate=json.loads(ready.read_text());service.assert_owned(owner)
    if gate['pid']!=owner['pid'] or gate['identity']!=service.external_identity(owner['pid']):raise ValueError('root gate identity differs')
    return owner,gate
   time.sleep(.1)
  raise TimeoutError('service pre-CUDA readiness timeout')
 except BaseException as primary:
  try:
   if service.current_identity(p.pid)==ident:p.terminate()
   try:p.wait(timeout=10)
   except subprocess.TimeoutExpired:
    if service.current_identity(p.pid)==ident:p.kill()
    p.wait(timeout=10)
   owner=created_owner(p.pid,ident)
   if owner is not None:service.stop(expected_record=owner)
  except BaseException as error:
   if hasattr(primary,'add_note'):primary.add_note('launch cleanup: '+repr(error))
  raise
