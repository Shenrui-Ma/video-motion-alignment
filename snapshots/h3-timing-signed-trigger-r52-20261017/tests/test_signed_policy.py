import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import signed_policy as s

def row(lag=5,gain=.8,window=(20,35),feature='left_arm_direction'):
    return {'baseline':'delayed_candidate' if lag>0 else 'advanced_candidate','status':'measured','min_gain':gain,
            'window':list(window),'feature':feature,'comparison':{str(c):{'proposal_lag':lag,'null_comparisons':[{'null_cost':1.,'proposal_cost':1.-gain} for _ in range(5)]} for c in (.3,.5)}}

class SignedTests(unittest.TestCase):
    def test_old_positive_groups_exact_except_explicit_direction(self):
        rows=[row(),row(window=(32,47),feature='arm_direction'),row(window=(80,95))]
        old=s.old.components(rows);new=s.components(rows)
        for group in new:
            for member in group['members']:member.pop('direction')
        self.assertEqual(old,new)

    def test_advance_is_new_candidate_but_final_alone_never_ON(self):
        value=row(-5)
        self.assertIsNone(s.old.candidate(value));self.assertEqual(s.candidate(value)['direction'],'advanced')
        self.assertFalse(s.Policy().update(0,[value])['active'])

    def test_same_direction_persistence_and_sign_flip(self):
        p=s.Policy();self.assertFalse(p.update(0,[row(-5)])['active']);self.assertTrue(p.update(1,[row(-4)])['active'])
        self.assertFalse(p.update(2,[row(5)])['active']);self.assertTrue(p.update(3,[row(6)])['active'])

    def test_shared_arm_and_overlap_unchanged(self):
        p=s.Policy();p.update(0,[row(-5)])
        self.assertFalse(p.update(1,[row(-5,feature='right_arm_direction')])['active'])
        self.assertFalse(p.update(2,[row(-5,window=(80,95))])['active'])

    def test_gain_equality_unknown_aligned_rejected(self):
        for value in (row(-5,gain=.5),dict(row(-5),status='unknown'),dict(row(-5),baseline='aligned')):
            self.assertIsNone(s.candidate(value))
        p=s.Policy();p.update(0,[row(-5)]);p.update(1,[]);self.assertFalse(p.update(2,[row(-5)])['active'])

    def test_mixed_component_keeps_original_strongest_selection(self):
        rows=[row(5,gain=.6),row(-5,gain=.9,window=(30,45))]
        group=s.components(rows);self.assertEqual(len(group),1)
        self.assertEqual(len(group[0]['members']),2);self.assertEqual(group[0]['representative']['direction'],'advanced')

    def test_invalid_candidate_sign_or_confidence_not_silently_relabelled(self):
        for lag in (0,2,-2,float('inf')):
            value=row(lag)
            with self.assertRaises(ValueError):s.candidate(value)
        value=row(-5);value['comparison']['0.5']['proposal_lag']=5
        with self.assertRaises(ValueError):s.candidate(value)
        value=row(-5);value['baseline']='delayed_candidate'
        with self.assertRaises(ValueError):s.candidate(value)

if __name__=='__main__':unittest.main()
