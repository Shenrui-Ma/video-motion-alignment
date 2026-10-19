import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r80_contract as c,execution_gate as gate,preflight
class NativeContract(unittest.TestCase):
 def test_same_original_numeric_graphs(self):
  jobs,order=c.registry()
  for run in order:
   case=jobs[run]['case'];a=c.read(ROOT/case['parent_graph']);b=c.read(ROOT/'configs/graphs'/(run+'.json'))
   for n,key in [('5','audit_dir'),('6','audit_dir'),('50','audit_dir'),('51','source_audit_dir'),('52','output_dir'),('5','run_id'),('6','run_id'),('50','run_id'),('51','run_id'),('52','run_id'),('51','source_run_id'),('6','pair_id'),('14','filename_prefix'),('5','prompt')]:a[n]['inputs'][key]=b[n]['inputs'][key]='ADMIN_OR_PROMPT'
   self.assertEqual(a,b)
  self.assertEqual(len(order),2);self.assertTrue(preflight.check()['passed'])
 def test_official_text_and_full_reference_labels(self):
  for case in c.read(ROOT/'configs/scientific_contract.json')['cases']:
   p=case['prompt']
   for key in ['source_prompt','edit_prompt','target_prompt']:self.assertIn(case['original_task'][key],p)
   for text in ['[video editing]','<Subject 1> (appears in [Shot 1]): partially_preserved','<Subject 2> (appears in [Shot 1]): fully_preserved','\n[Shot 1] ']:self.assertIn(text,p)
   self.assertNotRegex(p,r'\d{2}:\d{2}');self.assertNotIn('<Picture',p)
 def test_subject_replacement_does_not_preserve_male_identity(self):
  p=(ROOT/'configs/prompts/short_0352.txt').read_text()
  self.assertIn('target female identity and dress replace the source male identity',p)
  self.assertNotIn('Preserve the same man',p)
 def test_second_native_stays_blocked_until_explicit_review(self):
  order=c.read(ROOT/'configs/scientific_contract.json')['case_order']
  with tempfile.TemporaryDirectory() as d,patch.object(gate,'approval',return_value={'allowed_runs':order[:1],'runtime_profile_sha256':'runtime'}),patch.object(gate,'registry',return_value=({},order)):
   r=Path(d);(r/'audit').mkdir()
   self.assertTrue(gate.admitted_job(order[0],r));self.assertFalse(gate.admitted_job(order[1],r))
   (r/'audit/CONTINUE_AFTER_FIRST_NATIVE.json').write_text(json.dumps({'root_approved':True,'schema':'r80-second-native-approval-v1','task_fidelity_reviewed':False}))
   with self.assertRaisesRegex(ValueError,'review missing'):gate.admitted_job(order[1],r)
 def test_trial_policy_is_30gib_without_numeric_fallback(self):
  v=c.read(ROOT/'configs/scientific_contract.json')['capacity_trial'];self.assertEqual(v['minimum_free_mib'],30720);self.assertFalse(v['auto_retry_or_parameter_fallback'])
if __name__=='__main__':unittest.main()
