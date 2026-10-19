import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import verify_gate,INDICES,verify_runtime
from evaluate_physical import relabel
from tracking_plan import command

def gate():
 return {'schema':'r65-paired-runtime-gate-v1','passed':True,'source_id':'fitness','prompt_version':'R49_original','checks':{k:True for k in ['actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal','producer_seal']},'runs':{m:{'run_id':f'r65_fitness_seed2026101701_{m}','valid_frames':147,'NFE':20,'Euler_updates':20,'routed_blocks':0 if m=='native' else 450,'evaluation_indices':INDICES,'evaluation_fps':8} for m in ('native','forced')}}
class IntakeTests(unittest.TestCase):
 def test_actual_pair_required(self):
  g=gate();verify_gate(g,'fitness');g['passed']=False
  with self.assertRaises(ValueError):verify_gate(g,'fitness')
 def test_wrong_frame_map_rejected(self):
  g=gate();g['runs']['forced']['evaluation_indices']=list(range(49))
  with self.assertRaises(ValueError):verify_gate(g,'fitness')
 def test_all_off_or_wrong_NFE_rejected(self):
  for key,value in [('routed_blocks',0),('NFE',29),('valid_frames',158)]:
   g=gate();g['runs']['forced'][key]=value
   with self.assertRaises(ValueError):verify_gate(g,'fitness')
 def test_missing_clean_condition_check_rejected(self):
  g=gate();del g['checks']['actual_clean_conditions_equal']
  with self.assertRaises(ValueError):verify_gate(g,'fitness')
 def test_original_runtime_bytes_and_CPU_plan(self):
  c=verify_runtime();self.assertEqual(c['source_tracking_policy'],'fresh_host41_for_both_sources');argv=command('fitness','reference','GPU-example','python');self.assertIn('human/fitness/000',argv);self.assertIn('--control',argv)
 def test_labels_preserve_numeric_and_unknown(self):
  x={'automatic':{'lag_ms':250,'status':'unknown','value':None},'native':{'lag_ms':375},'rows':[{'automatic':0.3}]};y=relabel(x)
  self.assertEqual(y,{'forced':{'lag_ms':250,'status':'unknown','value':None},'native':{'lag_ms':375},'rows':[{'forced':0.3}]});self.assertIn('automatic',x)
if __name__=='__main__':unittest.main(verbosity=2)
