import copy,json,sys,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
import r134_contract as c
from input_contract import clip_nearest_map,clip_valid_count
class Contract(unittest.TestCase):
 def test_only_authorized_source_and_two_jobs(self):
  jobs,order=c.registry(R);self.assertEqual(c.SOURCES,('short_0353',));self.assertEqual(len(order),2)
  self.assertEqual([jobs[x]['arm'] for x in order],['native','forced'])
 def test_common_prompt_and_unchanged_edit(self):
  s=c.read(R/'configs/scientific_contract.json');a,b=s['cases'];self.assertEqual(a['prompt'],b['prompt']);self.assertEqual(a['original_task']['edit_prompt'],'Change the blue scrubs to green.')
  self.assertEqual(a['prompt'],(R/'design/GENERIC_RETENTION_TEMPLATE.txt').read_text())
  self.assertEqual(s['prompt_version'],a['prompt_version'])
  for key in ('source_prompt','target_prompt'):self.assertNotIn(a['original_task'][key],a['prompt'])
  self.assertIn('<Video 1>: partially_preserved - Preserve',a['prompt'])
 def test_pair_graph_has_only_route_and_id_differences(self):
  s=c.read(R/'configs/scientific_contract.json');a,b=[c.read(R/'configs/graphs'/(x['run_id']+'.json')) for x in s['cases']]
  def normalize(g):
   g=copy.deepcopy(g)
   for n in ('6','50','51','52'):g[n]['inputs']['run_id']='SAME'
   g['14']['inputs']['filename_prefix']='SAME';g['50']['inputs']['mode']='SAME';return g
  self.assertEqual(normalize(a),normalize(b))
 def test_numeric_modules_exact(self):
  for p,v in c.read(R/'configs/runtime_kernel_hashes.json').items():self.assertEqual(c.sha(R/p),v['parent_sha256'])
 def test_pixel_mapping_bound(self):
  p=c.read(R/'inputs/short_0353_provenance.json');self.assertTrue(p['decoded_pixel_mapping_exact']);self.assertEqual(p['input_frame_md5'],[p['original_transformed_frame_md5'][i] for i in p['input_to_original_frame']]);self.assertEqual(c.sha(R/'inputs/short_0353_video.mp4'),p['video_sha256'])
 def test_physical_time_and_padding(self):
  row=c.read(R/'design/INPUT_PLAN.json')['pairs'][0];p=c.read(R/'inputs/short_0353_provenance.json');self.assertEqual(clip_valid_count('0','49049/24000'),50);self.assertEqual(p['input_to_original_frame'],clip_nearest_map(row['source']['actual_pts_rational'],0,48,50)+[48]*6);self.assertEqual(p['padding_indices'],list(range(50,56)))
 def test_router_wrong_window_rejected(self):
  with self.assertRaises(ValueError):c.validate_router('mass_preserve',1.,0,0,0,99,0,50,6,15,'r134_short_0353_seed2026101701_forced',c.REMOTE/'audit/router')
 def test_correct_router_scope(self):
  c.validate_router('mass_preserve',1.,0,0,0,49,0,50,6,15,'r134_short_0353_seed2026101701_forced',c.REMOTE/'audit/router')
if __name__=='__main__':unittest.main()
