import copy
import unittest
import numpy as np

import diagnose as d
from segment_features import select


class SegmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scanner, cls.policy, cls.helper, cls.layout = d.load('r55')

    def fixture(self, count=90):
        t = np.arange(count)
        xy = np.zeros((count,17,2))
        for j in (5,6,7,8,9,10):
            xy[:,j,0] = np.sin(.075*t + .7*j)+.01*j
            xy[:,j,1] = np.cos(.113*t + .2*j)
        conf = np.ones((count,17))
        return self.helper.arm_features(xy, conf, t/24, t, {'video': {'fps':24}}, .5)

    def test_selected_vectors_are_exact_existing_vectors(self):
        f=self.fixture()
        for family,indices in [('upper',[0,2]),('forearm',[1,3])]:
            s=select(f,family)
            np.testing.assert_array_equal(s['arm_direction'],f['arm_direction'][:,indices])
            np.testing.assert_array_equal(s['left_arm_direction'],f['arm_direction'][:,indices[:1]])
            np.testing.assert_array_equal(s['right_arm_conf'],f['arm_conf'][:,indices[1:]])

    def test_hide_changes_only_fixed_confidences(self):
        raw={'frames':[{'frame':7,'time_s':7/24,'selected_person':0,
                        'persons':[{'coco17_xy':[[i,2*i] for i in range(17)],'coco17_score':[1.]*17}]}]}
        before=copy.deepcopy(raw)
        out=d.hide(raw,[9])
        self.assertEqual(raw,before)
        expected=copy.deepcopy(before)
        expected['frames'][0]['persons'][0]['coco17_score'][9]=0.
        del out['synthetic_visibility_diagnostic']
        self.assertEqual(out,expected)

    def test_wrist_invisibility_does_not_change_upper(self):
        f=self.fixture()
        conf=f['conf'].copy();conf[:,[9,10]]=0
        hidden=self.helper.arm_features(f['xy'],conf,f['times'],f['frames'],f['raw'],.5)
        np.testing.assert_array_equal(select(hidden,'upper')['arm_direction'],select(f,'upper')['arm_direction'])
        self.assertTrue(np.isnan(select(hidden,'forearm')['arm_direction']).all())

    def test_one_invisible_wrist_retains_only_same_side_available_forearm(self):
        f=self.fixture()
        conf=f['conf'].copy();conf[:,9]=0
        h=select(self.helper.arm_features(f['xy'],conf,f['times'],f['frames'],f['raw'],.5),'forearm')
        self.assertTrue(np.isnan(h['left_arm_direction']).all())
        np.testing.assert_array_equal(h['right_arm_direction'],select(f,'forearm')['right_arm_direction'])
        diag=self.scanner.m.local_diagnostic(select(f,'forearm'),h,[32,47],24,'left_arm_direction')
        self.assertIsNone(diag['reliable_lag_frames'])
        self.assertEqual(diag['status'],'unreliable_detection_coverage')

    def test_unchanged_segments_have_zero_lag(self):
        f=self.fixture()
        for family in ('upper','forearm'):
            s=select(f,family)
            for feature in d.NAMES[family]:
                result=self.scanner.m.local_diagnostic(s,s,[32,47],24,feature)
                self.assertEqual(result['reliable_lag_frames'],0)

    def test_high_residual_rejected_despite_full_visibility(self):
        f=select(self.fixture(),'upper')
        target=copy.deepcopy(f)
        for feature in ('arm_direction','left_arm_direction','right_arm_direction'):
            f[feature][:]=[1.,0.];target[feature][:]=[-1.,0.]
        result=self.scanner.m.local_diagnostic(f,target,[32,47],24,'left_arm_direction')
        self.assertIsNone(result['reliable_lag_frames'])
        self.assertIn('large_pose_difference_even_after_shift',result['flags'])
        gain=self.scanner.compare(f,target,[32,47],4,'left_arm_direction')
        self.assertEqual(gain['status'],'unknown')
        self.assertTrue(all(x['status']=='unknown_residual_shape' for x in gain['null_comparisons']))

    def test_actual_execution_ignores_detector_label_with_same_mask(self):
        g=self.scanner.Geometry(frames=90,valid_frames=87)
        a={'active':True,'physical_intervals':[[20,35]],'selected':[{'feature':'left_arm_direction','lags':[4,4]}]}
        b={'active':True,'physical_intervals':[[20,35]],'selected':[{'feature':'right_arm_direction','lags':[8,8]}]}
        self.assertNotEqual(d.proposal_signature(a),d.proposal_signature(b))
        self.assertEqual(d.execution_signature(a,g,self.layout),d.execution_signature(b,g,self.layout))

    def test_same_process_second_import_rejected(self):
        with self.assertRaisesRegex(ValueError,'fresh CPU process'):
            d.load('r50')


if __name__=='__main__':unittest.main()
