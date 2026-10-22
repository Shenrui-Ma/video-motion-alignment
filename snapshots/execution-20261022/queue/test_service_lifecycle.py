"""CPU-only lifecycle verification; never launches or signals real processes."""
import ast
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1] / 'inference'
PATHS = [ROOT / lane / 'scripts/manage_service.py' for lane in ['package', 'host9a', 'host9b']]


def load(path):
    spec = importlib.util.spec_from_file_location('service_' + path.parts[-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LifecycleTests(unittest.TestCase):
    def test_healthy_existing_service_keeps_identity(self):
        for path in PATHS:
            with self.subTest(path=path):
                m = load(path)
                record = {'pid': 17, 'start_ticks': '123', 'gpu_uuid': 'gpu-existing'}
                with mock.patch.object(m, 'read_record', return_value=record), mock.patch.object(m, 'alive', return_value=True), mock.patch.object(m, 'wait_ready', return_value=True) as wait, mock.patch.object(m, 'stop') as stop:
                    result = m.start()
                self.assertEqual(result['pid'], 17)
                self.assertEqual(result['state'], 'already_running')
                wait.assert_called_once_with(record, 90)
                stop.assert_not_called()

    def test_readiness_deadline_counts_request_time(self):
        for path in PATHS:
            with self.subTest(path=path):
                m = load(path)
                clock = [0.0]
                def slow_api(*args):
                    clock[0] += 10
                    raise OSError('request timed out')
                with mock.patch.object(m, 'alive', return_value=True), mock.patch.object(m, 'api', side_effect=slow_api) as api, mock.patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]), mock.patch.object(m.time, 'sleep', side_effect=lambda n: clock.__setitem__(0, clock[0] + n)):
                    self.assertFalse(m.wait_ready({'pid': 17}, 5))
                self.assertEqual(clock[0], 10)
                api.assert_called_once()

    def test_unhealthy_service_stopped_then_gpu_admission_rechecked(self):
        for path in PATHS:
            with self.subTest(path=path):
                m = load(path)
                record = {'pid': 17, 'start_ticks': '123'}
                with mock.patch.object(m, 'read_record', return_value=record), mock.patch.object(m, 'alive', return_value=True), mock.patch.object(m, 'wait_ready', return_value=False), mock.patch.object(m, 'stop', return_value={'stopped': True}) as stop, mock.patch.object(m, 'open', mock.mock_open(), create=True), mock.patch.object(m.fcntl, 'flock'), mock.patch.object(m.Path, 'exists', return_value=True), mock.patch.object(m.subprocess, 'check_output', return_value=m.GPU + ', 456\n'), mock.patch.object(m.subprocess, 'Popen') as popen:
                    with self.assertRaisesRegex(RuntimeError, 'existing compute process'):
                        m.start()
                stop.assert_called_once_with(record)
                popen.assert_not_called()

    def test_stop_uses_exact_inspected_record(self):
        for path in PATHS:
            with self.subTest(path=path):
                m = load(path)
                record = {'pid': 17, 'start_ticks': '123'}
                active = [True]
                def kill(pid, sig):
                    self.assertEqual(pid, 17)
                    active[0] = False
                with mock.patch.object(m, 'read_record', return_value={'pid': 99}) as read, mock.patch.object(m, 'alive', side_effect=lambda r: active[0] and r == record), mock.patch.object(m.os, 'kill', side_effect=kill) as signal:
                    result = m.stop(record)
                read.assert_not_called()
                signal.assert_called_once_with(17, m.signal.SIGTERM)
                self.assertTrue(result['stopped'])

    def test_unowned_or_reused_pid_is_not_signalled(self):
        for path in PATHS:
            with self.subTest(path=path):
                m = load(path)
                with mock.patch.object(m, 'alive', return_value=False), mock.patch.object(m.os, 'kill') as signal:
                    result = m.stop({'pid': 99, 'start_ticks': 'old'})
                signal.assert_not_called()
                self.assertTrue(result['stopped'])

    def test_timer_average_uses_measured_intervals(self):
        source = (ROOT / 'study_nodes.py').read_text()
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Timer')
        clock = [0.0]
        writes = []
        namespace = {'time': types.SimpleNamespace(perf_counter=lambda: clock[0]), 'atomic': lambda path, value: writes.append(value)}
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<Timer>', 'exec'), namespace)
        torch = types.SimpleNamespace(cuda=types.SimpleNamespace(synchronize=lambda: None))
        def executor(model, sigmas, extra, callback, noise, latent, mask, disable):
            clock[0] += 12
            callback(0, None, None, 2)
            clock[0] += 15
            callback(1, None, None, 2)
            clock[0] += 3
            return 'done'
        with mock.patch.dict(sys.modules, {'torch': torch}):
            self.assertEqual(namespace['Timer']('unused')(executor, None, None, {}, None, None), 'done')
        self.assertEqual(writes[-1]['sampler_wall_seconds'], 30)
        self.assertEqual(writes[-1]['per_step_seconds'], [12, 15])
        self.assertEqual(writes[-1]['mean_sampling_step_seconds'], 13.5)


if __name__ == '__main__':
    unittest.main()
