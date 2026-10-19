"""Real sealed-parent regression checks for the independent retry relocation."""
import importlib.util,json,shutil,tempfile,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('retry_inheritance_tested',ROOT/'scripts/retry_inheritance.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class RetryInheritanceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)/'retry';shutil.copytree(ROOT,cls.root,ignore=shutil.ignore_patterns('inputs','__pycache__'))
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def changed(self,rel,change,pattern):
  p=self.root/rel;before=p.read_bytes()
  try:
   p.write_bytes(change(before))
   with self.assertRaisesRegex(ValueError,pattern):module.check(self.root,inputs=False)
  finally:p.write_bytes(before)
 def test_exact_five_case_protocol_and_parent_inheritance(self):
  result=module.check(self.root,inputs=False);self.assertEqual(result['status'],'pass');self.assertTrue(result['protocol_byte_exact']);self.assertEqual(len(result['new_runs']),4)
 def test_scientific_protocol_mutation_rejected(self):
  def change(data):
   x=json.loads(data);x['actuator']['unapproved_gain']=0.75;return (json.dumps(x)+'\n').encode()
  self.changed('configs/protocol.json',change,'unapproved inherited file differs|new local binding changed')
 def test_graph_semantic_change_exceeds_path_relocation(self):
  rel=module.read(self.root/'configs/retry/inheritance.json')['graph_path_changes_only'][0]
  def change(data):
   x=json.loads(data);first=next(iter(x));x[first]['inputs']['unexpected_edit']=True;return (json.dumps(x)+'\n').encode()
  self.changed(rel,change,'relocation exceeds paths')
 def test_numeric_module_change_rejected(self):
  self.changed('extensions/H3AutomaticWindowRouter/dynamic_support.py',lambda b:b+b'\n# unreviewed change\n','unapproved inherited file differs|new local binding changed')
 def test_parent_noise_metadata_mutation_rejected(self):
  self.changed('configs/parents/chest/noise.json',lambda b:b+b'\n','unapproved inherited file differs|new local binding changed')
 def test_resource_source_must_match_reviewed_candidate(self):
  self.changed('scripts/run_observer.py',lambda b:b+b'\n# unreviewed change\n','unapproved inherited file differs|new local binding changed')
 def test_unreviewed_memory_margin_rejected(self):
  def change(data):
   x=json.loads(data);x['resources']['decoder_required_free_MiB']=1;return (json.dumps(x)+'\n').encode()
  self.changed('configs/protocol.json',change,'unapproved inherited file differs|new local binding changed')
if __name__=='__main__':unittest.main()
