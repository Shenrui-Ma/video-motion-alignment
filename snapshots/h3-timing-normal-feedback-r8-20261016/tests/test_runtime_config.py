import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/data5/researcher/h3_runs/timing_normal_feedback_r8_20261016'
sys.path.insert(0, str(ROOT / 'extensions'))
from H3EventAudit import audit_root

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

service = load('r8_service', ROOT / 'scripts/service.py')
preflight = load('r8_preflight', ROOT / 'scripts/preflight.py')


class RuntimeTests(unittest.TestCase):
    def test_parent_graph_only_router_and_admin_change(self):
        report = preflight.validate_reused_warmup(ROOT)
        self.assertTrue(report['validated'])
        self.assertEqual(report['seconds_per_iteration_seen'], [40.17, 33.1, 34.16])
        g = json.loads((ROOT / 'configs/r8_s05_normal_feedback.json').read_text())
        self.assertEqual(g['50'], {'class_type': 'H3FeedbackRouter', 'inputs': {
            'model': ['41', 0], 'positive': ['51', 0], 'policy': 'feedback', 'fixed_indices': '',
            'start_frame': 50, 'end_frame': 65, 'width': 1024, 'height': 576, 'length': 141,
            'run_id': 'r8_s05_normal_feedback', 'audit_dir': REMOTE + '/audit/feedback'}})
        self.assertEqual(g['7']['inputs']['model'], ['52', 0])
        self.assertEqual(g['52']['class_type'], 'H3X0Readout')

    def test_graph_paths_and_guard(self):
        g = json.loads((ROOT / 'configs/r8_s05_normal_feedback.json').read_text())
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

    def test_resource_isolation_queue_and_feedback_loading(self):
        self.assertEqual(str(service.RUN), REMOTE)
        self.assertEqual(service.PORT, 8469)
        self.assertEqual(service.GPU, 'GPU-REDACTED')
        self.assertEqual(json.loads((ROOT / 'configs/queue.json').read_text()),
                         {'jobs': ['r8_s05_normal_feedback'], 'sealed': True})
        self.assertIn('H3FeedbackRouter', service.command())
        launch = (ROOT / 'scripts/launch_remote.py').read_text()
        self.assertIn('object_info/H3FeedbackRouter', launch)
        self.assertIn('assert all(prov[\'core_matches\'].values())', launch)
        self.assertIn("(s.st_size,s.st_mtime_ns)==(old['bytes'],old['mtime_ns'])", launch)
        self.assertIn('finally:service.stop()', (ROOT / 'scripts/run_queue.py').read_text())

    def test_tampered_warmup_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binding = json.loads((ROOT / 'audit/parent_provenance_binding.json').read_text())
            for relative in [*binding['files'], 'audit/parent_provenance_binding.json', 'configs/r8_s05_normal_feedback.json']:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            (root / 'audit/parent_warmup_gate.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'parent evidence changed'):
                preflight.validate_reused_warmup(root)

    def test_admission_and_cleanup_identity(self):
        admission = json.loads((ROOT / 'configs/admission.json').read_text())
        empty = {'queue_running': [], 'queue_pending': []}
        other = {'gpu_uuid': 'other-gpu', 'pid': 1001}
        with patch.object(service, 'proc_uid', return_value=service.os.getuid() + 1):
            service.check_admission(admission, [other], empty)
        with patch.object(service, 'proc_uid', return_value=service.os.getuid()), patch.object(service, 'external_identity', return_value={}):
            with self.assertRaisesRegex(RuntimeError, 'Unexpected host compute'):
                service.check_admission(admission, [other], empty)
        with self.assertRaisesRegex(RuntimeError, 'Selected GPU'):
            service.check_admission(admission, [dict(other, gpu_uuid=service.GPU)], empty)
        fake = {'pid': 123, 'gpu_uuid': service.GPU, 'port': service.PORT,
                'identity': {'uid': service.os.getuid(), 'start_ticks': '1', 'cmdline': str(service.CORE / 'main.py') + ' ' + str(service.RUN)}}
        with patch.object(service, 'current_identity', return_value=fake['identity']):
            service.assert_owned(fake)
            with self.assertRaisesRegex(RuntimeError, 'GPU/port'):
                service.assert_owned(dict(fake, port=8468))
        with patch.object(service, 'current_identity', return_value=dict(fake['identity'], start_ticks='2')):
            with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
                service.assert_owned(fake)


if __name__ == '__main__':
    unittest.main()
