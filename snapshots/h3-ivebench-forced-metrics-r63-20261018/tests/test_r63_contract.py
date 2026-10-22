import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_pair import validate_gate
class Gates(unittest.TestCase):
 def fixture(self):
  return {'schema':'r63-paired-runtime-gate-v1','passed':True,'source_id':'short_0210','prompt_version':'P0','checks':{k:True for k in ['actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal']},'runs':{m:{'run_id':'r63_short_0210_seed2026101701_'+m,'valid_frames':87,'NFE':20,'routed_blocks':0 if m=='native' else 450,'video':{'file':'/test/'+m+'.mp4','sha256':'x'}} for m in ['native','forced']}}
 def test_valid_pair(self):validate_gate(self.fixture(),'short_0210',87)
 def test_weak_or_misaligned_actual_evidence_rejected(self):
  for key in ['actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal']:
   g=self.fixture();g['checks'][key]=False
   with self.assertRaises(ValueError):validate_gate(g,'short_0210',87)
 def test_empty_forced_output_not_accepted_as_intervention(self):
  g=self.fixture();g['runs']['forced']['routed_blocks']=0
  with self.assertRaises(ValueError):validate_gate(g,'short_0210',87)
 def test_different_padding_or_sampling_rejected(self):
  g=self.fixture();g['runs']['forced']['valid_frames']=90
  with self.assertRaises(ValueError):validate_gate(g,'short_0210',87)
 def test_changed_prompt_condition_rejected(self):
  g=self.fixture();g['prompt_version']='P1'
  with self.assertRaises(ValueError):validate_gate(g,'short_0210',87)
if __name__=='__main__':unittest.main()
