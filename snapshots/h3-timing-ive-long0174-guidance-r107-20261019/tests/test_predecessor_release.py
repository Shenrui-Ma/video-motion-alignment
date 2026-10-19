import importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('r107_release_runner',ROOT/'audit/root_run_control.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class ReleasedNative(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);base=Path(self.tmp.name);self.root=base/'new';self.old=base/'old';self.owner={'pid':123,'gpu_uuid':r.service.GPU,'port':1,'identity':{'uid':os.getuid(),'start_ticks':'22','cmdline':'python '+str(self.old/'scripts/service_entry.py')}}
  self.put(self.old/'processes/service.json',self.owner);self.put(self.old/'configs/runtime.json',{'port':1,'remote_root':str(self.old)});self.put(self.old/'deploy_manifest.json',{'files':{}})
  self.put(self.old/'logs/native_history.json',{'status':{'completed':True,'status_str':'success'}});self.put(self.old/'logs/native_job.json',{'service_pid':123,'service_identity':self.owner['identity']})
  self.put(self.old/'processes/cleanup.json',{'pid':123,'process_absent':True,'own_compute_absent':True})
  self.exitpath=self.old/'audit/attempt/ROOT_EXIT_RECEIPT.json';self.put(self.exitpath,{'passed':True,'owner':self.owner,'process_absent':True,'CUDA_allocation_absent':True})
  self.pendingpath=self.old/'audit/attempt/RELEASED_PENDING_REVIEW.json';self.put(self.pendingpath,{'pending':True})
  self.policy={'root':str(self.old),'owner':self.owner,'producer_seal_sha256':r.sha(self.old/'deploy_manifest.json'),'attempt':'attempt','last_run':'native','exit_sha256':r.sha(self.exitpath),'pending_receipt_sha256':r.sha(self.pendingpath)};self.put(self.root/'configs/predecessor.json',self.policy)
 def put(self,p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
 def check(self,identity=None,rows=None):
  with patch.object(r,'ROOT',self.root),patch.object(r.service,'current_identity',return_value=identity),patch.object(r.service,'compute_processes',return_value=rows or []):return r.verify_predecessor()
 def test_exact_release_with_native_pending_guidance(self):self.assertEqual(self.check()['last_successful_native'],'native')
 def test_live_parent_rejected(self):
  with self.assertRaises(ValueError):self.check(identity=self.owner['identity'])
 def test_parent_cuda_rejected(self):
  with self.assertRaises(ValueError):self.check(rows=[{'pid':123}])
 def test_other_user_cuda_allowed(self):self.assertEqual(self.check(rows=[{'pid':555}])['owner'],self.owner)
 def test_reused_pid_record_rejected(self):
  changed=dict(self.owner,pid=124);self.put(self.old/'processes/service.json',changed)
  with self.assertRaises(ValueError):self.check()
 def test_changed_native_history_rejected(self):
  self.put(self.old/'logs/native_history.json',{'status':{'completed':False,'status_str':'error'}})
  with self.assertRaises(ValueError):self.check()
 def test_changed_pending_receipt_rejected(self):
  self.put(self.pendingpath,{'pending':False})
  with self.assertRaises(ValueError):self.check()
 def test_changed_exit_receipt_rejected(self):
  self.put(self.exitpath,{'passed':False})
  with self.assertRaises(ValueError):self.check()
 def test_incomplete_cleanup_rejected(self):
  self.put(self.old/'processes/cleanup.json',{'pid':123,'process_absent':False,'own_compute_absent':True})
  with self.assertRaises(ValueError):self.check()
if __name__=='__main__':unittest.main()
