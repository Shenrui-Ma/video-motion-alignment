import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/data5/researcher/h3_runs/timing_normal_replay_r7_20261016'
sys.path.insert(0, str(ROOT / 'extensions'))
from H3EventAudit import audit_root
spec = importlib.util.spec_from_file_location('r7_service', ROOT / 'scripts/service.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class RuntimeTests(unittest.TestCase):
    def test_parent_graph_unchanged_except_passive_recorder(self):
        parent = json.loads((ROOT / 'audit/parent_native_graph.json').read_text())
        for name, bench in [('r7_s05_normal_native_bench2', True), ('r7_s05_normal_native_x0', False)]:
            g = json.loads((ROOT / 'configs' / (name + '.json')).read_text())
            g = json.loads(json.dumps(g).replace('timing_normal_replay_r7_20261016',
                'timing_autoresearch_20261016').replace(name, 's05_seed1_native'))
            if bench:
                g['9'] = parent['9']
                self.assertEqual(g['50']['inputs']['step_end'], 2)
                g['50']['inputs']['step_end'] = 20
            else:
                self.assertEqual(g['7']['inputs']['model'], ['52', 0])
                recorder = g.pop('52')
                self.assertEqual(recorder['class_type'], 'H3X0Readout')
                self.assertEqual([recorder['inputs'][k] for k in ('width', 'height', 'length')], [1024, 576, 141])
                g['7']['inputs']['model'] = ['50', 0]
            self.assertEqual(g, parent)

    def test_graph_paths_and_guard(self):
        for path in (ROOT / 'configs').glob('r7_*.json'):
            g = json.loads(path.read_text())
            for node in g.values():
                for key, value in node['inputs'].items():
                    if isinstance(value, list):
                        self.assertIn(value[0], g)
                    if key.endswith('dir'):
                        self.assertTrue(value.startswith(REMOTE + '/'))
                        with patch.object(Path, 'mkdir'):
                            self.assertEqual(str(audit_root(value)), value)
        for value in [REMOTE + '/../escape', REMOTE + '_wrong/audit', '/tmp/audit']:
            with patch.object(Path, 'mkdir'), self.assertRaises(ValueError):
                audit_root(value)

    def test_resource_isolation_and_queue(self):
        self.assertEqual(str(service.RUN), REMOTE)
        self.assertEqual(service.PORT, 8468)
        self.assertEqual(service.GPU, 'GPU-REDACTED')
        q = json.loads((ROOT / 'configs/queue.json').read_text())
        self.assertEqual(q, {'jobs': ['r7_s05_normal_native_bench2', 'r7_s05_normal_native_x0'], 'sealed': True})
        self.assertNotIn('capture_native', (ROOT / 'extensions/H3TemporalRouter/core.py').read_text())


if __name__ == '__main__':
    unittest.main()
