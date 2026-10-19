import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import common as c
import collect,render,metric_inputs

def fixture_gate():
 x=c.config();b=c.parent();props={'width':1152,'height':768,'nb_read_frames':'158','avg_frame_rate':'24/1'}
 native={'run_id':b['run_id'],'parent_root':b['producer_remote'],'video':copy.deepcopy(b['native_video']),'valid_frames':147,'NFE':20,'Euler_updates':20,'routed_blocks':0,'historical_parent':True}
 forced={'run_id':x['run_id'],'video':{'file':x['producer_remote']+'/output/fixture.mp4','sha256':'f'*64,'properties':props},'valid_frames':147,'NFE':20,'Euler_updates':20,'routed_blocks':450}
 return {'schema':'r101-historical-native-paired-runtime-gate-v1','passed':True,'source_id':x['source_id'],'prompt_version':'actual-parent-P1-verbatim','checks':{k:True for k in c.REQUIRED_CHECKS},'runtime_profile_sha256':x['producer_runtime_sha256'],'runtime_profile':c.read(ROOT/'configs/producer_runtime.json'),'valid_frames':147,'total_frames':158,'fps':24,'evaluation_crop_xywh':[0,0,1152,768],'runs':{'native':native,'forced':forced},'parent_evidence':{x['source_id']:{'passed':True,'large_files_verified':True,'parent_run':b['run_id'],'frozen_gate_raw_sha256':b['gate']['sha256']}},'first_allowed_prediction_divergence_index':6,'prefix_tensor_comparison':[{'step_zero_based':i,'model_call_one_based':i+1,'video':True,'audio':True,'parent_file_sha256':v['sha256'],'current_file_sha256':'c'*64} for i,v in enumerate(b['first_six_predictions'])],'parent_condition_tensor_files':[{'file':r['file'],'sha256':r['gate_file_sha256']} for r in b['condition_tensors']]}

class GateTests(unittest.TestCase):
 def test_real_parent_and_frozen_scope(self):self.assertEqual(c.validate_static()['columns'],['参考视频','普通编辑','时序引导'])
 def test_pair_pass(self):c.verify_gate(fixture_gate())
 def test_all_mandatory_checks_required(self):
  for key in c.REQUIRED_CHECKS:
   g=fixture_gate();del g['checks'][key]
   with self.assertRaises(ValueError):c.verify_gate(g)
 def test_false_or_integer_checks_rejected(self):
  for v in [False,1,None]:
   g=fixture_gate();g['checks']['producer_seal']=v
   with self.assertRaises(ValueError):c.verify_gate(g)
 def test_wrong_schema_source_prompt(self):
  for key in ['schema','source_id','prompt_version']:
   g=fixture_gate();g[key]='wrong'
   with self.assertRaises(ValueError):c.verify_gate(g)
 def test_runtime_changed(self):
  g=fixture_gate();g['runtime_profile']['port']=123
  with self.assertRaises(ValueError):c.verify_gate(g)
 def test_wrong_parent_video(self):
  g=fixture_gate();g['runs']['native']['video']['sha256']='0'*64
  with self.assertRaises(ValueError):c.verify_gate(g)
 def test_old_r66_native_refused(self):
  g=fixture_gate();g['runs']['native']['run_id']='r66_native'
  with self.assertRaises(ValueError):c.verify_gate(g)
 def test_wrong_forced_run(self):
  g=fixture_gate();g['runs']['forced']['run_id']='other'
  with self.assertRaises(ValueError):c.verify_gate(g)
 def test_count_and_route_changes(self):
  for arm in ['native','forced']:
   for key,value in [('valid_frames',158),('NFE',21),('Euler_updates',21),('routed_blocks',999)]:
    g=fixture_gate();g['runs'][arm][key]=value
    with self.assertRaises(ValueError):c.verify_gate(g)
 def test_geometry_and_fps_changes(self):
  for key,value in [('width',768),('height',1152),('nb_read_frames','147'),('avg_frame_rate','8/1')]:
   g=fixture_gate();g['runs']['forced']['video']['properties'][key]=value
   with self.assertRaises(ValueError):c.verify_gate(g)
 def test_timeline_crop_changes(self):
  for key,value in [('valid_frames',158),('total_frames',147),('fps',8),('evaluation_crop_xywh',[1,0,1152,768])]:
   g=fixture_gate();g[key]=value
   with self.assertRaises(ValueError):c.verify_gate(g)
 def test_parent_proof_requires_large_files(self):
  g=fixture_gate();g['parent_evidence'][c.config()['source_id']]['large_files_verified']=False
  with self.assertRaises(ValueError):c.verify_gate(g)
 def test_all_six_prefix_required(self):
  g=fixture_gate();g['prefix_tensor_comparison'].pop()
  with self.assertRaises(ValueError):c.verify_gate(g)
 def test_audio_and_video_prefix_bitwise(self):
  for modality in ['video','audio']:
   g=fixture_gate();g['prefix_tensor_comparison'][3][modality]=False
   with self.assertRaises(ValueError):c.verify_gate(g)
 def test_parent_prefix_sha_bound(self):
  g=fixture_gate();g['prefix_tensor_comparison'][4]['parent_file_sha256']='0'*64
  with self.assertRaises(ValueError):c.verify_gate(g)
 def test_eight_conditions_bound(self):
  for kind in ['missing','changed']:
   g=fixture_gate()
   if kind=='missing':g['parent_condition_tensor_files'].pop()
   else:g['parent_condition_tensor_files'][2]['sha256']='0'*64
   with self.assertRaises(ValueError):c.verify_gate(g)
 def test_unsafe_output_refused(self):
  for p in ['/tmp/output.mp4',c.config()['producer_remote']+'/output/../x.mp4']:
   with self.assertRaises(ValueError):c.safe_output(p)
 def test_unknown_attempt_no_remote_call(self):
  with patch.object(collect,'read_paths') as remote:
   with self.assertRaises(ValueError):collect.snapshot('unregistered')
   remote.assert_not_called()
 def test_pending_is_single_read(self):
  attempt=c.config()['expected_attempt'];paths=collect.names(attempt)
  with patch.object(collect,'read_paths',return_value={str(p):None for p in paths.values()}) as remote:
   self.assertEqual(collect.snapshot(attempt)['status'],'PENDING_ACTUAL_GATE_OR_ROOT_EXIT');self.assertEqual(remote.call_count,1)
 def test_real_root_attempt_location(self):
  p=collect.names(c.config()['expected_attempt']);self.assertEqual(str(p['started']),c.config()['producer_remote']+'/audit/root_character_guidance_attempt1/STARTED.json')
 def test_download_phase_no_parent_redownload(self):
  self.assertNotIn('parent',collect.names(c.config()['expected_attempt']))

