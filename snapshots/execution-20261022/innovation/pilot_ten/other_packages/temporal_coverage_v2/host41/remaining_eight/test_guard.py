from pathlib import Path
import importlib.util,unittest,json,os,tempfile
from unittest import mock
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('g',P/'coverage_v2_remaining8_handoff.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
class Checks(unittest.TestCase):
 def test_target(self):self.assertEqual(len(g.merge_manifest(g.REQ['base'],g.REQ['pilots'])['jobs']),56)
 def test_two_pilot_gate(self):
  self.assertEqual(len(g.REQ['pilot_ids']),2)
  self.assertFalse(g.preceding_status({g.REQ['pilot_ids'][0]:{'status':'completed'}},g.REQ['pilot_ids']))
  self.assertTrue(g.preceding_status({j:{'status':'completed'} for j in g.REQ['pilot_ids']},g.REQ['pilot_ids']))
 def test_failed_prerequisite(self):
  with self.assertRaises(RuntimeError):g.preceding_status({'x':{'status':'failed'}},['x'])
 def test_cancelled_partial_stays_absent(self):
  ids=[j['id'] for j in g.REQ['base']['jobs']+g.REQ['pilots']['jobs']]
  for case in ('short_0114','crouch__movie_man_4','long_0167'):self.assertNotIn('innov41_'+case+'_partial_temporal_rope',ids)
  self.assertEqual(sum(j.endswith('_partial_temporal_rope') for j in ids),7)
 def test_exact_graph(self):
  D=P.parents[3]/'direction_package/host41'
  for j in g.REQ['pilots']['jobs']:
   d=json.loads((P/j['graph']).read_text());o=json.loads((D/'graphs'/j['graph'].split('/')[-1].replace('temporal_coverage_v2','direction_gated')).read_text())
   for key in set(d)-{'14','50'}:self.assertEqual(d[key],o[key])
   self.assertEqual(d['50']['inputs']['step_end'],20);self.assertEqual(d['50']['inputs']['alpha'],.25);self.assertEqual(d['50']['inputs']['model'],['41',0]);self.assertEqual(d['50']['class_type'],'H3TemporalCoverageV2')
 def process(self):
  tmp=tempfile.TemporaryDirectory();root=Path(tmp.name);p=root/'123';p.mkdir();(p/'stat').write_text('123 (child) '+' '.join(['Z',str(os.getpid())]+['0']*17+['12']));(p/'cmdline').write_bytes(b'');return tmp,root
 def test_matching_zombie_exited(self):
  tmp,root=self.process()
  with tmp:self.assertEqual(g.identity({'pid':123,'start_ticks':'12'},'worker',root)['state'],'exited')
 def test_mismatched_zombie_stays_mismatch(self):
  tmp,root=self.process()
  with tmp:self.assertEqual(g.identity({'pid':123,'start_ticks':'13'},'worker',root)['state'],'identity_mismatch')
 def test_reap_nonblocking(self):
  with mock.patch.object(g.os,'waitpid',side_effect=[(123,0),(0,0)]) as wait:g.reap_finished_children();self.assertEqual(wait.call_count,2);wait.assert_called_with(-1,os.WNOHANG)
 def test_unique_receipt(self):self.assertIn("directory/'coverage_v2_remaining8_activation.json'",(P/'coverage_v2_remaining8_handoff.py').read_text())
if __name__=='__main__':unittest.main()
