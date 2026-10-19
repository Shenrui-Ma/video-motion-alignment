import ast,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r96_contract as c

class R96Migration(unittest.TestCase):
 def test_all_parent_source_prompt_numerical_bytes(self):
  bindings=c.read(ROOT/'audit/INHERITED_BYTE_BINDINGS.json')
  for path,digest in {**bindings['files'],**bindings['numerical_files']}.items():self.assertEqual(c.sha(ROOT/path),digest,path)
 def test_extension_contract_names_are_resolvable(self):
  for path in (ROOT/'extensions').glob('*/__init__.py'):
   tree=ast.parse(path.read_text())
   imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module and n.module.endswith('_contract')]
   self.assertTrue(all(name=='r96_contract' for name in imports),(path,imports))
 def test_host41_paths_and_single_initial_trial(self):
  runtime=c.read(ROOT/'configs/runtime.json');policy=c.read(ROOT/'configs/cgroup_policy.json')
  self.assertEqual(runtime['remote_root'],'/data4/researcher/h3_runs/timing_ive_native_screen_r96_20261018')
  self.assertEqual(runtime['host'],'H3_SERVER_B');self.assertEqual(runtime['uid'],1004)
  self.assertEqual(policy['initial_own_gpu_cards'],1);self.assertEqual(policy['startup_minimum_effective_headroom_bytes'],64*1024**3)
  script=(ROOT/'audit/root_run_batch.py').read_text();self.assertIn('require(not peers,',script)
 def test_administrative_guard_in_seal_and_before_cuda(self):
  self.assertIn("'cgroup_policy.json'",(ROOT/'scripts/execution_gate.py').read_text())
  service=(ROOT/'scripts/service.py').read_text();self.assertLess(service.index('cgroup_startup=cgroup_memory.check(RUN)'),service.index('process = subprocess.Popen(args'))
  wrapper=(ROOT/'audit/root_run_batch.py').read_text();self.assertLess(wrapper.index("audit/'CGROUP_PRE_GO.json'"),wrapper.index("ROOT/'processes/cuda_gate_go.json'"))

if __name__=='__main__':unittest.main()
