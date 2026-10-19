import copy,sys,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common as c
import paired as p
import collect_pair as intake
import render_pair as render
import remote

class PairTests(unittest.TestCase):
 def setUp(self):
  self.source='human2animal_2__movie_man_11';self.case=c.info(self.source);conf=c.config();self.owner={'pid':123,'identity':{'uid':1016,'start_ticks':'42','cmdline':'fixture'}}
  runs={}
  for mode in ('native','forced'):
   run=self.case['run_id'] if mode=='native' else self.case['forced_run_id'];graph=self.case['graph_sha256'] if mode=='native' else self.case['forced_graph_sha256']
   runs[mode]={'run_id':run,'NFE':20,'Euler_updates':20,'routed_blocks':0 if mode=='native' else 450,'valid_frames':self.case['valid_frames'],'evaluation_crop_xywh':self.case['crop_xywh'],'evaluation_indices':self.case['evaluation_indices'],'evaluation_fps':8,'video':{'file':conf['producer_remote']+'/output/'+mode+'.mp4','sha256':'a'*64,'properties':{'width':1152,'height':768,'nb_read_frames':str(self.case['geometry']['frames']),'avg_frame_rate':'24/1'}},'job_sha256':'b'*64,'history_sha256':'c'*64,'binding_artifacts':{f'configs/graphs/{run}.json':graph,f'logs/{run}_job.json':'b'*64,f'logs/{run}_history.json':'c'*64}}
  self.g={'schema':'r105-paired-runtime-gate-v1','passed':True,'source_id':self.source,'prompt_version':self.case['prompt_version'],'runs':runs,'checks':dict.fromkeys(p.PAIR_CHECKS,True),'runtime_profile_sha256':conf['producer_runtime_sha256'],'runtime_profile':c.read(c.ROOT/'configs/producer_runtime.json'),'service_owner':self.owner,'prefix_tensor_comparison':[{'step_zero_based':i,'video':True,'audio':True} for i in range(6)]}
 def reject(self,edit):
  g=copy.deepcopy(self.g);edit(g)
  with self.assertRaises(ValueError):p.verify_pair_gate(g,self.source,self.owner)
 def test_actual_pair(self):self.assertIs(p.verify_pair_gate(self.g,self.source,self.owner),self.g)
 def test_native_gate_cannot_make_pair(self):self.reject(lambda g:g.update(schema='r105-native-runtime-gate-v1'))
 def test_forced_missing(self):self.reject(lambda g:g['runs'].pop('forced'))
 def test_forced_execution_zero(self):self.reject(lambda g:g['runs']['forced'].update(routed_blocks=0))
 def test_required_noise_check_absent(self):self.reject(lambda g:g['checks'].pop('actual_initial_AV_noise_equal'))
 def test_failed_extra_check(self):self.reject(lambda g:g['checks'].update(new_check=False))
 def test_prefix_audio_difference(self):self.reject(lambda g:g['prefix_tensor_comparison'][2].update(audio=False))
 def test_prefix_duplicate_step(self):self.reject(lambda g:g['prefix_tensor_comparison'][5].update(step_zero_based=4))
 def test_missing_prefix(self):self.reject(lambda g:g.pop('prefix_tensor_comparison'))
 def test_wrong_forced_graph(self):self.reject(lambda g:g['runs']['forced']['binding_artifacts'].update({f'configs/graphs/{self.case["forced_run_id"]}.json':'0'*64}))
 def test_generation_mismatch(self):self.reject(lambda g:g.update(service_owner={'pid':123,'identity':{'uid':1016,'start_ticks':'43','cmdline':'fixture'}}))
 def test_reused_output_path(self):self.reject(lambda g:g['runs']['forced']['video'].update(file=g['runs']['native']['video']['file']))
 def test_preview_same_native_required(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'incoming'/self.source).mkdir(parents=True)
   with patch.object(p,'ROOT',root),patch.object(p,'verify_intake',return_value=self.g):
    p.require_same_native(self.source,self.g)
    other=copy.deepcopy(self.g);other['runs']['native']['video']['sha256']='0'*64
    with self.assertRaises(ValueError):p.require_same_native(self.source,other)
 def test_pending_pair_does_not_download(self):
  with tempfile.TemporaryDirectory() as d,patch.object(intake,'ROOT',Path(d)),patch.object(intake,'status',return_value={'status':'PENDING_GATE'}),patch.object(intake,'fetch') as fetch:
   with self.assertRaises(ValueError):intake.collect(self.source)
   fetch.assert_not_called()
 def test_three_equal_columns(self):
  cmd=render.command(['source','native','forced'],'caption','out',97,'ffmpeg');filters=cmd[cmd.index('-filter_complex')+1]
  self.assertEqual(filters.count('crop=1152:768:0:0'),3);self.assertIn('hstack=inputs=3',filters);self.assertIn('[images][3:v]',filters);self.assertNotIn('minterpolate',filters);self.assertNotIn('fps=',filters)
 def test_pair_requires_three_inputs(self):
  with self.assertRaises(ValueError):render.command(['source','native'],'c','o',97,'ffmpeg')
 def test_direct_host_and_uid(self):
  self.assertEqual(remote.SSH[-1],'H3_SERVER_A');self.assertEqual(c.config()['host'],remote.SSH[-1]);self.assertEqual(c.read(c.ROOT/'configs/producer_runtime.json')['uid'],1016)
 def test_labels(self):self.assertEqual(render.LABELS,('1.参考视频','2.普通编辑','3.固定时序引导'))

if __name__=='__main__':unittest.main()
