import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np
import arm_features as candidate

ORIGINAL = Path(__file__).resolve().parent / 'source_snapshot/scripts/timing_metrics.py'
spec = importlib.util.spec_from_file_location('r56_original_metrics', ORIGINAL)
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)


def example(n=150):
    t = np.arange(n)
    xy = np.zeros((n, 17, 2))
    xy[:, 5], xy[:, 6], xy[:, 11], xy[:, 12] = [-.4, 0], [.4, 0], [-.3, 1], [.3, 1]
    for joint in (7, 8, 9, 10):
        xy[:, joint, 0] = np.sin(t*.075+joint*.7)+joint*.01
        xy[:, joint, 1] = np.cos(t*.113+joint*.2)
    return xy, np.ones((n, 17)), t/24, t, {'video': {'fps': 24}}


class ArmFeatureTests(unittest.TestCase):
    def assert_arm_exact(self, before, after):
        for key in candidate.ARM_FIELDS:
            np.testing.assert_array_equal(before[key], after[key], err_msg=key)

    def test_original_six_fields_exact(self):
        xy, conf, times, frames, raw = example()
        rng = np.random.default_rng(20261017)
        conf[:, [7, 8, 9, 10]] = rng.uniform(0, 1, (len(xy), 4))
        xy[10:12, 7] = xy[10:12, 5]
        for threshold in (.3, .5):
            self.assert_arm_exact(original.pose_features(xy, conf, times, frames, raw, threshold),
                                  candidate.arm_features(xy, conf, times, frames, raw, threshold))

    def test_arm_arithmetic_ast_is_identical(self):
        def copied_block(path, name):
            function = next(node for node in ast.parse(path.read_text()).body
                            if isinstance(node, ast.FunctionDef) and node.name == name)
            start = next(i for i, node in enumerate(function.body)
                         if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Tuple))
            return [ast.dump(node, include_attributes=False) for node in function.body[start:start+3]]
        self.assertEqual(copied_block(ORIGINAL, 'pose_features'),
                         copied_block(Path(candidate.__file__), 'arm_features'))
        self.assertEqual(original.ARMS, candidate.ARMS)

    def test_missing_hips_keeps_visible_arm_directions(self):
        args = list(example())
        before = candidate.arm_features(*args, .5)
        args[0][:, [11, 12]] = np.nan
        args[1][:, [11, 12]] = 0
        with self.assertRaisesRegex(ValueError, 'torso anchors'):
            original.pose_features(*args, .5)
        self.assert_arm_exact(before, candidate.arm_features(*args, .5))

    def test_translation_and_positive_scale(self):
        xy, conf, times, frames, raw = example()
        before = candidate.arm_features(xy, conf, times, frames, raw, .5)
        for scale in (.125, 2.7, 16.):
            after = candidate.arm_features(xy*scale+np.array([113., -57.]), conf, times, frames, raw, .5)
            for key in candidate.ARM_FIELDS:
                np.testing.assert_allclose(before[key], after[key], rtol=1e-10, atol=1e-10, equal_nan=True)

    def test_occluded_endpoint_only_invalidates_its_bones(self):
        args = list(example())
        args[1][10:20, 7] = .49
        value = candidate.arm_features(*args, .5)
        self.assertTrue(np.isnan(value['left_arm_direction'][10:20]).all())
        self.assertTrue(np.isfinite(value['right_arm_direction'][10:20]).all())
        self.assertTrue(np.isfinite(value['arm_direction'][:10]).all())

    def test_zero_length_bone_invalid(self):
        args = list(example())
        args[0][10:20, 7] = args[0][10:20, 5]
        value = candidate.arm_features(*args, .5)
        self.assertTrue(np.isnan(value['arm_direction'][10:20, 0]).all())
        self.assertTrue(np.isfinite(value['right_arm_direction'][10:20]).all())

    def test_threshold_boundary_and_no_person(self):
        args = list(example())
        args[1][0, 7], args[1][1, 7] = .5, np.nextafter(.5, 0)
        value = candidate.arm_features(*args, .5)
        self.assertTrue(np.isfinite(value['left_arm_direction'][0]).all())
        self.assertTrue(np.isnan(value['left_arm_direction'][1]).all())
        args[0][:] = np.nan
        args[1][:] = 0
        value = candidate.arm_features(*args, .5)
        self.assertTrue(np.isnan(value['arm_direction']).all())

    def test_signed_lag_unchanged(self):
        xy, conf, times, frames, raw = example()
        source = candidate.arm_features(xy, conf, times, frames, raw, .5)
        for offset in (7, -5):
            shifted = (np.concatenate([xy[:1].repeat(offset, axis=0), xy[:-offset]]) if offset > 0
                       else np.concatenate([xy[-offset:], xy[-1:].repeat(-offset, axis=0)]))
            target = candidate.arm_features(shifted, conf, times, frames, raw, .5)
            for feature in ('arm_direction', 'left_arm_direction', 'right_arm_direction'):
                diagnostic = original.local_diagnostic(source, target, [50, 65], 24, feature)
                self.assertEqual(diagnostic['reliable_lag_frames'], offset)
                self.assertLess(diagnostic['best']['error'], 1e-10)

    def test_valid_prefix_preserves_physical_frames(self):
        xy, conf, times, frames, raw = example(10)
        raw['frames'] = [{'selected_person': 0, 'persons': [{'coco17_xy': x.tolist(), 'coco17_score': c.tolist()}],
                          'time_s': float(t), 'frame': int(i)} for x,c,t,i in zip(xy,conf,times,frames)]
        value = candidate.features(raw, SimpleNamespace(valid_frames=7), .5)
        self.assertIs(value['raw'], raw)
        np.testing.assert_array_equal(value['frames'], frames[:7])
        self.assert_arm_exact(candidate.arm_features(xy[:7],conf[:7],times[:7],frames[:7],raw,.5), value)


if __name__ == '__main__':
    unittest.main()
