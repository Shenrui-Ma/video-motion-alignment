import importlib.util,unittest,copy,json
from pathlib import Path
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('gate',P/'partial_remaining8_handoff.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
class Tests(unittest.TestCase):
 def test_unique_target(self): self.assertEqual(len(g.merge_manifest(g.REQ['base'],g.REQ['pilots'])['jobs']),46)
 def test_duplicate_rejected(self):
  with self.assertRaises(ValueError):g.merge_manifest(g.REQ['base'],g.REQ['base'])
 def test_pilots_wait(self):self.assertFalse(g.preceding_status({g.REQ['pilot_ids'][0]:{'status':'completed'}},g.REQ['pilot_ids']))
 def test_pilots_failed(self):
  with self.assertRaises(RuntimeError):g.preceding_status({g.REQ['pilot_ids'][0]:{'status':'failed'}},g.REQ['pilot_ids'])
 def test_graphs(self):
  for j in g.REQ['pilots']['jobs']:
   d=json.loads((P/j['graph']).read_text());n=d['50'];self.assertEqual(n['class_type'],'H3PartialRoPE');self.assertEqual(n['inputs']['alpha'],.25);self.assertEqual(n['inputs']['delta_mode'],'reference_origin');self.assertEqual(n['inputs']['schedule'],'all');self.assertEqual(json.loads(n['inputs']['frequency_mask']),[0]*8+[1]*8);self.assertEqual(d['52']['inputs']['model'],['50',0])
 def test_no_wrong_namespace(self):
  source=(P/'partial_remaining8_handoff.py').read_text();self.assertNotIn("directory/'direction_activation.json'",source);self.assertNotIn("directory/'partial_activation.json'",source)
 def test_no_silent_mutation(self):
  for j in g.REQ['pilots']['jobs']:
   d=json.loads((P/j['graph']).read_text());sid=j['id'].replace('_partial_temporal_rope','_direction_gated');original=json.loads((P.parents[3]/'direction_package/host41/graphs'/f'{sid}.json').read_text())
   for k in set(d)-{'14','50'}:self.assertEqual(d[k],original[k])
if __name__=='__main__':unittest.main()
