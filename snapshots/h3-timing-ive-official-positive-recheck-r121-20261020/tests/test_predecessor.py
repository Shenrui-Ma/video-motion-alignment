import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import predecessor as p
from r121_contract import sha
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
 def two_arm_fixture(self):
  runs=['r115_fixed','r115_matched'];arms=['fixed_one_bin','matched_one_bin']
  self.spec.update(kind='two_new_arm_control',required_runs=runs,required_arms=arms,runtime_gate='analysis/postrun/long_0174/PAIR_RUNTIME_GATE.json',gate_schema='r115-two-new-arm-runtime-gate-v1');self.config()
  path=self.old/self.spec['runtime_gate'];gate={'schema':self.spec['gate_schema'],'passed':True,'checks':{'prefix_and_bank':True},'service_owner':self.owner,'producer_seal_sha256':self.spec['producer_seal_sha256'],'runtime_profile_sha256':self.spec['runtime_sha256'],'new_run_ids':runs,'runs':{a:{'run_id':r} for a,r in zip(arms,runs)}};self.put(path,gate)
  for run in runs:self.put(self.old/'logs'/(run+'_job.json'),{'status':'success','name':run,'service_pid':99,'service_identity':self.owner['identity']})
  complete={'passed':True,'GPU_released':True,'jobs':runs,'remaining':[],'runtime_gate_sha256':sha(path)};self.put(self.old/'audit/actual/COMPLETE.json',complete)
  return path,gate,complete
 def test_two_arm_actual_complete_and_release_passes(self):
  self.two_arm_fixture();self.assertTrue(self.check()['passed'])
 def test_two_arm_second_job_incomplete_refused(self):
  self.two_arm_fixture();self.put(self.old/'logs/r115_matched_job.json',{'status':'running','name':'r115_matched','service_pid':99,'service_identity':self.owner['identity']})
  with self.assertRaisesRegex(ValueError,'job generation'):self.check()
 def test_two_arm_rewritten_gate_hash_refused(self):
  path,gate,_=self.two_arm_fixture();gate['checks']['prefix_and_bank']=False;self.put(path,gate)
  with self.assertRaisesRegex(ValueError,'gate differs'):self.check()
 def test_two_arm_wrong_owner_even_with_new_digest_refused(self):
  path,gate,complete=self.two_arm_fixture();gate['service_owner']=copy.deepcopy(self.owner);gate['service_owner']['identity']['start_ticks']='changed';self.put(path,gate);complete['runtime_gate_sha256']=sha(path);self.put(self.old/'audit/actual/COMPLETE.json',complete)
  with self.assertRaisesRegex(ValueError,'owner/runtime'):self.check()
 def test_two_arm_wrong_scope_even_with_new_digest_refused(self):
  path,gate,complete=self.two_arm_fixture();gate['new_run_ids']=['r115_fixed'];self.put(path,gate);complete['runtime_gate_sha256']=sha(path);self.put(self.old/'audit/actual/COMPLETE.json',complete)
  with self.assertRaisesRegex(ValueError,'scope differs'):self.check()
 def seed_fixture(self):
  seeds=[2026101702,2026101703];runs=[f'r113_short_0252_seed{s}_{a}' for s in seeds for a in ('native','fixed')]
  self.spec.update(kind='two_seed_pairs',required_runs=runs,required_seeds=seeds,required_source='short_0252',runtime_gate='analysis/postrun/PAIR_RUNTIME_GATE.json',gate_schema='r113-two-seed-runtime-gate-v1');self.config();receipts=[]
  for seed in seeds:
   path=self.old/'analysis/postrun'/f'seed{seed}'/'PAIR_RUNTIME_GATE.json';pair={'passed':True,'checks':{'prefix':True},'service_owner':self.owner,'source_id':'short_0252','seed':seed,'runs':{a:{'run_id':f'r113_short_0252_seed{seed}_{a}'} for a in ('native','fixed')}};self.put(path,pair);receipts.append({'seed':seed,'file':str(path),'sha256':sha(path)})
  path=self.old/self.spec['runtime_gate'];gate={'schema':self.spec['gate_schema'],'passed':True,'checks':{'all_pairs':True},'service_owner':self.owner,'producer_seal_sha256':self.spec['producer_seal_sha256'],'runtime_profile_sha256':self.spec['runtime_sha256'],'jobs':runs,'seeds':seeds,'source_id':'short_0252','pair_gate_receipts':receipts};self.put(path,gate)
  for run in runs:self.put(self.old/'logs'/(run+'_job.json'),{'status':'success','name':run,'service_pid':99,'service_identity':self.owner['identity']})
  complete={'passed':True,'GPU_released':True,'jobs':runs,'remaining':[],'runtime_gate_sha256':sha(path)};self.put(self.old/'audit/actual/COMPLETE.json',complete);return path,gate,complete
 def test_seed_pairs_complete(self):self.seed_fixture();self.assertTrue(self.check()['passed'])
 def test_seed_pair_modified_receipt_rejected(self):
  path,gate,complete=self.seed_fixture();self.put(Path(gate['pair_gate_receipts'][0]['file']),{'passed':False})
  with self.assertRaises(ValueError):self.check()
 def test_seed_fourth_job_missing_success_rejected(self):
  _,gate,_=self.seed_fixture();self.put(self.old/'logs'/(gate['jobs'][-1]+'_job.json'),{'status':'running'})
  with self.assertRaises(ValueError):self.check()
 def mf_fixture(self):
  path=self.r/'mf/FINAL_RELEASE_VERIFIED.json';value={k:True for k in ('passed','all_spawned_trackers_released','exact_processes_absent','exact_CUDA_allocations_absent','fresh_own_cuda_absent')};value.update(wrapper_identities=[{'pid':101}],tracker_identities=[{'pid':102}]);self.put(path,value);self.put(self.r/'configs/predecessor.json',{'required':[self.spec],'mf_final_release_path':str(path)});return path,value
 def test_MF_release_required_when_configured(self):
  self.seed_fixture();self.mf_fixture();self.assertEqual(self.check()['official_MF_release']['identities_verified_absent'],2)
 def test_MF_unreleased_flag_rejected(self):
  self.seed_fixture();path,value=self.mf_fixture();value['fresh_own_cuda_absent']=False;self.put(path,value)
  with self.assertRaisesRegex(ValueError,'MF final release'):self.check()
 def test_MF_cuda_pid_rejected(self):
  self.seed_fixture();self.mf_fixture()
  with self.assertRaisesRegex(ValueError,'MF process or CUDA'):self.check(compute=[{'pid':102}])
if __name__=='__main__':unittest.main()
