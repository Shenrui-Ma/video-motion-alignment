"""Stdlib-only checks; no torch import, NVIDIA query, CUDA or model execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('allocator_probe', HERE / 'route_allocator_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class FakeCuda:
    def __init__(self):
        self.events = []
        self.finished = False
    def synchronize(self): self.events.append('sync')
    def mem_get_info(self):
        self.events.append('mem_get_info')
        return (800 if self.finished else 900, 1000)
    def memory_stats(self): return {'active_bytes.all.current': 180 if self.finished else 80}
    def memory_allocated(self): return 200 if self.finished else 100
    def memory_reserved(self): return 300 if self.finished else 150
    def reset_peak_memory_stats(self): self.events.append('reset')
    def max_memory_allocated(self): self.events.append('max_allocated'); return 450
    def max_memory_reserved(self): self.events.append('max_reserved'); return 500


class ProbeTests(unittest.TestCase):
    def fixtures(self, root):
        (root / 'configs').mkdir()
        cases = []
        closure = {'ready': True, 'status': 'READY', 'cases': {}}
        for i, text in enumerate((100, 104, 102, 104, 103)):
            source = 'source' + str(i)
            rel = 'configs/' + source + '.json'
            case = {'run_id': 'run' + str(i), 'source_id': source,
                    'parent_run': 'parent' + str(i), 'parent_conditioning': rel}
            end = text + 2 * 27 * 943
            layout = {'seq_len': end + 150, 'segments': [
                [0, text, 'text'], [text, text + 27 * 943, 'ref_img'],
                [text + 27 * 943, end, 'video'], [end, end + 150, 'audio']]}
            (root / rel).write_text(json.dumps({'packed_layout': layout}))
            cases.append(case)
            closure['cases'][source] = {'ready': True, 'parent_run': case['parent_run'],
                'actual_file_sha256': {rel: probe.sha(root / rel)}, 'packed_layout': layout}
        (root / 'configs/protocol.json').write_text(json.dumps({'cases': cases}))
        (root / 'configs/PARENT_CLOSURE.json').write_text(json.dumps(closure))
        return cases, closure

    def test_selects_largest_actual_layout_and_stable_tie(self):
        with tempfile.TemporaryDirectory(dir=HERE / 'tmp') as folder:
            root = Path(folder); self.fixtures(root)
            result = probe.select_layout(root)
            self.assertEqual(result['selected']['run_id'], 'run1')
            self.assertEqual(len(result['all_actual_layouts']), 5)
            self.assertEqual(result['selected']['plan']['latent_interval_half_open'], [0, 27])

    def test_pending_or_changed_actual_metadata_rejected(self):
        with tempfile.TemporaryDirectory(dir=HERE / 'tmp') as folder:
            root = Path(folder); cases, closure = self.fixtures(root)
            p = root / 'configs/PARENT_CLOSURE.json'
            closure['ready'] = False; p.write_text(json.dumps(closure))
            with self.assertRaisesRegex(ValueError, 'bound first'): probe.select_layout(root)
            closure['ready'] = True; p.write_text(json.dumps(closure))
            (root / cases[0]['parent_conditioning']).write_text('{}')
            with self.assertRaisesRegex(ValueError, 'hash differs'): probe.select_layout(root)

    def test_partition_and_reference_shape_rejected(self):
        with tempfile.TemporaryDirectory(dir=HERE / 'tmp') as folder:
            root = Path(folder); cases, closure = self.fixtures(root)
            rel = cases[0]['parent_conditioning']
            layout = closure['cases']['source0']['packed_layout']
            layout['segments'][0][1] -= 1
            (root / rel).write_text(json.dumps({'packed_layout': layout}))
            closure['cases']['source0']['actual_file_sha256'][rel] = probe.sha(root / rel)
            (root / 'configs/PARENT_CLOSURE.json').write_text(json.dumps(closure))
            with self.assertRaisesRegex(ValueError, 'partition'): probe.select_layout(root)

    def test_owned_cap_and_busy_gpu_are_checked(self):
        rows = [{'gpu_uuid': 'other', 'pid': 1}]
        self.assertEqual(probe.check_compute(rows, 'target', lambda _: 10, 10), ['other'])
        with self.assertRaisesRegex(RuntimeError, 'two owned'):
            probe.check_compute(rows + [{'gpu_uuid': 'third', 'pid': 2}], 'target', lambda _: 10, 10)
        with self.assertRaisesRegex(RuntimeError, 'another compute'):
            probe.check_compute([{'gpu_uuid': 'target', 'pid': 9}], 'target', lambda _: 11, 10)
        self.assertEqual(probe.check_compute([{'gpu_uuid': 'target', 'pid': 9}], 'target', lambda _: 10, 10, 9), ['target'])
        with self.assertRaisesRegex(RuntimeError, 'unresolved'):
            probe.check_compute(rows, 'target', lambda _: None, 10)

    def test_one_call_boundary_excludes_later_validation(self):
        cuda = FakeCuda(); calls = []
        def call():
            cuda.events.append('route'); calls.append(1); cuda.finished = True
            return 'output'
        output, record = probe.measure_once(cuda, call)
        self.assertEqual(output, 'output'); self.assertEqual(calls, [1])
        self.assertEqual(cuda.events, ['sync', 'mem_get_info', 'reset', 'route', 'sync',
                                      'max_allocated', 'max_reserved', 'mem_get_info'])
        self.assertEqual(record['increment_peak_allocated_bytes'], 350)
        self.assertEqual(record['increment_peak_reserved_bytes'], 350)
        self.assertEqual(record['after']['driver_free_bytes'], 800)
        self.assertEqual(json.loads(json.dumps(record, allow_nan=False)), record)

    def test_failed_call_keeps_before_and_peak_evidence(self):
        cuda = FakeCuda()
        def call(): raise RuntimeError('synthetic allocation failure')
        with self.assertRaisesRegex(RuntimeError, 'synthetic') as cm:
            probe.measure_once(cuda, call)
        record = cm.exception.allocator_measurement
        self.assertEqual(record['status'], 'call_failed')
        self.assertEqual(record['before']['allocated_bytes'], 100)
        self.assertEqual(record['max_allocated_bytes'], 450)

    def test_import_does_not_import_torch_and_paths_stay_inside(self):
        import sys
        self.assertNotIn('torch', sys.modules)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            probe.owned_path(HERE, '../elsewhere')


if __name__ == '__main__':
    unittest.main()
