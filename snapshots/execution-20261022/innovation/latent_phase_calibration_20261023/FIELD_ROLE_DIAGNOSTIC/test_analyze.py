import unittest
from analyze import group_metric, local_optimum


class StatisticsTests(unittest.TestCase):
    def test_perfect_role_effect(self):
        rows=[{'role':t%5,'x':float(t%5)} for t in range(20)]
        s=group_metric(rows,'x')
        self.assertEqual(s['role_n'],[4]*5)
        self.assertEqual(s['role_means'],[0.,1.,2.,3.,4.])
        self.assertEqual(s['between_role_variance_equal_weight'],2.)
        self.assertEqual(s['role_eta_squared'],1.)

    def test_uniform_is_zero_variance_not_fake_eta(self):
        s=group_metric([{'role':t%5,'x':.25} for t in range(27)],'x')
        self.assertEqual(s['role_n'],[6,6,5,5,5])
        self.assertEqual(s['between_role_variance_equal_weight'],0.)
        self.assertIsNone(s['role_eta_squared'])

    def test_additive_call_offset_preserves_variance(self):
        r=[{'role':t%5,'x':float(t%7)} for t in range(29)]
        a=group_metric(r,'x');b=group_metric([dict(x=q['x']+32,role=q['role']) for q in reversed(r)],'x')
        self.assertAlmostEqual(a['between_role_ss'],b['between_role_ss'])
        self.assertAlmostEqual(a['role_eta_squared'],b['role_eta_squared'])

    def test_closed_form_stationarity_and_cap(self):
        for t in (.1,.3,.5,.7,.9):
            a=local_optimum(t)
            derivative=2*((3-2*t+.5)*a-(t+.125))
            if a==.5:self.assertLessEqual(derivative,0)
            else:self.assertAlmostEqual(derivative,0)
        self.assertEqual(local_optimum(.5),.25)


if __name__=='__main__':unittest.main()
