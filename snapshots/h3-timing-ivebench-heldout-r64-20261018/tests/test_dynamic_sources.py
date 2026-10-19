import ast,copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r64_contract as c

class DynamicSources(unittest.TestCase):
 def test_shapes_match_pinned_actual_core(self):
  p=ROOT/'source_snapshot/nodes_minimax_h3.py'
  self.assertEqual(c.sha(p),c.read(ROOT/'configs/parent_core_hashes.json')['comfy_extras/nodes_minimax_h3.py'])
  tree=ast.parse(p.read_text());names={'align_frame_count','video_latent_t','temporal_shape'};nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
  env={'FPS':24,'AUDIO_LATENT_FPS':40};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),env)
  for case in c.read(ROOT/'configs/scientific_contract.json')['cases'][::2]:
   t=c.geometry(case)['frames'];actual=env['temporal_shape'](t);shapes=c.latent_shapes(case)
   self.assertEqual(actual,(t,shapes['video'][2],shapes['audio'][-1]))
 def test_effective_bins_match_inherited_router(self):
  p=ROOT/'extensions/H3TemporalRouter/layout.py';tree=ast.parse(p.read_text());names={'frame_spans','event_latent_range'};nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names];env={'FRAME_PER_TOKEN':(1,4,4,4,4)};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),env)
  for case in c.read(ROOT/'configs/scientific_contract.json')['cases'][::2]:
   a=c.routing_layout(case);first,last=env['event_latent_range'](0,case['valid_frame_count']-1,a['total_latent_bins']);self.assertEqual([first,last],a['latent_interval_half_open'])
   spans=env['frame_spans'](a['total_latent_bins']);self.assertEqual(a['position_bin_coverage_inclusive'][1],sum(spans[:last])-1)
   for i in a['pure_pad_bins']:self.assertGreaterEqual(sum(spans[:i]),case['valid_frame_count'])
 def test_exact_source_lengths_and_source_target_match(self):
  jobs,order=c.registry(ROOT);expect=[(73,58,22,122,18),(107,105,32,178,32),(124,109,37,207,33),(73,57,22,122,18)]
  for run,e in zip(order[::2],expect):
   case=jobs[run]['case'];g=c.read(ROOT/'configs/graphs'/f'{run}.json');shape=c.latent_shapes(case);route=c.routing_layout(case)
   self.assertEqual((case['geometry']['frames'],case['valid_frame_count'],shape['video'][2],shape['audio'][-1],route['latent_interval_half_open'][1]),e)
   self.assertEqual(g['5']['inputs']['length'],e[0]);self.assertEqual(g['52']['inputs']['length'],e[0]);self.assertEqual(g['22']['inputs']['file'],case['video'])
 def test_audio_and_manual_annotations_not_conditions(self):
  for p in (ROOT/'configs/graphs').glob('*.json'):
   g=c.read(p);self.assertNotIn('ref_audio',g['5']['inputs']);self.assertNotIn('ref_image',g['5']['inputs']);self.assertEqual(g['5']['inputs']['ref_video'],['23',0]);self.assertNotIn('CHECKPOINT',p.read_text())
 def test_source_frozen_original_metadata_used(self):
  selected=c.read(ROOT/'configs/source_selection/SELECTED_4_MANIFEST.json');self.assertEqual(selected['denominators']['new_h3_outputs_examined'],0)
  cases=c.read(ROOT/'configs/scientific_contract.json')['cases'];self.assertEqual([x['prompt'] for x in cases[::2]],[x['edit_prompt'] for x in selected['pairs']])
 def test_wrong_geometry_fails(self):
  original=c.read
  def read(p):
   v=original(p)
   if Path(p).name=='scientific_contract.json':v['cases'][0]['geometry']['frames']=90
   return v
  with patch.object(c,'read',side_effect=read):
   with self.assertRaisesRegex(ValueError,'geometry'):c.registry(ROOT)
 def test_wrong_original_prompt_fails(self):
  original=c.read
  def read(p):
   v=original(p)
   if Path(p).name=='scientific_contract.json':v['cases'][0]['prompt']='Preserve the waving at a specific time'
   return v
  with patch.object(c,'read',side_effect=read):
   with self.assertRaisesRegex(ValueError,'P0 edit prompt'):c.registry(ROOT)
 def test_numeric_cores_exact_r63(self):
  for f in ('extensions/H3TemporalRouter/core.py','extensions/H3TemporalRouter/layout.py','extensions/H3X0Readout/core.py','scripts/int8_row_chunking.py','scripts/compatibility_bootstrap.py','scripts/backend_dispatch_audit.py'):
   self.assertEqual(c.sha(ROOT/f),c.sha(ROOT/'source_snapshot/r63'/f),f)

if __name__=='__main__':unittest.main()
