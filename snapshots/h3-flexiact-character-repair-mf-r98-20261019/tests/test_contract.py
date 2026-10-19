import unittest,json,hashlib,sys,copy,os
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'));from common import *
from prepare_native import validate_gate
from tracking_plan import command
class ContractTests(unittest.TestCase):
 def test_frozen_numeric_files(self):
  inherited=read(R/'configs/NUMERIC_INHERITANCE.json')
  for name,rec in inherited['files'].items():self.assertEqual(sha(METRIC/name),rec['sha256'])
  self.assertEqual(sha(R/'runtime/release/release49.py'),inherited['release49']['sha256'])
 def test_actual_gate_and_output(self):validate_gate(read(R/'incoming/NATIVE_RUNTIME_GATE.json'),sha(R/'incoming/native.mp4'))
 def test_wrong_video_rejected(self):
  with self.assertRaises(ValueError):validate_gate(read(R/'incoming/NATIVE_RUNTIME_GATE.json'),'0'*64)
 def test_routed_native_rejected(self):
  g=read(R/'incoming/NATIVE_RUNTIME_GATE.json');g['routed_blocks']=450
  with self.assertRaises(ValueError):validate_gate(g,sha(R/'incoming/native.mp4'))
 def test_wrong_valid_domain_rejected(self):
  g=read(R/'incoming/NATIVE_RUNTIME_GATE.json');g['valid_frames']=158
  with self.assertRaises(ValueError):validate_gate(g,sha(R/'incoming/native.mp4'))
 def test_guided_pending(self):
  with self.assertRaisesRegex(ValueError,'PENDING'):command('guided','GPU-test','python')
 def test_reference_launch_is_only_plan(self):
  args=command('reference','GPU-test','python');self.assertIn('CUDA_VISIBLE_DEVICES=GPU-test',args);self.assertFalse((R/'controls').exists())
 def test_official_original_motion_source(self):
  item=read(METRIC/'SOURCE_INPUTS.json')['inputs'][0];self.assertEqual(item['id'],CASE);self.assertEqual(sha(METRIC/item['file']),item['sha256']);self.assertEqual(item['pts_seconds'],[i/8 for i in range(49)])
 def test_admin_wrapper_only_namespace_changed(self):
  parent=Path('/Users/researcher/DevProjects/h3-flexiact-expanded-evaluation-r66-20261018/scripts/track_shared.py')
  expected=read(R/'configs/WRAPPER_INHERITANCE.json')['normalized_parent_sha256'];text=(R/'scripts/track_shared.py').read_text().replace('r98_frozen_run_tracks','r66_frozen_run_tracks').replace('R98_BINDING.json','R66_BINDING.json');self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),expected)
if __name__=='__main__':unittest.main()
