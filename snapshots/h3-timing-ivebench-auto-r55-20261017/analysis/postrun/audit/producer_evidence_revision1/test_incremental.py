import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import contract as c
import incremental_case as inc
import remote_consume as remote
import test_postrun as fixtures

class IncrementalTests(unittest.TestCase):
 def test_partial_gate_keeps_fixed_denominator(self):
  run=inc.P['cases'][0]['run_id'];value={'status':'pass','partial_batch':True,'planned_denominator':5,'verified_runs':[run],'cases':[{'run':run}]}
  inc.validate_partial_gate(value,run)
  for key,v in [('partial_batch',False),('planned_denominator',1),('verified_runs',[run,'other']),('cases',[])]:
   with self.assertRaises(ValueError):inc.validate_partial_gate(dict(value,**{key:v}),run)
 def test_unknown_case_rejected(self):
  with self.assertRaises(ValueError):inc.case_for('invented')
 def test_selected_case_inventory_ignores_unfinished_other_case(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);fixtures.InventoryTests().fixture(root);case=inc.P['cases'][0]
   for other in inc.P['cases'][1:]:(root/'logs'/f'{other["run_id"]}_history.json').unlink()
   with patch.object(remote,'ROOT',root):paths=remote.inventory([case])
   rels=[str(x.relative_to(root)) for x in paths]
   self.assertEqual(sum('/x0/' in x and x.endswith('.pt') for x in rels),21)
   self.assertEqual(sum(x.endswith('/request.json') for x in rels),20)
 def test_relative_source_pose_paths_are_resolved_under_producer(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);fixtures.InventoryTests().fixture(root);protocol=c.read(root/'configs/protocol.json')
   for case in protocol['cases']:case['source_pose_path']=str(Path(case['source_pose_path']).relative_to(root))
   c.save(root/'configs/protocol.json',protocol)
   with patch.object(remote,'ROOT',root):paths=remote.inventory([inc.P['cases'][0]])
   self.assertIn(root/protocol['cases'][0]['source_pose_path'],paths)
   protocol['cases'][0]['source_pose_path']='../outside.pose.json';c.save(root/'configs/protocol.json',protocol)
   with patch.object(remote,'ROOT',root),self.assertRaises(ValueError):remote.inventory([inc.P['cases'][0]])
 def fixture_reuse(self,base):
  run=inc.P['cases'][0]['run_id'];src=base/'completed_cases'/run;final=src/'final'/run;full=base/'captured/batch';final.mkdir(parents=True);full.mkdir(parents=True)
  row={'sha256':'same','bytes':4};c.save(src/'FILE_INVENTORY.json',{'source.pt':row});c.save(full/'FILE_INVENTORY.json',{'source.pt':row});c.save(full/'RUN_GATE.json',{'passed':True});c.save(src/'CASE_RUNTIME_GATE.json',{'status':'pass'})
  (final/'score.mp4').write_bytes(b'exact score');c.save(final/'SUMMARY.json',{'passed':True});c.save(final/'CASE_FILES.json',{n:c.sha(final/n) for n in ('score.mp4','SUMMARY.json')})
  c.save(src/'CASE_READY.json',{'partial_batch':True,'planned_denominator':5,'run_id':run,'file_inventory_sha256':c.sha(src/'FILE_INVENTORY.json'),'runtime_gate_sha256':c.sha(src/'CASE_RUNTIME_GATE.json'),'case_files_sha256':c.sha(final/'CASE_FILES.json')})
  return src,final,full
 def test_full_batch_reuses_exact_score_bytes(self):
  with tempfile.TemporaryDirectory() as d:
   base=Path(d);src,final,full=self.fixture_reuse(base);dest=full/'final'/inc.P['cases'][0]['run_id']
   with patch.object(remote,'HERE',base),patch.object(remote,'ARC',full),patch.object(remote,'check_case_summary'):
    self.assertTrue(remote.reuse_incremental_case(inc.P['cases'][0],dest))
   self.assertEqual(c.sha(final/'score.mp4'),c.sha(dest/'score.mp4'));self.assertTrue(c.read(dest/'REUSED_INCREMENTAL.json')['all_original_dependencies_equal'])
 def test_reuse_rejects_input_or_output_change(self):
  for mode in ('input','output'):
   with tempfile.TemporaryDirectory() as d:
    base=Path(d);src,final,full=self.fixture_reuse(base)
    if mode=='input':c.save(full/'FILE_INVENTORY.json',{'source.pt':{'sha256':'changed','bytes':4}})
    else:(final/'score.mp4').write_bytes(b'changed')
    with patch.object(remote,'HERE',base),patch.object(remote,'ARC',full),patch.object(remote,'check_case_summary'),self.assertRaises(ValueError):remote.reuse_incremental_case(inc.P['cases'][0],full/'final/out')
if __name__=='__main__':unittest.main()
