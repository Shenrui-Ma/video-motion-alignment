import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/data3/researcher/h3_runs/timing_feedback_r6_20261016'
sys.path.insert(0, str(ROOT / 'extensions'))
from H3EventAudit import audit_root
spec = importlib.util.spec_from_file_location('r6_service', ROOT / 'scripts/service.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


def graph(name):
    return json.loads((ROOT / 'configs' / (name + '.json')).read_text())


class RuntimeTests(unittest.TestCase):
    def test_formal_changes_only_controller_and_admin(self):
        parent = json.loads((ROOT / 'audit/parent_full_graph.json').read_text())
        actual = graph('r6_s05_feedback')
        normalized = json.loads(json.dumps(actual).replace('timing_feedback_r6_20261016',
            'timing_architecture_r2_20261016').replace('r6_s05_feedback', 'r2_s05_full_6to14'))
        node = normalized.pop('50')
        parent.pop('50')
        self.assertEqual(normalized, parent)
        self.assertEqual(node['class_type'], 'H3FeedbackRouter')
        self.assertEqual(node['inputs']['policy'], 'feedback')
        self.assertEqual(node['inputs']['fixed_indices'], '')
        self.assertEqual([node['inputs'][k] for k in ('start_frame', 'end_frame',
            'width', 'height', 'length')], [50, 65, 1312, 736, 141])

    def test_benchmark_is_parent_full_without_feedback_or_x0(self):
        parent = json.loads((ROOT / 'audit/parent_full_graph.json').read_text())
        actual = graph('r6_s05_feedback_bench2')
        actual = json.loads(json.dumps(actual).replace('timing_feedback_r6_20261016',
            'timing_architecture_r2_20261016').replace('r6_s05_feedback_bench2', 'r2_s05_full_6to14'))
        parent.pop('52')
        parent['7']['inputs']['model'] = ['50', 0]
        parent['50']['inputs']['step_start'] = 0
        parent['50']['inputs']['step_end'] = 2
        parent['9']['inputs']['sigmas'] = '1, 0.995633187773, 0'
        self.assertEqual(actual, parent)

    def test_paths_links_and_guard(self):
        for name in ['r6_s05_feedback', 'r6_s05_feedback_bench2']:
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
        self.assertEqual(service.PORT, 8467)
        self.assertEqual(service.GPU, 'GPU-REDACTED')
        queue = json.loads((ROOT / 'configs/queue.json').read_text())
        self.assertEqual(queue, {'jobs': ['r6_s05_feedback_retry1'], 'sealed': True})
        retry = graph('r6_s05_feedback_retry1')
        self.assertEqual(json.loads(json.dumps(retry).replace('r6_s05_feedback_retry1', 'r6_s05_feedback')), graph('r6_s05_feedback'))
        parent = json.loads((ROOT / 'configs/parent_runtime_provenance.json').read_text())
        hashes = json.loads((ROOT / 'configs/model_hashes_host41.json').read_text())
        for name, record in parent['models'].items():
            self.assertEqual(record['prior_full_sha256'], hashes[name]['sha256'])
        self.assertIn('H3FeedbackRouter', (ROOT / 'scripts/service.py').read_text())
        self.assertIn('/object_info/H3FeedbackRouter', (ROOT / 'scripts/launch_remote.py').read_text())


if __name__ == '__main__':
    unittest.main()
