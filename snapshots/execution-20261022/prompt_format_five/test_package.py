"""CPU contracts for the prompt-only and attention-only paired comparisons."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from build_package import BASE, HERE, CASES, VARIANTS, ROLES, six_section


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jobs = json.loads((HERE/'all_twenty_comparisons.json').read_text())['jobs']
        cls.bykey = {(j['metadata']['task_id'], j['metadata']['prompt_variant'], j['metadata']['guidance_method']):j for j in cls.jobs}
        cls.catalog = {c['task_id']:c for c in json.loads((BASE/'innovation/pilot_ten/manifest_preparation/catalog.json').read_text())['cases']}
        cls.metric = json.loads((BASE/'metrics/manifest.json').read_text())['jobs']

    def graph(self, sid, variant, role):
        return json.loads((HERE/'package'/self.bykey[sid,variant,role]['graph']).read_text())

    def test_count_and_unique_ids(self):
        self.assertEqual(len(self.jobs),20)
        self.assertEqual(len({j['id'] for j in self.jobs}),20)
        active=json.loads((HERE/'package/jobs.json').read_text())['jobs']
        self.assertEqual(len(active),5)
        self.assertEqual({j['metadata']['method'] for j in active},{'six_section_native'})
        self.assertEqual(len(json.loads((HERE/'reuse.json').read_text())['items']),2)

    def test_prompt_variants_change_only_prompt_and_output_prefix(self):
        for sid in CASES:
            for role in ROLES:
                with self.subTest(case=sid,role=role):
                    a,b = [self.graph(sid,v,role) for v in VARIANTS]
                    a['5']['inputs'].pop('prompt'); b['5']['inputs'].pop('prompt')
                    a['14']['inputs'].pop('filename_prefix'); b['14']['inputs'].pop('filename_prefix')
                    self.assertEqual(a,b)

    def test_attention_variants_change_only_router_and_output(self):
        for sid in CASES:
            for variant in VARIANTS:
                with self.subTest(case=sid,variant=variant):
                    a,b = [self.graph(sid,variant,r) for r in ROLES]
                    for g in (a,b):
                        for k in ('mode','alpha','schedule'): g['50']['inputs'].pop(k)
                        g['14']['inputs'].pop('filename_prefix')
                    self.assertEqual(a,b)

    def test_exact_prompt_template_and_no_extra_semantics(self):
        for sid in CASES:
            instruction = next(j['metadata']['edit_prompt'] for j in self.metric if j['task_id']==sid)
            for role in ROLES:
                self.assertEqual(self.graph(sid,'raw',role)['5']['inputs']['prompt'],instruction)
                p=self.graph(sid,'six_section',role)['5']['inputs']['prompt']
                self.assertEqual(p,six_section(instruction))
                self.assertEqual(p.count(instruction),1)
                self.assertEqual(len(p.split('\n\n')),6)
                self.assertEqual(p.count('Not specified.'),4)
                self.assertNotIn('Preserve',p)

    def test_geometry_seed_sampling_and_models_frozen(self):
        for sid in CASES:
            c=self.catalog[sid];geo=c['geometry']
            original=json.loads(Path(c['graphs']['native']['copy']).read_text())
            for variant in VARIANTS:
                for role in ROLES:
                    with self.subTest(case=sid,variant=variant,role=role):
                        g=self.graph(sid,variant,role)
                        for n in ('1','2','3','4','8','9','41','13'):self.assertEqual(g[n],original[n])
                        self.assertEqual(g['6']['inputs']['noise_seed'],c['seed'])
                        self.assertEqual(g['5']['inputs']['width'],geo['width'])
                        self.assertEqual(g['5']['inputs']['height'],geo['height'])
                        self.assertEqual(g['5']['inputs']['length'],geo.get('sampled_frames',geo.get('frames')))
                        self.assertEqual(g['22'],original['22'])
                        self.assertEqual(len(g['9']['inputs']['sigmas'].split(',')),21)
                        r=g['50']['inputs']
                        self.assertEqual([r[k] for k in ('start_frame','end_frame','radius','time_offset','block_start','block_end','step_start','step_end')],
                                         [0,geo['valid_frames']-1,0,0,0,50,0,20])
                        self.assertEqual(r['alpha'],1.0 if role=='native' else .25)
                        self.assertEqual(r['mode'],'native' if role=='native' else 'mass_preserve')

    def test_no_historical_conditioning_or_x0_observer(self):
        for job in self.jobs:
            g=json.loads((HERE/'package'/job['graph']).read_text())
            self.assertEqual(g['5']['class_type'],'H3StudyReference')
            self.assertFalse(any('Cached' in n['class_type'] or 'X0' in n['class_type'] or 'Pose' in n['class_type'] for n in g.values()))
            self.assertEqual(g['7']['inputs']['conditioning'],['5',0])
            self.assertEqual(g['50']['inputs']['positive'],['5',0])
            self.assertEqual(g['10']['inputs']['latent_image'],['5',1])

    def test_graph_references_and_hashes(self):
        for job in self.jobs:
            p=HERE/'package'/job['graph'];g=json.loads(p.read_text())
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),job['metadata']['graph_sha256'])
            for node in g.values():
                for v in node['inputs'].values():
                    if isinstance(v,list) and len(v)==2:
                        self.assertIn(v[0],g)
            self.assertEqual(job['metadata']['cohort'],'prompt_format')
            self.assertEqual(job['metadata']['method'],job['metadata']['prompt_variant']+'_'+job['metadata']['guidance_method'])

    def test_reused_doctor_graphs_identical(self):
        for role in ROLES:
            g=self.graph('short_0343','raw',role)
            old=json.loads((BASE/f'inference/package/graphs/new_short_0343_{role}.json').read_text())
            for x in (g,old):x['14']['inputs'].pop('filename_prefix')
            self.assertEqual(g,old)
        reused=json.loads((HERE/'reuse.json').read_text())['items']
        for x in reused:
            old=next(j for j in self.metric if j['id']==x['existing_job_id'])
            self.assertEqual(x['video_sha256'],old['sha256'])
            self.assertEqual(x['metadata']['seed'],old['seed'])

    def test_input_files_hashes_and_no_images(self):
        for x in json.loads((HERE/'assets.json').read_text())['assets']:
            p=Path(x['local_file']);self.assertTrue(p.is_file())
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),x['sha256'])
        self.assertTrue(all(j['metadata']['reference_image'] is None for j in self.jobs))


if __name__=='__main__':unittest.main(verbosity=2)
