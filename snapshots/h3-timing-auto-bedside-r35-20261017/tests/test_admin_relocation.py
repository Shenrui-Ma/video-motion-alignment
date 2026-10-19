import copy,hashlib,json,sys,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'scripts'),str(R/'extensions')]
from observer_import import t
from r35_contract import expected_graph
class AdministrativeRelocationTests(unittest.TestCase):
 def read(self,name):return json.loads((R/name).read_text())
 def test_observer_and_actuator_exact_except_source_binding(self):
  old=self.read('configs/inherited_policy.json')
  new=self.read('configs/protocol.json');observer=copy.deepcopy(new['observer']);observer['source_pose_sha256']=old['observer']['source_pose_sha256'];self.assertEqual(observer,old['observer']);self.assertEqual(new['actuator'],old['actuator'])
 def test_17_numerical_files_identical(self):
  spec=self.read('configs/r27_inheritance.json');self.assertEqual(len(spec['exact_numerical_files']),17)
  for rel,digest in spec['exact_numerical_files'].items():self.assertEqual(hashlib.sha256((R/rel).read_bytes()).hexdigest(),digest)
 def test_exact_new_device_and_peer(self):
  import service
  self.assertEqual(service.GPU,t.MAIN_UUID);self.assertEqual(service.PORT,8497);self.assertEqual(t.MAIN_UUID,t.DECODER_UUID);self.assertEqual(t.MAIN_UUID,'GPU-REDACTED');self.assertEqual(t.SECOND_TASK_UUID,'GPU-REDACTED');self.assertNotEqual(t.SECOND_TASK_UUID,t.MAIN_UUID)
 def test_graph_and_input_metadata_unchanged(self):
  case=self.read('configs/protocol.json')['cases'][0];g=self.read('configs/'+case['run_id']+'.json');self.assertEqual(g,expected_graph(self.read('configs/parent_graph.json'),case));self.assertEqual(case['seed'],2026101311);self.assertEqual(case['source_id'],'07_real_ary_v')
 def test_default_admission_denies(self):
  self.assertTrue(t.admission_document(False)['root_live_review_required'])
  with self.assertRaises(ValueError):t.admission_document(True)
 def test_protocol_and_all_evidence_binding(self):
  t.bindings();self.assertEqual(t.sha(R/'configs/protocol.json'),t.PROTOCOL_SHA)
if __name__=='__main__':unittest.main()
