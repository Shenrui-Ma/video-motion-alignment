"""Verify isolated graph paths against the actual audit-root enforcement."""
import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/data3/researcher/h3_runs/timing_target_path_r4_20261016'


class RuntimePaths(unittest.TestCase):
    def test_enforced_audit_root_matches_graphs(self):
        tree = ast.parse((ROOT / 'extensions/H3EventAudit/__init__.py').read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'audit_root')
        allowed = next(n.value.func.value.args[0].value for n in function.body
                       if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                       and n.targets[0].id == 'allowed')
        self.assertEqual(allowed, REMOTE)
        graphs = list((ROOT / 'configs').glob('r4_*.json'))
        self.assertGreaterEqual(len(graphs), 2)
        for graph in graphs:
            for node in json.loads(graph.read_text()).values():
                for key, value in node['inputs'].items():
                    if key in {'audit_dir', 'source_audit_dir', 'output_dir'}:
                        self.assertTrue(value.startswith(allowed + '/audit'), (graph.name, key, value))

    def test_no_previous_round_path_in_active_extensions(self):
        for file in (ROOT / 'extensions').rglob('*.py'):
            source = file.read_text()
            self.assertNotIn('timing_spatial_r3_20261016', source, str(file))
            self.assertNotIn('timing_architecture_r2_20261016', source, str(file))


if __name__ == '__main__':
    unittest.main()
