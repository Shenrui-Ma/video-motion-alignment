"""Synthetic contract boundary checks, not claims about an actual R132 output."""
from pathlib import Path
import sys,copy,unittest
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
import common as c

class ConsumerTests(unittest.TestCase):
 def setUp(self):
  cfg=c.config();rt=c.read(R/'configs/runtime.json');run=cfg['case']['run_id'];old=Path('/Users/researcher/DevProjects/h3-ive-aligned-media-clock-metrics-r129-20261020/incoming/ALIGNED_RUNTIME_GATE.json');base=c.read(old);layout=copy.deepcopy(base['alignment']['layout']);stats=c.read(R/'design/R122_native_prefix_statistics.json')
  prefix={'diagnostics_complete':True,'equality_required':False,'steps_zero_based':list(range(6)),'streams':['video','audio'],'parent_manifest_sha256':c.sha(R/'design/R122_native_x0_manifest.json'),'parent_statistics_sha256':c.sha(R/'design/R122_native_prefix_statistics.json'),'comparisons':[]}
  for i,row in enumerate(stats['captures']):
   streams={}
   for k,z in row['streams'].items():
    streams[k]={'equality_required':False,'sample_count':1024,'parent_tensor_sha256':z['tensor_sha256'],'actual_tensor_sha256':z['tensor_sha256'],'full_tensor_sha256_equal':True,'sample_difference_rms':0.0,'sample_difference_max_abs':0.0,'actual_whole_tensor_rms':z['rms'],'parent_whole_tensor_rms':z['rms'],'actual_whole_tensor_mean':z['mean'],'parent_whole_tensor_mean':z['mean']}
   prefix['comparisons'].append({'step_zero_based':i,'streams':streams})
  owner={'pid':12345,'identity':{'uid':rt['uid'],'start_ticks':'123456','cmdline':cfg['producer_remote']+'/scripts/service_entry.py'},'gpu_uuid':rt['gpu_uuid'],'port':rt['port']}
  arm={'run_id':run,'valid_frames':106,'evaluation_crop_xywh':[16,8,1280,720],'NFE':20,'Euler_updates':20,'routed_blocks':450,'original_rope_table_blocks':1000,'video':{'file':cfg['producer_remote']+'/output/fixture.mp4'}}
  branch={'new_method_claim':False,'original_QKV_and_table_preserved':True,'extra_query_scope':'target_video_only','reference_scope':'all_video_reference_keys','first_six_prediction_equality_required':False,'layout_validation_count':1,'rotation_calls':450,'original_rope_table_calls':1000,'layout':layout,'rotation':{'displacement_rope_units':layout['target_time_displacement'],'time_channel_pairs':[[0,16],[48,64]],'inv_freq':[1.0]*16,'inv_freq_sha256':'a'*64}}
  self.g={'schema':'r132-reference-origin-runtime-gate-v1','source_id':'long_0039','passed':True,'checks':{k:True for k in c.REQUIRED_CHECKS},'producer_seal_sha256':cfg['producer_seal_sha256'],'runtime_profile_sha256':cfg['runtime_sha256'],'runtime_profile':rt,'service_owner':owner,'runs':{'reference_origin':arm},'first_six_prediction_equality_required':False,'reference_origin':branch,'prefix_comparison':prefix,'condition_comparison':{'strict_metadata_pixels_tokens_positions_equal':True},'evaluation_plan_sha256':c.sha(R/'design/R129_EVALUATION_PLAN.json')}
  self.start={'owner':owner};self.complete={'schema':'r132-one-output-completion-v1','passed':True,'GPU_released':True,'jobs':[run],'remaining':[],'service_owner':owner};self.release={'passed':True,'process_absent':True,'CUDA_allocation_absent':True,'owner':owner}
 def check(self):return c.verify_gate(self.g,self.start,self.complete,self.release)
 def test_valid_reference_branch(self):self.check()
 def test_wrong_router_count(self):
  self.g['runs']['reference_origin']['routed_blocks']=0
  with self.assertRaises(ValueError):self.check()
 def test_wrong_role(self):
  self.g['runs']['aligned']=self.g['runs'].pop('reference_origin')
  with self.assertRaises(ValueError):self.check()
 def test_missing_condition_gate(self):
  self.g['checks'].pop('original_input_pixels_tokens_positions_equal_R122')
  with self.assertRaises(ValueError):self.check()
 def test_prefix_difference_recorded_not_rejected(self):
  d=self.g['prefix_comparison']['comparisons'][0]['streams']['video'];d.update(actual_tensor_sha256='f'*64,full_tensor_sha256_equal=False,sample_difference_rms=.001,sample_difference_max_abs=.01);self.check()
 def test_prefix_missing_stream_rejected(self):
  self.g['prefix_comparison']['comparisons'][2]['streams'].pop('audio')
  with self.assertRaises(ValueError):self.check()
 def test_prefix_nonfinite_rejected(self):
  self.g['prefix_comparison']['comparisons'][2]['streams']['audio']['sample_difference_rms']=float('nan')
  with self.assertRaises(ValueError):self.check()
 def test_wrong_rotation_direction_rejected(self):
  self.g['reference_origin']['rotation']['displacement_rope_units']*= -1
  with self.assertRaises(ValueError):self.check()
 def test_no_release_rejected(self):
  self.release['CUDA_allocation_absent']=False
  with self.assertRaises(ValueError):self.check()
 def test_float_condition_sha_only_is_observational(self):
  p=c.read(R/'design/r122_long_0039_shared_conditioning.json');a=copy.deepcopy(p);a['conditioning_embedding']['sha256']='a'*64;out=c.compare_condition_metadata(a,p);self.assertFalse(out['conditioning_embedding']['sha256_equal'])
 def test_float_condition_geometry_is_strict(self):
  p=c.read(R/'design/r122_long_0039_shared_conditioning.json');a=copy.deepcopy(p);a['conditioning_embedding']['shape'][0]+=1
  with self.assertRaises(ValueError):c.compare_condition_metadata(a,p)
 def test_original_pixel_metadata_is_strict(self):
  p=c.read(R/'design/r122_long_0039_shared_conditioning.json');a=copy.deepcopy(p);a['input_video']['sha256']='a'*64
  with self.assertRaises(ValueError):c.compare_condition_metadata(a,p)
 def test_transport_host(self):
  import remote
  self.assertEqual(remote.SSH[-1],'H3_SERVER_B')
if __name__=='__main__':unittest.main()
