import ast,unittest
from contract import *
class EvaluationAddendumTests(unittest.TestCase):
 def test_predeclared_coverage_preserved(self):
  p=read(HERE/'PROTOCOL.json');s=read(Path(p['root_local'])/'configs/scientific_contract.json')['evaluation'];a=read(HERE/'EVALUATION_ADDENDUM.json')
  self.assertEqual(p['cases'][0]['predeclared_windows'],s['fixed_windows']);self.assertEqual(p['primary_visual_frames'],s['stills']);self.assertEqual(p['cases'][0]['windows'],s['fixed_windows']+[[0,140]]);self.assertEqual(p['fixed_visual_frames'],sorted(set(s['stills']+[0,35,70,105,140])));self.assertEqual(a['actual_render_frame_union'],p['fixed_visual_frames']);self.assertEqual(sha(HERE/'EVALUATION_ADDENDUM.json'),p['evaluation_addendum']['sha256'])
 def test_runtime_drives_config_and_old_math_unchanged(self):
  p=read(HERE/'PROTOCOL.json');old=Path(p['root_local'])/'audit/postrun_v1_evidence';f=read(old/'FREEZE.json')
  for name in ('evaluate.py','presentation.py','remote_consume.py','consume.py','one_phase.py','contract.py','timing_metrics.py','pairwise_gain.py','physical_tolerance.py','scan_current_pose.py'):
   self.assertEqual(sha(HERE/name),f['files'][name])
  src=(HERE/'remote_consume.py').read_text();self.assertIn("case['windows']",src);self.assertIn("P['fixed_visual_frames']",src)
  body=(HERE/'presentation.py').read_text();self.assertIn("if i in p['fixed_visual_frames']",body)
 def test_authorization_and_old_evidence_preserved(self):
  p=read(HERE/'PROTOCOL.json');b=read(HERE/'BINDING.template.json');self.assertIs(b['approved_for_consumer_start'],False);self.assertEqual(b['protocol_sha256'],sha(HERE/'PROTOCOL.json'));a=read(HERE/'EVALUATION_ADDENDUM.json');old=Path(p['root_local'])/'audit/postrun_v1_evidence';self.assertEqual(sha(old/'FREEZE.json'),a['old_freeze_sha256']);self.assertEqual(sha(old/'PROTOCOL.json'),a['old_protocol_sha256']);self.assertIs(a['actual_results_read'],False)
if __name__=='__main__':unittest.main()
