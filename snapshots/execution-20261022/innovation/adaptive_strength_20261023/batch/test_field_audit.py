"""Independent failure-injection checks for a replayable gain-field audit."""
import copy
import unittest
from field_audit import check_layer, check_field, FieldAuditError


def layer(step=1, block=0):
    active = step > 0
    c = dict(step_index=step, layer_index=block, prior_weight=1., smoothness=.625,
             alpha=[.25]*3, usable_evidence=[False,active,False],
             solver_succeeded=[False,active,False], fallback_to_prior=[True,not active,True],
             anchor_created=[False,not active,False], initialized=[False,True,False],
             anchor_step=[-1,0,-1], anchor_temporal=[1.,2.,1.], anchor_complement=[1.,4.,1.],
             temporal_energy=[0.,2.,0.], complement_energy=[0.,4.,0.],
             normalized_temporal=[0.,.5,0.], normalized_complement=[0.,.5,0.],
             quadratic_diagonal=[0.,2.5,0.], quadratic_rhs=[0.,.625,0.], edge_weights=[0.,0.],
             segments=[dict(interval_half_open=[1,2],converged=True,iterations=1,iteration_limit=20)] if active else [])
    return dict(forward=step,block=block,applied=True,finite_output=True,attention_calls=5,
                alpha=[.25]*3,bin_energy=[2.,3.,5.],correction_energy=10.,applied_energy=.625,control=c)


def document():
    return dict(schema='h3-temporal-gain-field-v1',status='sampling',started_calls=1000,completed_calls=1000,
                native_override_calls=1000,routed_calls=1000,completed_forward_calls=20,
                calls_by_forward=[50]*20,routed_by_forward=[50]*20,calls_by_block=[20]*50,routed_by_block=[20]*50,
                step_interval_half_open=[0,20],block_interval_half_open=[0,50],
                feature_config=dict(mode='gain_field',alpha_prior=.25,
                alpha_max=.5,probes=8,basis='centered',smoothness=.625,prior_weight=1.),
                full_dit_forward_calls_added=0,intermediate_vae_decode_calls=0,
                feature_forward_summaries=[dict(forward=s,layers=[layer(s,b) for b in range(50)]) for s in range(20)])


class AuditTests(unittest.TestCase):
    def test_valid_twenty_by_fifty_trace(self):
        r=check_field(document());self.assertEqual(r['blocks'],1000);self.assertEqual(r['created_bin_anchors'],50)
    def test_wrong_dose_rejected(self):
        r=layer();r['applied_energy']=.626
        with self.assertRaises(FieldAuditError):check_layer(r)
    def test_fake_solver_success_rejected_by_independent_kkt(self):
        r=layer();r['alpha'][1]=r['control']['alpha'][1]=.4
        r['applied_energy']=sum(a*a*e for a,e in zip(r['alpha'],r['bin_energy']))
        with self.assertRaisesRegex(FieldAuditError,'KKT'):check_layer(r)
    def test_false_energy_normalization_rejected(self):
        r=layer();r['control']['temporal_energy'][1]=4.
        with self.assertRaisesRegex(FieldAuditError,'inconsistent'):check_layer(r)
    def test_overwritten_anchor_rejected_even_when_ratio_unchanged(self):
        d=document();c=d['feature_forward_summaries'][9]['layers'][6]['control']
        c['anchor_temporal'][1]=4.;c['anchor_complement'][1]=8.
        with self.assertRaisesRegex(FieldAuditError,'overwritten'):check_field(d)
    def test_applied_and_reported_alpha_must_match(self):
        r=layer();r['control']['alpha'][1]=.3
        with self.assertRaisesRegex(FieldAuditError,'differs'):check_layer(r)
    def test_failed_solver_is_counted_and_uses_prior(self):
        r=layer();r['control']['segments'][0]['converged']=False
        r['control']['solver_succeeded'][1]=False;r['control']['fallback_to_prior'][1]=True
        self.assertEqual(check_layer(r)['solver_failures'],1)
    def test_unsupported_smoothing_edge_rejected(self):
        r=layer();r['control']['edge_weights'][0]=1.
        with self.assertRaisesRegex(FieldAuditError,'edge'):check_layer(r)
    def test_duplicate_layer_rejected(self):
        d=document();d['feature_forward_summaries'][3]['layers'][2]['block']=1
        with self.assertRaises(FieldAuditError):check_field(d)
    def test_nonfinite_rejected(self):
        r=layer();r['alpha'][1]=float('nan')
        with self.assertRaises(FieldAuditError):check_layer(r)
    def test_real_execution_counts_required(self):
        for key in ('started_calls','completed_calls','native_override_calls','routed_calls'):
            d=document();d[key]=999
            with self.assertRaises(FieldAuditError):check_field(d)


if __name__=='__main__':unittest.main()
