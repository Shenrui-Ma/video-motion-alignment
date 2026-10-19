import ast
from fractions import Fraction
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import input_contract as c


class Inputs(unittest.TestCase):
    def test_root_original_design_and_source_order_exact(self):
        b=c.read(ROOT/'audit/ROOT_DESIGN_BINDINGS.json')
        for path,digest in b.items():self.assertEqual(c.sha(ROOT/path),digest)
        proposal=c.read(ROOT/'design/PROPOSAL.json');self.assertEqual([x['source_id'] for x in proposal['cases']],list(c.SOURCES))
        for name,digest in c.read(ROOT/'configs/source_selection_hashes.json').items():self.assertEqual(c.sha(ROOT/'configs/source_selection'/name),digest)

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
            source=row['source'];a=row['clip']['start_frame'];b=row['clip']['end_frame_inclusive'];mapping=c.clip_nearest_map(source['actual_pts_rational'],a,b,n)
            self.assertEqual(plan['input_to_original_frame'],mapping+[mapping[-1]]*(t-n))
            self.assertEqual(mapping[0],a);self.assertEqual(mapping[-1],b);self.assertEqual(n,c.clip_valid_count(row['clip']['start_pts_rational'],row['clip']['end_exclusive_rational']))

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

    def test_exact_root_P1_and_official_task(self):
        for row in c.read(ROOT/'design/PROPOSAL.json')['cases']:
            sid=row['source_id'];p=ROOT/'configs/prompts'/(sid+'.txt');self.assertEqual(c.sha(p),row['prompt_sha256']);self.assertEqual(p.read_bytes(),(ROOT/'design'/(sid+'_P1_candidate.txt')).read_bytes());self.assertIn('Requested edit: '+row['official_task']['edit_prompt'],p.read_text())

    def test_numerical_snapshot_matches_R71(self):
        for path,spec in c.read(ROOT/'source_snapshot/r71/configs/runtime_kernel_hashes.json').items():
            self.assertEqual(c.sha(ROOT/'source_snapshot/r71'/path),spec['current_sha256'])


if __name__=='__main__':unittest.main()

class SourceTimeAndPrompt(unittest.TestCase):
 def test_rational_source_time_agrees_with_actual_pts(self):
  for row in c.read(ROOT/'design/INPUT_PLAN.json')['pairs']:
   s=row['source'];self.assertEqual(len(s['actual_pts_rational']),len(s['actual_pts_s']))
   self.assertLessEqual(max(abs(float(Fraction(a))-b) for a,b in zip(s['actual_pts_rational'],s['actual_pts_s'])),1.1e-6)
 def test_root_requested_protocol_sections_preserved(self):
  for row in c.read(ROOT/'design/INPUT_PLAN.json')['pairs']:
   p=(ROOT/'configs/prompts'/(row['pair_id']+'.txt')).read_text()
   for h in ['subject_definitions:','summary:','retention_analysis:','detailed_description:','overall_soundscape:','non_diegetic_music:','<Video 1>','<Subject 1>','[video editing]']:self.assertIn(h,p)
   self.assertEqual(p.count('Requested edit: '+row['edit_prompt']),1)
 def test_source_30fps_count_and_clipped_25fps_counts(self):
  self.assertEqual(c.LENGTHS,((124,120),(158,144),(158,144)))
  rows={r['source_id']:r for r in c.read(ROOT/'design/INPUT_PLAN.json')['pairs']}
  self.assertEqual(rows['long_0081']['source']['frame_count'],149)
  self.assertEqual(rows['long_0059']['clip']['start_frame'],175)
  self.assertEqual(rows['long_0163']['clip']['start_frame'],52)
 def test_original_LFS_bytes_and_full_or_clip_scope(self):
  rows=c.read(ROOT/'design/PROPOSAL.json')['cases']
  for x in rows:self.assertEqual(c.sha(ROOT/'inputs'/(x['source_id']+'_original.mp4')),x['source']['official_lfs']['oid'])
  cases=c.read(ROOT/'configs/scientific_contract.json')['cases'][::2];self.assertEqual([x['task_scope']=='style_extension' for x in cases],[False,False,False]);self.assertEqual([x['evaluation_scope']=='IVEBench素材片段探索' for x in cases],[False,True,True])
