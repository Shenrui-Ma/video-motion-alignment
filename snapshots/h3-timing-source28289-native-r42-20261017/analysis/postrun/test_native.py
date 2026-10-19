import ast,json,unittest
from pathlib import Path
from contract import *
from presentation import layout_keys
class NativeTests(unittest.TestCase):
 def test_single_native_no_event_window(self):
  p=read(HERE/'PROTOCOL.json');self.assertEqual(len(p['cases']),1);c=p['cases'][0];self.assertEqual((c['source_id'],c['seed']),('28289',2026101701));self.assertEqual(c['windows'],[[0,31],[32,63],[64,95],[96,127],[125,140],[0,140]]);self.assertIn('no preselected failure',c['window_scope']);self.assertEqual(p['fixed_visual_frames'],[0,24,35,48,70,72,96,105,120,140]);self.assertEqual(p['scan_rows'],186)
 def test_actual_source_design_byte_exact(self):
  p=read(HERE/'PROTOCOL.json');root=Path(p['root_local']);self.assertEqual((HERE/'SOURCE_DESIGN.json').read_bytes(),(root/'design/PROTOCOL.json').read_bytes());self.assertEqual(sha(root/'deploy_manifest.json'),p['producer_manifest_sha256'])
 def test_all_math_reused_original(self):
  old=HERE.parents[2]/'h3-timing-new-actions-native-r38-20261017/analysis/postrun'
  for n in ('contract.py','evaluate.py','timing_metrics.py','pairwise_gain.py','physical_tolerance.py','scan_current_pose.py'):self.assertEqual((HERE/n).read_bytes(),(old/n).read_bytes())
 def test_renderer_body_same_and_two_actual_keys(self):
  q=HERE.parents[2]/'h3-timing-manual-source51310-r41-20261017/analysis/postrun/presentation.py';a=q.read_text();b=(HERE/'presentation.py').read_text();get=lambda s:next(ast.get_source_segment(s,n) for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name=='render_layout');self.assertEqual(get(a),get(b))
  p=read(HERE/'PROTOCOL.json');row=p['presentation']['layouts']['source_native'];self.assertEqual(layout_keys({'SOURCE':1,'Native':2},row),['SOURCE','Native']);self.assertEqual(row['labels'],['1.参考视频','2.编辑后视频']);self.assertEqual(sha(HERE/row['asset']),row['asset_sha256'])
  with self.assertRaises(ValueError):layout_keys({'SOURCE':1,'NATIVE':2},row)
 def test_source_and_target_provenance_required(self):
  s=(HERE/'remote_consume.py').read_text();self.assertIn("raw['provenance']==read(source)['provenance']",s);self.assertIn('technical pose failure',s);self.assertIn("len(P['cases'])",s)
 def test_common_support_covers_every_scan(self):
  windows=[]
  for length in (16,32):
   for a in sorted(set(range(0,141-length+1,4))|{141-length}):windows.append((a,a+length-1))
  self.assertEqual(len(windows),62);self.assertTrue(all(0<=a<=b<=140 for a,b in windows));s=(HERE/'remote_consume.py').read_text();self.assertIn("regions[f'scan_{a}_{a+length-1}']",s)
if __name__=='__main__':unittest.main()
