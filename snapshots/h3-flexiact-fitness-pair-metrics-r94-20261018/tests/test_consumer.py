"""CPU synthetic receipts only. These fixtures are not generated-video evidence."""
import copy,sys,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common as c
import render_pair as r
import make_showcase as show
import remote
REAL_READ=c.read
class ConsumerTests(unittest.TestCase):
 def gate(self,pair=c.PAIRS[0]):
  p=c.pair_info(pair);checks={k:True for k in ['actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal','producer_seal','actual_runtime_device','native_service','forced_service','native_reference_geometry','forced_reference_geometry']}
  g={'schema':'r94-paired-runtime-gate-v1','passed':True,'source_id':pair,'pair_key':pair,'checks':checks,'runtime_profile_sha256':c.config()['producer_runtime_sha256'],'runtime_profile':c.read(c.ROOT/'configs/producer_runtime.json'),'prefix_tensor_comparison':[{'step_zero_based':i,'video':True,'audio':True} for i in range(6)],'runs':{}}
  for k in ['motion_source_id','original_pair_id','group','prompt_version']:g[k]=p[k]
  for arm in c.METHODS:g['runs'][arm]={'run_id':p['runs'][arm]['run_id'],'valid_frames':147,'NFE':20,'Euler_updates':20,'routed_blocks':0 if arm=='native' else 450,'evaluation_indices':c.INDICES,'evaluation_fps':8,'evaluation_crop_xywh':[0,0,1152,768],'video':{'properties':{'width':1152,'height':768,'nb_read_frames':'158','avg_frame_rate':'24/1'}}}
  for arm in c.METHODS:
   for suffix in ['history','shared_conditions','actual_execution_counts','actual_layout','sampled_finite','actual_noise_cache']:g['checks'][arm+'_'+suffix]=True
  return g
 def test_single_fresh_p1_pair(self):
  for pair in c.PAIRS:self.assertIs(c.verify_gate(g:=self.gate(pair),pair),g)
  self.assertEqual([c.pair_info(x)['prompt_version'] for x in c.PAIRS],['P1'])
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
  g=self.gate();g['prompt_version']='P0'
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_wrong_pair_rejected(self):
  with self.assertRaises(ValueError):c.verify_gate(self.gate(),'one_leg__movie_man_9')
 def test_old_native_rejected(self):
  g=self.gate();g['runs']['native']['run_id']='r72_fitness__game_man_5_seed2026101701_p1'
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
  self.assertEqual(report['fixed_denominator'],1);self.assertEqual(len(report['rows']),1);self.assertEqual(report['completed_pairs'],0);self.assertTrue(all(x['task_success']=='UNREVIEWED' and x['MF'] is None for x in report['rows']))
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
class ExtraTests(unittest.TestCase):
 gate=ConsumerTests.gate
 def test_missing_actual_conditions(self):
  g=self.gate();del g['checks']['native_shared_conditions']
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_prefix_all_six_required(self):
  g=self.gate();g['prefix_tensor_comparison'].pop()
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_prefix_audio_mismatch(self):
  g=self.gate();g['prefix_tensor_comparison'][3]['audio']=False
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_prefix_index_mismatch(self):
  g=self.gate();g['prefix_tensor_comparison'][0]['step_zero_based']=6
  with self.assertRaises(ValueError):c.verify_gate(g,c.PAIRS[0])
 def test_render_four_inputs_rejected(self):
  with self.assertRaises(ValueError):r.command(['s','n','f','old'],'c','o',147,'ffmpeg')
 def test_one_shot_pending_no_collect_or_render(self):
  import consume_pair as one
  with patch.object(one,'bind') as bind,patch.object(one,'status',return_value={'status':'PENDING_GATE'}) as status,patch.object(one,'collect') as collect,patch.object(one,'render') as render:
   result,code=one.consume('fixture','out','ffmpeg','ffprobe','font')
   self.assertEqual(code,3);self.assertEqual(result['status'],'PENDING_GATE');bind.assert_called_once();status.assert_called_once();collect.assert_not_called();render.assert_not_called()

class HistoryEvidenceTests(unittest.TestCase):
 def fixture(self):
  pair=c.PAIRS[0];p=c.pair_info(pair);owner={'pid':123,'identity':{'uid':1016,'start_ticks':'555','cmdline':'test'}}
  graph={'14':{'class_type':'SaveVideo','inputs':{}}};job={'status':'success','name':p['runs']['native']['run_id'],'service_pid':123,'service_identity':owner['identity'],'graph_sha256':p['runs']['native']['graph_sha256'],'prompt_id':'fixture-id'}
  history={'status':{'completed':True,'status_str':'success'},'prompt':[0,'fixture-id',graph],'outputs':{'14':{'images':[{'type':'output','subfolder':'','filename':'fixture.mp4'}]}}}
  gate={'runs':{'native':{'video':{'file':c.config()['producer_remote']+'/output/fixture.mp4','sha256':'fixture-video-sha'}}}}
  values={'native_job.json':job,'native_history.json':history,'native_graph.json':graph}
  return pair,p,owner,history,gate,values
 def test_exact_history_and_graph_accept(self):
  pair,p,owner,h,g,values=self.fixture()
  with patch.object(c,'read',side_effect=lambda path:values[Path(path).name] if Path(path).name in values else REAL_READ(path)),patch.object(c,'sha',side_effect=lambda path:p['runs']['native']['graph_sha256'] if str(path).endswith('graph.json') else 'fixture-video-sha'):
   c.verify_small_evidence(Path('/synthetic'),'native',pair,owner,g)
 def test_successful_other_prompt_rejected(self):
  pair,p,owner,h,g,values=self.fixture();h['prompt'][1]='different-execution'
  with patch.object(c,'read',side_effect=lambda path:values[Path(path).name] if Path(path).name in values else REAL_READ(path)),patch.object(c,'sha',return_value=p['runs']['native']['graph_sha256']):
   with self.assertRaises(ValueError):c.verify_small_evidence(Path('/synthetic'),'native',pair,owner,g)

if __name__=='__main__':unittest.main()
