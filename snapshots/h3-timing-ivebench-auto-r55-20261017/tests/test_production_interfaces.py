"""Administrative gates remain closed before actual parents and root policy choice."""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import prepare_graphs
from choose_policy import main as choose_policy
from gpu_release_gate import wait_after_child
from intake_parent_metadata import inspect


class ProductionInterfaces(unittest.TestCase):
    def test_graph_entry_point_is_repeatable_and_preserves_parent_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'configs').mkdir()
            (root / 'audit').mkdir()
            shutil.copyfile(ROOT / 'configs/protocol.json', root / 'configs/protocol.json')
            cases=json.loads((ROOT/'configs/protocol.json').read_text())['cases']
            for case in cases:
                path=root/case['parent_graph'];path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/case['parent_graph'],path)
            parents = {case['parent_graph']:(root/case['parent_graph']).read_bytes() for case in cases}
            with patch.object(prepare_graphs, 'ROOT', root):
                prepare_graphs.main()
                first = (root / 'audit/GRAPH_PREPARATION.json').read_bytes()
                prepare_graphs.main()
            self.assertEqual(first, (root / 'audit/GRAPH_PREPARATION.json').read_bytes())
            report = json.loads(first)
            self.assertEqual(len(report['cases']), 5)
            self.assertFalse(report['actual_parent_history_verified'])
            self.assertEqual(parents, {rel:(root/rel).read_bytes() for rel in parents})

    def test_missing_parent_is_pending_and_policy_requires_root_decision(self):
        with tempfile.TemporaryDirectory() as folder:
            result = inspect(Path(folder))
            self.assertEqual(result['status'], 'WAITING_R54_ARCHIVE')
            self.assertFalse(result['production_ready'])
        with self.assertRaisesRegex(ValueError, 'explicit root'):
            choose_policy('signed_R53', '/missing/evidence.json', 'test only')

    def test_release_wait_allows_only_exited_decoder_nvml_tail(self):
        now = [0.0]
        child = {'returncode': 0, 'process': {'pid': 42}}
        attempts = [ValueError('decoder GPU has active compute'), {'empty': True}]

        def idle(_):
            result = attempts.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        result = wait_after_child('decoder', child, idle, lambda _: None,
                                  clock=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
                                  compute_pids=lambda: [42] if attempts else [])
        self.assertTrue(result['strict_original_idle_assertion_passed'])
        self.assertEqual(result['wait_seconds'], .25)
        with self.assertRaisesRegex(RuntimeError, 'foreign GPU compute'):
            wait_after_child('decoder', child, lambda _: {}, lambda _: None, compute_pids=lambda: [43])
        with self.assertRaisesRegex(RuntimeError, 'still live or reused'):
            wait_after_child('decoder', child, lambda _: {}, lambda _: {'pid': 42}, compute_pids=lambda: [])


if __name__ == '__main__':
    unittest.main()
