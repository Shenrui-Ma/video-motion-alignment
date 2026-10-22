"""Append validated pilot assets only after the running H3 batch exits naturally."""
import argparse,fcntl,hashlib,importlib.util,json,os,time,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load_helpers(root):
 p=root/'scripts/anchor_runtime_helpers.py';s=importlib.util.spec_from_file_location('h3_previous_guard',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def validate_request(req,base):
 assert req['status']=='ready' and req['cpu_tests']['passed'] is True
 assert req['base']==base,'Frozen base manifest differs'
 new=req['pilots']['jobs'];ids=[j['id'] for j in base['jobs']+new]
 assert new and len(ids)==len(set(ids)),'Duplicate pilot identity'
 assert all(j.get('max_attempts')==1 for j in new)
 assert all(j.get('graph') and j.get('metadata') for j in new)
 assert req['assets'] and req['service_change']
 return {**base,'jobs':base['jobs']+new,'planned_count':len(ids)}

def assert_current(req,actual,target,g):
 assert g.digest(actual) in (g.digest(req['base']),g.digest(target)),'External manifest edit'

def prepare_file_changes(req):
 """Validate every staged file before replacing any live file at the idle boundary."""
 changes=[req['service_change']]+req.get('additional_file_changes',[])
 paths=[str(Path(c['path']).resolve()) for c in changes]
 assert len(paths)==len(set(paths)),'Duplicate replacement target'
 prepared=[]
 for change in changes:
  path=Path(change['path']);before=sha(path)
  assert before in (change['before_sha256'],change['after_sha256']),str(path)+' live hash differs'
  staged=Path(change['staged_path']);raw=staged.read_bytes()
  assert hashlib.sha256(raw).hexdigest()==change['after_sha256'],str(staged)+' staged hash differs'
  compile(raw,str(path),'exec')
  prepared.append((path,raw,before!=change['after_sha256']))
 return prepared

def apply_file_changes(prepared):
 for path,raw,replace in prepared:
  if replace:
   temp=path.with_name(path.name+'.overnight.tmp');temp.write_bytes(raw)
   temp.chmod(path.stat().st_mode&0o777);os.replace(temp,path)

def idle_snapshot(snap):
 return (snap['worker']['state'] in ('exited','missing_record') and snap['service']['state'] in ('exited','missing_record') and not any(snap['locks'].values()) and not snap['port_listening'])

def run(root,request):
 g=load_helpers(root);d=root/'innovation_handoff/anchor_priority_20261023';d.mkdir(exist_ok=True)
 with (d/'guard.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  g.atomic(d/'pid.json',{'pid':os.getpid(),'uid':os.getuid(),'start_ticks':Path('/proc',str(os.getpid()),'stat').read_text().rsplit(')',1)[1].split()[19]})
  while True:
   g.reap_finished_children()
   req=g.read(request)
   if not req or req.get('status')!='ready':
    g.atomic(d/'status.json',{'status':'waiting_validated_package','unix':time.time()});time.sleep(30);continue
   target=validate_request(req,req['base']);snap=g.snapshot(root);snap['ready_for_deployment']=idle_snapshot(snap);assert_current(req,snap['manifest'],target,g)
   receipt=g.read(d/'activation.json',{})
   if receipt:assert receipt.get('target_hash')==g.digest(target),'Activation package changed'
   if receipt.get('phase') in ('armed','activated'):
    own=g.identity(receipt.get('worker'),str(root/'scripts/host_worker.py'))
    states={j['id']:snap['states'].get(j['id'],{}).get('status','not_started') for j in req['pilots']['jobs']}
    g.atomic(d/'status.json',{'status':'activated','worker':own,'pilot_states':states,'unix':time.time()})
    if own['state']=='owned_alive' or any(s!='not_started' for s in states.values()):return
    assert own['state']=='exited','Unverifiable pilot worker'
   missing=[j['id'] for j in req['base']['jobs'] if snap['states'].get(j['id'],{}).get('status')!='completed']
   if missing or not snap['ready_for_deployment']:
    g.atomic(d/'status.json',{'status':'waiting_previous_batch','pending':missing,'worker':snap['worker'],'service':snap['service'],'unix':time.time()});time.sleep(30);continue
   with (root/'innovation_handoff/activation.lock').open('a') as gate:
    fcntl.flock(gate,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fresh=g.snapshot(root);fresh['ready_for_deployment']=idle_snapshot(fresh);assert_current(req,fresh['manifest'],target,g)
    if not fresh['ready_for_deployment']:continue
    g.verify_assets(req['assets'])
    # Successful prior videos/audits must exist; fixed base includes all earlier jobs.
    previous=[{'id':j['id'],'status':fresh['states'][j['id']]['status']} for j in req['base']['jobs']]
    prepared=prepare_file_changes(req)
    apply_file_changes(prepared)
    g.atomic(d/'previous_verified.json',{'rows':previous,'unix':time.time()})
    g.atomic(root/'jobs.json',target)
    receipt={'phase':'prepared','base_hash':g.digest(req['base']),'target_hash':g.digest(target),'request_sha256':sha(request),'unix':time.time()};g.atomic(d/'activation.json',receipt)
    # launch_owned_worker writes PID before releasing its pipe-gated child.
    g.launch_owned_worker(root,d/'activation.json',receipt)
    g.atomic(d/'status.json',{'status':'activated','worker':receipt['worker'],'unix':time.time()})
    return

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--request',required=True);a=p.parse_args()
 try:run(Path(a.root),Path(a.request))
 except Exception as e:
  d=Path(a.root)/'innovation_handoff/anchor_priority_20261023';d.mkdir(exist_ok=True);(d/'error.json').write_text(json.dumps({'status':'failed','error':repr(e),'unix':time.time()}));raise
