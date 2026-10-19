import ast,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from contract import *
class MatchedTests(unittest.TestCase):
 def test_all_five_methods_and_dose_boundary(self):
  p=read(HERE/'PROTOCOL.json')
  self.assertEqual(p['comparators_order'],['Native','GlobalFull6to14','Auto','EarlyGlobalPulse','MatchedGlobal'])
  self.assertEqual(set(p['parents']),{'Native','GlobalFull6to14','EarlyGlobalPulse'})
  self.assertIn('not dose-matched',p['scope']);self.assertIn('not manual per-event ground truth',p['scope'])
  self.assertEqual(p['producer_manifest_sha256'],sha(Path(p['root_local'])/'deploy_manifest.json'))
  self.assertEqual(p['source_pose_sha256'],sha(Path(p['root_local'])/'configs/source.pose.json'))
 def test_snapshot_exact_counts_and_no_models_in_status(self):
  s=(HERE/'remote_consume.py').read_text();tree=ast.parse(s);func={n.name:ast.get_source_segment(s,n) for n in tree.body if isinstance(n,ast.FunctionDef)}
  self.assertIn("len(c['branches'])==24",func['inventory']);self.assertIn('len(expected)==29',func['inventory'])
  self.assertNotIn('sha(f)',func['snapshot']);self.assertNotIn('torch',func['status'])
 def test_completed_static_parent_wrong_pose_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);(r/'output').mkdir();(r/'output/r.mp4').write_bytes(b'video');(r/'pose.json').write_text('{}')
   save(r/'FILE_INVENTORY.json',{'configs/source.pose.json':{'sha256':'source'},'output/r.mp4':{'sha256':sha(r/'output/r.mp4')}})
   save(r/'CPU_COMPLETE.json',{'passed':True,'run_id':'r','phases':list(PHASES)})
   save(r/'RUN_GATE.json',{'passed':True,'run_id':'r','file_inventory_sha256':sha(r/'FILE_INVENTORY.json')})
   save(r/'DERIVED_FILES.json',{'CPU_COMPLETE.json':sha(r/'CPU_COMPLETE.json'),'pose.json':sha(r/'pose.json')})
   row={'archive_root':str(r),'required_files':{n:sha(r/n) for n in ('RUN_GATE.json','CPU_COMPLETE.json','FILE_INVENTORY.json','DERIVED_FILES.json')},'source_pose_sha256':'source','pose_relative':'pose.json','pose_sha256':sha(r/'pose.json'),'video':str(r/'output/r.mp4'),'video_sha256':sha(r/'output/r.mp4')}
   self.assertEqual(validate_completed_static_parent(row)['run_id'],'r')
   (r/'pose.json').write_text('changed')
   with self.assertRaises(ValueError):validate_completed_static_parent(row)
 def test_parent_cost_tamper_rejected(self):
  with patch('contract.sha',return_value='bad'):
   with self.assertRaises(ValueError):checked_parent_costs()
 def test_current_pose_provenance_checked_without_exception(self):
  s=(HERE/'outcome.py').read_text();self.assertIn("raw['provenance']==read(source)['provenance']",s)
if __name__=='__main__':unittest.main()
