import unittest
from automatic_window_policy import Policy,components

def row(window,feature='left_arm_direction',benefit=.6,gain=.7):
    return {'window':window,'feature':feature,'status':'measured','baseline':'delayed_candidate','min_gain':gain,
            'comparison':{str(c):{'proposal_lag':8,'null_comparisons':[
                {'proposal_cost':.1,'null_cost':.1+benefit} for _ in range(5)]} for c in (.3,.5)}}

class Tests(unittest.TestCase):
    def test_no_candidate(self):self.assertFalse(Policy().update(0,[])['active'])
    def test_two_observations(self):
        p=Policy();self.assertFalse(p.update(0,[row([20,35])])['active'])
        self.assertTrue(p.update(1,[row([24,39])])['active'])
    def test_variable_count(self):
        p=Policy();r=[row([20,35]),row([60,75],'right_arm_direction')]
        p.update(0,r);self.assertEqual(len(p.update(1,r)['selected']),2)
    def test_unknown_breaks_persistence(self):
        p=Policy();r=[row([20,35])];p.update(0,r);p.update(1,[])
        self.assertFalse(p.update(2,r)['active']);self.assertTrue(p.update(3,r)['active'])
    def test_part_mismatch(self):
        p=Policy();p.update(0,[row([20,35])])
        self.assertFalse(p.update(1,[row([20,35],'right_arm_direction')])['active'])
    def test_absolute_ranking(self):
        g=components([row([20,35],benefit=.4,gain=.9),row([24,39],benefit=.6,gain=.7)])
        self.assertEqual(g[0]['representative']['window'],[24,39])
    def test_consecutive_indices(self):
        p=Policy()
        with self.assertRaises(ValueError):p.update(5,[])
    def test_duplicate_index(self):
        p=Policy();p.update(0,[])
        with self.assertRaises(ValueError):p.update(0,[])
    def test_chain_retained(self):
        g=components([row([10,25]),row([24,39]),row([38,53])])
        self.assertEqual(len(g),1);self.assertEqual(len(g[0]['members']),3)

if __name__=='__main__':unittest.main()
