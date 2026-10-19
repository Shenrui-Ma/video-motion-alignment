import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

R = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R/'scripts'), str(R/'analysis/postrun')]
import r113_contract as contract
import capture_checks
import execution_gate
import job
import verify_pair
from test_sampler_capture import run


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class SeedContractTests(unittest.TestCase):
    def copy_config(self, root):
        for folder in ('configs', 'design'):
            shutil.copytree(R/folder, root/folder)

    def test_exact_four_run_order(self):
        jobs, order = contract.registry()
        self.assertEqual([(jobs[r]['seed'], jobs[r]['arm']) for r in order],
                         [(s, a) for s in (2026101702, 2026101703) for a in ('native', 'fixed')])

    def test_same_seed_only_route_and_run_identity_change(self):
        for seed in contract.SEEDS:
            graphs = [contract.read(R/'configs/graphs'/(contract.pair_id(seed)+'_'+a+'.json'))
                      for a in contract.ARMS]
            a, b = graphs
            changed = {(n, k) for n in a for k, v in a[n]['inputs'].items() if v != b[n]['inputs'][k]}
            self.assertEqual(changed, {('6', 'run_id'), ('14', 'filename_prefix'),
                ('50', 'run_id'), ('50', 'mode'), ('51', 'run_id'), ('52', 'run_id')})
            self.assertEqual(a['6']['inputs']['pair_id'], b['6']['inputs']['pair_id'])
            self.assertEqual(a['6']['inputs']['noise_seed'], b['6']['inputs']['noise_seed'])

    def test_different_seeds_have_distinct_noise_cache(self):
        a, b = [contract.read(R/'configs/graphs'/(contract.pair_id(s)+'_native.json'))
                for s in contract.SEEDS]
        changed = {(n, k) for n in a for k, v in a[n]['inputs'].items() if v != b[n]['inputs'][k]}
        self.assertEqual(changed, {('6', 'run_id'), ('6', 'noise_seed'), ('6', 'pair_id'),
            ('14', 'filename_prefix'), ('50', 'run_id'), ('51', 'run_id'), ('52', 'run_id')})

    def test_graph_mutations_rejected(self):
        mutations = [('6', 'noise_seed', 2026101701), ('6', 'pair_id', 'old_seed'),
                     ('5', 'prompt', 'changed'), ('8', 'sampler_name', 'res_multistep'),
                     ('9', 'sigmas', '1,0'), ('50', 'mode', 'native'),
                     ('50', 'alpha', 3.), ('50', 'step_start', 5), ('50', 'end_frame', 106)]
        for node, key, value in mutations:
            with self.subTest(node=node, key=key), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.copy_config(root)
                path = root/'configs/graphs'/(contract.RUNS[1]+'.json')
                graph = contract.read(path)
                graph[node]['inputs'][key] = value
                write(path, graph)
                with self.assertRaises(ValueError):
                    contract.registry(root)

    def test_queue_cannot_skip_or_reorder_a_seed(self):
        for runs in [contract.RUNS[:2], tuple(reversed(contract.RUNS)), contract.RUNS[2:]+contract.RUNS[:2]]:
            with self.subTest(runs=runs), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.copy_config(root)
                write(root/'configs/queue.json', {'jobs': list(runs), 'finalize': True})
                with self.assertRaises(ValueError):
                    contract.registry(root)

    def test_foreign_seed_rejected(self):
        with self.assertRaises(ValueError):
            contract.pair_id(2026101701)

    def test_original_events_frozen(self):
        original = contract.read(R/'design/R73_ORIGINAL_EVENT_EVIDENCE.json')
        plan = contract.read(R/'design/PREREGISTERED_EVENTS.json')
        self.assertEqual(plan['original_evidence_sha256'], contract.sha(R/'design/R73_ORIGINAL_EVENT_EVIDENCE.json'))
        self.assertEqual(plan['events'], [{'name': e['name'], 'source_frames': e['source_boundary_frames']}
                                          for e in original['events'][:3]])
        self.assertTrue(plan['report_all_seeds'])

    def test_pending_review_does_not_admit_gpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                contract.root_gpu_review(root)

    def test_root_review_binds_exact_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root/'deploy_manifest.json', {'files': {}})
            review = {'approved': True, 'reviewer': 'root', 'scope': 'r113-two-seed-gpu-execution',
                      'producer_seal_sha256': contract.sha(root/'deploy_manifest.json')}
            write(root/'audit/GPU_DEPLOYMENT_REVIEW.json', review)
            self.assertEqual(contract.root_gpu_review(root), review)
            write(root/'deploy_manifest.json', {'files': {}, 'changed': True})
            with self.assertRaises(ValueError):
                contract.root_gpu_review(root)

    def test_fixed_requires_same_seed_native_and_generation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(job, 'RUN', Path(tmp)):
            root = Path(tmp)
            binding = {'arm': 'fixed', 'source_id': 'short_0252', 'pair_key': contract.PAIR_KEYS[0]}
            owner = {'pid': 50, 'identity': {'start_ticks': '100'}}
            name = contract.RUNS[0]
            write(root/'logs'/(name+'_job.json'), {'status': 'success', 'service_pid': 50,
                                                 'service_identity': owner['identity']})
            write(root/'logs'/(name+'_history.json'), {'status': {'completed': True, 'status_str': 'success'}})
            job.require_native_generation(binding, owner)
            with self.assertRaises(RuntimeError):
                job.require_native_generation(binding, {'pid': 51, 'identity': owner['identity']})
            binding['pair_key'] = contract.PAIR_KEYS[1]
            with self.assertRaises(FileNotFoundError):
                job.require_native_generation(binding, owner)


class ActualPrefixTests(unittest.TestCase):
    def inspect(self, folder):
        config, *_ = run('sample_euler', True, folder)
        path = folder/config.run_id
        manifest = contract.read(path/'manifest.json')
        shapes = dict(zip(('video', 'audio'), config.shapes))
        with patch.object(capture_checks, 'SHAPES', shapes), patch.object(capture_checks, 'GEOMETRY', manifest['geometry']):
            return capture_checks.inspect_capture(path, config.run_id, manifest['sigmas_video'], 2026101701, 'sample_euler')

    def test_real_euler_first_six_predictions_equal(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.inspect(Path(tmp)/'a')
            b = self.inspect(Path(tmp)/'b')
            self.assertEqual(sorted(a[2]), list(range(6)))
            self.assertEqual(len(a[1]), 23)
            self.assertTrue(all(verify_pair.compare_prefix(a[2], b[2]).values()))
            self.assertEqual(len(verify_pair.compare_prefix(a[2], b[2])), 20)

    def test_each_preintervention_step_and_stream_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, a = self.inspect(Path(tmp)/'a')
            _, _, b = self.inspect(Path(tmp)/'b')
            for step in range(6):
                for stream in ('video', 'audio'):
                    changed = copy.deepcopy(b)
                    changed[step]['normalized'][stream].view(-1)[0] += 1
                    self.assertFalse(all(verify_pair.compare_prefix(a, changed).values()))


if __name__ == '__main__':
    unittest.main()
