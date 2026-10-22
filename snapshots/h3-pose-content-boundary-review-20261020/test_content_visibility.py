import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np
from content_visibility import features

SOURCE = Path('/Users/researcher/DevProjects/h3-ive-handkerchief-full-context-metrics-r126-20261020/audit/visible_arm_feasibility_20261020/scripts/arm_features.py')
spec = importlib.util.spec_from_file_location('frozen_arm_features', SOURCE)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


class ContentBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.geometry = SimpleNamespace(width=100, height=80, valid_frames=1)
        points = [[40, 40] for _ in range(17)]
        points[5], points[7], points[9] = [20, 20], [40, 40], [60, 50]
        points[6], points[8], points[10] = [30, 20], [50, 40], [70, 50]
        self.raw = {'frames': [{'frame': 0, 'time_s': 0,
                    'selected_person': 0, 'persons': [{'coco17_xy': points,
                    'coco17_score': [0.9] * 17}]}]}

    def result(self, rect=(10, 10, 80, 60)):
        return features(self.raw, self.geometry, 0.5, rect, base)

    def test_in_content_descriptor_is_identical(self):
        old = base.features(self.raw, self.geometry, 0.5)
        new = self.result()
        for key in base.ARM_FIELDS:
            np.testing.assert_equal(new[key], old[key])

    def test_high_confidence_outside_elbow_rejects_both_left_segments(self):
        self.raw['frames'][0]['persons'][0]['coco17_xy'][7] = [40, 81]
        old = copy.deepcopy(self.raw)
        new = self.result()
        self.assertTrue(np.isnan(new['left_arm_direction']).all())
        self.assertTrue(np.isfinite(new['right_arm_direction']).all())
        self.assertEqual(new['conf'][0, 7], 0)
        self.assertEqual(self.raw, old)

    def test_padding_endpoint_is_excluded(self):
        self.raw['frames'][0]['persons'][0]['coco17_xy'][9] = [8, 50]
        new = self.result()
        self.assertTrue(np.isfinite(new['left_arm_direction'][0, 0]).all())
        self.assertTrue(np.isnan(new['left_arm_direction'][0, 1]).all())

    def test_right_and_bottom_are_exclusive(self):
        points = self.raw['frames'][0]['persons'][0]['coco17_xy']
        points[5], points[7], points[9] = [10, 10], [90, 40], [60, 70]
        new = self.result()
        self.assertTrue(new['joint_inside_content'][0, 5])
        self.assertFalse(new['joint_inside_content'][0, 7])
        self.assertFalse(new['joint_inside_content'][0, 9])

    def test_confidence_threshold_remains_active(self):
        self.raw['frames'][0]['persons'][0]['coco17_score'][9] = 0.49
        self.assertTrue(np.isnan(self.result()['left_arm_direction'][0, 1]).all())

    def test_missing_person_remains_unknown(self):
        self.raw['frames'][0]['selected_person'] = None
        new = self.result()
        self.assertTrue(np.isnan(new['arm_direction']).all())
        self.assertFalse(new['joint_inside_content'].any())

    def test_bad_rectangle_rejected(self):
        for rect in ((-1, 0, 100, 80), (0, 0, 101, 80), (0, 0, 0, 80),
                     (0, 0, 100, float('nan')), (0, 0, 100)):
            with self.subTest(rect=rect), self.assertRaises(ValueError):
                self.result(rect)


if __name__ == '__main__':
    unittest.main()
