import importlib.util,json,unittest
from pathlib import Path
P=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('g',P/'coverage_after_partial7_handoff.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
class Tests(unittest.TestCase):
 def test_target45(self):self.assertEqual(len(g.merge_manifest(g.REQ['base'],g.REQ['pilots'])['jobs']),45)
 def test_exactly_seven_prerequisites(self):self.assertEqual(len(g.REQ['prerequisite_ids']),7)
 def test_running_seventh_waits(self):
  states={j:{'status':'completed'} for j in g.REQ['prerequisite_ids']};states['innov41_short_0343_partial_temporal_rope']['status']='submitted';self.assertFalse(g.preceding_status(states,g.REQ['prerequisite_ids']))
 def test_completed_seven_passes(self):self.assertTrue(g.preceding_status({j:{'status':'completed'} for j in g.REQ['prerequisite_ids']},g.REQ['prerequisite_ids']))
 def test_cancelled_excluded(self):
  cancelled={j['id'] for j in json.loads((P/'receipt.json').read_text())['cancelled_jobs']};target=g.merge_manifest(g.REQ['base'],g.REQ['pilots']);self.assertFalse(cancelled.intersection(j['id'] for j in target['jobs']));self.assertFalse(cancelled.intersection(g.REQ['prerequisite_ids']))
 def test_current_preserved(self):self.assertIn('innov41_short_0343_partial_temporal_rope',{j['id'] for j in g.REQ['base']['jobs']})
 def test_distinct_receipt(self):
  source=(P/'coverage_after_partial7_handoff.py').read_text();self.assertIn("directory/'coverage_after_partial7_activation.json'",source);self.assertNotIn("directory/'coverage_pilots_activation.json'",source);self.assertIn('reap_finished_children()',source)
if __name__=='__main__':unittest.main()
