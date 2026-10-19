import copy,hashlib,json,sys,tempfile,unittest,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'scripts'),str(R/'extensions')]
from parent_binding import check
from r44_contract import expected_graph
class NewCaseEvidenceTests(unittest.TestCase):
 def test_all_raw_evidence_bytes_bound(self):
  bound=json.loads((R/'configs/parent_evidence_bindings.json').read_text())
  for name,v in bound.items():self.assertEqual(hashlib.sha256((R/'configs'/name).read_bytes()).hexdigest(),v['sha256'],name)
  self.assertEqual(hashlib.sha256((R/'configs/source.pose.json').read_bytes()).hexdigest(),'20d6079ec8eb3e9824f599a23447bc122c49d796289f4408345eda4e3645946c')
 def test_actual21_endpoint_and_embedding_inventory(self):
  result=check(R,remote=False);self.assertEqual(result['available_native_indices'],list(range(20)))
  c=json.loads((R/'configs/parent_conditioning.json').read_text());inventory=json.loads((R/'configs/parent_file_inventory.json').read_text())
  self.assertEqual(c['packed_layout']['seq_len'],87366);self.assertEqual(inventory['audit/'+c['conditioning_embedding']['tensor_file']]['bytes'],137914056)
 def test_parent_graph_scientific_inputs_and_capture_unmodified(self):
  p=json.loads((R/'configs/parent_graph.json').read_text());case=json.loads((R/'configs/protocol.json').read_text())['cases'][0];g=expected_graph(p,case)
  for n in ('1','2','3','4','7','8','9','10','11','12','13','21','22','23','41'):self.assertEqual(g[n],p[n],n)
  for key in ('prompt','width','height','length','semantic_fps','phase_frames','clip','vae','ref_image','ref_video'):self.assertEqual(g['5']['inputs'][key],p['5']['inputs'][key],key)
  self.assertEqual(g['6']['inputs']['noise_seed'],2026101701)
 def test_wrong_source_parent_gate_history_or_capture_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);shutil.copytree(R/'configs',root/'configs')
   for name,key,val in [('parent_runtime_gate.json','checks',{'bad':False}),('parent_captures.json','seed',2026101311),('parent_run_gate.json','file_inventory_sha256','wrong')]:
    path=root/'configs'/name;original=path.read_bytes();obj=json.loads(original);obj[key]=val;path.write_text(json.dumps(obj))
    with self.assertRaises(ValueError,msg=name):check(root,False)
    path.write_bytes(original)
if __name__=='__main__':unittest.main()
