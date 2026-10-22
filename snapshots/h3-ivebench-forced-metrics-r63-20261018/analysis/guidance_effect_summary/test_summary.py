import copy
import unittest
from summarize_pair import summarize


def fixture(active=True):
    counts = [50 if active and 6 <= i < 15 else 0 for i in range(20)]
    rows = [{'forward_index':i, 'routed_blocks':n,
             **({'sampled_ref_mass_mean':.1, 'sampled_correction_ratio_mean':.2,
                 'sampled_finite':True, 'layer_stats':[{}]*50} if n else {})} for i,n in enumerate(counts)]
    return {'run_id':'example', 'routed_by_forward':counts, 'routed_calls':sum(counts),
            'completed_forward_calls':20, 'expected_sampling_steps':20, 'forward_summaries':rows}


class SummaryTests(unittest.TestCase):
    def test_nine_active_steps_and_efficiency(self):
        row=summarize(fixture(),{'name':'example','status':'success','submitted_unix':100,'observed_unix':300})
        self.assertEqual(row['active_zero_based_steps'],list(range(6,15)))
        self.assertEqual(row['routed_attention_calls'],450)
        self.assertTrue(row['sampled_attention_output_changed'])
        self.assertAlmostEqual(row['sampled_correction_ratio']['mean_of_active_step_means'],.2)
        self.assertEqual(row['efficiency']['job_wall_seconds_per_NFE_including_loading'],10)

    def test_zero_route_is_explicit(self):
        row=summarize(fixture(False));self.assertFalse(row['intervention_executed'])
        self.assertFalse(row['sampled_attention_output_changed']);self.assertIsNone(row['sampled_ref_mass'])

    def test_called_but_zero_correction_and_missing_stats(self):
        data=fixture()
        for row in data['forward_summaries']:
            if row['routed_blocks']:row['sampled_correction_ratio_mean']=0.
        self.assertTrue(summarize(data)['intervention_executed']);self.assertFalse(summarize(data)['sampled_attention_output_changed'])
        data['forward_summaries'][6].pop('sampled_ref_mass_mean')
        self.assertIsNone(summarize(data)['sampled_attention_output_changed'])
        for row in data['forward_summaries']:row.pop('sampled_ref_mass_mean',None)
        self.assertIsNone(summarize(data)['sampled_attention_output_changed'])

    def test_inconsistent_counts_or_wrong_run_rejected(self):
        data=fixture();data['routed_calls']=0
        with self.assertRaises(ValueError):summarize(data)
        with self.assertRaises(ValueError):summarize(fixture(),{'name':'other','submitted_unix':0,'observed_unix':1})


if __name__=='__main__':unittest.main(verbosity=2)
