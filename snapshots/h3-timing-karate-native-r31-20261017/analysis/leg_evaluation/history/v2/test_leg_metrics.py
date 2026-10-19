import unittest
import json
import hashlib
import tempfile
from pathlib import Path
import numpy as np
from leg_metrics import leg_view, diagnostic, summarize, windows, metrics, compare, validate_intake


def save_pose(path, pose, confidence, video_sha='a' * 64):
    records = [{'frame': i, 'time_s': i / 24, 'selected_person': 0,
                'persons': [{'coco17_xy': pose['xy'][i].tolist(),
                             'coco17_score': confidence[i].tolist()}]}
               for i in range(141)]
    path.write_text(json.dumps({'video': {'fps': 24, 'sha256': video_sha}, 'frames': records}))
    return {'pose_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'video_sha256': video_sha}


def synthetic(delay=0, scale=1, translation=0):
    n = 150
    t = np.arange(n)
    xy = np.zeros((n, 17, 2))
    xy[:, 5], xy[:, 6] = [-.4, 0], [.4, 0]
    xy[:, 11], xy[:, 12] = [-.3, 1], [.3, 1]
    for j in (13, 14, 15, 16):
        xy[:, j, 0] = np.sin(t * .075 + j * .7) + j * .01
        xy[:, j, 1] = 1.5 + np.cos(t * .113 + j * .2)
    if delay > 0:
        xy = np.concatenate([xy[:1].repeat(delay, axis=0), xy[:-delay]])
    elif delay < 0:
        xy = np.concatenate([xy[-delay:], xy[-1:].repeat(-delay, axis=0)])
    xy = xy * scale + translation
    return metrics.pose_features(xy, np.ones((n, 17)), t / 24, t,
                                 {'video': {'fps': 24}}, .3)


class LegTests(unittest.TestCase):
    def test_known_delay_and_similarity(self):
        source = leg_view(synthetic())
        edited = leg_view(synthetic(7, 2.7, 100))
        for name in ('leg_direction', 'left_leg_direction', 'right_leg_direction'):
            row = diagnostic(source, edited, [50, 65], name)['diagnostic']
            self.assertEqual(row['reliable_lag_frames'], 7)
            self.assertLess(row['best']['error'], 1e-12)

    def test_advance_sign(self):
        row = diagnostic(leg_view(synthetic()), leg_view(synthetic(-5)),
                         [50, 65], 'leg_direction')['diagnostic']
        self.assertEqual(row['reliable_lag_frames'], -5)

    def test_arm_changes_do_not_change_legs(self):
        pose = synthetic()
        before = leg_view(pose)['arm_direction'].copy()
        pose['xy'][:, 7:11] = 123456
        np.testing.assert_array_equal(before, leg_view(pose)['arm_direction'])

    def test_missing_leg_is_unknown(self):
        pose = synthetic()
        pose['conf'][:, [13, 15]] = 0
        row = diagnostic(leg_view(synthetic()), leg_view(pose),
                         [50, 65], 'left_leg_direction')
        self.assertIsNone(row['diagnostic']['reliable_lag_frames'])
        self.assertEqual(summarize(row, row), 'UNKNOWN')

    def test_zero_bone_is_invalid(self):
        pose = synthetic()
        pose['xy'][:, 13] = pose['xy'][:, 11]
        self.assertTrue(np.isnan(leg_view(pose)['arm_direction'][:, 0]).all())

    def test_parent_module_and_input_unchanged(self):
        pose = synthetic()
        old = pose['arm_direction'].copy()
        leg_view(pose)
        np.testing.assert_array_equal(pose['arm_direction'], old)
        self.assertEqual(metrics.ARMS, [(5, 7), (7, 9), (6, 8), (8, 10)])

    def test_complete_window_grid(self):
        actual = windows(141)
        self.assertEqual(len(actual) * 3, 186)
        self.assertIn([125, 140], actual)
        self.assertIn([109, 140], actual)
        self.assertEqual(len(actual), len({tuple(x) for x in actual}))

    def test_missing_anchors_keep_unknown(self):
        row = diagnostic(None, leg_view(synthetic()), [50, 65], 'leg_direction')
        self.assertEqual(row['diagnostic']['status'], 'unknown_visibility')
        self.assertEqual(summarize(row, row), 'UNKNOWN')

    def test_complete_comparison_common_support(self):
        pose = synthetic()
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / 'source.json', Path(folder) / 'target.json'
            binding = {'__source__': save_pose(source, pose, np.ones((141, 17)))}
            confidence = np.full((141, 17), .7)
            confidence[:5, 13] = 0
            binding['same_motion'] = save_pose(target, pose, confidence)
            result = compare(source, {'same_motion': target}, bindings=binding)
        self.assertEqual(len(result['whole_scan']['same_motion']['rows']), 186)
        for threshold in ('0.3', '0.5'):
            all_legs = result['common_support'][threshold][0]
            self.assertAlmostEqual(all_legs['common_valid_fraction'], (141 * 4 - 10) / (141 * 4))
            self.assertEqual(all_legs['same_frame_errors']['same_motion'], 0)
            self.assertEqual(all_legs['common_weights'][0], [0, 0, .7, .7])

    def test_cross_threshold_disagreement_is_unknown(self):
        a = {'diagnostic': {'reliable_lag_frames': 4}}
        b = {'diagnostic': {'reliable_lag_frames': 8}}
        self.assertEqual(summarize(a, b), 'UNKNOWN')

    def test_static_legs_are_ambiguous(self):
        pose = synthetic()
        pose['xy'][:, 11:17] = pose['xy'][0, 11:17]
        row = diagnostic(leg_view(pose), leg_view(pose), [50, 65], 'leg_direction')
        self.assertIsNone(row['diagnostic']['reliable_lag_frames'])
        self.assertIn('flat_or_multiple_matching_phases', row['diagnostic']['flags'])

    def test_tail_delay_requires_unknown(self):
        source, target = leg_view(synthetic()), leg_view(synthetic(24))
        for pose in (source, target):
            for key, value in list(pose.items()):
                if isinstance(value, np.ndarray) and value.shape[0] == 150:
                    pose[key] = value[:141]
        row = diagnostic(source, target, [116, 132], 'leg_direction')
        self.assertIsNone(row['diagnostic']['reliable_lag_frames'])

    def test_two_targets_share_order_invariant_weights(self):
        pose = synthetic()
        with tempfile.TemporaryDirectory() as folder:
            source, a, b = [Path(folder) / (x + '.json') for x in ('source', 'a', 'b')]
            confidence = np.full((141, 17), .6)
            confidence[:3, 14] = 0
            bindings = {'__source__': save_pose(source, pose, np.ones((141, 17))),
                        'a': save_pose(a, pose, np.full((141, 17), .8)),
                        'b': save_pose(b, pose, confidence)}
            first = compare(source, {'a': a, 'b': b}, bindings=bindings)
            second = compare(source, {'b': b, 'a': a}, bindings=bindings)
        self.assertEqual(first['common_support'], second['common_support'])

    def test_intake_rejects_fps_time_and_hash_mismatches(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pose.json'
            binding = save_pose(path, synthetic(), np.ones((141, 17)))
            validate_intake(path, binding)
            with self.assertRaises(ValueError):
                validate_intake(path, {**binding, 'pose_sha256': '0' * 64})
            with self.assertRaises(ValueError):
                validate_intake(path, {**binding, 'video_sha256': '0' * 64})
            for mutate in ('fps', 'time'):
                save_pose(path, synthetic(), np.ones((141, 17)))
                raw = json.loads(path.read_text())
                if mutate == 'fps': raw['video']['fps'] = 30
                else: raw['frames'][20]['time_s'] += .01
                path.write_text(json.dumps(raw))
                updated = {**binding, 'pose_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                with self.assertRaises(ValueError): validate_intake(path, updated)


if __name__ == '__main__':
    unittest.main()
