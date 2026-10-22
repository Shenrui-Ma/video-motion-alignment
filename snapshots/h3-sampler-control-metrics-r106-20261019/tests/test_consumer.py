import copy,importlib.util,sys,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('r106_consume',R/'scripts/consume.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
def fixture():
 owner={'pid':123,'identity':{'start_ticks':'999','uid':1016},'gpu_uuid':'GPU-test'}
 checks={'all_other_bound':True}
 for step in (0,1):
  for kind,keys in [('raw',('state_video','state_audio','prediction_video','prediction_audio')),('normalized',('video','audio'))]:
   for key in keys:checks[f'step{step}_{kind}_{key}']=True
 gate={'schema':'r106-fresh-native-solver-pair-runtime-gate-v1','passed':True,'checks':checks,'source_id':'short_0252','valid_frames':98,'evaluation_indices':list(range(98)),'frame_rate':24,'evaluation_crop_xywh':[16,8,1280,720],'service_owner':owner,'equal_prefix_steps':[0,1],'runtime_profile':{'remote_root':c.REMOTE,'gpu_uuid':'GPU-test'},'runs':{a:{'run_id':r,'solver':a,'sampler_function':'sample_'+a,'NFE':20,'solver_updates':20,'routed_blocks':0,'valid_frames':98,'video':{'file':c.REMOTE+'/output/'+r+'_00001_.mp4'}} for a,r in zip(c.ARMS,c.RUNS)}}
 return [gate,{'passed':True,'jobs':c.RUNS,'GPU_released':True},{'passed':True,'process_absent':True,'CUDA_allocation_absent':True,'owner':owner},{'owner':owner}]
class GateTests(unittest.TestCase):
 def test_both_fresh_native_accepted(self):self.assertEqual(set(c.validate_gate(*fixture())),set(c.ARMS))
 def test_wrong_solver_rejected(self):
  f=fixture();f[0]['runs']['res_multistep']['sampler_function']='sample_euler'
  with self.assertRaises(ValueError):c.validate_gate(*f)
 def test_missing_raw_state_evidence_rejected(self):
  f=fixture();del f[0]['checks']['step1_raw_state_audio']
  with self.assertRaises(ValueError):c.validate_gate(*f)
 def test_nonzero_guidance_rejected(self):
  f=fixture();f[0]['runs']['euler']['routed_blocks']=450
  with self.assertRaises(ValueError):c.validate_gate(*f)
 def test_release_generation_rejected(self):
  f=copy.deepcopy(fixture());f[2]['owner']=dict(f[2]['owner'],pid=999)
  with self.assertRaises(ValueError):c.validate_gate(*f)
 def test_path_escape_rejected(self):
  f=fixture();f[0]['runs']['euler']['video']['file']=c.REMOTE+'/output/../secrets.mp4'
  with self.assertRaises(ValueError):c.validate_gate(*f)
 def test_time_shift_rejected(self):
  v={'streams':[{'width':3840,'height':808,'avg_frame_rate':'24/1'}],'frames':[{'best_effort_timestamp_time':str(i/24)} for i in range(98)]}
  c.validate_comparison_time(v);v['frames'][20]['best_effort_timestamp_time']='1.2'
  with self.assertRaises(ValueError):c.validate_comparison_time(v)
if __name__=='__main__':unittest.main()
