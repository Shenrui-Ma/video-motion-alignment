"""Stdlib mocks only; never instantiate RealOperations or start any service."""
import copy,hashlib,importlib.util,json,subprocess,sys,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('launch_admin',R/'audit/root_admit_and_start_preCUDA.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
OLD_LOCAL=R.parent/'h3-timing-auto-source51310-r40-20261017/audit/root_actual_admission/service.json'
def actual_old():return json.loads(OLD_LOCAL.read_text())
def owner(pid=200):
 command=['python3',str(m.ROOT/'scripts/service_entry.py'),str(m.ROOT)]
 return {'pid':pid,'gpu_uuid':m.GPU,'port':m.PORT,'command':command,'identity':{'uid':1016,'start_ticks':'123','cmdline':' '.join(command)+' '}}
def release_fixture():
 o=actual_old();path=m.OLD/'analysis/postrun/captured'/m.OLD_RUN/'RUN_GATE.json';h='a'*64
 g={'passed':True,'run_id':m.OLD_RUN,'owner':o,'runtime':{'status':'pass'}}
 c={'pid':o['pid'],'service_record':o,'process_absent':True,'own_compute_absent':True,'child_compute_absent':True}
 r={'pid':o['pid'],'owner':o['identity'],'gate_file':str(path),'gate_sha256':h}
 return g,c,r,path,h
class Tests(unittest.TestCase):
 def test_real_historical_command_identity_matches(self):self.assertEqual(m.external_from_owner(actual_old()),{k:m.OLD_ID[k] for k in ('uid','start_ticks','cmdline_sha256')})
 def test_old_completed_gate_exact_cleanup(self):
  args=release_fixture();self.assertEqual(m.validate_release(*args,True)['pid'],16635)
 def test_old_partial_gate_and_each_cleanup_boolean_refused(self):
  for which,key,val in [(0,'passed',False),(0,'passed',1),(1,'process_absent',False),(1,'own_compute_absent',1),(1,'child_compute_absent',False)]:
   args=list(copy.deepcopy(release_fixture()));args[which][key]=val
   with self.assertRaises(ValueError):m.validate_release(*args,True)
 def test_stale_release_and_live_or_reused_pid_refused(self):
  for key,val in [('pid',12),('gate_sha256','b'*64),('gate_file','elsewhere')]:
   args=list(copy.deepcopy(release_fixture()));args[2][key]=val
   with self.assertRaises(ValueError):m.validate_release(*args,True)
  with self.assertRaises(ValueError):m.validate_release(*release_fixture(),False)
 def test_cleanup_wrong_generation_refused(self):
  args=list(copy.deepcopy(release_fixture()));args[1]['service_record']['identity']['start_ticks']='other'
  # deepcopy whole tuple preserves object aliases; separately change copied cleanup owner.
  args=list(release_fixture());args[1]=copy.deepcopy(args[1]);args[1]['service_record']['identity']['start_ticks']='other'
  with self.assertRaises(ValueError):m.validate_release(*args,True)
 def test_peer_live_identity_and_root_device(self):
  o=owner(400);o['gpu_uuid']=m.PEER_GPU;o['command']=['python3','/data5/researcher/h3_runs/peer_case'];e=m.external_from_owner(o)
  c={'pid':400,'root':'/data5/researcher/h3_runs/peer_case','identity':e}
  m.validate_peer(c,o,e,1016)
  for key,value in [('uid',1020),('start_ticks','bad'),('cmdline_sha256','b'*64)]:
   bad=dict(e);bad[key]=value
   with self.assertRaises(ValueError):m.validate_peer(c,o,bad,1016)
  bad=copy.deepcopy(o);bad['gpu_uuid']=m.GPU
  with self.assertRaises(ValueError):m.validate_peer(c,bad,e,1016)
 def test_peer_registration_only_changes_permitted(self):
  old={'scope':'own_user_video_jobs','root_live_review_required':False,'existing_comfy_port':None,'permitted_compute_processes':[{'pid':16635,'identity':{k:m.OLD_ID[k] for k in ('uid','start_ticks','cmdline_sha256')}},{'pid':12345,'identity':{'uid':1016,'start_ticks':'777','cmdline_sha256':'c'*64}}]}
  o=owner();new=m.next_peer_admission(old,o,m.external_from_owner(o))
  self.assertEqual([x['pid'] for x in new['permitted_compute_processes']],[12345,200]);self.assertEqual({k:v for k,v in old.items() if k!='permitted_compute_processes'},{k:v for k,v in new.items() if k!='permitted_compute_processes'})
  self.assertEqual(old['permitted_compute_processes'][0]['pid'],16635)
 def test_peer_registration_reused_old_or_duplicate_new_refused(self):
  o=owner();old={'scope':'own_user_video_jobs','ready_for_launch':True,'permitted_compute_processes':[{'pid':16635,'identity':{'uid':1016,'start_ticks':'reused','cmdline_sha256':'b'*64}}]}
  with self.assertRaises(ValueError):m.next_peer_admission(old,o,m.external_from_owner(o))
  old['permitted_compute_processes']=[{'pid':200,'identity':m.external_from_owner(o)}]
  with self.assertRaises(ValueError):m.next_peer_admission(old,o,m.external_from_owner(o))
 def test_preCUDA_gate_checks_target_and_identity(self):
  o=owner();e=m.external_from_owner(o);g={'schema':'r43-before-CUDA-root-gate-v1','pid':200,'identity':e,'target':str(m.ROOT/'scripts/compatibility_bootstrap.py'),'target_sha256':'a'*64}
  m.validate_gate(g,o,e,'a'*64)
  for key,value in [('pid',201),('target_sha256','b'*64),('target','/tmp/other.py')]:
   bad=dict(g);bad[key]=value
   with self.assertRaises(ValueError):m.validate_gate(bad,o,e,'a'*64)
 def test_service_register_go_http_controller_order(self):
  ops=FakeOps();m.launch_sequence(ops);self.assertEqual(ops.calls,['precheck','service_only','ready','register_peer','recheck','go','http','controller'])
 def test_explicit_null_peer_same_gates_without_registration(self):
  ops=FakeOps(has_peer=False);m.launch_sequence(ops);self.assertEqual(ops.calls,['precheck','service_only','ready','recheck','go','http','controller'])
 def test_null_peer_config_requires_bound_release(self):
  c={'schema':'r43-root-launch-config-v1','root_approved':True,'old_run_gate_sha256':'a'*64,'old_cleanup_sha256':'b'*64,'old_release_sha256':'c'*64,'peer':None}
  self.assertIsNone(m.check_config(c)['peer'])
  c['old_cleanup_sha256']=None
  with self.assertRaises(ValueError):m.check_config(c)
 def test_null_peer_rejects_unknown_own_gpu_pid(self):
  self.assertTrue(m.validate_peerless_processes([],lambda pid:1016,1016))
  self.assertTrue(m.validate_peerless_processes([{'pid':20,'gpu_uuid':m.PEER_GPU}],lambda pid:1015,1016))
  for gpu in (m.GPU,m.PEER_GPU,'third-card'):
   with self.assertRaisesRegex(ValueError,'zero existing own'):m.validate_peerless_processes([{'pid':999,'gpu_uuid':gpu}],lambda pid:1016,1016)
 def test_startup_log_binds_this_child(self):
  row={'service_only':True,'controller_started':False,'service':owner(),'gate_ready':{'pid':200}}
  text=json.dumps({'supervisor_pid':99})+'\n'+json.dumps(row)
  self.assertEqual(m.owner_from_startup_log(text),owner())
  for bad in ('',text+'\n'+json.dumps(row),json.dumps(dict(row,gate_ready={'pid':201}))):
   with self.assertRaises(ValueError):m.owner_from_startup_log(bad)
 def test_bad_release_or_peer_cannot_launch(self):
  for failure in ('precheck','register_peer','recheck','http'):
   ops=FakeOps(failure)
   with self.assertRaises(ValueError):m.launch_sequence(ops)
   if failure=='precheck':self.assertNotIn('service_only',ops.calls)
   if failure in ('precheck','register_peer','recheck'):self.assertNotIn('go',ops.calls)
   self.assertNotIn('controller',ops.calls)
 def test_unapproved_template_refused(self):
  c=json.loads((R/'audit/root_admit_and_start_preCUDA.CONFIG.template.json').read_text())
  with self.assertRaises(ValueError):m.check_config(c)
 def test_plan_is_inert_stdlib_subprocess(self):
  p=subprocess.run([sys.executable,str(R/'audit/root_admit_and_start_preCUDA.py'),'--plan'],text=True,capture_output=True,timeout=10)
  self.assertEqual(p.returncode,0,p.stderr);v=json.loads(p.stdout);self.assertTrue(v['prepared_only']);self.assertEqual(v['port'],8505)
 def test_producer_seal_remains_exact(self):
  p=R/'deploy_manifest.json';self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),m.MANIFEST_SHA)
  for rel,item in json.loads(p.read_text())['files'].items():self.assertEqual(hashlib.sha256((R/rel).read_bytes()).hexdigest(),item['sha256'],rel)
class FakeOps:
 def __init__(self,fail=None,has_peer=True):self.calls=[];self.fail=fail;self.has_peer=has_peer
 def step(self,n):
  self.calls.append(n)
  if self.fail==n:raise ValueError('simulated refusal')
 def precheck(self):self.step('precheck')
 def launch_service_only(self):self.step('service_only')
 def ready_owner(self):self.step('ready');return owner(),{'gate':'synthetic'}
 def register_peer(self,o):self.step('register_peer')
 def recheck_before_go(self,o,g):self.step('recheck')
 def go(self,g):self.step('go')
 def wait_http(self,o):self.step('http')
 def start_controller(self,o):self.step('controller')
if __name__=='__main__':unittest.main()
