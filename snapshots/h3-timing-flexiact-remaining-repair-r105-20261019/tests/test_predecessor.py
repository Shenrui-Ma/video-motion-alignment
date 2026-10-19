import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import predecessor as p
from r105_contract import sha
class ActualPredecessorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.r=Path(self.tmp.name);self.old=self.r/'old'
  self.owner={'pid':99,'identity':{'uid':1016,'start_ticks':'11','cmdline':str(self.old/'scripts/service_entry.py')},'port':8565,'gpu_uuid':'GPU3'}
  self.put(self.old/'deploy_manifest.json',{'files':{}});self.put(self.old/'configs/runtime.json',{'uid':1016,'remote_root':str(self.old),'port':8565,'gpu_uuid':'GPU3'})
  self.put(self.old/'processes/service.json',self.owner);self.put(self.old/'audit/actual/STARTED.json',{'owner':self.owner})
  self.exit={'passed':True,'owner':self.owner,'process_absent':True,'CUDA_allocation_absent':True};self.put(self.old/'audit/actual/ROOT_EXIT_RECEIPT.json',self.exit)
  self.complete={'passed':True,'all_sources_reviewed':True,'GPU_released':True,'remaining_sources':[],'terminal_sources':[{'source_id':'a'}]};self.put(self.old/'audit/actual/COMPLETE.json',self.complete)
  self.spec={'key':'p','remote_root':str(self.old),'producer_seal_sha256':sha(self.old/'deploy_manifest.json'),'runtime_sha256':sha(self.old/'configs/runtime.json'),'kind':'screen','required_sources':['a']};self.config()
 def put(self,path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
 def config(self):self.put(self.r/'configs/predecessor.json',{'required':[self.spec]})
 def check(self,names=('p=actual',),identity=None,compute=()):return p.check(self.r,names,current_identity=lambda pid:identity,compute_processes=lambda:list(compute))
 def test_complete_absent_passes(self):self.assertTrue(self.check()['passed'])
 def test_missing_attempt_rejected(self):
  with self.assertRaises(ValueError):self.check(())
 def test_duplicate_attempt_rejected(self):
  with self.assertRaises(ValueError):self.check(('p=actual','p=actual'))
 def test_wrong_attempt_rejected(self):
  with self.assertRaises(FileNotFoundError):self.check(('p=other',))
 def test_unsafe_attempt_rejected(self):
  with self.assertRaises(ValueError):self.check(('p=../actual',))
 def test_incomplete_rejected(self):
  self.complete['all_sources_reviewed']=False;self.put(self.old/'audit/actual/COMPLETE.json',self.complete)
  with self.assertRaises(ValueError):self.check()
 def test_live_or_reused_pid_rejected(self):
  with self.assertRaises(ValueError):self.check(identity=self.owner['identity'])
 def test_stale_cuda_rejected(self):
  with self.assertRaises(ValueError):self.check(compute=[{'pid':99}])
 def test_other_process_left_alone(self):self.assertTrue(self.check(compute=[{'pid':100}])['passed'])
 def test_replacement_generation_rejected(self):
  o=copy.deepcopy(self.owner);o['identity']['start_ticks']='12';self.put(self.old/'processes/service.json',o)
  with self.assertRaises(ValueError):self.check()
 def test_native_completion_actual_job_binding(self):
  self.spec.update(kind='native',required_runs=['native_run'],native_gate='analysis/postrun/NATIVE_RUNTIME_GATE.json');self.config()
  gate=self.old/self.spec['native_gate'];self.put(gate,{'passed':True,'checks':{'a':True},'run_id':'native_run'})
  self.put(self.old/'logs/native_run_job.json',{'status':'success','service_pid':99,'service_identity':self.owner['identity']})
  self.put(self.old/'audit/actual/COMPLETE.json',{'passed':True,'GPU_released':True,'jobs':['native_run'],'runtime_gate_sha256':sha(gate)})
  self.assertTrue(self.check()['passed'])
  self.put(self.old/'logs/native_run_job.json',{'status':'success','service_pid':98,'service_identity':self.owner['identity']})
  with self.assertRaises(ValueError):self.check()
 def test_single_control_gate_generation(self):
  self.spec.update(kind='single_control',required_runs=['forced_run']);self.config();gate=self.old/'analysis/postrun/a/PAIR_RUNTIME_GATE.json'
  self.put(gate,{'passed':True,'checks':{'a':True},'service_owner':self.owner})
  value={'passed':True,'GPU_released':True,'jobs':['forced_run'],'remaining':[],'gates':{'a':{'file':str(gate),'sha256':sha(gate)}}};self.put(self.old/'audit/actual/COMPLETE.json',value)
  self.assertTrue(self.check()['passed']);self.put(gate,{'passed':False})
  with self.assertRaises(ValueError):self.check()
if __name__=='__main__':unittest.main()
