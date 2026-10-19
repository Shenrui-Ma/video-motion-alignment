import itertools,math,unittest
from bounds import interval,ratio_extreme,joint_decision,select_candidate


def observed(n=25,proposal=.05,null=1.5,weight=1):
    return [{'frame':i//2,'proposal':proposal,'null':null,'weight':weight} for i in range(n)]


class BoundsTest(unittest.TestCase):
    def test_complete_exact(self):
        slots=observed(32)
        for method in ('uniform','confidence_completion'):
            for tight in (False,True):
                b=interval(slots,method,tight)
                self.assertTrue(b['certified']);self.assertAlmostEqual(b['proposal_cost_upper'],.05)
                self.assertAlmostEqual(b['advantage_normalized_lower'],.7)

    def test_25_of_32_strong_certificate(self):
        slots=observed()+[{'frame':13+i//2,'proposal':None,'null':None,'weight':None} for i in range(7)]
        for method in ('uniform','confidence_completion'):
            self.assertTrue(interval(slots,method,False)['certified'])
        self.assertAlmostEqual(interval(slots,'uniform',False)['proposal_cost_upper'],15.25/32)

    def test_high_observed_gain_not_enough(self):
        slots=observed(null=.4)+[{'frame':13+i//2,'proposal':None,'null':None,'weight':None} for i in range(7)]
        self.assertGreater((.4-.05)/.4,.5)
        for method in ('uniform','confidence_completion'):self.assertFalse(interval(slots,method,True)['certified'])

    def test_observed_low_weights_not_probabilities(self):
        slots=observed(weight=.5)+[{'frame':13+i//2,'proposal':None,'null':None,'weight':None} for i in range(7)]
        self.assertFalse(interval(slots,'confidence_completion',True)['certified'])

    def test_partial_tightens_bounds(self):
        slots=observed(16)+[{'frame':9,'proposal':.1,'null':None,'weight':None},
                            {'frame':10,'proposal':None,'null':1.8,'weight':None}]
        for m in ('uniform','confidence_completion'):
            c,t=interval(slots,m,False),interval(slots,m,True)
            self.assertGreater(t['advantage_unnormalized_lower'],c['advantage_unnormalized_lower'])
            self.assertLessEqual(t['proposal_cost_upper'],c['proposal_cost_upper'])
            self.assertGreaterEqual(t['null_cost_lower'],c['null_cost_lower'])

    def test_enumerated_completions_no_false_certificate(self):
        base=observed(16,proposal=.1,null=1.0,weight=.6)
        partial=[{'frame':9,'proposal':.2,'null':None,'weight':None},
                 {'frame':10,'proposal':None,'null':.7,'weight':None}]
        for method,tight in itertools.product(('uniform','confidence_completion'),(False,True)):
            b=interval(base+partial,method,tight)
            for dn,dp,w1,w2 in itertools.product((0.,.5,1.,2.),(0.,.5,1.,2.),(0.,.5,1.),(0.,.5,1.)):
                bw=1 if method=='uniform' else .6
                if method=='uniform':w1=w2=1
                W=16*bw+w1+w2;cp=(16*bw*.1+w1*.2+w2*dp)/W;cn=(16*bw+w1*dn+w2*.7)/W
                self.assertLessEqual(b['advantage_normalized_lower'],.5*cn-cp+1e-12)
                self.assertGreaterEqual(b['proposal_cost_upper']+1e-12,cp)
                self.assertLessEqual(b['null_cost_lower'],cn+1e-12)
                if b['certified']:
                    self.assertGreater(.5*cn-cp,0);self.assertLessEqual(cp,.5)

    def test_correlated_unit_vector_missing_enumeration(self):
        vectors=[(math.cos(a),math.sin(a)) for a in (0,math.pi/2,math.pi,3*math.pi/2)]
        base=observed(16,.05,1.5)
        for s,p,n in itertools.product(vectors,repeat=3):
            dp=math.dist(s,p);dn=math.dist(s,n)
            for kp,kn in itertools.product((False,True),repeat=2):
                slot={'frame':8,'proposal':dp if kp else None,'null':dn if kn else None,'weight':1 if kp and kn else None}
                for method in ('uniform','confidence_completion'):
                    b=interval(base+[slot],method,True)
                    for weight in ((1.,) if method=='uniform' or kp and kn else (0.,.5,1.)):
                        W=16+weight;cp=(.8+weight*dp)/W;cn=(24+weight*dn)/W
                        self.assertGreaterEqual(b['proposal_cost_upper']+1e-12,cp)
                        self.assertLessEqual(b['advantage_normalized_lower'],.5*cn-cp+1e-12)

    def test_ratio_extrema_against_weight_vertices(self):
        vals=[.1,.9,1.7];S=.4;W=2
        actual=[(S+sum(a*b for a,b in zip(ws,vals)))/(W+sum(ws)) for ws in itertools.product((0,.5,1),repeat=3)]
        self.assertAlmostEqual(ratio_extreme(S,W,vals,True),max(actual))
        self.assertAlmostEqual(ratio_extreme(S,W,vals,False),min(actual))

    def test_constant_and_unknown(self):
        for slots in (observed(32,0,0),[{'frame':i,'proposal':None,'null':None,'weight':None} for i in range(16)]):
            for m in ('uniform','confidence_completion'):self.assertFalse(interval(slots,m,True)['certified'])

    def test_invalid_slots_rejected(self):
        for patch in ({'proposal':2.01},{'weight':1.2},{'proposal':None,'weight':0},{'null':float('nan')}):
            with self.assertRaises(ValueError):interval(observed(16)+[observed(1)[0]|patch],'uniform',True)

    def test_candidate_coverage_independent_but_alias_reject(self):
        curve=[{'lag_frames':l,'error':.5 if l!=4 else .01,'valid_frame_count':16,'coverage':.78125} for l in range(-24,25)]
        self.assertEqual(select_candidate(curve)['candidate_lag'],4)
        curve[20+24]['error']=.01
        self.assertIn('observed_flat_or_multiple_phases',select_candidate(curve)['candidate_flags'])
        curve=[dict(r,error=0.) for r in curve]
        self.assertIn('observed_flat_or_multiple_phases',select_candidate(curve)['candidate_flags'])

    def test_both_conf_all_nulls_required(self):
        def entry(lag=4):return {'candidate_lag':lag,'candidate_flags':[],
                'comparisons':[{'null_lag':e,'bound':{'certified':True}} for e in range(-2,3)]}
        self.assertEqual(joint_decision({'0.3':entry(),'0.5':entry()})['status'],'CERTIFIED_DELAYED_EVIDENCE')
        e=entry();e['comparisons'][2]['bound']['certified']=False
        self.assertEqual(joint_decision({'0.3':entry(),'0.5':e})['status'],'UNKNOWN')
        self.assertEqual(joint_decision({'0.3':entry(),'0.5':entry(-4)})['status'],'UNKNOWN')
        e=entry();e['comparisons'].pop()
        self.assertEqual(joint_decision({'0.3':entry(),'0.5':e})['status'],'UNKNOWN')

    def test_known_signed_shifts_propose_correct_lag(self):
        def v(t):
            a=.009*t*t+.3*math.sin(.173*t)
            return math.cos(a),math.sin(a)
        for shift in (0,-4,4,-8,8,-12,12):
            curve=[{'lag_frames':lag,'error':sum(math.dist(v(t),v(t+lag-shift)) for t in range(50,66))/16,
                    'valid_frame_count':16,'coverage':1.} for lag in range(-24,25)]
            self.assertEqual(select_candidate(curve)['candidate_lag'],shift)


if __name__=='__main__':unittest.main()
