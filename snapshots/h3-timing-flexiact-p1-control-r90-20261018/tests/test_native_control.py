import copy,hashlib,importlib.util,json,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r90_contract as c
import preflight
spec=importlib.util.spec_from_file_location('runner_native_test',ROOT/'audit/root_run_native.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class NativeContract(unittest.TestCase):
 def cloned(self):
  d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup);root=Path(d.name)
  for folder in ('configs','design'):shutil.copytree(ROOT/folder,root/folder)
  return root
 def test_one_Native_exact_full_P1(self):
  jobs,order=c.registry();self.assertEqual(order,[c.RUN_ID]);self.assertEqual(jobs[c.RUN_ID]['arm'],'native');self.assertTrue(c.prompt_values().endswith('\n'));self.assertEqual(c.sha(ROOT/'configs/prompts/one_leg__movie_man_9_p1.txt'),c.P1_SHA)
 def test_prompt_newline_change_is_rejected(self):
  root=self.cloned();p=root/'configs/prompts/one_leg__movie_man_9_p1.txt';p.write_text(p.read_text().rstrip('\n'))
  with self.assertRaisesRegex(ValueError,'bytes changed'):c.registry(root)
 def test_native_only_and_finalize_required(self):
  for key,value in [('jobs',[c.RUN_ID,'extra']),('finalize',False)]:
   root=self.cloned();p=root/'configs/queue.json';d=c.read(p);d[key]=value;p.write_text(json.dumps(d))
   with self.assertRaisesRegex(ValueError,'finalize'):c.registry(root)
 def test_model_sampler_and_route_changes_rejected(self):
  for node,key,value in [('50','mode','mass_preserve'),('5','semantic_fps',4),('6','noise_seed',1),('7','sampler_name','heun'),('5','length',147)]:
   root=self.cloned();p=root/'configs/graphs'/(c.RUN_ID+'.json');d=c.read(p);d[node]['inputs'][key]=value;p.write_text(json.dumps(d))
   with self.assertRaisesRegex(ValueError,'allowed prompt'):c.registry(root)
 def test_exact_numeric_six_files(self):
  for path,row in c.read(ROOT/'configs/runtime_kernel_hashes.json').items():self.assertEqual(c.sha(ROOT/path),row['parent_sha256'])
 def test_parent_failed_gate_refused(self):
  root=self.cloned();p=root/'design/R85_ACTUAL/PAIR_RUNTIME_GATE.json';d=c.read(p);d['passed']=False;p.write_text(json.dumps(d))
  with self.assertRaises(ValueError):c.registry(root)
 def test_graph_diff_is_only_prompt_and_administrative_ids_paths(self):
  a=c.read(ROOT/'configs/parent_graphs/r85_actual_native.json');b=c.read(ROOT/'configs/graphs'/(c.RUN_ID+'.json'))
  diffs={(n,k) for n in a for k,v in a[n]['inputs'].items() if b[n]['inputs'].get(k)!=v}
  expected={('5','prompt'),('5','run_id'),('5','audit_dir'),('6','audit_dir'),('6','run_id'),('6','pair_id'),('50','audit_dir'),('50','run_id'),('51','source_audit_dir'),('51','source_run_id'),('51','run_id'),('52','output_dir'),('52','run_id'),('14','filename_prefix')}
  self.assertEqual(diffs,expected)
 def noise_fixture(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);base=Path(t.name);root=base/'new';old=base/'old'
  (root/'audit').mkdir(parents=True);(root/'configs').mkdir();(old/'audit').mkdir(parents=True)
  data=b'actual original AV bytes';src=old/'audit/noise.pt';src.write_bytes(data)
  (root/'configs/parent_bindings.json').write_text(json.dumps({'r85_root':str(old),'noise_cache_relative':'audit/noise.pt','noise_cache_sha256':hashlib.sha256(data).hexdigest()}))
  return root,src,data
 def test_original_noise_copy_exact_and_idempotent(self):
  root,src,data=self.noise_fixture()
  with patch.object(runner,'ROOT',root):a=runner.prepare_original_noise();b=runner.prepare_original_noise()
  self.assertEqual(Path(a['destination']).read_bytes(),data);self.assertEqual(a,b);self.assertEqual(src.read_bytes(),data)
 def test_changed_parent_noise_and_existing_cache_refused(self):
  root,src,data=self.noise_fixture();src.write_bytes(b'changed')
  with patch.object(runner,'ROOT',root),self.assertRaisesRegex(ValueError,'original R85'):runner.prepare_original_noise()
  src.write_bytes(data);(root/'audit/r90_one_leg__movie_man_9_seed2026101701_noise.pt').write_bytes(b'other')
  with patch.object(runner,'ROOT',root),self.assertRaisesRegex(ValueError,'new noise cache'):runner.prepare_original_noise()
if __name__=='__main__':unittest.main()
