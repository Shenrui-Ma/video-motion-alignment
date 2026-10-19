import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import common,source_cache,score_one,tracking_plan,summarize,make_triptych

def gate():
 p=common.pair_info(common.PAIR_KEYS[0]);key=p['pair_key']
 return {'schema':'r66-paired-runtime-gate-v1','passed':True,'source_id':key,'pair_key':key,'motion_source_id':p['motion_source_id'],'original_pair_id':p['original_pair_id'],'group':p['group'],'prompt_version':'R49_original','checks':{k:True for k in ['actual_clean_conditions_equal','actual_initial_AV_noise_equal','Native_prefix_0_5_equal','producer_seal','native_reference_geometry','forced_reference_geometry']},'runs':{m:{'run_id':f'r66_{key}_seed2026101701_{m}','valid_frames':147,'NFE':20,'Euler_updates':20,'routed_blocks':0 if m=='native' else 450,'evaluation_indices':common.INDICES,'evaluation_fps':8} for m in common.METHODS}}
class IntakeTests(unittest.TestCase):
 def test_runtime_frozen_and_plan_only(self):
  c=common.verify_runtime();self.assertEqual(len(c['pairs']),8);self.assertEqual(len(c['motion_sources']),5)
  command=tracking_plan.command('human2animal_1','reference','GPU-test','python');self.assertIn('human/human2animal_1/000',command);self.assertIn('--control',command)
 def test_actual_pair_required(self):
  g=gate();common.verify_gate(g,common.PAIR_KEYS[0]);g['passed']=False
  with self.assertRaises(ValueError):common.verify_gate(g,common.PAIR_KEYS[0])
 def test_wrong_target_pair_rejected(self):
  with self.assertRaises(ValueError):common.verify_gate(gate(),common.PAIR_KEYS[1])
 def test_wrong_group_rejected(self):
  g=gate();g['group']='official_csv_identity_generalization'
  with self.assertRaises(ValueError):common.verify_gate(g,common.PAIR_KEYS[0])
 def test_wrong_frame_map_rejected(self):
  g=gate();g['runs']['forced']['evaluation_indices']=list(range(49))
  with self.assertRaises(ValueError):common.verify_gate(g,common.PAIR_KEYS[0])
 def test_all_off_or_extra_prediction_rejected(self):
  for k,v in [('routed_blocks',0),('NFE',29),('valid_frames',158)]:
   g=gate();g['runs']['forced'][k]=v
   with self.assertRaises(ValueError):common.verify_gate(g,common.PAIR_KEYS[0])
 def test_missing_reference_shape_proof_rejected(self):
  g=gate();del g['checks']['forced_reference_geometry']
  with self.assertRaises(ValueError):common.verify_gate(g,common.PAIR_KEYS[0])
 def test_shared_source_different_target_have_same_reference_id(self):
  a,b=map(common.pair_info,common.PAIR_KEYS[:2]);self.assertEqual(a['reference_id'],b['reference_id']);self.assertNotEqual(a['pair_key'],b['pair_key']);self.assertNotEqual(a['portrait_sha256'],b['portrait_sha256'])
 def test_full_and_short_presentation_timestamps(self):
  for n in [48,147]:
   cmd=make_triptych.build(['a','b','c'],'font.ttf','out.mp4',n);graph=cmd[cmd.index('-filter_complex')+1]
   self.assertEqual(graph.count('start_frame=0:end_frame='+str(n)),3);self.assertIn('hstack=inputs=3',graph);self.assertNotIn('minterpolate',graph)
 def test_fixed_missing_denominators_and_separate_groups(self):
  value=summarize.summarize();self.assertEqual(value['total_pairs'],8);self.assertEqual([x['prespecified_pair_denominator'] for x in value['groups']],[2,6]);self.assertEqual([x['motion_source_denominator'] for x in value['groups']],[2,3]);self.assertTrue(all(x['mean_paired_delta'] is None for x in value['groups']))

class ReuseTests(unittest.TestCase):
 def fixtures(self):
  c=common.read(ROOT/'configs/contract.json');r=c['reuse_r65'];item=common.source_item('fitness');report={'case':item,'passed':True,'manifest_sha256':r['source_manifest_sha256'],'admission_before_cuda':{'hostname':'host41','gpu_name':'RTX'}}
  binding={'frozen_numerical_tracker':{'sha256':common.sha(common.METRIC/'run_tracks.py')},'administrative_wrapper':{'sha256':r['wrapper_sha256']},'root_registration':{'consumer_freeze_sha256':r['consumer_freeze_sha256'],'input_manifest':{'sha256':r['source_manifest_sha256']}},'hostname':'host41'}
  return report,binding,{'inputs':[item]},c
 def test_matching_fresh_r65_reference_allowed(self):
  report,binding,manifest,c=self.fixtures();self.assertIs(source_cache.validate_r65_report(report,binding,manifest,'fitness',c),report)
 def test_historical_r49_cache_rejected(self):
  report,binding,manifest,c=self.fixtures();binding['root_registration']['consumer_freeze_sha256']='R49'
  with self.assertRaises(ValueError):source_cache.validate_r65_report(report,binding,manifest,'fitness',c)
 def test_other_reference_video_rejected(self):
  report,binding,manifest,c=self.fixtures();report['case']['sha256']='other'
  with self.assertRaises(ValueError):source_cache.validate_r65_report(report,binding,manifest,'fitness',c)
 def test_wrong_manifest_rejected(self):
  report,binding,manifest,c=self.fixtures();report['manifest_sha256']='other'
  with self.assertRaises(ValueError):source_cache.validate_r65_report(report,binding,manifest,'fitness',c)
 def test_source_target_host_gpu_torch_mismatch_rejected(self):
  a={k:'fixed' for k in ['torch_version','cuda_version','checkpoint_sha256','metric_functions_sha256','vendor_manifest_sha256','grid_size','mask','tracks_dtype']};a['admission_before_cuda']={'hostname':'host41','gpu_name':'RTX'}
  score_one.same_runtime(a,copy.deepcopy(a))
  for location in ['hostname','gpu_name','torch_version']:
   b=copy.deepcopy(a)
   if location=='torch_version':b[location]='other'
   else:b['admission_before_cuda'][location]='other'
   with self.assertRaises(ValueError):score_one.same_runtime(a,b)

class NumericInheritanceTests(unittest.TestCase):
 def test_scoring_functions_exact_and_undefined_preserved(self):
  import torch
  torch.set_num_threads(1);adapter=common.load('test_r66_metric',common.METRIC/'metric_adapter.py');old=Path('/Users/researcher/DevProjects/h3-flexiact-forced-metrics-r65-20261018/runtime/official_metric/metric_adapter.py')
  self.assertEqual(common.sha(common.METRIC/'metric_adapter.py'),common.sha(old))
  t=torch.arange(49,dtype=torch.float32);tracks=torch.stack([torch.stack([t*(i+1),t*.5],-1) for i in range(4)])
  result,matrix=adapter.score_tracks(tracks,tracks);self.assertEqual(result['status'],'finite')
  direction=torch.tensor([[i+1,.5] for i in range(4)],dtype=torch.float32);direction=direction/direction.norm(dim=-1,keepdim=True);expected=(direction@direction.T-torch.eye(4)).max(dim=1).values.mean().item()
  self.assertAlmostEqual(result['score'],expected,places=6)
  zero,_=adapter.score_tracks(torch.zeros_like(tracks),torch.zeros_like(tracks));self.assertIsNone(zero['score']);self.assertEqual(zero['status'],'undefined_nonfinite_official_score')
if __name__=='__main__':unittest.main(verbosity=2)
