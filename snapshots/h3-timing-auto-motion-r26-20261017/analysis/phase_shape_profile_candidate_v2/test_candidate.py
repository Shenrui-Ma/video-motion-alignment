import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from frozen import V1,SYNTH,V1_ROOT
import profile_v2 as model
import synthetic_v2 as synthetic
import evaluation
import run_once

class CandidateTests(unittest.TestCase):
    def geometry(self,values):
        membership=np.isin(V1.LAGS,values)[:,None]
        return {k:v.item() for k,v in model.set_geometry(membership).items()}

    def test_wide_connected_direction_set(self):
        g=self.geometry(range(7,16))
        self.assertEqual(g['components'],1);self.assertTrue(g['same_side'])
        self.assertFalse(g['null']);self.assertFalse(g['boundary'])
        self.assertGreater(g['high']-g['low'],4)

    def test_topology_null_boundary_empty(self):
        self.assertEqual(self.geometry([7,8,15,16])['components'],2)
        self.assertFalse(self.geometry([-9,-8,8,9])['same_side'])
        self.assertTrue(self.geometry([1,2,3,4])['null'])
        self.assertTrue(self.geometry([22,23,24])['boundary'])
        self.assertFalse(self.geometry([])['same_side'])
        self.assertEqual(model.component_lists([-5,-4,7,8]),[[-5,-4],[7,8]])

    def test_original31_input_hashes_and_truths_exact(self):
        old=json.loads((V1_ROOT/'CASE_MANIFEST.json').read_text())['cases']
        self.assertEqual(len(synthetic.cases()),43)
        self.assertEqual(synthetic.cases()[:31],SYNTH.cases())
        for case,bound in zip(synthetic.cases()[:31],old):
            self.assertEqual(case,bound['case'])
            a,b,truth,_=synthetic.build(case)
            actual={name:{k:run_once.array_record(v) for k,v in values.items()} for name,values in [('source',a),('target',b)]}
            self.assertEqual(actual,bound['inputs'])
            np.testing.assert_array_equal(truth['source_phase'],np.full((141,2),case['truth']))

    def test_same_profile_loss_common_support_and_value(self):
        a=SYNTH.features('identifiable');b=SYNTH.features('identifiable',6,SYNTH.ROTATION)
        old,oe=V1.analyze(a,b);new,ne=model.analyze(a,b)
        for part in V1.PARTS:
            for key in ('profile_loss','common_mask','value','J','gain','best_profile_rms','phase_low','phase_high'):
                np.testing.assert_array_equal(oe[part+'__'+key],ne[part+'__'+key])
        for row in new['selected']:
            self.assertNotIn('lag',row);self.assertFalse(row['point_estimate_validated'])
            self.assertEqual(row['direction'],'delay')

    def test_all_local_warps_monotone_and_bounded(self):
        t=np.linspace(0,140,10001)
        for case in synthetic.local_cases():
            for rows in case['bumps']:
                d,dp=synthetic.delay(t,rows)
                self.assertGreaterEqual(float((1-dp).min()),.1-1e-12)
                self.assertTrue((np.diff(t-d)>0).all())
                self.assertEqual(d[0],0);self.assertEqual(d[-1],0)

    def test_inverse_and_plateau_truth(self):
        s=np.linspace(0,140,513)
        for case in synthetic.local_cases():
            for rows in case['bumps']:
                u=synthetic.inverse_w(s,rows)
                np.testing.assert_allclose(u-synthetic.delay(u,rows)[0],s,atol=1e-10,rtol=0)
                for row in rows:
                    start=row['a']+row['R']-row['D'];end=row['b']-row['D']
                    points=np.linspace(start,end,31)
                    np.testing.assert_allclose(synthetic.inverse_w(points,rows)-points,row['D'],atol=1e-10,rtol=0)

    def test_continuous_ramp_derivative(self):
        for D,R in [(6,10),(12,20),(-6,10),(-12,20)]:
            rows=[synthetic.bump(D,24,R,76)]
            for edge in (24,24+R,76,76+R):
                d,dp=synthetic.delay(np.array([edge-1e-6,edge,edge+1e-6]),rows)
                self.assertLess(float(np.ptp(d)),1e-10)
                self.assertLess(float(np.ptp(dp)),1e-6)

    def test_shape_controls_have_zero_time_warp(self):
        for case in synthetic.local_cases():
            if case['expected']=='local_zero':
                a,b,truth,plateaus=synthetic.build(case)
                np.testing.assert_array_equal(truth['target_delay'],np.zeros((141,2)))
                np.testing.assert_allclose(truth['source_phase'],0,atol=1e-12)
                self.assertEqual(plateaus,[])
                if case['id']=='local_zero_identity':np.testing.assert_array_equal(a['directions'],b['directions'])

    def test_separate_limbs_and_occlusion(self):
        case=next(c for c in synthetic.local_cases() if c['id']=='local_separate_arms_occluded')
        _,b,truth,_=synthetic.build(case)
        self.assertEqual(truth['target_delay'][40,0],6);self.assertEqual(truth['target_delay'][40,1],0)
        self.assertEqual(truth['target_delay'][90,0],0);self.assertEqual(truth['target_delay'][90,1],12)
        self.assertTrue(np.isnan(b['directions'][60:66]).all())

    def test_local_verdict_direction_and_point_are_separate(self):
        case=next(c for c in synthetic.local_cases() if c['id']=='local_single_6')
        _,_,truth,plateaus=synthetic.build(case)
        evidence={p+'__common_mask':np.ones((141,2),bool) for p in V1.PARTS}
        rows=[{'part':p['part'],'start':p['source_start'],'end':p['source_end'],
               'direction':'delay','diagnostic_best_lag':15} for p in plateaus]
        result={'K':2,'selected':rows}
        v=evaluation.local_verdict(case,result,evidence,truth,plateaus)
        self.assertTrue(v['direction_task']['pass'])
        self.assertFalse(v['draft_point_task_diagnostic']['pass'])
        self.assertFalse(v['transition_constant_lag_requirement'])
        rows[0]['direction']='advance'
        self.assertFalse(evaluation.local_verdict(case,result,evidence,truth,plateaus)['direction_task']['pass'])

    def test_old_reason_failure_is_preserved(self):
        case=next(c for c in SYNTH.cases() if c['id']=='uniform')
        result={'K':0,'selected':[],'parts':{p:{'counts':{'NO_SUPPORTED_TIME_DEVIATION':1}} for p in V1.PARTS}}
        old=evaluation.original_point_verdict(case,result,{})
        direction=evaluation.original_direction_verdict(case,result,{})
        self.assertTrue(old['checks']['K_zero']);self.assertFalse(old['checks']['required_rejection'])
        self.assertFalse(old['pass']);self.assertTrue(direction['pass'])

    def test_atomic_commit_refuses_changed_input(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'audit') as directory:
            path=Path(directory)/'COMPLETE.json'
            with patch.object(run_once,'verify',side_effect=ValueError('hash changed')):
                with self.assertRaises(ValueError):run_once.commit(path,{},[{}])
            self.assertFalse(path.exists())

if __name__=='__main__':unittest.main()
