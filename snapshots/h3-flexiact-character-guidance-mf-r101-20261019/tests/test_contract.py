"""CPU-only fixtures; no producer, model load, or tracker invocation."""
import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import common as c
import tracking_plan

class Contract(unittest.TestCase):
 def setUp(self):
  self.cfg=c.read(ROOT/'configs/r101_consumer_contract.json');self.media=copy.deepcopy(self.cfg['media']);self.media.pop('target');self.media['forced']={'file':'fixture.mp4','sha256':'f'*64}
  self.g={'schema':'r101-historical-native-paired-runtime-gate-v1','passed':True,'checks':{k:True for k in c.read(ROOT/'configs/GATE_REQUIRED_CHECKS.json')},'source_id':self.cfg['source_id'],'prompt_version':'actual-parent-P1-verbatim','runtime_profile_sha256':self.cfg['producer_runtime_sha256'],'valid_frames':147,'total_frames':158,'fps':24,'evaluation_crop_xywh':[0,0,1152,768],'runs':{},'first_allowed_prediction_divergence_index':6,'prefix_tensor_comparison':[{'step_zero_based':i,'video':True,'audio':True} for i in range(6)]}
  for role,count in [('native',0),('forced',450)]:self.g['runs'][role]={'run_id':self.cfg['parent_run_id' if role=='native' else 'run_id'],'video':{'sha256':self.media[role]['sha256'],'properties':{'width':1152,'height':768,'nb_read_frames':'158','avg_frame_rate':'24/1'}},'valid_frames':147,'NFE':20,'Euler_updates':20,'routed_blocks':count,'historical_parent':role=='native'}
 def bad(self,g=None,media=None):
  with self.assertRaises(ValueError):c.validate_gate(g or self.g,media or self.media)
 def test_gate_fixture_passes(self):self.assertIs(c.validate_gate(self.g,self.media),self.g)
 def test_failed_gate(self):self.g['passed']=False;self.bad()
 def test_missing_mandatory_check(self):self.g['checks'].pop(next(iter(self.g['checks'])));self.bad()
 def test_false_actual_noise(self):self.g['checks']['actual_raw_AV_noise_equal_Native']=False;self.bad()
 def test_old_native_rejected(self):self.media['native']['sha256']='a'*64;self.bad()
 def test_changed_guided(self):self.g['runs']['forced']['video']['sha256']='a'*64;self.bad()
 def test_missing_routes(self):self.g['runs']['forced']['routed_blocks']=0;self.bad()
 def test_padding_not_evaluated(self):self.g['valid_frames']=158;self.bad()
 def test_wrong_fps(self):self.g['fps']=8;self.bad()
 def test_wrong_crop(self):self.g['evaluation_crop_xywh']=[16,8,1152,768];self.bad()
 def test_wrong_shape(self):self.g['runs']['forced']['video']['properties']['width']=1280;self.bad()
 def test_prefix_missing(self):self.g['prefix_tensor_comparison'].pop();self.bad()
 def test_prefix_audio_false(self):self.g['prefix_tensor_comparison'][2]['audio']=False;self.bad()
 def test_wrong_run(self):self.g['runs']['forced']['run_id']='old';self.bad()
 def test_original_cache_passes(self):self.assertEqual(set(c.validate_cache()),{'reference','native'})
 def test_static_freeze(self):self.assertIn('files',c.verify_runtime())
 def test_cache_host_mismatch(self):
  original=c.read
  def changed(p):
   j=original(p)
   if Path(p).name=='CACHE_REUSE.json':j['expected_runtime']['hostname']='other-host'
   return j
  with patch.object(c,'read',changed),self.assertRaises(ValueError):c.validate_cache()
 def test_cache_new_native_mismatch(self):
  original=c.read
  def changed(p):
   j=original(p)
   if Path(p).name=='r101_consumer_contract.json':j['media']['native']['sha256']='a'*64
   return j
  with patch.object(c,'read',changed),self.assertRaises(ValueError):c.validate_cache()
 def test_no_gpu_command_before_actual_pair(self):
  with self.assertRaisesRegex(ValueError,'pending'):tracking_plan.command('GPU-fixture','python')
 def test_numeric_inheritance(self):
  for n,v in c.read(ROOT/'configs/NUMERIC_INHERITANCE.json')['files'].items():self.assertEqual(c.sha(c.METRIC/n),v['sha256'],n)

if __name__=='__main__':unittest.main()
