import itertools
import unittest
import torch
from phase_calibration import timeline, path_match, calibrate, features, align


class PhaseTests(unittest.TestCase):
    def setUp(self):torch.set_num_threads(1)

    def test_full_valid_bins_and_centers(self):
        a,b,c,m=timeline(32,105)
        self.assertEqual(m.nonzero().flatten().tolist(),list(range(31)))
        self.assertEqual(c[:6].tolist(),[0,2.5,6.5,10.5,14.5,17])
        self.assertEqual(int(b[31]),106)
        self.assertEqual(int(timeline(47,144)[3].sum()),42)

    def test_dynamic_programming_against_exhaustive_oracle(self):
        c=torch.tensor([[.9,.2,.8,.4],[.7,.1,.3,.8],[.8,.6,.2,.1]],dtype=torch.float64)
        ids=torch.arange(4);ti=torch.arange(3)
        p=path_match(c,ids,ti)
        score=lambda x:sum(float(c[i,j]) for i,j in enumerate(x))+.05*sum(abs(x[i]-x[i-1]-1) for i in range(1,3))
        feasible=[x for x in itertools.product(range(4),repeat=3) if all(x[i]-x[i-1] in (0,1,2) for i in (1,2))]
        self.assertAlmostEqual(score(p),min(map(score,feasible)),places=12)

    def test_known_shifts_and_bias(self):
        torch.manual_seed(47)
        p=torch.randn(22,24,4,4,dtype=torch.float64)
        c=timeline(22,73)[2];ids=torch.arange(22)
        r=calibrate(p,ids,c)
        self.assertTrue(r['all_shifts_passed'])
        self.assertTrue(r['static_bias']['passed'])
        for s in r['shifts']:
            self.assertEqual(s['correct_fraction'],1)
            self.assertTrue(all(row['absolute_bin_error']==0 for row in s['rows']))

    def test_no_information_not_zero_error(self):
        r=calibrate(torch.zeros(20,24,4,4,dtype=torch.float64),torch.arange(20),timeline(20,68)[2])
        self.assertFalse(r['all_shifts_passed'])
        for s in r['shifts']:
            self.assertIsNone(s['correct_fraction'])
            self.assertEqual(s['accepted_summary']['n'],0)

    def test_periodic_features_retain_ambiguity(self):
        p=torch.zeros(20,24,4,4,dtype=torch.float64)
        for i in range(20):p[i]=torch.sin(torch.tensor(i*1.5707963267948966))
        f,ids,v,_=features(p,torch.arange(20),timeline(20,68)[2])
        a=align(f,f,ids,ids,timeline(20,68)[2],v,v)
        self.assertTrue(any('ambiguous_local_match' in r['reasons'] for r in a['rows']))

    def test_shift_does_not_wrap_or_pad(self):
        torch.manual_seed(9)
        p=torch.randn(12,24,4,4,dtype=torch.float64)
        r=calibrate(p,torch.arange(12),timeline(12,39)[2])
        for s in r['shifts']:
            for row in s['rows']:
                self.assertGreaterEqual(row['expected_source_bin'],1)
                self.assertLessEqual(row['expected_source_bin'],10)


if __name__=='__main__':unittest.main()
