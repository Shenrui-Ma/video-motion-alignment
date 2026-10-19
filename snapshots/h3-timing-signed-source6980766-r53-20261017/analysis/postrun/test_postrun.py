import copy,json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import contract as c
import evaluate
class ContractTests(unittest.TestCase):
 def fixture_release(self,root,arc,new):
  (root/'configs').mkdir();(arc/'configs').mkdir();c.save(root/'configs/queue.json',new);c.save(arc/'configs/queue.json',{'jobs':['one'],'finalize':False});c.save(arc/'FILE_INVENTORY.json',{'configs/queue.json':{'sha256':c.sha(arc/'configs/queue.json')}})
 def test_integer_finalize_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'root';arc=Path(d)/'arc';root.mkdir();arc.mkdir();self.fixture_release(root,arc,{'jobs':['one'],'finalize':1})
   with self.assertRaisesRegex(ValueError,'false->true'):c.verify_source_archive(root,arc,{},'one')
 def test_true_release_exact_gate(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'root';arc=Path(d)/'arc';root.mkdir();arc.mkdir();self.fixture_release(root,arc,{'jobs':['one'],'finalize':True});owner={'pid':4,'identity':{'start_ticks':'a'}};c.save(arc/'RUN_GATE.json',{'passed':True,'run_id':'one','owner':owner});(root/'audit').mkdir();c.save(root/'audit/root_release_request.json',{'pid':4,'owner':owner['identity'],'gate_file':str(arc/'RUN_GATE.json'),'gate_sha256':c.sha(arc/'RUN_GATE.json'),'unix':(arc/'RUN_GATE.json').stat().st_mtime+1});self.assertTrue(c.verify_source_archive(root,arc,owner,'one')['all_other_scientific_files_unchanged'])
 def test_technical_not_unknown(self):
  with self.assertRaises(ValueError):c.observer_summary({'status':'error','windows':[]})
  self.assertEqual(c.observer_summary({'status':'unknown_visibility','windows':[]})['all_denominator'],0)
 def test_fullscan_missing_rows_rejected(self):
  with self.assertRaises(ValueError):c.observer_summary({'status':'measured','windows':[]})
 def test_replay_wrong_source_value_summary_rejected(self):
  expected={'index':3,'scan_sha256':'a','producer_observer_sha256':'a','pose_sha256':'b','source_pose_sha256':'c','summary':{'rows':186}}
  record=dict(expected,passed=True,all_numeric_values_equal=True);self.assertTrue(c.validate_replay(record,expected))
  for key in expected:
   bad=copy.deepcopy(record);bad[key]='wrong'
   with self.subTest(key=key),self.assertRaises(ValueError):c.validate_replay(bad,expected)
 def test_unknown_replay_binding_current_pose(self):
  with tempfile.TemporaryDirectory() as d:
   arc=Path(d);root=Path('/producer');source=arc/'configs/source.pose.json';pose=arc/'audit/obs/pose.json';response=arc/'audit/obs/response.json';c.save(source,{'source':1});c.save(pose,{'pose':2});c.save(response,{'pose':{'file':str(root/'audit/obs/pose.json'),'sha256':c.sha(pose)}});ob={'physical_index':0,'status':'unknown_visibility','source_pose_sha256':c.sha(source),'edited_pose_sha256':c.sha(pose),'windows':[]};m={'physical_index':0,'status':'complete','response_file':str(root/'audit/obs/response.json'),'response_sha256':c.sha(response),'observer':ob};c.save(arc/'audit/counterfactual/run.json',{'counterfactual':{'measurements':[m]}})
   self.assertEqual(c.replay_binding(arc,root,'run',0)['summary']['all_denominator'],0);c.save(pose,{'pose':3})
   with self.assertRaises(ValueError):c.replay_binding(arc,root,'run',0)
 def complete_fixture(self,arc):
  c.save(arc/'original.json',{'input':1});c.save(arc/'FILE_INVENTORY.json',{'original.json':{'sha256':c.sha(arc/'original.json')}})
  names=['RUN_GATE.json','RUNTIME_GATE.json','DECISION_LEDGER.json','verify.log','ADMIN_ADMISSION_AT_ARCHIVE.json']+[f'observer_replay/{i:03d}.json' for i in range(20)]+['final/pose.json']
  for n in names:c.save(arc/n,{'fixture':n})
  c.save(arc/'CPU_COMPLETE.json',{'passed':True,'observer_replay_indices':list(range(20)),'derived_outputs':['final/pose.json']});names+=['CPU_COMPLETE.json'];c.save(arc/'DERIVED_FILES.json',{n:c.sha(arc/n) for n in names})
 def test_complete_exact_inventory(self):
  with tempfile.TemporaryDirectory() as d:self.complete_fixture(Path(d));self.assertTrue(c.validate_complete_inventory(Path(d))['passed'])
 def test_extra_file_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   arc=Path(d);self.complete_fixture(arc);c.save(arc/'extra.json',{})
   with self.assertRaises(ValueError):c.validate_complete_inventory(arc)
 def test_missing_file_and_deleted_manifest_entry_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   arc=Path(d);self.complete_fixture(arc);name='final/pose.json';(arc/name).unlink();m=c.read(arc/'DERIVED_FILES.json');del m[name];c.save(arc/'DERIVED_FILES.json',m)
   with self.assertRaises(ValueError):c.validate_complete_inventory(arc)
 def test_missing_replay_or_edited_output_rejected(self):
  for op in ('missing','corrupt'):
   with tempfile.TemporaryDirectory() as d:
    arc=Path(d);self.complete_fixture(arc)
    if op=='missing':(arc/'observer_replay/019.json').unlink()
    else:c.save(arc/'final/pose.json',{'changed':1})
    with self.assertRaises(ValueError):c.validate_complete_inventory(arc)
 def test_region_support_no_oracle_window(self):
  ledger={'rows':[{'chosen':'full','decision':{'physical_intervals':[[2,3],[7,9]],'latent_bins':[1,2]}}]};r=evaluate.region_sets(ledger,{'windows':[],'descriptive_windows':[[0,140]]});self.assertEqual(r['actual_physical_union'],[2,3,7,8,9]);self.assertEqual(r['actual_bin_support_union'],list(range(1,9)));self.assertEqual(set(r['actual_bin_support_union'])|set(r['actual_bin_support_complement']),set(range(141)))
class DeliveryTests(unittest.TestCase):
 complete_fixture=ContractTests.complete_fixture
 def test_local_exact_inventory(self):
  with tempfile.TemporaryDirectory() as d:
   arc=Path(d);self.complete_fixture(arc);self.assertTrue(c.validate_local_inventory(arc)['all_large_PT_verified_remote']);c.save(arc/'old_extra.json',{})
   with self.assertRaises(ValueError):c.validate_local_inventory(arc)
 def test_local_missing_output(self):
  with tempfile.TemporaryDirectory() as d:
   arc=Path(d);self.complete_fixture(arc);(arc/'final/pose.json').unlink()
   with self.assertRaises((ValueError,FileNotFoundError)):c.validate_local_inventory(arc)
 def test_playback_full_pts_and_gap(self):
  p={'streams':[{'width':1312,'height':736,'r_frame_rate':'24/1','avg_frame_rate':'24/1','duration':'5.875000','time_base':'1/12288'}],'frames':[{'best_effort_timestamp_time':str(i/24)} for i in range(141)]};self.assertTrue(c.check_playback_probe(p)['passed']);p['frames'][50]['best_effort_timestamp_time']=str(51/24)
  with self.assertRaises(ValueError):c.check_playback_probe(p)
class MetricTests(unittest.TestCase):
 def test_common_support_shared_min_and_missing_joint(self):
  import numpy as np
  class M:
   clean=staticmethod(lambda x:x)
   @staticmethod
   def load_pose(path,t):return data[path]
  def item(x,w):
   obj={'frames':np.arange(141)}
   for feat,conf in [('arm_direction','arm_conf'),('wrist_relative','wrist_conf'),('body_xy','body_conf'),('left_arm_direction','left_arm_conf'),('right_arm_direction','right_arm_conf')]:obj[feat]=np.full((141,2,2),x,dtype=float);obj[conf]=np.full((141,2),w)
   return obj
  data={'s':item(0.,1.),'a':item(1.,.8),'b':item(2.,.5)};data['b']['arm_direction'][0,0]=np.nan
  result=evaluate.common_regions('s',{'a':'a','b':'b'},{'two':[0,1]},.3,M);row=result['rows'][0];self.assertEqual(row['common_valid_joint_frames'],3);self.assertEqual(row['common_weight_sum'],1.5);self.assertAlmostEqual(row['runs']['a']['same_frame_error_on_common_support'],2**.5);self.assertAlmostEqual(row['runs']['b']['same_frame_error_on_common_support'],2*2**.5)
 def test_torso_unknown_preserved_other_errors_raise(self):
  class M:
   @staticmethod
   def load_pose(p,t):raise ValueError(evaluate.UNKNOWN)
  self.assertEqual(evaluate.fixed_metrics('s',{'a':'a'},[[0,15]],[.3],M)['a']['0.3']['status'],'unknown_visibility')
  with patch.object(M,'load_pose',side_effect=ValueError('broken JSON')),self.assertRaises(ValueError):evaluate.fixed_metrics('s',{'a':'a'},[[0,15]],[.3],M)
if __name__=='__main__':unittest.main()
