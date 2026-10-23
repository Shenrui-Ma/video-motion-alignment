import ast
import json
import unittest
from pathlib import Path
from build import METHODS, OUT, ROOT, SOURCE, sha


def input_schema(path, class_name):
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'INPUT_TYPES')
    isolated = ast.ClassDef(name=class_name, bases=[], keywords=[], body=[method], decorator_list=[])
    namespace = {'SCHEDULES': {'all': tuple(range(20))}}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[isolated], type_ignores=[])), str(path), 'exec'), namespace)
    return namespace[class_name].INPUT_TYPES()


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals = json.loads((SOURCE/'jobs.json').read_text())['jobs']
        cls.jobs = {m: json.loads((OUT/m/'jobs.json').read_text())['jobs'] for m in METHODS}

    def test_ten_cases_and_pilot_order(self):
        for method, jobs in self.jobs.items():
            self.assertEqual(len(jobs), 10)
            self.assertEqual([j['metadata']['task_id'] for j in jobs], [j['metadata']['task_id'] for j in self.originals])
            pilot = json.loads((OUT/method/'pilot_jobs.json').read_text())['jobs']
            self.assertEqual([j['metadata']['task_id'] for j in pilot], ['short_0252','short_0358'])

    def test_only_intervention_and_save_prefix_change(self):
        for method, jobs in self.jobs.items():
            for original, job in zip(self.originals, jobs):
                before = json.loads((SOURCE/original['graph']).read_text())
                after = json.loads((OUT/method/job['graph']).read_text())
                self.assertEqual(set(before), set(after))
                changed = {key for key in before if before[key] != after[key]}
                self.assertEqual(changed, {'14','50'})
                for key in ['prompt','seed','geometry','evaluation_crop_xywh','reference_video','source_video','reference_image','comparison_outputs']:
                    self.assertEqual(job['metadata'][key], original['metadata'][key])
                self.assertEqual(job['metadata']['direction_source_graph_sha256'], sha(SOURCE/original['graph']))

    def test_full_weak_and_whole_valid_video(self):
        for method, jobs in self.jobs.items():
            for job in jobs:
                graph = json.loads((OUT/method/job['graph']).read_text())
                args = graph['50']['inputs']
                self.assertEqual(args['alpha'], .25)
                self.assertTrue(args['enabled'])
                self.assertEqual((args['block_start'], args['block_end']), (0,50))
                self.assertEqual(args['start_frame'], 0)
                self.assertEqual(args['end_frame'], job['metadata']['valid_frames']-1)
                self.assertEqual(job['metadata']['cohort'], 'innovation')
                if method == 'partial_temporal_rope':
                    self.assertEqual(args['schedule'], 'all')
                    self.assertEqual(args['delta_mode'], 'reference_origin')
                    self.assertEqual(args['delta_frames'], 0.)
                    self.assertEqual(json.loads(args['frequency_mask']), [0]*8+[1]*8)
                else:
                    self.assertEqual((args['step_start'],args['step_end']), (0,20))
                    self.assertEqual((args['radius'],args['entropy'],args['temporal_penalty'],args['minimum_mean_gap']), (2,.5,.25,0.))

    def test_node_schemas_and_links(self):
        configs = {
            'partial_temporal_rope': ('partial_rope/H3PartialRoPE/adapter.py', 'H3PartialRoPE'),
            'temporal_coverage': ('temporal_coverage/nodes.py', 'H3TemporalCoverage')}
        for method, (filename, cls) in configs.items():
            schema = input_schema(ROOT/'innovation'/filename, cls)
            for job in self.jobs[method]:
                graph = json.loads((OUT/method/job['graph']).read_text())
                args = graph['50']['inputs']
                self.assertEqual(graph['50']['class_type'], cls)
                self.assertTrue(set(schema['required']).issubset(args))
                self.assertTrue(set(args).issubset(set(schema['required'])|set(schema.get('optional',{}))))
                for node in graph.values():
                    for value in node['inputs'].values():
                        if isinstance(value,list) and len(value)==2 and isinstance(value[0],str):
                            self.assertIn(value[0], graph)
                self.assertEqual(graph['52']['inputs']['model'], ['50',0])
                self.assertEqual(graph['7']['inputs']['model'], ['52',0])

    def test_deployment_hashes_match_actual_code(self):
        deployment = json.loads((OUT/'deployment_files.json').read_text())
        for record in deployment['files']:
            self.assertEqual(sha(Path(record['file'])), record['sha256'])
        self.assertEqual(deployment['deployment_status'], 'not_deployed')


if __name__ == '__main__':
    unittest.main()
