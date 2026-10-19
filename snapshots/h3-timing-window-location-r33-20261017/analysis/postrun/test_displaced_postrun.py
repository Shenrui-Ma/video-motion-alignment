import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import contract as c
from evaluate import check_provenance
class DisplacedPostrunTests(unittest.TestCase):
 def test_fixed_scope(self):
  p=c.read(c.HERE/'PROTOCOL.json');self.assertEqual(list(p['parents']),['N','F','Auto']);self.assertEqual(p['cases'][0]['windows'],[[50,65],[69,81],[80,92],[99,111]]);self.assertEqual(p['fixed_visual_frames'],[55,86,105]);self.assertEqual(p['fixed_clip_inclusive'],[42,82]);self.assertEqual(p['common_support_subsets'],[['N','F','Auto','Displaced'],['Auto','Displaced']]);self.assertEqual(p['scan_rows'],186)
 def test_blind_order_frozen_and_equal_budget_static(self):
  import random
  p=c.read(c.HERE/'PROTOCOL.json');x=['Auto','Displaced'];random.Random(2026101713).shuffle(x);self.assertEqual(p['blind_order'],x)
  s=(c.HERE/'displaced_evaluate.py').read_text();self.assertIn("'online_observations':0",s);self.assertIn("'NFE':21",s);self.assertNotIn('interaction(',s)
 def test_technical_error_not_UNKNOWN(self):
  with self.assertRaises(ValueError):c.observer_summary({'status':'error','windows':[]})
  self.assertEqual(c.observer_summary({'status':'unknown_visibility','windows':[]})['scientific_status'],'unknown_visibility')
 def test_exact_parent_provenance_or_registered_source_exception(self):
  p=c.read(c.HERE/'PROTOCOL.json');source=c.read(c.HERE/p['cases'][0]['source_pose']);parents=[c.read(c.HERE/v['pose'])['provenance'] for v in p['parents'].values()];check_provenance(source['provenance'],parents[0],parents,source['video']['sha256'])
  bad=copy.deepcopy(parents[0]);bad['person_selection']='wrong'
  with self.assertRaises(ValueError):check_provenance(source['provenance'],bad,parents,source['video']['sha256'])
 def test_new_method_has_no_automatic_window_input(self):
  s=(c.HERE/'remote_consume.py').read_text();self.assertNotIn('observer_replay',s);self.assertIn('verify_completed.py',s)
 def test_full_and_fixed_clip_are_saved(self):
  s=(c.HERE/'evaluate.py').read_text();self.assertIn("full_comparison.mp4",s);self.assertIn("fixed_clip_comparison.mp4",s)
if __name__=='__main__':unittest.main()
