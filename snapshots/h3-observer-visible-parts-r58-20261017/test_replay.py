import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import replay


class ReplayGuards(unittest.TestCase):
    def test_different_proposals_with_same_bin_execute_identically(self):
        geometry = SimpleNamespace(valid_frames=87, latent_bins=27)
        first = {'active': True, 'physical_intervals': [[1, 2]],
                 'selected': [{'window': [1, 2], 'feature': 'left_arm_direction', 'lags': {'0.3': 4}}]}
        second = {'active': True, 'physical_intervals': [[3, 4]],
                  'selected': [{'window': [3, 4], 'feature': 'right_arm_direction', 'lags': {'0.3': 8}}]}
        self.assertNotEqual(replay.route_signature(first), replay.route_signature(second))
        self.assertEqual(replay.execution_signature(first, geometry),
                         replay.execution_signature(second, geometry))
        second['physical_intervals'] = [[5, 8]]
        self.assertNotEqual(replay.execution_signature(first, geometry),
                            replay.execution_signature(second, geometry))

    def test_export_binding_and_tamper_rejection(self):
        root = Path('/Users/researcher/DevProjects/h3-timing-ivebench-auto-r55-20261017/analysis/postrun/audit/live_pose_export/1792245969261988000')
        row = json.loads((root / 'INDEX.json').read_text())['rows'][0]
        request_path, response_path, target = [root / row[k]['relative_file']
                                               for k in ('request', 'response', 'target_pose')]
        request, response = replay.read(request_path), replay.read(response_path)
        replay.check_evidence(row, request, response, target, request_path, response_path)
        for key in ('pose', 'observer'):
            altered = copy.deepcopy(response)
            altered[key]['sha256'] = '0' * 64
            with self.assertRaises(ValueError):
                replay.check_evidence(row, request, altered, target, request_path, response_path)
        altered = copy.deepcopy(row)
        altered['original_decision']['response_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            replay.check_evidence(altered, request, response, target, request_path, response_path)

    def test_repeated_module_load_is_rejected(self):
        previous = replay._LOADED_VERSION
        try:
            replay._LOADED_VERSION = 'r55'
            with self.assertRaisesRegex(RuntimeError, 'fresh process'):
                replay.load_modules('r50')
        finally:
            replay._LOADED_VERSION = previous


if __name__ == '__main__':
    unittest.main()
