import copy
import json
from pathlib import Path
import unittest
import diagnose as d


class TransformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads((d.ROOT / 'configs/parents/short_0210/source.pose.json').read_text())

    def test_time_content_and_scores(self):
        for delta in d.SHIFTS:
            target = d.shifted(self.raw, 87, delta)
            for t, row in enumerate(target['frames']):
                entry = target['synthetic_diagnostic']['ledger'][t]
                self.assertEqual(row['frame'], t)
                self.assertEqual(row['time_s'], self.raw['frames'][t]['time_s'])
                self.assertEqual(entry['valid_mask'], t < 87 and 0 <= t-delta < 87)
                if entry['valid_mask']:
                    self.assertEqual(row['persons'], self.raw['frames'][t-delta]['persons'])
                    self.assertEqual(row['selected_person'], self.raw['frames'][t-delta]['selected_person'])
                    self.assertEqual(entry['source_content_index'], t-delta)

    def test_outside_confidence_zero_and_no_wrap(self):
        for delta in d.SHIFTS:
            target = d.shifted(self.raw, 87, delta)
            for row, entry in zip(target['frames'], target['synthetic_diagnostic']['ledger']):
                if not entry['valid_mask']:
                    self.assertIsNone(entry['source_content_index'])
                    self.assertIsNone(row['selected_person'])
                    for p in row['persons']:
                        self.assertEqual(p['coco17_score'], [0.] * 17)
                        self.assertEqual(p['coco17_xy'], [[0., 0.]] * 17)

    def test_identity_valid_prefix(self):
        transformed = d.shifted(self.raw, 87, 0)
        for source, target in zip(self.raw['frames'][:87], transformed['frames'][:87]):
            self.assertEqual(source['persons'], target['persons'])
            self.assertEqual(source['selected_person'], target['selected_person'])

    def test_no_input_mutation(self):
        before = copy.deepcopy(self.raw)
        d.shifted(self.raw, 87, 8)
        self.assertEqual(self.raw, before)

    def test_validated_geometry_and_sources(self):
        d.verify_sources()
        scanner, _ = d.load_modules()
        protocol = json.loads((d.HERE / 'source_snapshot/configs/protocol.json').read_text())
        for case in protocol['cases']:
            geom = scanner.Geometry.from_case(case)
            source = d.HERE / 'source_snapshot' / case['source_pose_path']
            raw = scanner.valid_pose(source, geom)
            self.assertEqual(len(raw['frames']), 90)
            self.assertEqual(d.sha(source), case['source_pose_sha256'])

    def test_signed_policy_identical_observation_persistence(self):
        _, policy = d.load_modules()
        for lag, baseline in [(4, 'delayed_candidate'), (-4, 'advanced_candidate')]:
            row = {'window': [20,35], 'feature': 'left_arm_direction', 'baseline': baseline,
                   'status': 'measured', 'min_gain': 1., 'comparison': {str(c):
                      {'proposal_lag': lag, 'null_comparisons': [{'null_cost': .2, 'proposal_cost': 0.}]}
                      for c in (.3,.5)}}
            p = policy.Policy(threshold=.5)
            self.assertFalse(p.update(0, [row])['active'])
            self.assertTrue(p.update(1, [row])['active'])
            self.assertFalse(p.update(2, [])['active'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
