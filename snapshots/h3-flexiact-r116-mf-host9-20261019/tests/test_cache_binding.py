import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import common as c


class CacheBinding(unittest.TestCase):
    def setUp(self):
        folder = ROOT/'cases/human2animal_1__game_man_4'
        self.manifest = c.read(folder/'INPUTS.json')
        self.report = c.read(folder/'tracks/source/REPORT.json')

    def test_actual_source_domain(self):
        c.validate_flex_report(self.report, self.manifest, 'source')

    def test_changed_source_pixels_rejected(self):
        self.manifest['source_score_sha256'] = 'different'
        with self.assertRaises(AssertionError):
            c.validate_flex_report(self.report, self.manifest, 'source')

    def test_changed_frame_time_rejected(self):
        self.report['timebase']['frames'][20]['best_effort_timestamp_time'] = '2.6'
        with self.assertRaises(AssertionError):
            c.validate_flex_report(self.report, self.manifest, 'source')

    def test_changed_tracker_settings_rejected(self):
        for key, value in [('checkpoint_sha256', 'different'), ('grid_size', 10),
                           ('mask', 'different'), ('tracks_shape', [3025, 48, 2]),
                           ('metric_functions_sha256', 'different')]:
            changed = copy.deepcopy(self.report)
            changed[key] = value
            with self.assertRaises(AssertionError):
                c.validate_flex_report(changed, self.manifest, 'source')

    def test_actual_pair_and_all_fixed_instants_bound(self):
        gate = c.read(ROOT/'configs/GATE.json')
        manifest = c.read(ROOT/'configs/CONSUMER_INPUTS.json')
        self.assertTrue(gate['passed'])
        self.assertEqual(manifest['evaluate_indices'], list(range(0, 147, 3)))
        self.assertEqual(set(x['role'] for x in self.manifest['targets']), {'native', 'forced'})
        for target in self.manifest['targets']:
            self.assertEqual(target['full_sha256'], gate['runs'][target['role']]['video']['sha256'])
            self.assertEqual(len(target['score_frame_md5']), 49)


if __name__ == '__main__':
    unittest.main()
