"""Protect original benchmark task semantics and isolated runtime wiring."""
import importlib.util,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import r54_contract as c
import preflight,service

class OriginalTasks(unittest.TestCase):
 def test_five_original_prompts_and_video_only(self):
  jobs,order=c.registry(ROOT)
  self.assertEqual(len(order),5)
  for run in order:
   row=c.validate_job(run,ROOT);g=c.read(ROOT/'configs/graphs'/f'{run}.json');case=row['case']
   self.assertNotIn('21',g);self.assertNotIn('ref_image',g['5']['inputs'])
   self.assertEqual(g['5']['inputs']['prompt'],c.PROMPTS[case['source_id']])
   self.assertEqual(g['22']['inputs']['file'],case['video'])
   self.assertEqual((g['5']['inputs']['width'],g['5']['inputs']['height'],g['5']['inputs']['length']),(1312,736,90))
   self.assertEqual(g['51']['inputs']['source_run_id'],'r54_'+case['source_id']+'_shared')
 def test_profile_and_root_launch_gate(self):
  self.assertEqual(service.GPU,'GPU-REDACTED')
  self.assertEqual(service.PORT,8515)
  self.assertEqual(service.RUNTIME['host'],'H3_SERVER_B')
  self.assertIn('--use-pytorch-cross-attention',service.command())
  self.assertNotIn('--fast',service.command())
  self.assertIsNone(c.read(ROOT/'configs/admission.json')['existing_comfy_port'])
  self.assertFalse(c.read(ROOT/'configs/admission.json')['ready_for_launch'])
  with self.assertRaises(ValueError):preflight.check(ROOT,live=True)
 def test_predeclared_valid_prefixes(self):
  cases=c.read(ROOT/'configs/scientific_contract.json')['cases']
  self.assertEqual([x['valid_frame_count'] for x in cases],[87,86,74,78,89])
  for case in cases:
   self.assertEqual(case['prompt'],case['original_task']['edit_prompt'])
   self.assertEqual((case['reference_video_count'],case['reference_image_count']),(1,0))
if __name__=='__main__':unittest.main()
