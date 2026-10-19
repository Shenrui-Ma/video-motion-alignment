import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/data5/researcher/h3_runs/timing_native_screen_r14_host9_20261016'
sys.path.insert(0, str(ROOT / 'extensions'))
from H3EventAudit import audit_root
spec = importlib.util.spec_from_file_location('r14_service', ROOT / 'scripts/service.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


def graph(name):
    return json.loads((ROOT / 'configs' / (name + '.json')).read_text())


class RuntimeTests(unittest.TestCase):
    def test_formal_changes_only_seed_off_and_admin(self):
        parent = json.loads((ROOT / 'audit/parent_r11_graph.json').read_text())
        actual = graph('r14_s05_seed1313_native_host9')
        normalized = json.loads(json.dumps(actual).replace('/data5/researcher/h3_runs/timing_native_screen_r14_host9_20261016',
            '/data3/researcher/h3_runs/timing_schedule_controls_r11_20261016').replace('r14_s05_seed1313_native_host9',
            'r11_s05_continuous6to19'))
        self.assertEqual(normalized['6']['inputs']['noise_seed'], 2026101313)
        self.assertEqual(normalized['6']['inputs']['pair_id'], '05_sam_1312x736_2026101313_v3')
        self.assertEqual(normalized['50']['inputs']['policy'], 'off')
        self.assertEqual(normalized['50']['inputs']['fixed_indices'], '')
        normalized['6']['inputs']['noise_seed'] = parent['6']['inputs']['noise_seed']
        normalized['6']['inputs']['pair_id'] = parent['6']['inputs']['pair_id']
        normalized['50']['inputs']['policy'] = parent['50']['inputs']['policy']
        normalized['50']['inputs']['fixed_indices'] = parent['50']['inputs']['fixed_indices']
        self.assertEqual(normalized, parent)

    def test_matches_historical_seed2_scientific_inputs(self):
        parent = json.loads((ROOT / 'audit/parent_seed2_graph.json').read_text())
        actual = graph('r14_s05_seed1313_native_host9')
        for number in ['1', '2', '3', '4', '41', '7', '8', '9', '10', '11', '12', '13', '21', '22', '23']:
            self.assertEqual(actual[number], parent[number], number)
        for number in ['5', '6', '14', '51', '52']:
            fields = dict(actual[number]['inputs'])
            expected = dict(parent[number]['inputs'])
            for key in ['audit_dir', 'source_audit_dir', 'output_dir', 'run_id', 'filename_prefix', 'pair_id', 'noise_seed']:
                fields.pop(key, None); expected.pop(key, None)
            self.assertEqual(fields, expected, number)
        self.assertEqual(actual['5']['inputs']['run_id'], parent['5']['inputs']['run_id'])
        self.assertEqual(actual['51']['inputs']['source_run_id'], parent['51']['inputs']['source_run_id'])

    def test_paths_links_and_guard(self):
        for name in ['r14_s05_seed1313_native_host9']:
            g = graph(name)
            for node in g.values():
                for key, value in node['inputs'].items():
                    if isinstance(value, list):
                        self.assertIn(value[0], g)
                    if key.endswith('dir'):
                        self.assertTrue(value.startswith(REMOTE + '/'))
                        with patch.object(Path, 'mkdir'):
                            self.assertEqual(str(audit_root(value)), value)
        for path in [REMOTE + '_bad/audit', REMOTE + '/../escape', '/tmp/audit']:
            with patch.object(Path, 'mkdir'), self.assertRaises(ValueError):
                audit_root(path)
        for path in list((ROOT / 'scripts').glob('*.py')) + list((ROOT / 'extensions').rglob('*.py')):
            if 'H3FeedbackRouter' in path.parts:
                continue  # Frozen observer source retains its original provenance.
            self.assertNotIn('timing_architecture_r2_20261016', path.read_text(), str(path))

    def test_isolation_queue_and_model_provenance(self):
        self.assertEqual(str(service.RUN), REMOTE)
        self.assertEqual(service.PORT, 8475)
        self.assertEqual(service.GPU, 'GPU-REDACTED')
        queue = json.loads((ROOT / 'configs/queue.json').read_text())
        self.assertEqual(queue, {'jobs': ['r14_s05_seed1313_native_host9'], 'sealed': True})
        parent = json.loads((ROOT / 'configs/parent_runtime_provenance.json').read_text())
        hashes = json.loads((ROOT / 'configs/model_hashes_host9.json').read_text())
        for name, record in parent['models'].items():
            self.assertEqual(record['prior_full_sha256'], hashes[name]['sha256'])
        self.assertIn('H3FeedbackRouter', (ROOT / 'scripts/service.py').read_text())
        self.assertIn('/object_info/H3FeedbackRouter', (ROOT / 'scripts/launch_remote.py').read_text())

    def test_cleanup_identity_guard(self):
        identity = {'uid': 1000, 'start_ticks': '22',
                    'cmdline': str(service.CORE / 'main.py') + ' ' + REMOTE}
        record = {'pid': 12, 'identity': identity, 'gpu_uuid': service.GPU, 'port': service.PORT}
        with patch.object(service, 'current_identity', return_value=identity), patch.object(service.os, 'getuid', return_value=1000):
            self.assertEqual(service.assert_owned(record), identity)
            with self.assertRaisesRegex(RuntimeError, 'different GPU/port'):
                service.assert_owned(dict(record, port=8467))
        with patch.object(service, 'current_identity', return_value=dict(identity, start_ticks='23')):
            with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
                service.assert_owned(record)


if __name__ == '__main__':
    unittest.main()
