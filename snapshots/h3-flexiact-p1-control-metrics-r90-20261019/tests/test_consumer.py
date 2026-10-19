import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import common as c
import collect
import render

def fixture_gate():
 x=c.config();return {'schema':'r90-p1-native-runtime-gate-v1','passed':True,'run_id':x['run_id'],'source_id':x['source_id'],'prompt_version':x['prompt_version'],'checks':{k:True for k in c.REQUIRED_CHECKS},'runtime_profile_sha256':x['producer_runtime_sha256'],'runtime_profile':c.read(ROOT/'configs/producer_runtime.json'),'parent_R85_P0_gate_sha256':c.sha(ROOT/'configs/historical/PAIR_RUNTIME_GATE.json'),'valid_frames':147,'NFE':20,'Euler_updates':20,'routed_blocks':0,'evaluation_indices':list(range(0,147,3)),'video':{'file':x['producer_remote']+'/output/result.mp4','sha256':'fixture','properties':{'width':1152,'height':768,'nb_read_frames':'158','avg_frame_rate':'24/1'}}}
class GateTests(unittest.TestCase):
 def test_registered_scope_and_old_source(self):self.assertEqual(c.validate_static()['columns'],['参考动作','旧普通编辑','新版普通编辑'])
 def test_gate_pass(self):c.verify_gate(fixture_gate())
 def test_all_mandatory_checks_required(self):
  for key in c.REQUIRED_CHECKS:
   x=fixture_gate();del x['checks'][key]
   with self.assertRaises(ValueError):c.verify_gate(x)
 def test_false_or_nonboolean_check_refused(self):
  for value in [False,1,None]:
   x=fixture_gate();x['checks']['producer_seal']=value
   with self.assertRaises(ValueError):c.verify_gate(x)
 def test_wrong_run_or_prompt_refused(self):
  for key in ['schema','run_id','source_id','prompt_version']:
   x=fixture_gate();x[key]='other'
   with self.assertRaises(ValueError):c.verify_gate(x)
 def test_runtime_or_parent_changes_refused(self):
  for key in ['runtime_profile_sha256','parent_R85_P0_gate_sha256']:
   x=fixture_gate();x[key]='other'
   with self.assertRaises(ValueError):c.verify_gate(x)
 def test_route_or_count_change_refused(self):
  for key,value in [('valid_frames',158),('NFE',21),('Euler_updates',21),('routed_blocks',450),('evaluation_indices',[0])]:
   x=fixture_gate();x[key]=value
   with self.assertRaises(ValueError):c.verify_gate(x)
 def test_final_geometry_mismatch_refused(self):
  for key,value in [('width',768),('height',1152),('nb_read_frames',147),('avg_frame_rate','8/1')]:
   x=fixture_gate();x['video']['properties'][key]=value
   with self.assertRaises(ValueError):c.verify_gate(x)
 def test_output_escape_refused(self):
  for path in ['/tmp/result.mp4',c.config()['producer_remote']+'/output/../result.mp4']:
   with self.assertRaises(ValueError):c.safe_output(path)
 def test_unknown_attempt_refused_before_remote(self):
  with patch.object(collect,'read_paths') as read:
   with self.assertRaises(ValueError):collect.snapshot('other_attempt')
   read.assert_not_called()
 def test_missing_completion_is_pending_once(self):
  attempt=c.config()['expected_attempt'];paths=collect.names(attempt)
  with patch.object(collect,'read_paths',return_value={str(p):None for p in paths.values()}) as read:
   self.assertEqual(collect.snapshot(attempt)['status'],'PENDING_ACTUAL_GATE_OR_ROOT_EXIT');self.assertEqual(read.call_count,1)
class TimeTests(unittest.TestCase):
 def test_all49_times_on7pages_exact(self):
  p=render.page_indices();self.assertEqual(len(p),7);self.assertEqual([i for page in p for i in page],list(range(49)));self.assertEqual([i*3 for page in p for i in page],list(range(0,147,3)))
 def test_original_physical_time_grid(self):
  for i in range(49):self.assertEqual(i/8,(3*i)/24)
 def test_media_pts_exact(self):render.check_time({'width':1152,'height':768,'count':158,'avg_frame_rate':'24/1','pts_s':[i/24 for i in range(158)]},158,1152,768)
 def test_wrong_pts_or_fps_refused(self):
  s={'width':1152,'height':768,'count':158,'avg_frame_rate':'24/1','pts_s':[i/24 for i in range(158)]}
  for key,value in [('avg_frame_rate','25/1'),('pts_s',[i/24+.01 for i in range(158)])]:
   d=copy.deepcopy(s);d[key]=value
   with self.assertRaises(ValueError):render.check_time(d,158,1152,768)
 def test_command_uses_equal_full_geometry_and_valid_prefix(self):
  cmd=render.command(['source','old','new'],'caption','output',147,'ffmpeg');fs=cmd[cmd.index('-filter_complex')+1]
  self.assertEqual(fs.count('end_frame=147'),3);self.assertNotIn('crop=',fs);self.assertNotIn('fps=',fs);self.assertIn('hstack=inputs=3',fs);self.assertIn('-an',cmd)
 def test_requires3columns(self):
  with self.assertRaises(ValueError):render.command(['a','b'],'cap','out',147,'ffmpeg')
if __name__=='__main__':unittest.main(verbosity=2)
