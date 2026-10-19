import ast,copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from contract import *
from presentation import layout_keys
from outcome import parent_costs
class ManualTests(unittest.TestCase):
 def test_source_and_producer_binding(self):
  p=read(HERE/'PROTOCOL.json');root=Path(p['root_local'])
  self.assertEqual(sha(root/'deploy_manifest.json'),p['producer_manifest_sha256']);self.assertEqual(sha(root/'configs/source.pose.json'),p['source_pose_sha256'])
  self.assertEqual(read(root/'configs/source.pose.json')['video']['sha256'],p['source_video_sha256']);self.assertEqual(p['comparators_order'],['Native','Auto','Manual']);self.assertEqual(set(p['parents']),{'Native'})
  self.assertEqual(p['manual_plan']['physical_span'],[56,127]);self.assertEqual(p['manual_plan']['latent_bins'],list(range(17,38)));self.assertEqual(p['manual_plan']['denoise_indices'],list(range(6,15)));self.assertEqual(sha(HERE/p['manual_plan']['file']),p['manual_plan']['sha256'])
 def test_parent_raw_bytes_and_math_exact(self):
  p=read(HERE/'PROTOCOL.json');old=Path('/Users/researcher/DevProjects/h3-timing-auto-source51310-r40-20261017')
  for a,b in [('Native.pose.json','native.pose.json'),('Native_job.json','native_job.json'),('manual_reference_plan.json','manual_reference_plan.NOT_RUN.json')]:self.assertEqual((HERE/'parents'/a).read_bytes(),(old/'analysis/postrun/parents'/b).read_bytes())
  for n in ('timing_metrics.py','pairwise_gain.py','physical_tolerance.py','scan_current_pose.py'):self.assertEqual((HERE/n).read_bytes(),(old/'scripts'/n).read_bytes())
  self.assertEqual(p['scientific_endpoints']['primary_event_window'],[64,95]);self.assertIn(['Native','Auto'],p['common_support_groups'])
 def test_inventory_exact_counts(self):
  s=(HERE/'remote_consume.py').read_text();tree=ast.parse(s);f={n.name:ast.get_source_segment(s,n) for n in tree.body if isinstance(n,ast.FunctionDef)}
  self.assertIn("len(c['branches'])==29",f['inventory']);self.assertIn('len(expected)==39',f['inventory']);self.assertIn("c['measurements']==[]",f['inventory']);self.assertNotIn('sha(f)',f['snapshot']);self.assertNotIn('torch',f['status'])
 def test_chinese_layout_real_dictionary_keys(self):
  p=read(HERE/'PROTOCOL.json');videos={k:Path(k) for k in ('SOURCE','Native','Auto','Manual')}
  for layout in p['presentation']['layouts'].values():
   self.assertEqual(layout_keys(videos,layout),layout['keys']);self.assertEqual(sha(HERE/layout['asset']),layout['asset_sha256'])
  layout=p['presentation']['layouts']['source_native_auto_manual'];self.assertEqual(layout['labels'],['1.参考视频','2.编辑后视频','3.自动时序干预','4.人工窗口引导'])
  with self.assertRaises(ValueError):layout_keys({'SOURCE':'s','Native':'n','auto':'wrong','Manual':'m'},layout)
  bad=copy.deepcopy(layout);bad['keys'][2]='Manual'
  with self.assertRaises(ValueError):layout_keys(videos,bad)
 def test_technical_exceptions_not_unknown_or_pose_reuse(self):
  s=(HERE/'outcome.py').read_text();self.assertIn("raw['provenance']==read(source)['provenance']",s);self.assertIn('technical pose error, not scientific UNKNOWN',s);self.assertIn('partial phase requires reviewed recovery',s)
 def test_parent_cost_evidence_tamper(self):
  with patch('outcome.sha',return_value='changed'):
   with self.assertRaises(ValueError):parent_costs({},read(HERE/'PROTOCOL.json'))
 def test_actual_auto_producer_manifest_not_interchangeable(self):
  from test_postrun import ParentTests
  with tempfile.TemporaryDirectory() as d:
   b,p=ParentTests().fixture(Path(d));p['auto_producer_manifest_sha256']='another producer'
   with self.assertRaises(ValueError):validate_auto_parent(b,p)
 def test_no_consumer_gpu_or_autostart(self):
  p=read(HERE/'PROTOCOL.json');self.assertTrue(p['no_gpu']);self.assertTrue(p['no_consumer_started']);self.assertFalse(read(HERE/'BINDING.template.json')['approved_for_consumer_start'])
  self.assertFalse((HERE/'BINDING.json').exists());self.assertFalse((HERE/'AUTO_PARENT_BINDING.json').exists())
if __name__=='__main__':unittest.main()
