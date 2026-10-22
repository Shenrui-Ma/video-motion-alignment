"""CPU contract regressions; all transport operations are mocked."""
import copy
import importlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.with_name('h3-oxygen-generic-retention-metrics-r141-20261020')
sys.path.insert(0, str(ROOT / 'scripts'))
import common
import paired
import remote
import review


class Host9Binding(unittest.TestCase):
    def setUp(self):
        self.config = common.config()
        self.source = common.info('short_0252')
        self.path = self.config['producer_remote'] + '/configs/runtime.json'

    def test_all_helpers_import_without_model_runtime(self):
        for path in (ROOT / 'scripts').glob('*.py'):
            importlib.import_module(path.stem)
        self.assertNotIn('torch', sys.modules)
        self.assertEqual(common.ROOT, ROOT)

    def test_static_manifest_and_bound_host(self):
        self.assertEqual(common.validate_static()['host'], 'H3_SERVER_A')
        self.assertEqual(
            self.config['producer_remote'],
            '/home/researcher/h3_runs/timing_oxygen_generic_retention_r141b_host9_20261020',
        )

    def test_reads_use_host9(self):
        with patch.object(remote.subprocess, 'run', return_value=SimpleNamespace(stdout='{}')) as call:
            remote.read_paths([self.path])
        self.assertEqual(call.call_args.args[0][5], 'H3_SERVER_A')
        self.assertIn(self.config['producer_remote'], call.call_args.args[0][-1])

    def test_transfers_use_host9(self):
        with patch.object(remote.subprocess, 'run') as call:
            remote.fetch(self.path, '/tmp/host9_consumer_mock.json')
        self.assertIn('H3_SERVER_A:' + self.path, call.call_args.args[0])

    def test_source_digest_uses_host9(self):
        digest = 'a' * 64
        with patch.object(remote.subprocess, 'run', return_value=SimpleNamespace(stdout=digest + '\n')) as call:
            remote.verify_source_bytes(self.path, digest)
        self.assertEqual(call.call_args.args[0][5], 'H3_SERVER_A')

    def test_old_remote_root_rejected_before_transport(self):
        old = common.read(BASE / 'configs/contract.json')['producer_remote'] + '/configs/runtime.json'
        with patch.object(remote.subprocess, 'run') as call:
            for operation in (
                lambda: remote.read_paths([old]),
                lambda: remote.fetch(old, '/tmp/host9_consumer_mock.json'),
                lambda: remote.verify_source_bytes(old, 'a' * 64),
            ):
                with self.assertRaises(ValueError):
                    operation()
        call.assert_not_called()

    def test_science_and_events_unchanged(self):
        for name in ('producer_scientific_contract.json', 'PREREGISTERED_EVENTS.json'):
            self.assertEqual((ROOT / 'configs' / name).read_bytes(), (BASE / 'configs' / name).read_bytes())
        before = common.read(BASE / 'configs/SOURCE_EVENT_REVIEW_CUES.json')
        after = common.read(ROOT / 'configs/SOURCE_EVENT_REVIEW_CUES.json')
        for current, old in zip(after['items'], before['items']):
            current['evidence']['file'] = old['evidence']['file']
        self.assertEqual(after, before)
        old = common.read(BASE / 'configs/contract.json')
        self.assertEqual(self.config['method'], old['method'])
        self.assertEqual(self.source['prompt'], old['sources'][0]['prompt'])
        for path in (ROOT / 'configs/graphs').glob('*.json'):
            normalized = path.read_text().replace(self.config['producer_remote'], old['producer_remote'])
            self.assertEqual(normalized, (BASE / 'configs/graphs' / path.name).read_text())
        for name in ('consume_native.py', 'consume_pair.py'):
            text = (ROOT / 'scripts' / name).read_text()
            self.assertIn(str(ROOT / 'showcase'), text)
            self.assertNotIn(str(BASE / 'showcase'), text)

    def test_input_inodes_reused(self):
        for path in (ROOT / 'inputs').iterdir():
            self.assertEqual(path.stat().st_ino, (BASE / 'inputs' / path.name).stat().st_ino)

    def test_prompt_mutation_rejected(self):
        common.verify_official_prompt(self.source)
        changed = copy.deepcopy(self.source)
        changed['prompt'] += ' Move faster.'
        with self.assertRaises(ValueError):
            common.verify_official_prompt(changed)

    def test_padding_cannot_be_annotated_as_valid_event(self):
        self.assertEqual(self.source['valid_frames'], 98)
        review.checked_event({'status': 'OBSERVED', 'frames': [96, 97]}, 98)
        with self.assertRaises(ValueError):
            review.checked_event({'status': 'OBSERVED', 'frames': [97, 98]}, 98)

    def gate(self):
        owner = {'pid': 123, 'identity': {'uid': 1016, 'start_ticks': 'fixture'}}
        gate = {
            'schema': 'r123-paired-runtime-gate-v1',
            'passed': True,
            'source_id': 'short_0252',
            'prompt_version': self.source['prompt_version'],
            'checks': dict.fromkeys(paired.PAIR_CHECKS, True),
            'runtime_profile_sha256': self.config['producer_runtime_sha256'],
            'runtime_profile': common.read(ROOT / 'configs/producer_runtime.json'),
            'service_owner': owner,
            'prefix_tensor_comparison': [
                {'step_zero_based': i, 'video': True, 'audio': True} for i in range(6)
            ],
            'runs': {},
        }
        for mode in ('native', 'forced'):
            run = self.source['run_id' if mode == 'native' else 'forced_run_id']
            graph = self.source['graph_sha256' if mode == 'native' else 'forced_graph_sha256']
            gate['runs'][mode] = {
                'run_id': run, 'NFE': 20, 'Euler_updates': 20,
                'routed_blocks': 0 if mode == 'native' else 450,
                'valid_frames': 98, 'evaluation_crop_xywh': self.source['crop_xywh'],
                'task_scope': self.source['task_scope'],
                'evaluation_scope': self.source['evaluation_scope'],
                'job_sha256': 'a' * 64, 'history_sha256': 'b' * 64,
                'video': {
                    'file': self.config['producer_remote'] + '/output/' + run + '.mp4',
                    'properties': {'width': 1312, 'height': 736, 'nb_read_frames': 107, 'avg_frame_rate': '24/1'},
                },
                'binding_artifacts': {
                    'configs/graphs/' + run + '.json': graph,
                    'logs/' + run + '_job.json': 'a' * 64,
                    'logs/' + run + '_history.json': 'b' * 64,
                },
            }
        return gate, owner

    def test_actual_noise_and_six_step_prefix_required(self):
        gate, owner = self.gate()
        paired.verify_pair_gate(gate, 'short_0252', owner)
        for key in ('native_registered_initial_noise_equal', 'forced_registered_initial_noise_equal', 'actual_initial_AV_noise_equal'):
            changed = copy.deepcopy(gate)
            changed['checks'].pop(key)
            with self.assertRaises(ValueError):
                paired.verify_pair_gate(changed, 'short_0252', owner)
        changed = copy.deepcopy(gate)
        changed['prefix_tensor_comparison'][5]['audio'] = False
        with self.assertRaises(ValueError):
            paired.verify_pair_gate(changed, 'short_0252', owner)


if __name__ == '__main__':
    unittest.main()