class TimeTests(unittest.TestCase):
 def test_all49_original_times(self):self.assertEqual([i*3 for p in render.page_indices() for i in p],list(range(0,147,3)))
 def test_physical_time_equivalence(self):
  for i in range(49):self.assertEqual(i/8,(3*i)/24)
 def test_media_pts(self):render.check_time({'width':1152,'height':768,'count':158,'avg_frame_rate':'24/1','pts_s':[i/24 for i in range(158)]},158,1152,768)
 def test_offset_pts_refused(self):
  with self.assertRaises(ValueError):render.check_time({'width':1152,'height':768,'count':158,'avg_frame_rate':'24/1','pts_s':[i/24+.01 for i in range(158)]},158,1152,768)
 def test_full_valid_same_geometry(self):
  cmd=render.command(['a','b','c'],'cap','out',147,'ffmpeg');fs=cmd[cmd.index('-filter_complex')+1];self.assertEqual(fs.count('end_frame=147'),3);self.assertNotIn('crop=',fs);self.assertNotIn('fps=',fs);self.assertIn('hstack=inputs=3',fs)
 def test_three_columns_only(self):
  with self.assertRaises(ValueError):render.command(['a','b'],'cap','out',147,'ffmpeg')

class MetricTests(unittest.TestCase):
 def test_input_manifest_has_no_fake_score(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'incoming').mkdir();forced=root/'incoming/forced.mp4';forced.write_bytes(b'fixture-forced')
   for name in ['PAIR_RUNTIME_GATE.json','COLLECTION.json']:(root/'incoming'/name).write_text('{}')
   cfg=copy.deepcopy(c.config());g=fixture_gate();g['runs']['forced']['video']['sha256']=c.sha(forced)
   with patch.object(metric_inputs,'ROOT',root),patch.object(metric_inputs,'validate_static',return_value=cfg),patch.object(metric_inputs,'verify_intake',return_value=g):
    metric_inputs.prepare();d=c.read(root/'prepared/MF_INPUTS.json');self.assertIsNone(d['scores']);self.assertEqual(d['physical_frame_indices'],list(range(0,147,3)));self.assertEqual(d['physical_pts_seconds'],[i/8 for i in range(49)]);metric_inputs.prepare()
 def test_generated_sha_mismatch_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'incoming').mkdir();(root/'incoming/forced.mp4').write_bytes(b'wrong')
   with patch.object(metric_inputs,'ROOT',root),patch.object(metric_inputs,'validate_static',return_value=c.config()),patch.object(metric_inputs,'verify_intake',return_value=fixture_gate()):
    with self.assertRaises(ValueError):metric_inputs.prepare()
if __name__=='__main__':unittest.main(verbosity=2)
