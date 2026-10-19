import copy,hashlib,json,sys,unittest,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
from H3StaticWindowRouter.pair_gate import parent_condition_matches,historical_input_signature
from r37_contract import expected_graph,RUN_ID,SEED

def signed(tree):return {'tree':tree,'sha256':hashlib.sha256(json.dumps(tree,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()}
class NormalBindingTests(unittest.TestCase):
 def test_actual_full_parent_tree_except_two_corresponding_UUIDs(self):
  parent=json.loads((ROOT/'configs/parent_actual_condition_tree.json').read_text());self.assertTrue(parent_condition_matches(parent,parent))
  tree=copy.deepcopy(parent['tree']);token=str(uuid.uuid4());tree['original']['positive'][0]['uuid']=token;tree['processed']['positive'][0]['uuid']=token
  self.assertTrue(parent_condition_matches(signed(tree),parent))
  bad=copy.deepcopy(tree);bad['processed']['positive'][0]['model_conds']['minimax_payload']['cond']['seed']+=1
  with self.assertRaises(ValueError):parent_condition_matches(signed(bad),parent)
  bad=copy.deepcopy(tree);bad['processed']['positive'][0]['uuid']=str(uuid.uuid4())
  with self.assertRaises(ValueError):parent_condition_matches(signed(bad),parent)
  bad=signed(tree);bad['sha256']='wrong'
  with self.assertRaises(ValueError):parent_condition_matches(bad,parent)
 def test_actual_historical_input_signature_and_no_tensor_claim(self):
  records=json.loads((ROOT/'PROTOCOL.json').read_text())['pairing']['actual_prefix_evidence']
  self.assertEqual([r['index'] for r in records],list(range(5)))
  for r in records:
   proof=historical_input_signature({'same_input':r['native_input_signature']},r)
   self.assertTrue(proof['historical_packed_input_signature_equal']);self.assertFalse(proof['historical_packed_input_tensor_entity_comparison'])
   bad=copy.deepcopy(r['native_input_signature']);bad['sha256']='wrong'
   with self.assertRaises(ValueError):historical_input_signature({'same_input':bad},r)
 def test_normal_graph_only_static_router_and_admin_paths_change(self):
  parent=json.loads((ROOT/'configs/parent_graph.json').read_text());actual=expected_graph();self.assertEqual(SEED,2026101313)
  changes=[]
  def walk(a,b,p=''):
   if isinstance(a,dict) and isinstance(b,dict):
    for k in set(a)|set(b):walk(a.get(k),b.get(k),p+'/'+k)
   elif a!=b:changes.append(p)
  walk(parent,actual)
  allowed={'/14/inputs/filename_prefix','/5/inputs/audit_dir','/5/inputs/run_id','/50/class_type','/50/inputs/audit_dir','/50/inputs/run_id','/51/inputs/run_id','/51/inputs/source_audit_dir','/51/inputs/source_run_id','/52/inputs/output_dir','/52/inputs/run_id','/6/inputs/audit_dir','/6/inputs/pair_id','/6/inputs/run_id'}
  self.assertEqual(set(changes),allowed)
  self.assertEqual(actual['6']['inputs']['noise_seed'],SEED);self.assertEqual(actual['50']['class_type'],'H3StaticWindowRouter')
 def test_R34_transaction_and_R27_kernel_byte_reuse(self):
  old=ROOT.parent/'h3-timing-fixed-early-global-r34-20261017'
  for n in ['core.py','static_plan.py','dynamic_support.py','guards.py','signatures.py']:
   p=ROOT/'extensions/H3StaticWindowRouter'/n
   if p.exists() and (old/'extensions/H3StaticWindowRouter'/n).exists():self.assertEqual(p.read_bytes(),(old/'extensions/H3StaticWindowRouter'/n).read_bytes())
if __name__=='__main__':unittest.main()
