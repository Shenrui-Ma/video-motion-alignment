import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common,collect,render

def fixture():
 c=common.config();p=common.read(common.ROOT/'configs/parent_bindings.json')
 return {'schema':'r97-schedule-control-runtime-gate-v1','passed':True,'checks':{x:True for x in common.REQUIRED_CHECKS},'run_id':c['run_id'],'source_id':c['source_id'],'prompt_version':c['prompt_version'],'runtime_profile_sha256':c['producer_runtime_sha256'],'runtime_profile':common.read(common.ROOT/'configs/producer_runtime.json'),'NFE':20,'Euler_updates':20,'routed_blocks':700,'valid_frames':105,'evaluation_crop_xywh':[16,8,1280,720],'first_allowed_prediction_divergence_index':15,'video':{'file':c['producer_remote']+'/output/result.mp4','sha256':'a'*64,'properties':{'width':1312,'height':736,'nb_read_frames':'107','avg_frame_rate':'24/1'}},'parent_evidence':{'passed':True,'frozen_gate_raw_sha256':p['parent_gate_sha256'],'gate_canonical_sha256':common.canonical_gate(common.read(common.ROOT/'configs/parent_gate.json')),'ignored_gate_field':'top-level created_unix only','prefix_file_hashes_verified':15},'parent_fixed_video':p['parent_video'],'prefix_tensor_comparison':[{'step_zero_based':i,'model_call_one_based':i+1,'video':True,'audio':True,'parent_file_sha256':r['sha256'],'current_file_sha256':'b'*64} for i,r in enumerate(p['parent_snapshots_prefix'])]}
class GateTests(unittest.TestCase):
 def test_valid(self):common.verify_gate(fixture())
 def reject(self,change):
  g=fixture();change(g)
  with self.assertRaises(ValueError):common.verify_gate(g)
 def test_not_passed(self):self.reject(lambda g:g.update(passed=False))
 def test_missing_check(self):self.reject(lambda g:g['checks'].pop('actual_raw_AV_noise_equal_R89_fixed'))
 def test_false_check(self):self.reject(lambda g:g['checks'].update(actual_history=False))
 def test_false_new_check(self):self.reject(lambda g:g['checks'].update(other=False))
 def test_runtime_hash(self):self.reject(lambda g:g.update(runtime_profile_sha256='x'))
 def test_runtime_content(self):self.reject(lambda g:g['runtime_profile'].update(port=1))
 def test_routecount(self):self.reject(lambda g:g.update(routed_blocks=450))
 def test_nfe(self):self.reject(lambda g:g.update(NFE=19))
 def test_prefix_short(self):self.reject(lambda g:g['prefix_tensor_comparison'].pop())
 def test_prefix_order(self):self.reject(lambda g:g['prefix_tensor_comparison'][3].update(step_zero_based=4))
 def test_prefix_audio(self):self.reject(lambda g:g['prefix_tensor_comparison'][7].update(audio=False))
 def test_prefix_parent(self):self.reject(lambda g:g['prefix_tensor_comparison'][10].update(parent_file_sha256='z'*64))
 def test_prefix_current(self):self.reject(lambda g:g['prefix_tensor_comparison'][10].update(current_file_sha256=''))
 def test_parent_not_verified(self):self.reject(lambda g:g['parent_evidence'].update(prefix_file_hashes_verified=0))
 def test_parent_gate(self):self.reject(lambda g:g['parent_evidence'].update(gate_canonical_sha256='z'))
 def test_parent_output(self):self.reject(lambda g:g['parent_fixed_video'].update(sha256='z'))
 def test_unsafe_path(self):self.reject(lambda g:g['video'].update(file=common.config()['producer_remote']+'/output/../wrong.mp4'))
 def test_wrong_root(self):self.reject(lambda g:g['video'].update(file='/tmp/result.mp4'))
 def test_wrong_fps(self):self.reject(lambda g:g['video']['properties'].update(avg_frame_rate='8/1'))
 def test_wrong_frames(self):self.reject(lambda g:g['video']['properties'].update(nb_read_frames='105'))
 def test_valid_interval(self):self.reject(lambda g:g.update(valid_frames=107))
 def test_divergence(self):self.reject(lambda g:g.update(first_allowed_prediction_divergence_index=6))
 def test_parent_only_creation_ignored(self):
  a={'passed':True,'created_unix':1,'value':1};b={**a,'created_unix':2};self.assertEqual(common.canonical_gate(a),common.canonical_gate(b));b['value']=2;self.assertNotEqual(common.canonical_gate(a),common.canonical_gate(b))
 def test_pending_cannot_fetch(self):
  with tempfile.TemporaryDirectory() as d,patch.object(collect,'ROOT',Path(d)),patch.object(collect,'status',return_value={'status':'PENDING_GATE'}),patch.object(collect,'fetch') as f:
   with self.assertRaises(ValueError):collect.collect()
   f.assert_not_called()
 def test_pts_offset_rejected(self):
  with self.assertRaises(ValueError):render.check_time({'width':1,'height':1,'count':2,'avg_frame_rate':'24/1','pts_s':[.1,.1+1/24]},2,1,1)
 def test_same_time_command(self):
  cmd=render.command(['a','b','c','d'],'cap','out',105,'ffmpeg');text=' '.join(cmd)
  self.assertIn('hstack=inputs=4',text);self.assertEqual(text.count('trim=start_frame=0:end_frame=105'),4);self.assertNotIn('minterpolate',text);self.assertNotIn('setpts=4',text)
 def test_three_panels_rejected(self):
  with self.assertRaises(ValueError):render.command(['a','b','c'],'cap','out',105,'ffmpeg')

class SmallTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.p=Path(self.temp.name);self.c=common.config();self.g=fixture();self.owner={'pid':1,'identity':{'start_ticks':5,'uid':1016,'cmdline':['test']}}
  self.graph={'a':1};self.write('extended_graph.json',self.graph);self.graphsha=common.sha(self.p/'extended_graph.json');self.c={**self.c,'graph_sha256':self.graphsha}
  self.job={'status':'success','name':self.c['run_id'],'service_pid':1,'service_identity':self.owner['identity'],'graph_sha256':self.graphsha,'prompt_id':'p'}
  self.history={'status':{'completed':True,'status_str':'success'},'prompt':[0,'p',self.graph],'outputs':{'14':{'images':[{'type':'output','filename':'result.mp4'}]}}}
  self.router={'run_id':self.c['run_id'],'routed_calls':700,'completed_forward_calls':20,'routed_by_forward':[0]*6+[50]*14}
  (self.p/'extended.mp4').write_bytes(b'fake fixture');self.g['video']['sha256']=common.sha(self.p/'extended.mp4')
 def tearDown(self):self.temp.cleanup()
 def write(self,n,v):(self.p/n).write_text(json.dumps(v))
 def check(self):
  for n,v in [('extended_job.json',self.job),('extended_history.json',self.history),('extended_router.json',self.router)]:self.write(n,v)
  with patch.object(common,'config',return_value=self.c):common.verify_small(self.p,self.owner,self.g)
 def test_valid_evidence(self):self.check()
 def test_pid_reuse(self):
  self.job['service_identity']={**self.owner['identity'],'start_ticks':6}
  with self.assertRaises(ValueError):self.check()
 def test_wrong_history(self):
  self.history['prompt'][1]='different'
  with self.assertRaises(ValueError):self.check()
 def test_wrong_output(self):
  self.history['outputs']['14']['images'][0]['filename']='other.mp4'
  with self.assertRaises(ValueError):self.check()
 def test_wrong_router(self):
  self.router['routed_calls']=450
  with self.assertRaises(ValueError):self.check()
 def test_incomplete_job(self):
  self.job['status']='running'
  with self.assertRaises(ValueError):self.check()
if __name__=='__main__':unittest.main()
