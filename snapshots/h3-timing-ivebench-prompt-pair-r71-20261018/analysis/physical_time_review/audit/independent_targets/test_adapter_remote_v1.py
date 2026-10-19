import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'vendor/physical'))
import evaluate90
from adapter import independent_targets


def pose(missing_torso=False, malformed=False):
    import numpy as np
    frames = []
    for i in range(90):
        xy = np.zeros((17, 2))
        xy[5], xy[6], xy[11], xy[12] = [-.4, 0], [.4, 0], [-.3, 1], [.3, 1]
        for j in (7, 8, 9, 10):
            xy[j] = [np.sin(i * .075 + j * .7), np.cos(i * .113 + j * .2)]
        confidence = np.ones(17)
        if missing_torso:
            confidence[11:13] = 0
        frames.append({'frame': i, 'time_s': i / 24, 'selected_person': 0,
                       'persons': [{'coco17_xy': xy.tolist(),
                                    'coco17_score': confidence.tolist()}]})
    if malformed:
        frames[0]['persons'][0]['coco17_xy'] = [[0, 0]]
    return {'video': {'width': 1312, 'height': 736, 'container_frame_count': 90, 'fps': 24},
            'frames': frames}


class IsolationTests(unittest.TestCase):
    def test_bad_a_does_not_hide_good_b(self):
        source, bad, good = pose(), pose(True), pose()
        original = evaluate90.evaluate(source, bad, good, 'short_0210')
        self.assertTrue(all(x['status'] == 'unknown_visibility'
                            for x in original['confidence_results'].values()))
        split = independent_targets(evaluate90.evaluate, source, {'A': bad, 'B': good}, 'short_0210')
        self.assertTrue(all(x['status'] == 'unknown_visibility'
                            for x in split['A']['confidence_results'].values()))
        self.assertTrue(all(x['status'] == 'measured'
                            for x in split['B']['confidence_results'].values()))
        self.assertTrue(all(x['lag_frames_at_confidence_03_05'] == [0, 0]
                            for x in split['B']['lag_summary']))

    def test_both_measurable_keep_exact_original_diagnostics(self):
        source, a, b = pose(), pose(), pose()
        original = evaluate90.evaluate(source, a, b, 'short_0210')
        split = independent_targets(evaluate90.evaluate, source, {'A': a, 'B': b}, 'short_0210')
        for name, old_name in [('A', 'native'), ('B', 'auto')]:
            for confidence, record in original['confidence_results'].items():
                for old, new in zip(record['rows'], split[name]['confidence_results'][confidence]['rows']):
                    self.assertEqual(old['diagnostics'][old_name], new['diagnostic'])
                    self.assertNotIn('common_support', new)

    def test_bad_source_remains_unknown_for_both(self):
        split = independent_targets(evaluate90.evaluate, pose(True), {'A': pose(), 'B': pose()}, 'short_0210')
        for result in split.values():
            self.assertTrue(all(x['status'] == 'unknown_visibility'
                                for x in result['confidence_results'].values()))

    def test_malformed_input_is_technical_failure(self):
        with self.assertRaisesRegex(ValueError, 'Malformed'):
            independent_targets(evaluate90.evaluate, pose(), {'A': pose(malformed=True)}, 'short_0210')

    def test_inputs_are_not_mutated(self):
        source, target = pose(), pose()
        before = copy.deepcopy((source, target))
        independent_targets(evaluate90.evaluate, source, {'B': target}, 'short_0210')
        self.assertEqual(before, (source, target))


if __name__ == '__main__':
    unittest.main()
