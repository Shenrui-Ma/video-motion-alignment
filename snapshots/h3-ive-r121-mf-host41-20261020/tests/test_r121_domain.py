import unittest,copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from r121_binding import reviewed_roles,validate_domain
class Domain(unittest.TestCase):
 def completion(self):
  return dict(schema='r121-screen-completion-v1',passed=True,GPU_released=True,all_sources_reviewed=True,remaining_sources=[],unreviewed_native_results=[],terminal_sources=[{'source_id':s}for s in ['short_0252','short_0358']],guided_sources=['short_0358'],native_only_sources=['short_0252'],successful_runs=['r121_short_0252_seed2026101701_native','r121_short_0358_seed2026101701_native','r121_short_0358_seed2026101701_forced'])
 def test_actual_skipped_native_retained(self):self.assertEqual(reviewed_roles(self.completion()),{'short_0252':['native'],'short_0358':['native','forced']})
 def test_requires_release(self):
  c=self.completion();c['GPU_released']=False
  with self.assertRaises(AssertionError):reviewed_roles(c)
 def test_requires_all_reviewed(self):
  c=self.completion();c['remaining_sources']=['short_0358']
  with self.assertRaises(AssertionError):reviewed_roles(c)
 def test_reject_unknown_run(self):
  c=self.completion();c['successful_runs'][-1]+='_other'
  with self.assertRaises(AssertionError):reviewed_roles(c)
 def test_two_native_valid(self):
  c=self.completion();c['guided_sources']=[];c['native_only_sources']=['short_0252','short_0358'];c['successful_runs']=c['successful_runs'][:2]
  self.assertEqual(sum(map(len,reviewed_roles(c).values())),2)
 def manifest(self):return dict(source_id='short_0252',valid_frames=98,total_frames=107,fps=24,crop_xywh=[16,8,1280,720],evaluation_indices=list(range(98)),raw_videos={'source':{},'native':{}},reference_image_used=False,input_to_original_frame=list(range(98)))
 def test_native_domain(self):self.assertEqual(validate_domain('short_0252',self.manifest(),['native']),98)
 def test_padding_rejected(self):
  m=self.manifest();m['evaluation_indices'].append(98)
  with self.assertRaises(AssertionError):validate_domain('short_0252',m,['native'])
 def test_wrong_source_domain(self):
  with self.assertRaises(AssertionError):validate_domain('short_0358',self.manifest(),['native'])
 def test_false_paired_rejected(self):
  with self.assertRaises(AssertionError):validate_domain('short_0252',self.manifest(),['native','forced'])
if __name__=='__main__':unittest.main()
