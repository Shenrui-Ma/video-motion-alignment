"""Independent dense oracle for the root's sparse diagnostic, CPU only."""
import importlib.util
import pathlib
import sys
import unittest
import numpy as np

spec = importlib.util.spec_from_file_location('observed', pathlib.Path(__file__).with_name('evaluate_probabilities.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Probability(unittest.TestCase):
    def test_grouped_lse_matches_flattened_token_softmax_all_axes(self):
        rng = np.random.default_rng(927)
        q = rng.normal(size=(7,3,4,5))
        k = rng.normal(size=q.shape)
        valid = np.array([1,1,0,1,1,0,1], dtype=bool)
        out = m.retrieval_probabilities(q,k,valid)
        expected = np.zeros_like(out)
        tids = np.flatnonzero(valid)
        for h in range(4):
            for t in tids:
                for p in range(3):
                    logits = np.array([q[t,p,h]@k[j,r,h]/np.sqrt(5) for j in tids for r in range(3)])
                    weights = np.exp(logits-logits.max())
                    weights /= weights.sum()
                    expected[h,t,p,tids] = weights.reshape(len(tids),3).sum(axis=1)
        np.testing.assert_allclose(out,expected,rtol=3e-15,atol=3e-15)
        self.assertEqual(np.count_nonzero(out[...,~valid]),0)
        self.assertEqual(np.count_nonzero(out[:,~valid]),0)

    def test_late_generated_event_uses_its_time_but_source_target_span(self):
        spans = [[0,0],[1,4],[5,8],[9,12],[13,16],[17,17]]
        valid = np.ones(6,dtype=bool)
        p = np.zeros((2,6,3,6))
        rp = np.zeros_like(p)
        for t in range(6):
            p[:,t,:,max(0,t-1)] = 1
            rp[:,t,:,t] = 1
        case = {'case_id':'fixture','frozen_events':[{'id':'transition',
          'source':[5,8],'native':[9,12],'global_weak':[5,8],
          'midpoint_offsets_frames':{'native':4,'global_weak':0},
          'offset_uncertainty_frames':{'native':[1,7],'global_weak':[-3,3]}}]}
        event=m.summarize(p,rp,spans,valid,case,'native')['events'][0]
        self.assertEqual(event['query_bins'],[3])
        self.assertEqual(event['reference_bins'],[2])
        self.assertEqual(event['signed_phase_frames']['count'],6)
        self.assertEqual(event['signed_phase_frames']['mean'],4)
        self.assertEqual(event['reference_event_mass']['mean'],1)
        self.assertEqual(event['self_bias_subtracted_phase_diagnostic']['mean'],4)

    def test_static_content_has_uniform_mass_and_high_entropy(self):
        q=np.ones((6,3,4,5),dtype=np.float32)
        valid=np.array([1,1,1,1,0,0],dtype=bool)
        p=m.retrieval_probabilities(q,q,valid)
        np.testing.assert_array_equal(p[:,valid][...,valid],np.full((4,4,3,4),.25))
        # Static data must not magically peak at the diagonal through bin indices.
        self.assertEqual(float(p[0,2,0,2]),.25)


if __name__ == '__main__':
    unittest.main(verbosity=2)
