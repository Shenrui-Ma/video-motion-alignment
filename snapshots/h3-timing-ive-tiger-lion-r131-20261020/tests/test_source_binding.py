from pathlib import Path
import copy,json,sys,unittest
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
import r123_contract as c
from preflight import check
class SourceBinding(unittest.TestCase):
 def test_preflight(self):self.assertTrue(check(R)['passed'])
 def test_exact_official_fields(self):
  s=c.read(R/'configs/scientific_contract.json');row=s['cases'][0];official=c.read(R/'design/INPUT_PLAN.json')['official_task']
  for k in ['source_prompt','edit_prompt','target_prompt']:self.assertIn(official[k],row['prompt'])
  self.assertEqual(row['prompt'].split('\n\nretention_analysis:')[0].splitlines()[-1],official['edit_prompt'])
 def test_geometry_and_valid_support(self):
  row=c.read(R/'configs/scientific_contract.json')['cases'][0]
  self.assertEqual(c.geometry(row)['frames'],73);self.assertEqual(row['valid_frame_count'],60)
  self.assertEqual(c.latent_shapes(row),{'video':(1,24,22,46,82),'audio':(1,32,2,122)})
  self.assertEqual(c.routing_layout(row)['latent_interval_half_open'],[0,18]);self.assertEqual(c.routing_layout(row)['pure_pad_bins'],[18,19,20,21])
 def test_only_mode_and_run_ids_between_graphs(self):
  a,b=c.read(R/'configs/scientific_contract.json')['cases'];x=c.expected_graph(R,a);y=c.expected_graph(R,b)
  for node in ['6','50','51','52']:x[node]['inputs']['run_id']=y[node]['inputs']['run_id']
  x['14']['inputs']['filename_prefix']=y['14']['inputs']['filename_prefix'];x['50']['inputs']['mode']=y['50']['inputs']['mode']
  self.assertEqual(x,y)
 def test_actual_parent_noise_shape_sha(self):
  n=c.read(R/'configs/parent_noise.json');m=c.read(R/'inputs/initial_AV_noise_r128.json')
  self.assertEqual(n['signature'],m['signature']);self.assertEqual(n['source_sha256'],c.sha(R/'inputs/initial_AV_noise_r128.pt'))
  self.assertEqual(n['signature']['shapes'],[[1,24,22,46,82],[1,32,2,122]])
 def test_every_prepared_frame_has_source_mapping(self):
  p=c.read(R/'inputs/short_0177_provenance.json');self.assertEqual(len(p['input_to_original_frame']),73);self.assertEqual(p['padding_indices'],list(range(60,73)))
  for i,j in enumerate(p['input_to_original_frame']):self.assertEqual(p['input_frame_md5'][i],p['original_transformed_frame_md5'][j])
  self.assertEqual(p['input_to_original_frame'][60:],[61]*13)
 def test_event_definitions_only_for_evaluation(self):
  e=c.read(R/'design/PREREGISTERED_EVENTS.json');self.assertFalse(e['generated_outputs_exist']);self.assertEqual(e['reviewed_all_prepared_valid_frames'],list(range(60)))
  self.assertNotIn('29',c.PROMPTS['short_0177']);self.assertNotIn('41',c.PROMPTS['short_0177'])
 def test_exact_numerical_kernel_inheritance(self):
  for rel,row in c.read(R/'configs/runtime_kernel_hashes.json').items():self.assertEqual(c.sha(R/rel),row['parent_sha256'])
if __name__=='__main__':unittest.main()
