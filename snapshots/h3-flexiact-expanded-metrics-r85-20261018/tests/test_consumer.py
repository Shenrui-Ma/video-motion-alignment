"""CPU synthetic receipts only. These fixtures are not generated-video evidence."""
import copy,sys,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common as c
import render_pair as r
import make_showcase as show
import remote
class ConsumerTests(unittest.TestCase):
 def gate(self,pair=c.PAIRS[0]):
  p=c.pair_info(pair);checks={k:True for k in ['actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal','producer_seal','actual_runtime_device','native_service','forced_service','native_reference_geometry','forced_reference_geometry']}
  g={'schema':'r85-paired-runtime-gate-v1','passed':True,'source_id':pair,'pair_key':pair,'checks':checks,'runtime_profile_sha256':c.config()['producer_runtime_sha256'],'runs':{}}
  for k in ['motion_source_id','original_pair_id','group','prompt_version']:g[k]=p[k]
  for arm in c.METHODS:g['runs'][arm]={'run_id':p['runs'][arm]['run_id'],'valid_frames':147,'NFE':20,'Euler_updates':20,'routed_blocks':0 if arm=='native' else 450,'evaluation_indices':c.INDICES,'evaluation_fps':8,'evaluation_crop_xywh':[0,0,1152,768],'video':{'properties':{'width':1152,'height':768,'nb_read_frames':'158','avg_frame_rate':'24/1'}}}
  return g
 def test_all_three_and_mixed_prompt_versions(self):
  for pair in c.PAIRS:self.assertIs(c.verify_gate(g:=self.gate(pair),pair),g)
  self.assertEqual([c.pair_info(x)['prompt_version'] for x in c.PAIRS],['P0','P1','P1'])
 def test_failed_gate_rejected(self):
  g=self.gate();g['passed']=False
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_missing_prefix_rejected(self):
  g=self.gate();del g['checks']['Native_prefix_0_5_equal']
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_nonboolean_check_rejected(self):
  g=self.gate();g['checks']['producer_seal']=1
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_wrong_prompt_version_rejected(self):
  g=self.gate();g['prompt_version']='P1'
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_wrong_pair_rejected(self):
  with self.assertRaises(ValueError):c.verify_gate(self.gate(),c.PAIRS[1])
 def test_old_native_rejected(self):
  g=self.gate();g['runs']['native']['run_id']='r72_one_leg__movie_man_9_seed2026101701_p0'
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_all_off_forced_rejected(self):
  g=self.gate();g['runs']['forced']['routed_blocks']=0
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_tailpad_not_valid(self):
  g=self.gate();g['runs']['forced']['valid_frames']=158
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_wrong_original_frame_map(self):
  g=self.gate();g['runs']['native']['evaluation_indices']=list(range(49))
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_wrong_actual_geometry(self):
  g=self.gate();g['runs']['native']['video']['properties']['nb_read_frames']='147'
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_output_path_bounds(self):
  root=c.config()['producer_remote'];self.assertEqual(str(c.safe_output(root+'/output/a.mp4')),root+'/output/a.mp4')
  for p in [root+'/other/a.mp4',root+'/output/../a.mp4','/tmp/a.mp4']:
   with self.assertRaises(ValueError):c.safe_output(p)
 def test_exact_service_generation(self):
  pair=c.PAIRS[0];run=c.pair_info(pair)['runs']['native'];owner={'pid':123,'identity':{'uid':1016,'start_ticks':'555','cmdline':'test'}};job={'status':'success','name':run['run_id'],'service_pid':123,'service_identity':copy.deepcopy(owner['identity']),'graph_sha256':run['graph_sha256']}
  c.verify_job(job,'native',pair,owner,self.gate());job['service_identity']['start_ticks']='556'
  with self.assertRaises(ValueError):c.verify_job(job,'native',pair,owner,self.gate())
 def test_render_exact_prefix_and_labels(self):
  cmd=r.command(['s.mp4','n.mp4','f.mp4'],'c.png','o.mp4',147,'ffmpeg');filters=cmd[cmd.index('-filter_complex')+1]
  self.assertEqual(filters.count('trim=start_frame=0:end_frame=147'),3);self.assertNotIn('fps=',filters);self.assertNotIn('scale=',filters);self.assertEqual(r.LABELS,('1.参考视频','2.普通编辑','3.时序引导'))
 def test_render_tail_not_allowed(self):
  with self.assertRaises(ValueError):r.command(['s','n','f'],'c','o',158,'ffmpeg')
 def test_physical_pts(self):
  a={'width':1152,'height':768,'count':158,'avg_frame_rate':'24/1','pts_s':[i/24 for i in range(158)]};r.check_time(a,158,1152,768);a['pts_s'][60]+=1/24
  with self.assertRaises(ValueError):r.check_time(a,158,1152,768)
 def test_denominator_pending_not_complete(self):
  with patch('pathlib.Path.exists',return_value=False):report=show.summary()
  self.assertEqual(report['fixed_denominator'],3);self.assertEqual(len(report['rows']),3);self.assertEqual(report['completed_pairs'],0);self.assertTrue(all(x['task_success']=='UNREVIEWED' and x['MF'] is None for x in report['rows']))
 def test_ssh_transient_retryable(self):
  with patch('remote.subprocess.run',side_effect=subprocess.CalledProcessError(255,['ssh'],stderr='network unavailable')):
   with self.assertRaises(ConnectionError):remote.read_paths([c.config()['producer_remote']+'/test.json'])
 def test_remote_validation_not_transient(self):
  with patch('remote.subprocess.run',side_effect=subprocess.CalledProcessError(1,['ssh'],stderr='invalid evidence')):
   with self.assertRaises(subprocess.CalledProcessError):remote.read_paths([c.config()['producer_remote']+'/test.json'])
 def test_static_assets_match(self):
  c.validate_static()
  for pair in c.PAIRS:
   for name in ['source','target','provenance','source_original_8fps']:
    rec=c.pair_info(pair)[name];self.assertEqual(c.sha(c.ROOT/rec['file']),rec['sha256'])
if __name__=='__main__':unittest.main()
