import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from contract import adult_only, require_sequence, validate_pose_shape


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.g = dict(width=1312, height=736, frames=107, valid_frames=98, fps=24)
        self.raw = dict(video=dict(width=1312, height=736, container_frame_count=107, fps=24), frames=[
            dict(frame=i, time_s=i/24, selected_person=0, persons=[dict(box_xyxy=[600, 0, 1000, 700]), dict(box_xyxy=[50, 0, 400, 700])]) for i in range(107)])

    def test_full_sequence_required(self):
        rows = [dict(index=i, status='complete') for i in range(20)]
        require_sequence(rows)
        with self.assertRaisesRegex(ValueError, 'missing'):
            require_sequence(rows[:-1])

    def test_failure_not_imputed_unknown(self):
        rows = [dict(index=i, status='complete') for i in range(20)]
        rows[6]['status'] = 'failed'
        with self.assertRaisesRegex(ValueError, 'technical failure'):
            require_sequence(rows)

    def test_adult_remains_raw_unmodified(self):
        before = copy.deepcopy(self.raw)
        result, rejected = adult_only(self.raw, self.g)
        self.assertEqual(self.raw, before)
        self.assertEqual(rejected, [])
        self.assertTrue(all(r['selected_person'] == 0 for r in result['frames']))

    def test_child_never_substituted(self):
        self.raw['frames'][0]['selected_person'] = 1
        result, rejected = adult_only(self.raw, self.g)
        self.assertEqual(rejected, [0])
        self.assertIsNone(result['frames'][0]['selected_person'])
        self.assertEqual(len(result['frames'][0]['persons']), 2)

    def test_original_time_mandatory(self):
        self.raw['frames'][20]['time_s'] += 1/24
        with self.assertRaisesRegex(ValueError, 'physical time'):
            validate_pose_shape(self.raw, self.g)

    def test_padding_retained_in_pose_then_excluded_by_geometry(self):
        result, _ = adult_only(self.raw, self.g)
        self.assertEqual(len(result['frames']), 107)
        self.assertEqual([r['frame'] for r in result['frames'][:98]], list(range(98)))


if __name__ == '__main__':
    unittest.main()
