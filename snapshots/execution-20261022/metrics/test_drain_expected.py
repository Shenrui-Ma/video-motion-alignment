"""Draining executable manifests must preserve original metric denominators."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import watch_outputs as relay


class DrainedExpectedJobsTest(unittest.TestCase):
    def test_original_plans_survive_drain_and_innovation_cohort(self):
        def job(name, task, method, cohort='expansion'):
            return dict(id=name, metadata=dict(task_id=task, benchmark='IVEBench', method=method, cohort=cohort))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a_done = job('expand_a_native', 'a', 'native')
            a_parked = job('expand_a_weak', 'a', 'global_weak')
            b_parked = job('expand_b_native', 'b', 'native')
            innovation = job('innov_a_direction', 'a', 'direction_gated', 'innovation')
            plans = {
                'supervision/innovation_handoff/records/host9a/original_manifest.json': [a_done, a_parked],
                'supervision/innovation_handoff/records/host41/original_manifest.json': [b_parked],
                'inference/host9a/jobs.json': [a_done, innovation],
                'inference/host9b/jobs.json': [],
            }
            for rel, jobs in plans.items():
                path = root / rel; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({'jobs': jobs}))
            source = dict(id='a__source', task_id='a', dataset='IVEBench', method='source', cohort='main')
            with patch.object(relay, 'ROOT', root / 'metrics'):
                expected = {j['id']: j for j in relay.expected_jobs({'jobs': [source]})}
            self.assertEqual(set(expected), {'expand_a_native', 'expand_a_weak', 'expand_b_native', 'innov_a_direction', 'a__source', 'b__source'})
            self.assertEqual(expected['innov_a_direction']['cohort'], 'innovation')
            self.assertEqual(expected['expand_a_weak']['cohort'], 'expansion')
            self.assertEqual(expected['a__source']['cohort'], 'main')


if __name__ == '__main__':
    unittest.main()
