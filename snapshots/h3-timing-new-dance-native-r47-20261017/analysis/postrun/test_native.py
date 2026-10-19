import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from contract import *
from presentation import layout_keys

class NativeTests(unittest.TestCase):
 def test_two_fixed_sources_identities_and_predeclared_coverage(self):
  p=read(HERE/'PROTOCOL.json')
  self.assertEqual([c['source_id'] for c in p['cases']],['10264579','6980766'])
  self.assertEqual([c['identity'] for c in p['cases']],['Sam Altman','Elon Musk'])
  for c in p['cases']:
   self.assertEqual(c['seed'],2026101701)
   self.assertEqual(c['windows'],[[0,31],[32,63],[64,95],[96,127],[125,140],[0,140]])
   self.assertIn('no preselected failure',c['window_scope'])
  self.assertEqual(p['fixed_visual_frames'],[0,24,48,72,96,120,140]);self.assertEqual(p['scan_rows'],186)
 def test_actual_source_design_and_producer_seal(self):
  p=read(HERE/'PROTOCOL.json');root=Path(p['root_local'])
  self.assertEqual((HERE/'SOURCE_DESIGN.json').read_bytes(),(root/'design/PROTOCOL.json').read_bytes())
  self.assertEqual(sha(root/'deploy_manifest.json'),p['producer_manifest_sha256'])
  self.assertTrue(check_declared_cases(p,read(root/'configs/scientific_contract.json')))
 def test_math_and_renderer_byte_identical_to_R43(self):
  old=HERE.parents[2]/'h3-timing-source51765-native-r43-20261017/analysis/postrun'
  for n in ('evaluate.py','timing_metrics.py','pairwise_gain.py','physical_tolerance.py','scan_current_pose.py','presentation.py'):
   self.assertEqual((HERE/n).read_bytes(),(old/n).read_bytes())
 def test_chinese_caption_exact_two_columns(self):
  p=read(HERE/'PROTOCOL.json');row=p['presentation']['layouts']['source_native']
  self.assertEqual(layout_keys({'SOURCE':1,'Native':2},row),['SOURCE','Native'])
  self.assertEqual(row['labels'],['1.参考视频','2.编辑后视频']);self.assertEqual(sha(HERE/row['asset']),row['asset_sha256'])
  with self.assertRaises(ValueError):layout_keys({'SOURCE':1,'NATIVE':2},row)
 def test_one_actual_render_per_case_and_all_pose_binding(self):
  s=(HERE/'remote_consume.py').read_text()
  self.assertEqual(s.count("render_layout({'SOURCE':sourcevideo,'Native':video}"),1)
  self.assertNotIn("media_and_pixels({'SOURCE':sourcevideo",s)
  self.assertIn("raw['provenance']==read(source)['provenance']",s);self.assertIn('technical pose failure',s)
  self.assertIn("'runtime_cost_evidence':read(ARC/'RUNTIME_GATE.json')['runs'][run]",s)
 def test_whole_scan_regions_cover_all62_windows(self):
  windows=[]
  for length in (16,32):
   for a in sorted(set(range(0,141-length+1,4))|{141-length}):windows.append((a,a+length-1))
  self.assertEqual(len(windows),62)
  self.assertIn("regions[f'scan_{a}_{a+length-1}']",(HERE/'remote_consume.py').read_text())
 def test_prepared_binding_not_started(self):
  p=read(HERE/'PROTOCOL.json');b=read(HERE/'BINDING.template.json')
  self.assertIs(b['approved_for_consumer_start'],False)
  self.assertEqual(b['protocol_sha256'],sha(HERE/'PROTOCOL.json'))
  self.assertEqual(b['producer_manifest_sha256'],p['producer_manifest_sha256'])
  self.assertFalse((HERE/'BINDING.json').exists())
  self.assertEqual(sha(HERE/'EVALUATION_BINDING.json'),p['evaluation_addendum']['sha256'])
class IdentityTests(unittest.TestCase):
 def test_source_identity_prompt_and_order_swaps_rejected(self):
  p=read(HERE/'PROTOCOL.json');producer=read(Path(p['root_local'])/'configs/scientific_contract.json')
  for key in ('source_id','identity','prompt','portrait_sha256','video_sha256','run_id'):
   q=copy.deepcopy(p);q['cases'][1][key]=q['cases'][0][key]
   with self.subTest(key=key),self.assertRaises(ValueError):check_declared_cases(q,producer)
  q=copy.deepcopy(p);q['cases'].reverse()
  with self.assertRaises(ValueError):check_declared_cases(q,producer)
 def test_both_case_summaries_need_exact_source_identity(self):
  p=read(HERE/'PROTOCOL.json')
  for case in p['cases']:
   s={k:case[k] for k in ('run_id','source_id','seed','identity','portrait_sha256')}
   s.update(passed=True,source_video_sha256=case['video_sha256'],NFE=20,actual_routed_blocks=0,all_UNKNOWN_retained=True)
   self.assertTrue(check_case_summary(s,case))
   for key,value in [('identity','wrong'),('source_video_sha256','bad'),('NFE',19),('actual_routed_blocks',50),('all_UNKNOWN_retained',False)]:
    with self.subTest(key=key),self.assertRaises(ValueError):check_case_summary(dict(s,**{key:value}),case)
 def test_technical_scan_failures_are_not_unknown(self):
  with self.assertRaises(ValueError):observer_summary({'status':'failed','windows':[]})
  r=observer_summary({'status':'unknown_visibility','windows':[],'reasons':['occluded']})
  self.assertEqual(r['known_denominator'],0);self.assertEqual(r['all_denominator'],0);self.assertEqual(r['scientific_status'],'unknown_visibility')
class PortablePreparationTests(unittest.TestCase):
 def test_empty_parent_directory_created_before_sync(self):
  import one_phase
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'PROTOCOL.json').write_text('{}');save(root/'FREEZE.json',{'files':{}});save(root/'BINDING.json',{'approved_for_consumer_start':True,'protocol_sha256':sha(root/'PROTOCOL.json')})
   calls=[]
   def fake(cmd,**kw):
    if cmd[0]=='rsync':self.assertTrue((root/'parents').is_dir())
    calls.append(cmd)
   with patch.object(one_phase,'HERE',root),patch.object(one_phase.subprocess,'run',side_effect=fake):one_phase.prepare()
   self.assertEqual(len(calls),2)
if __name__=='__main__':unittest.main()

