import unittest,json,importlib.util,tempfile
from pathlib import Path
from unittest import mock
P=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('g',P/'coverage_v2_handoff.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
class Checks(unittest.TestCase):
 def test_target(self):self.assertEqual(len(g.merge_manifest(g.REQ['base'],g.REQ['pilots'])['jobs']),48)
 def test_only_two(self):self.assertEqual(len(g.REQ['pilots']['jobs']),2)
 def test_preserves_frozen_graph(self):
  old=P.parents[1]/'temporal_coverage/host41'
  for j in g.REQ['pilots']['jobs']:
   n=json.loads((P/j['graph']).read_text());o=json.loads((old/j['graph'].replace('temporal_coverage_v2','temporal_coverage')).read_text())
   for k in set(n)-{'14','50'}:self.assertEqual(n[k],o[k])
   self.assertEqual(n['50']['inputs']['iterations'],64);self.assertEqual(n['50']['inputs']['alpha'],.25)
 def test_service_unchanged_except_whitelist(self):
  old=(P/'manage_service.before.py').read_text();new=(P/'manage_service.after.py').read_text();self.assertEqual(new.replace("'H3TemporalCoverage','H3TemporalCoverageV2',","'H3TemporalCoverage',"),old)
 def test_live_service_blocks_change(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);(r/'innovation_handoff').mkdir()
   with mock.patch.object(g,'snapshot',return_value={'ready_for_deployment':False}):self.assertFalse(g.install_service_at_boundary({**g.REQ,'root':t}))
 def test_previous_held_jobs_not_restored(self):
  ids=[j['id'] for j in g.REQ['base']['jobs']]
  self.assertEqual(len([x for x in ids if x.endswith('_temporal_coverage')]),3)
  self.assertEqual(len([x for x in ids if x.endswith('_partial_temporal_rope')]),7)
 def test_unique_receipt(self):self.assertIn("directory/'coverage_v2_activation.json'",(P/'coverage_v2_handoff.py').read_text())
if __name__=='__main__':unittest.main()
