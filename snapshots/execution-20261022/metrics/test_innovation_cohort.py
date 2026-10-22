"""CPU-only regression tests for innovation routing and paired metric summaries."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import watch_outputs as relay
from aggregate import INNOVATION_METHODS, aggregate


class InnovationCohortTests(unittest.TestCase):
    def test_explicit_cohort_precedes_legacy_id(self):
        self.assertEqual(relay.result_cohort('new_x', {'cohort': 'innovation'}), 'innovation')
        self.assertEqual(relay.result_cohort('new_x', {}), 'main')
        self.assertEqual(relay.result_cohort('expand2_x', {}), 'expansion')

    def test_expected_jobs_reuses_main_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / 'inference/host9a'
            package.mkdir(parents=True)
            job = dict(id='new_innovation_x', metadata=dict(task_id='x', benchmark='IVEBench', method='direction_gated', cohort='innovation'))
            (package / 'jobs.json').write_text(json.dumps({'jobs': [job]}))
            source = dict(id='x__source', task_id='x', dataset='IVEBench', method='source', cohort='main')
            with patch.object(relay, 'ROOT', root / 'metrics'):
                expected = relay.expected_jobs({'jobs': [source]})
            self.assertEqual(len(expected), 2)
            self.assertEqual(expected[0]['cohort'], 'main')
            self.assertEqual(expected[1]['cohort'], 'innovation')

    def test_add_result_routes_innovation_without_duplicate_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source_path = Path(temp) / 'source.mp4'
            source_path.write_bytes(b'test fixture')
            source = dict(id='x__source', task_id='x', dataset='IVEBench', method='source', cohort='main')
            manifest = {'jobs': [source]}
            m = dict(task_id='x', method='partial_temporal_rope', benchmark='IVEBench', cohort='innovation', reference_video=str(source_path), evaluation_metadata={'edit_prompt': 'Add glasses.'}, valid_frames=73, evaluation_crop_xywh=[0, 0, 320, 320], fps=24, seed=1, prompt='Add glasses.')
            result = dict(job_id='new_partial_x', metadata=m, files=[{'path': '/remote/out.mp4', 'sha256': 'fixture'}], timing={'sampling_seconds': 40})
            with patch.object(relay, 'transfer') as transfer:
                self.assertTrue(relay.add_result('test-host', result, manifest))
                self.assertFalse(relay.add_result('test-host', result, manifest))
            self.assertEqual(len(manifest['jobs']), 2)
            self.assertEqual(manifest['jobs'][1]['cohort'], 'innovation')
            self.assertEqual(manifest['jobs'][0], source)
            self.assertEqual(transfer.call_count, 2)

    def test_innovation_means_controls_reference_and_missing_rows(self):
        expected, rows = [], []
        def add(task, dataset, method, cohort, score, timing=None):
            job = dict(id=f'{cohort}_{dataset}_{task}_{method}', task_id=task, dataset=dataset, method=method, cohort=cohort)
            if timing:
                job['timing'] = timing
            expected.append(job)
            if score is not None:
                rows.append(dict(job, job_id=job['id'], metric='motion_fidelity', status='done', score=score))
        for task, dataset in [('a', 'IVEBench'), ('b', 'FlexiAct')]:
            add(task, dataset, 'source', 'main', .99)
            add(task, dataset, 'native', 'main', .5)
            add(task, dataset, 'global_weak', 'main', .6)
            add(task, dataset, 'direction_gated', 'innovation', .8 if task == 'a' else .7, {'sampling_seconds': 100, 'mean_sampling_step_seconds': 5})
            add(task, dataset, 'partial_temporal_rope', 'innovation', None)
            add(task, dataset, 'temporal_coverage', 'innovation', .75)
        # Same task in expansion must not replace the frozen main controls.
        add('a', 'IVEBench', 'global_weak', 'expansion', .95)
        result = aggregate(rows, expected)
        main = result['main_IVEBench']['methods']
        self.assertEqual(main['native']['motion_fidelity']['mean'], .5)
        self.assertNotIn('direction_gated', main)
        self.assertEqual(result['expansion_IVEBench']['methods']['global_weak']['motion_fidelity']['mean'], .95)
        innovation = result['innovation_all']
        self.assertAlmostEqual(innovation['methods']['direction_gated']['motion_fidelity']['mean'], .75)
        self.assertAlmostEqual(innovation['methods']['direction_gated']['motion_fidelity_delta_from_reference']['mean'], -.24)
        self.assertEqual(innovation['methods']['direction_gated']['timing']['mean_sampling_seconds'], 100)
        self.assertEqual(innovation['methods']['partial_temporal_rope']['motion_fidelity']['n_pending'], 2)
        self.assertEqual(innovation['complete_paired_subset']['motion_fidelity']['n_complete_cases'], 0)
        pair = innovation['paired_against_main_controls']['direction_gated']['motion_fidelity']
        self.assertEqual(pair['n_complete_cases'], 2)
        self.assertAlmostEqual(pair['mean_delta_from_global_weak'], .15)
        ive = result['innovation_IVEBench']['paired_against_main_controls']['direction_gated']['motion_fidelity']
        self.assertEqual(ive['n_complete_cases'], 1)
        self.assertEqual(ive['method_means']['global_weak'], .6)
        missing = innovation['paired_against_main_controls']['partial_temporal_rope']['motion_fidelity']
        self.assertEqual(missing['n_complete_cases'], 0)
        self.assertIsNone(missing['mean_delta_from_global_weak'])
        self.assertEqual(set(innovation['methods']), set(INNOVATION_METHODS))


if __name__ == '__main__':
    unittest.main()
