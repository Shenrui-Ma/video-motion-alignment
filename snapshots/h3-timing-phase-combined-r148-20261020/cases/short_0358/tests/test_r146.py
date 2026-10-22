import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r132_contract as c,gpu_query as g
class Contracts(unittest.TestCase):
 def test_scope(self):
  jobs,order=c.registry();s=c.science();graph=c.expected_graph();i=graph['50']['inputs']
  self.assertEqual(len(order),1);self.assertEqual((i['step_start'],i['step_end'],i['alpha'],i['block_start'],i['block_end']),(6,15,1.,0,50))
  self.assertEqual(graph['6']['inputs']['pair_id'],s['noise_pair_id']);self.assertEqual(graph['6']['inputs']['noise_seed'],s['cases'][0]['seed'])
  self.assertNotIn('2',graph);self.assertEqual(graph['5']['class_type'],'H3CachedReferenceConditioning')
 def test_only_exact_unavailable_rows(self):
  uuid=next(iter(g.QUARANTINED));rows,excluded=g.parse_compute(uuid+', [N/A], [N/A]','GPU-selected');self.assertEqual(rows,[]);self.assertEqual(len(excluded),1)
  rows,_=g.parse_compute(uuid+', 1646285, 100','GPU-selected');self.assertEqual(rows[0]['pid'],1646285)
 def test_unknown_and_selected_rejected(self):
  for row in ['GPU-selected, [N/A], [N/A]',next(iter(g.QUARANTINED))+', 123, [N/A]']:
   with self.assertRaises(ValueError):g.parse_compute(row,'GPU-selected')
  rows,excluded=g.parse_compute('GPU-unrelated, [N/A], [N/A]','GPU-selected');self.assertEqual(rows,[]);self.assertEqual(len(excluded),1)
  with self.assertRaises(ValueError):g.parse_compute('GPU-other, broken, 15','GPU-selected')

class Deployment(unittest.TestCase):
 def test_actual_command_whitelists_cached_loader(self):
  import service
  import ast
  source=(ROOT/'scripts/service.py').read_text();tree=ast.parse(source)
  values=[node.value for node in ast.walk(tree) if isinstance(node,ast.Constant) and isinstance(node.value,str)]
  self.assertIn('H3CachedCondition',values)
  self.assertIn("'H3CachedCondition']:",(ROOT/'scripts/launch_remote.py').read_text())
