import copy
import itertools
import random
import unittest
import numpy as np
from bindings import V2
from selector import solve,relation,better,key
import profile_v3
import synthetic_v2


def row(a,b,phase,value=1.,part='left_arm'):
    phase=[phase] if isinstance(phase,int) else phase
    return dict(start=a,end=b,phase_set=phase,lag=phase[0] if phase else 0,value=value,part=part)


def oracle(rows):
    winner=(0.,[])
    for flags in itertools.product((False,True),repeat=len(rows)):
        chosen=sorted([r for r,take in zip(rows,flags) if take],key=key)
        if any(relation(a,b)['status']!='ROBUST_ORDERED' for a,b in zip(chosen,chosen[1:])):continue
        candidate=(sum(r['value'] for r in chosen),chosen)
        if better(candidate,winner):winner=candidate
    return winner


class TestCandidate(unittest.TestCase):
    def test_empty(self):self.assertEqual(solve([])['K'],0)
    def test_source_overlap(self):
        r=solve([row(3,9,5,2),row(6,13,20,3)])
        self.assertEqual(r['K'],1);self.assertEqual(r['objective'],3)
    def test_target_reversal(self):
        a,b=row(27,55,6,2),row(59,68,-22,1)
        self.assertEqual(relation(a,b)['status'],'NO_ORDERED_PHASE_PAIR')
        self.assertEqual(solve([a,b])['K'],1)
    def test_wide_set_ambiguity(self):
        a,b=row(0,9,[3,4,5],2),row(10,19,[3,4,5],1)
        self.assertEqual(relation(a,b)['status'],'SET_ORDER_AMBIGUITY')
        result=solve([a,b]);self.assertEqual(result['K'],1)
        self.assertEqual(result['selected'][0]['phase_set'],[3,4,5])
    def test_touching_target_rejected(self):
        self.assertEqual(solve([row(0,9,6),row(10,19,5)])['K'],1)
    def test_robust_chain(self):
        self.assertEqual(solve([row(0,9,[3,4]),row(15,24,[3,4])])['K'],2)
    def test_isolated_alias_survives(self):
        self.assertEqual(solve([row(59,68,-22)])['K'],1)
    def test_minimum_segments_tie(self):
        result=solve([row(0,9,6),row(10,19,6),row(0,19,6,2)])
        self.assertEqual(result['K'],1)
    def test_lex_tie(self):
        result=solve([row(0,9,8),row(0,9,6)])
        self.assertEqual(result['selected'][0]['lag'],6)
    def test_different_limbs_require_separate_call(self):
        with self.assertRaises(ValueError):solve([row(0,9,6),row(0,9,6,part='right_arm')])
    def test_invalid_candidate(self):
        for bad in [row(-1,9,6),row(0,141,6),row(0,9,6,float('nan')),row(0,9,6,-1),row(0,9,[])]:
            with self.assertRaises(ValueError):solve([bad])
    def test_input_unchanged(self):
        rows=[row(0,9,[3,4]),row(15,24,[3,4])];before=copy.deepcopy(rows);solve(rows)
        self.assertEqual(rows,before)
    def test_exact_small_oracle(self):
        rng=random.Random(20261017)
        for trial in range(160):
            rows=[]
            for index in range(8):
                a=rng.randrange(0,30);b=a+rng.randrange(1,8);d=rng.randrange(-12,13)
                rows.append(row(a,b,list(range(d,d+rng.randrange(1,5))),rng.randrange(1,6)))
            expected=oracle(rows);actual=solve(rows)
            self.assertEqual(actual['objective'],expected[0],trial)
            self.assertEqual([key(r) for r in actual['selected']],[key(r) for r in expected[1]],trial)
    def test_wrapper_evidence_and_baseline_unchanged(self):
        case=next(c for c in synthetic_v2.cases() if c['id']=='local_single_6')
        x,y,_,_=synthetic_v2.build(case)
        before,ea=V2.analyze(x,y);new,eb=profile_v3.analyze(x,y);after,ec=V2.analyze(x,y)
        self.assertEqual(before['selected'],after['selected'])
        for name in ea:np.testing.assert_equal(ea[name],eb[name]);np.testing.assert_equal(ea[name],ec[name])
        for part in before['parts']:
            self.assertEqual(before['parts'][part]['counts'],new['parts'][part]['counts'])
            compact=new['parts'][part]['selector_audit']['source_only_selected']
            self.assertEqual([(r['start'],r['end'],r['lag']) for r in compact],[(r['start'],r['end'],r['diagnostic_best_lag']) for r in before['parts'][part]['selected']])

if __name__=='__main__':unittest.main()
