import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/data3/researcher/h3_runs/timing_schedule_controls_r11_20261016'
sys.path.insert(0, str(ROOT / 'extensions'))
from H3EventAudit import audit_root
spec = importlib.util.spec_from_file_location('r11_service', ROOT / 'scripts/service.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


def graph(name):
    return json.loads((ROOT / 'configs' / (name + '.json')).read_text())


class RuntimeTests(unittest.TestCase):
    def test_formal_changes_only_fixed_schedule_and_admin(self):
        parent = json.loads((ROOT / 'audit/parent_hold_graph.json').read_text())
        rows = [('r11_s05_continuous6to19', list(range(6, 20))),
                ('r11_s05_skip7_6to14', [6, *range(8, 15)])]
        for name, mask in rows:
            actual = graph(name)
            normalized = json.loads(json.dumps(actual).replace('timing_schedule_controls_r11_20261016',
                'timing_hold_control_r9_20261016').replace(name, 'r9_s05_hold2'))
            node = normalized['50']
            self.assertEqual(node['class_type'], 'H3FeedbackRouter')
            self.assertEqual(node['inputs']['policy'], 'fixed')
            self.assertEqual(node['inputs']['fixed_indices'], ','.join(map(str, mask)))
            node['inputs']['policy'] = 'feedback'
            node['inputs']['fixed_indices'] = ''
            self.assertEqual(normalized, parent)

    def test_paths_links_and_guard(self):
        for name in ['r11_s05_continuous6to19', 'r11_s05_skip7_6to14']:
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
        self.assertEqual(service.PORT, 8472)
        self.assertEqual(service.GPU, 'GPU-REDACTED')
        queue = json.loads((ROOT / 'configs/queue.json').read_text())
        self.assertEqual(queue, {'jobs': ['r11_s05_continuous6to19', 'r11_s05_skip7_6to14'], 'sealed': True})
        parent = json.loads((ROOT / 'configs/parent_runtime_provenance.json').read_text())
        hashes = json.loads((ROOT / 'configs/model_hashes_host41.json').read_text())
        for name, record in parent['models'].items():
            self.assertEqual(record['prior_full_sha256'], hashes[name]['sha256'])
        self.assertIn('H3FeedbackRouter', (ROOT / 'scripts/service.py').read_text())
        self.assertIn('/object_info/H3FeedbackRouter', (ROOT / 'scripts/launch_remote.py').read_text())

    def test_admission_rejects_occupied_selected_gpu_and_our_other_jobs(self):
        admission = {'scope': 'own_user_video_jobs', 'permitted_compute_processes': []}
        empty = {'queue_running': [], 'queue_pending': []}
        with self.assertRaisesRegex(RuntimeError, 'Selected GPU'):
            service.check_admission(admission, [{'pid': 11, 'gpu_uuid': service.GPU}], empty)
        other = {'pid': 12, 'gpu_uuid': 'OTHER_GPU'}
        with patch.object(service, 'proc_uid', return_value=1001), patch.object(service.os, 'getuid', return_value=1000):
            service.check_admission(admission, [other], empty)
        with patch.object(service, 'proc_uid', return_value=1000), patch.object(service.os, 'getuid', return_value=1000), \
                patch.object(service, 'external_identity', return_value={'uid': 1000}), self.assertRaises(RuntimeError):
            service.check_admission(admission, [other], empty)
        with self.assertRaisesRegex(RuntimeError, 'queued/running'):
            service.check_admission(admission, [], {'queue_running': [1], 'queue_pending': []})

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
