import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/data5/researcher/h3_runs/timing_softband_r5_20261016'
sys.path.insert(0, str(ROOT / 'extensions'))
from H3EventAudit import audit_root
spec = importlib.util.spec_from_file_location('r5_service', ROOT / 'scripts/service.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


def graph(name):
    return json.loads((ROOT / 'configs' / (name + '.json')).read_text())


class RuntimeTests(unittest.TestCase):
    def test_formal_only_radius_and_admin_differ_from_R3_full(self):
        parent = json.loads((ROOT / 'audit/parent_full_graph.json').read_text())
        actual = graph('r5_s05_softband_6to14')
        normalized = json.loads(json.dumps(actual).replace('timing_softband_r5_20261016',
            'timing_spatial_r3_20261016').replace('r5_s05_softband_6to14', 'r3_s05_full_6to14'))
        self.assertEqual(normalized['50']['inputs']['radius'], 1)
        normalized['50']['inputs']['radius'] = 0
        self.assertEqual(normalized, parent)

    def test_benchmark_uses_actual_band_without_x0(self):
        formal = graph('r5_s05_softband_6to14')
        expected = json.loads(json.dumps(formal).replace('r5_s05_softband_6to14', 'r5_s05_softband_bench2'))
        expected.pop('52')
        expected['7']['inputs']['model'] = ['50', 0]
        expected['9']['inputs']['sigmas'] = '1,0.995633187773,0'
        expected['50']['inputs']['step_start'] = 0
        expected['50']['inputs']['step_end'] = 2
        self.assertEqual(graph('r5_s05_softband_bench2'), expected)

    def test_paths_links_and_guard(self):
        for name in ['r5_s05_softband_6to14', 'r5_s05_softband_bench2']:
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

    def test_isolation_queue_models_and_admission(self):
        self.assertEqual(str(service.RUN), REMOTE)
        self.assertEqual(service.PORT, 8466)
        self.assertEqual(service.GPU, 'GPU-REDACTED')
        queue = json.loads((ROOT / 'configs/queue.json').read_text())
        self.assertEqual(queue, {'jobs': ['r5_s05_softband_bench2', 'r5_s05_softband_6to14'], 'sealed': True})
        parent = json.loads((ROOT / 'configs/parent_runtime_provenance.json').read_text())
        hashes = json.loads((ROOT / 'configs/model_hashes_host9.json').read_text())
        for name, record in parent['models'].items():
            self.assertEqual(record['prior_full_sha256'], hashes[name]['sha256'])
        a = {'scope': 'own_user_video_jobs', 'permitted_compute_processes': []}
        empty = {'queue_running': [], 'queue_pending': []}
        service.check_admission(a, [], empty)
        with self.assertRaises(RuntimeError):
            service.check_admission(a, [{'gpu_uuid': service.GPU, 'pid': 100}], empty)
        with patch.object(service, 'proc_uid', return_value=service.os.getuid() + 1):
            service.check_admission(a, [{'gpu_uuid': 'GPU-other', 'pid': 100}], empty)


if __name__ == '__main__':
    unittest.main()
