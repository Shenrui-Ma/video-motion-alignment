"""Exercise the actual snapshot method through its registered identity boundary."""
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import r123_contract as contract

spec = importlib.util.spec_from_file_location(
    'snapshot_identity_target', ROOT / 'extensions/H3PairAudit/__init__.py'
)
snapshot_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot_module)


class ReachedTensorVerification(Exception):
    pass


class SnapshotIdentity(unittest.TestCase):
    def exercise(self, run_id, source_id):
        module = types.ModuleType('comfy.ldm.minimax.model')
        module.PackedLayout = object
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / (source_id + '_conditioning.json')).write_text(json.dumps({
                'schema': 'h3-event-audit-v1', 'run_id': source_id,
                'conditioning_embedding': {},
            }))
            with patch.dict(sys.modules, {'comfy.ldm.minimax.model': module}), \
                    patch.object(contract, 'audit_dir', return_value=path), \
                    patch.object(snapshot_module, '_verify_tensor', side_effect=ReachedTensorVerification):
                snapshot_module.H3PairConditionSnapshot().snapshot(
                    [(object(), {})], {}, str(path), source_id, run_id
                )

    def test_registered_native_and_forced_reach_tensor_verification(self):
        jobs, order = contract.registry()
        for run_id in order:
            graph = contract.expected_graph(ROOT, jobs[run_id]['case'])
            with self.subTest(run_id=run_id), self.assertRaises(ReachedTensorVerification):
                self.exercise(run_id, graph['51']['inputs']['source_run_id'])

    def test_stale_and_other_source_ids_rejected_before_tensor_access(self):
        run_id = contract.registry()[1][0]
        for source_id in ('r123_short_0252_shared', 'r141_short_0210_shared'):
            with self.subTest(source_id=source_id), self.assertRaisesRegex(ValueError, 'source-conditioning identity mismatch'):
                self.exercise(run_id, source_id)

    def test_unregistered_run_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unknown run'):
            self.exercise('r123_short_0252_seed2026101703_native', 'r141_short_0252_shared')


if __name__ == '__main__':
    unittest.main()
