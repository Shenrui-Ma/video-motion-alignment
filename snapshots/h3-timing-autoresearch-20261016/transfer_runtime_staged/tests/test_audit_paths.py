"""Call the real transfer audit node path contract; CPU only, no Comfy/model load."""
import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

STAGE = Path(__file__).resolve().parents[1]
PINNED = Path('/data5/researcher/h3_runs/timing_autoresearch_20261016_transfer0')
PRIMARY = Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
try:
    import torch
except ImportError:
    torch = None


@unittest.skipIf(torch is None, 'Run with the existing torch CPU interpreter; no dependencies installed')
class RealAuditPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            'transfer_event_audit_contract', STAGE / 'extensions/H3EventAudit/__init__.py')
        cls.node = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.node)

    def test_all_four_graphs_call_real_guard_and_real_noise_entrypoint(self):
        self.assertFalse(torch.cuda.is_initialized())
        with mock.patch.object(Path, 'mkdir') as mkdir:
            for graph in sorted((STAGE / 'configs').glob('s*_x0.json')):
                data = json.loads(graph.read_text())
                root = self.node.audit_root(data['5']['inputs']['audit_dir'])
                self.assertEqual(root, PINNED / 'audit')
                noise = self.node.H3EventAuditNoise().get_noise(**data['6']['inputs'])[0]
                self.assertEqual(noise.root, PINNED / 'audit')
                self.assertEqual(noise.seed, data['6']['inputs']['noise_seed'])
                self.assertEqual(noise.run_id, graph.stem)
            self.assertEqual(mkdir.call_count, 8)
        self.assertFalse(torch.cuda.is_initialized())

    def test_old_root_relative_prefix_sibling_and_traversal_rejected_before_mkdir(self):
        bad = [str(PRIMARY / 'audit'), 'audit', '/tmp/audit',
               str(PINNED) + '_elsewhere/audit', str(PINNED / '../audit'),
               '/tmp/timing_autoresearch_20261016_transfer0/audit',
               str(PINNED / '../timing_autoresearch_20261016/audit')]
        with mock.patch.object(Path, 'mkdir') as mkdir:
            for value in bad:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    self.node.audit_root(value)
            mkdir.assert_not_called()

    def test_nested_valid_path_allowed(self):
        with mock.patch.object(Path, 'mkdir'):
            self.assertEqual(self.node.audit_root(str(PINNED / 'audit/inner')), PINNED / 'audit/inner')

    def test_real_symlink_escape_rejected(self):
        # Virtualize only the pinned root's canonical location; exercise real
        # Path.resolve on an actual symlink without touching remote-style /data5.
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            allowed = base / 'instance'
            outside = base / 'other'
            allowed.mkdir(); outside.mkdir()
            (allowed / 'escape').symlink_to(outside, target_is_directory=True)
            original = Path.resolve
            def resolve(path, *args, **kwargs):
                if path == PINNED:
                    return original(allowed)
                return original(path, *args, **kwargs)
            with mock.patch.object(Path, 'resolve', resolve), mock.patch.object(Path, 'mkdir') as mkdir:
                with self.assertRaises(ValueError):
                    self.node.audit_root(str(allowed / 'escape/audit'))
                mkdir.assert_not_called()

    def test_reference_entrypoint_uses_guard_before_native_execute(self):
        tree = ast.parse((STAGE / 'extensions/H3EventAudit/__init__.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'H3EventAuditReference')
        encode = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'encode')
        guard = next(n.lineno for n in ast.walk(encode) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == 'audit_root')
        native = next(n.lineno for n in ast.walk(encode) if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute) and n.func.attr == 'execute')
        self.assertLess(guard, native)

    def test_both_node_defaults_match_transfer_root(self):
        for cls in (self.node.H3EventAuditReference, self.node.H3EventAuditNoise):
            self.assertEqual(cls.INPUT_TYPES()['required']['audit_dir'][1]['default'], str(PINNED / 'audit'))

    def test_only_path_guard_and_defaults_differ_from_frozen_v1(self):
        old = (STAGE / 'tests/fixtures/v1_event_audit.py.txt').read_text()
        new = (STAGE / 'extensions/H3EventAudit/__init__.py').read_text()
        def normalized(source):
            tree = ast.parse(source.replace(str(PINNED / 'audit'), str(PRIMARY / 'audit')))
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name == 'audit_root':
                    node.body = [ast.Pass()]
            return ast.dump(tree, include_attributes=False)
        self.assertEqual(normalized(old), normalized(new))


if __name__ == '__main__':
    unittest.main(verbosity=2)
