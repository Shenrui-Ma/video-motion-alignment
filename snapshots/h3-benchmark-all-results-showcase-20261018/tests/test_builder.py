import importlib.util,io,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('builder',Path(__file__).resolve().parents[1]/'scripts/build_showcase.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
class BuilderTests(unittest.TestCase):
 def test_reference_origin_control_keeps_intervention_and_separate_scores(self):
  item={'id':'reference','comparison_kind':'reference_origin_control','ordinary_video_path':'a','guided_video_path':'b','comparison_video_path':'c','actual_routed_blocks':450,'quantitative_metrics':{'motion_fidelity':{'native':.8,'reference_origin':.7,'guided':None}}}
  self.assertEqual(b.classify(item),'reference_origin');self.assertEqual(b.activation(item),'active')
  self.assertNotEqual(b.classify(item),'guided')
  out=io.StringIO();b.render_motion_fidelity(out,item)
  self.assertIn('参考分支相位引导',out.getvalue());self.assertIn('0.700000',out.getvalue());self.assertNotIn('时序引导',out.getvalue())
  self.assertEqual(b.classify({**item,'guided_video_path':None}),'pending')
  item['valid_frames']=106;item['quantitative_metrics']['event_timing']={'fps':24,'events':[{'name':'event','source_frames':[20,23],'native_frames':[24,27],'reference_origin_frames':[21,24]}]}
  out=io.StringIO();b.render_event_timing(out,item);self.assertIn('参考分支相位引导',out.getvalue());self.assertIn('-0.083–0.167',out.getvalue())
  item['quantitative_metrics']['motion_fidelity']['reference_origin']=float('nan')
  with self.assertRaises(ValueError):b.render_motion_fidelity(io.StringIO(),item)
 def test_positional_control_roles_and_scores(self):
  item={'id':'aligned','comparison_kind':'positional_control','ordinary_video_path':'a','alternative_video_path':'b','comparison_video_path':'c','guidance_activation':'active','quantitative_metrics':{'motion_fidelity':{'native':.8,'aligned':.9,'guided':None}}}
  self.assertEqual(b.classify(item),'positional');self.assertEqual(b.activation(item),'not_applicable')
  out=io.StringIO();b.render_motion_fidelity(out,item)
  self.assertIn('RoPE 时间坐标对齐',out.getvalue());self.assertIn('0.900000',out.getvalue());self.assertNotIn('时序引导',out.getvalue())
  with self.assertRaises(ValueError):b.classify({**item,'guided_video_path':'d'})
  item['quantitative_metrics']['motion_fidelity']['aligned']=float('nan')
  with self.assertRaises(ValueError):b.render_motion_fidelity(io.StringIO(),item)
 def test_sampler_is_not_guidance_or_prompt(self):
  item={'id':'sampler','comparison_kind':'sampler_control','ordinary_video_path':'a','alternative_video_path':'b','comparison_video_path':'c','guidance_activation':'active'}
  self.assertEqual(b.classify(item),'sampler');self.assertEqual(b.activation(item),'not_applicable')
  with self.assertRaises(ValueError):b.classify({**item,'guided_video_path':'d'})
 def test_sampler_score_labels(self):
  item={'id':'sampler','comparison_kind':'sampler_control','quantitative_metrics':{'motion_fidelity':{'euler':.8,'res_multistep':.7}}}
  out=io.StringIO();b.render_motion_fidelity(out,item)
  self.assertIn('Euler 普通编辑',out.getvalue());self.assertIn('0.700000',out.getvalue());self.assertNotIn('时序引导',out.getvalue())
  item['quantitative_metrics']['motion_fidelity']['euler']=float('nan')
  with self.assertRaises(ValueError):b.render_motion_fidelity(io.StringIO(),item)
 def test_sampler_event_times_keep_solver_identity(self):
  item={'id':'sampler','comparison_kind':'sampler_control','valid_frames':98,'quantitative_metrics':{'event_timing':{'fps':24,'events':[{'name':'hands','source_frames':[42,45],'euler_frames':[57,60],'res_multistep_frames':[57,60]},{'name':'final','source_visible_frames':[96,97],'euler_visible_frames':[96,97],'res_multistep_visible_frames':[96,97],'arrival_time':'UNKNOWN'}]}}}
  out=io.StringIO();b.render_event_timing(out,item);value=out.getvalue()
  self.assertIn('Euler 普通编辑',value);self.assertIn('0.500–0.750',value);self.assertIn('到达时刻未定',value);self.assertNotIn('时序引导',value)
 def test_prompt_is_separate(self):
  self.assertEqual(b.classify({'ordinary_video_path':'a','guided_video_path':None,'alternative_video_path':'b','comparison_video_path':'c'}),'prompt')
 def test_partial_is_pending(self):self.assertEqual(b.classify({'ordinary_video_path':'a'}),'pending')
 def test_real_pair(self):self.assertEqual(b.classify({'ordinary_video_path':'a','guided_video_path':'b','comparison_video_path':'c'}),'guided')
 def test_missing_media_rejected(self):
  with self.assertRaises(ValueError):b.validate_item({'id':'x','benchmark':'IVEBench','source_id':'x','title':'t','task':'t','ordinary_video_path':'/nonexistent/a.mp4'}, {})
 def test_declared_sha_checked(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.mp4';p.write_bytes(b'fake')
   with self.assertRaises(ValueError):b.validate_item({'id':'x','benchmark':'IVEBench','source_id':'x','title':'t','task':'t','ordinary_video_path':str(p),'media_sha256':{'ordinary_video_path':'wrong'}},{})
 def test_reference_image_required(self):
  with self.assertRaises(ValueError):b.validate_item({'id':'x','benchmark':'IVEBench','source_id':'x','title':'t','task':'t','reference_image_used':True},{})
 def test_dedup_is_actual_sha(self):
  a={'id':'a','benchmark':'IVEBench','media':{'reference_video_path':{'sha256':'s'},'ordinary_video_path':{'sha256':'n'},'guided_video_path':{'sha256':'f'}}};c={**a,'id':'c','variant':'another page'}
  r,d=b.deduplicate([a,c]);self.assertEqual(len(r),1);self.assertEqual(d[0]['retained_id'],'a')
 def test_different_method_output_retained(self):
  a={'id':'a','benchmark':'IVEBench','media':{'ordinary_video_path':{'sha256':'n'},'guided_video_path':{'sha256':'f'}}};c={**a,'id':'c','media':{'ordinary_video_path':{'sha256':'n'},'guided_video_path':{'sha256':'g'}}}
  self.assertEqual(len(b.deduplicate([a,c])[0]),2)
 def test_status_no_keyword_inference(self):self.assertEqual(b.status_label('no_clear_improvement'),'待人工复核')
 def test_zero_actual(self):self.assertEqual(b.activation({'actual_routed_blocks':0}),'zero')
 def test_external_source_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.html';p.write_text('<video preload="none"><source src="file:///a.mp4"></video>')
   with self.assertRaises(ValueError):b.verify_html(p,1)
 def test_stream_boundary_count(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.html';p.write_text(' '*((1024*1024)-12)+'<video preload="none"><source src="data:video/mp4;base64,YQ=="></video>')
   self.assertEqual(b.verify_html(p,1)['data_videos'],1)
if __name__=='__main__':unittest.main()
