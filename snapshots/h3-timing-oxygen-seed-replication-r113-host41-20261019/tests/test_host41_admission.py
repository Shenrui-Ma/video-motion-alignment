import copy, hashlib, importlib.util, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'scripts'))
spec=importlib.util.spec_from_file_location('r113_host41_wrapper',R/'audit/root_run_seedpairs.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class Host41AdmissionTests(unittest.TestCase):
 def fixture(self,root):
  p=root/'FINAL_RELEASE_VERIFIED.json'
  v={k:True for k in ('passed','all_spawned_trackers_released','exact_processes_absent','exact_CUDA_allocations_absent','fresh_own_cuda_absent')}
  v['wrapper_identities']=[{'pid':11,'uid':1004,'start_ticks':'1','cmdline_sha256':'a'*64}]
  v['tracker_identities']=[{'pid':12,'uid':1004,'start_ticks':'2','cmdline_sha256':'b'*64}]
  p.write_text(json.dumps(v));return p,v
 def invoke(self,p,processes=(),identity=None,uid=1234):
  review={'mf_release_verification':{'file':str(p),'sha256':r.sha(p)}}
  with patch.object(r,'MF_RELEASE_PATH',p),patch.object(r.service,'current_identity',return_value=identity),patch.object(r.service,'compute_processes',return_value=list(processes)),patch.object(r.service,'proc_uid',return_value=uid):
   return r.require_mf_released(review)
 def test_exact_released_wrappers_and_trackers_pass(self):
  with tempfile.TemporaryDirectory() as d:
   p,v=self.fixture(Path(d));self.assertTrue(self.invoke(p)['passed'])
 def test_foreign_cuda_allowed(self):
  with tempfile.TemporaryDirectory() as d:
   p,v=self.fixture(Path(d));self.assertTrue(self.invoke(p,[{'pid':70}],uid=1005)['passed'])
 def test_own_or_unreadable_cuda_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p,v=self.fixture(Path(d))
   for uid in (1004,None):
    with self.subTest(uid=uid),self.assertRaises(ValueError):self.invoke(p,[{'pid':70}],uid=uid)
 def test_any_release_boolean_false_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p,v=self.fixture(Path(d))
   for k in [k for k in v if isinstance(v[k],bool)]:
    changed=copy.deepcopy(v);changed[k]=False;p.write_text(json.dumps(changed))
    with self.subTest(field=k),self.assertRaises(ValueError):self.invoke(p)
 def test_live_or_reused_process_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p,v=self.fixture(Path(d))
   with self.assertRaises(ValueError):self.invoke(p,identity={'start_ticks':'new'})
 def test_leftover_wrapper_or_tracker_cuda_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p,v=self.fixture(Path(d))
   for pid in (11,12):
    with self.subTest(pid=pid),self.assertRaises(ValueError):self.invoke(p,[{'pid':pid}],uid=1005)
 def test_missing_identity_evidence_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p,v=self.fixture(Path(d))
   for group in ('wrapper_identities','tracker_identities'):
    changed=copy.deepcopy(v);changed[group]=[];p.write_text(json.dumps(changed))
    with self.subTest(group=group),self.assertRaises(ValueError):self.invoke(p)
 def test_wrong_sha_or_receipt_path_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p,v=self.fixture(Path(d));review={'mf_release_verification':{'file':str(p),'sha256':'0'*64}}
   with patch.object(r,'MF_RELEASE_PATH',p),self.assertRaises(ValueError):r.require_mf_released(review)
   review['mf_release_verification']['sha256']=r.sha(p)
   with self.assertRaises(ValueError):r.require_mf_released(review)
 def test_protected_scientific_files_unchanged(self):
  binding=json.loads((R/'design/HOST41_ADMIN_BINDING.json').read_text())
  for rel,row in binding['protected'].items():
   with self.subTest(file=rel):self.assertEqual(hashlib.sha256((R/rel).read_bytes()).hexdigest(),row['source_sha256'])
 def test_migration_changes_only_graph_output_roots(self):
  source=R/'source_snapshot'/'r106_graph.json'
  # Expected graph is derived from frozen scientific contract, not an old host path.
  import r113_contract
  jobs,order=r113_contract.registry(R)
  self.assertEqual(len(order),4)
  for run in order:
   graph=json.loads((R/'configs/graphs'/(run+'.json')).read_text())
   self.assertNotIn('/home/researcher/h3_runs/timing_oxygen_seed_replication_r113_20261019',json.dumps(graph))
 def test_full_gate_runs_before_launch(self):
  s=(R/'audit/root_run_seedpairs.py').read_text()
  self.assertLess(s.index("require(not args.peer_root"),s.index("run(['python3','-u','scripts/launch_remote.py'"))
  self.assertLess(s.index("cgroup_memory.check(ROOT)"),s.index("run(['python3','-u','scripts/launch_remote.py'"))
  self.assertLess(s.index("require_mf_released(review))"),s.index("run(['python3','-u','scripts/launch_remote.py'"))
if __name__=='__main__':unittest.main()
