import ast
from fractions import Fraction
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import input_contract as c


class Inputs(unittest.TestCase):
    def test_selected_five_frozen_before_generation(self):
        for name,digest in c.read(ROOT/'configs/source_selection_hashes.json').items():self.assertEqual(c.sha(ROOT/'configs/source_selection'/name),digest)
        d=c.read(ROOT/'configs/source_selection/SELECTED_5_MANIFEST.json')
        self.assertEqual(d['selected_order'],list(c.SOURCES));self.assertTrue(d['selection_before_generation'])
        self.assertTrue(all(x['generated_h3_results_consulted']==0 for x in d['pairs']))

    def test_shapes_equal_actual_pinned_H3_code(self):
        p=ROOT/'source_snapshot/nodes_minimax_h3.py';self.assertEqual(c.sha(p),c.read(ROOT/'source_snapshot/r71/configs/parent_core_hashes.json')['comfy_extras/nodes_minimax_h3.py'])
        names={'align_frame_count','video_latent_t','temporal_shape'}
        nodes=[x for x in ast.parse(p.read_text()).body if isinstance(x,ast.FunctionDef) and x.name in names]
        env={'FPS':24,'AUDIO_LATENT_FPS':40};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),env)
        for t,n in c.LENGTHS:self.assertEqual(env['temporal_shape'](t),(t,c.latent_shape(t)['video'][2],c.latent_shape(t)['audio'][-1]))

    def test_nearest_tie_earlier(self):
        self.assertEqual(c.nearest_map(['0','1/12'],2),[0,0])

    def test_complete_source_mapping_and_tail(self):
        rows=c.read(ROOT/'design/INPUT_PLAN.json')['pairs']
        for row,(t,n) in zip(rows,c.LENGTHS):
            plan=row['input_protocol'];self.assertEqual((plan['h3_frame_count'],plan['effective_frame_count']),(t,n))
            source=row['source'];mapping=c.nearest_map(source['actual_pts_rational'],n)
            self.assertEqual(plan['input_to_original_frame'],mapping+[mapping[-1]]*(t-n))
            self.assertEqual(mapping[0],0);self.assertEqual(mapping[-1],source['frame_count']-1)

    def test_effective_bins_equal_inherited_router(self):
        p=ROOT/'source_snapshot/r71/extensions/H3TemporalRouter/layout.py'
        nodes=[x for x in ast.parse(p.read_text()).body if isinstance(x,ast.FunctionDef) and x.name in {'frame_spans','event_latent_range'}]
        env={'FRAME_PER_TOKEN':(1,4,4,4,4)};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),env)
        for t,n in c.LENGTHS:
            layout=c.route_bins(t,n);self.assertEqual(list(env['event_latent_range'](0,n-1,layout['total_latent_bins'])),layout['latent_interval_half_open'])
            spans=env['frame_spans'](layout['total_latent_bins'])
            self.assertTrue(all(sum(spans[:k])>=n for k in layout['pure_pad_bins']))

    def test_input_transform_exact_R64_functions(self):
        def funcs(path):return {n.name:ast.dump(n) for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in {'frame_hashes','decode'}}
        self.assertEqual(funcs(ROOT/'scripts/prepare_inputs.py'),funcs(ROOT/'source_snapshot/r64/prepare_inputs.py'))

    def test_actual_prepared_hash_and_pixel_mapping(self):
        for row in c.read(ROOT/'design/INPUT_PLAN.json')['pairs']:
            name=row['pair_id'];p=c.read(ROOT/'inputs'/(name+'_provenance.json'))
            self.assertEqual(c.sha(ROOT/'inputs'/(name+'_video.mp4')),p['video_sha256'])
            self.assertEqual(c.sha(ROOT/'inputs'/(name+'_original.mp4')),row['source']['sha256'])
            self.assertEqual(p['input_frame_md5'],[p['original_transformed_frame_md5'][i] for i in p['input_to_original_frame']])
            self.assertTrue(p['decoded_pixel_mapping_exact'])

    def test_draft_preserves_each_official_edit(self):
        template=(ROOT/'design/P1_TEMPLATE_DRAFT.txt').read_text();self.assertIn('apply the requested edit.',template)
        self.assertNotIn('appearance edit.',template)
        for row in c.read(ROOT/'design/INPUT_PLAN.json')['pairs']:
            prompt=(ROOT/'configs/prompts'/(row['pair_id']+'_DRAFT.txt')).read_text()
            self.assertEqual(prompt,template.format(source_prompt=row['source_prompt'],edit_prompt=row['edit_prompt'],target_prompt=row['target_prompt']))
            self.assertIn('Requested edit: '+row['edit_prompt'],prompt)

    def test_numerical_snapshot_matches_R71(self):
        for path,spec in c.read(ROOT/'source_snapshot/r71/configs/runtime_kernel_hashes.json').items():
            self.assertEqual(c.sha(ROOT/'source_snapshot/r71'/path),spec['current_sha256'])


if __name__=='__main__':unittest.main()
