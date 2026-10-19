import copy,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r118_contract as c
spec=importlib.util.spec_from_file_location('r118_host41_runner',ROOT/'audit/root_run_control.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
class Host41Binding(unittest.TestCase):
 def test_protected_science_files_unchanged(self):
  p=c.read(ROOT/'design/HOST41_ADMIN_BINDING.json')
  for rel,row in p['protected'].items():self.assertTrue(row['byte_equal']);self.assertEqual(c.sha(ROOT/rel),row['source_sha256'])
 def test_original_full_memory_gate(self):
  p=c.read(ROOT/'configs/cgroup_policy.json')['working_set'];self.assertEqual(p['minimum_high_headroom_bytes'],64*1024**3);self.assertEqual(p['minimum_max_headroom_bytes'],76*1024**3);self.assertEqual(p['maximum_startup_psi_avg10'],1.)
 def test_single_own_h3_after_mf(self):
  s=(ROOT/'audit/root_run_control.py').read_text();self.assertIn("require(not args.peer_root,'host41 single own H3 only')",s);self.assertLess(s.index('require_mf_released(review))'),s.index("run(['python3','-u','scripts/launch_remote.py'"))
 def exercise(self,alter=lambda x:None,ident=None,processes=(),uid=1010,path=None):
  final=Path('/data4/researcher/h3_runs/display_pending_mf_20261019/audit/FINAL_RELEASE_VERIFIED.json')
  receipt={'passed':True,'all_spawned_trackers_released':True,'fresh_own_cuda_absent':True,'wrapper_identities':[{'pid':7,'uid':1004,'start_ticks':'99','cmdline_sha256':'abc'}]};alter(receipt)
  review={'mf_release_verification':{'file':str(path or final),'sha256':'digest'}}
  with patch.object(w,'read',return_value=receipt),patch.object(w,'sha',return_value='digest'),patch.object(w.service,'current_identity',return_value=ident),patch.object(w.service,'compute_processes',return_value=list(processes)),patch.object(w.service,'proc_uid',return_value=uid):return w.require_mf_released(review)
 def test_mf_release_pass(self):self.assertTrue(self.exercise()['passed'])
 def test_mf_failed_receipt_rejected(self):
  with self.assertRaises(ValueError):self.exercise(lambda x:x.update(passed=False))
 def test_mf_incomplete_release_rejected(self):
  with self.assertRaises(ValueError):self.exercise(lambda x:x.update(all_spawned_trackers_released=False))
 def test_wrapper_live_or_pid_reuse_rejected(self):
  with self.assertRaises(ValueError):self.exercise(ident={'pid':7})
 def test_wrapper_cuda_rejected(self):
  with self.assertRaises(ValueError):self.exercise(processes=[{'pid':7}])
 def test_own_tracker_cuda_rejected(self):
  with self.assertRaises(ValueError):self.exercise(processes=[{'pid':8}],uid=1004)
 def test_other_user_cuda_allowed(self):self.assertTrue(self.exercise(processes=[{'pid':8}],uid=1006)['passed'])
 def test_unknown_uid_rejected(self):
  with self.assertRaises(ValueError):self.exercise(processes=[{'pid':8}],uid=None)
 def test_wrong_receipt_path_rejected(self):
  with self.assertRaises(ValueError):self.exercise(path=Path('/tmp/other.json'))
 def test_empty_wrapper_evidence_rejected(self):
  with self.assertRaises(ValueError):self.exercise(lambda x:x.update(wrapper_identities=[]))
if __name__=='__main__':unittest.main()
