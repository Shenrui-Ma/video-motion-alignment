import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import contract as c
from joint_evaluate import interaction
from evaluate import check_provenance
class JointPostrunTests(unittest.TestCase):
 def test_fixed_scope(self):
  p=c.read(c.HERE/'PROTOCOL.json');self.assertEqual(list(p['parents']),['N','F','B']);self.assertEqual(p['cases'][0]['windows'],[[50,65],[69,81],[80,92],[99,111]]);self.assertEqual(p['fixed_visual_frames'],[55,86,105]);self.assertEqual(p['fixed_clip_inclusive'],[42,82]);self.assertEqual(p['common_support_subsets'],[['N','F','B','FB'],['F','FB']]);self.assertEqual(p['scan_rows'],186)
 def test_interaction_only_common_support(self):
  row={'region':'x','feature':'arm_direction','status':'usable_exploratory','common_valid_fraction':1.,'runs':{k:{'same_frame_error_on_common_support':v} for k,v in [('N',4.),('F',2.),('B',3.),('FB',1.)]}}
  self.assertEqual(interaction({'rows':[row]})[0]['E_FB_minus_F_minus_B_plus_N'],0.)
  for status in ('insufficient_common_support','empty_region'):
   bad=copy.deepcopy(row);bad['status']=status;self.assertIsNone(interaction({'rows':[bad]})[0]['E_FB_minus_F_minus_B_plus_N'])
  row['runs']['FB']['same_frame_error_on_common_support']=None;self.assertIsNone(interaction({'rows':[row]})[0]['E_FB_minus_F_minus_B_plus_N'])
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
