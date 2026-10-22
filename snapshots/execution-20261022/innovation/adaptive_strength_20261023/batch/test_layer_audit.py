"""Synthetic audit faults; test oracle uses bisection, not runtime active sets."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from layer_audit import LayerAuditError,check_layer_budget,check_allocation,check_calibration,measure


def allocation(u,e,valid):
    n=len(u);ids=[i for i in range(n) if valid[i]];a=[.25]*n
    target=.0625*sum(e[i] for i in ids);mult=None;iterations=0;scale=1.
    if not ids:reason='no_eligible_layers'
    elif len({u[i] for i in ids})==1:
        reason='uniform_quality_prior' if u[ids[0]] else 'zero_quality_prior'
    else:
        scale=max(e[i] for i in ids);iterations=1
        capacity=.25*sum(e[i] for i in ids if u[i]>0)
        if capacity<target:
            reason='positive_quality_cap_limited'
            for i in ids:a[i]=.5 if u[i] else 0.
            mult=1.
        else:
            reason='allocated';lo,hi=0.,1.
            def energy(c):return sum(e[i]*min(.5,c*u[i])**2 for i in ids)
            while energy(hi)<target:hi*=2
            for _ in range(120):
                mid=(lo+hi)/2
                if energy(mid)<target:lo=mid
                else:hi=mid
            mult=(lo+hi)/2
            for i in ids:a[i]=min(.5,mult*u[i])
    bm=measure([e[i] for i in ids],[a[i] for i in ids]);all_bm=measure(e,a)
    rec={'eligible':list(valid),'quality':list(u),'relative_energy':list(e),'alpha':list(a),
         'reason':reason,'iterations':iterations,'eligible_target':bm['baseline'],
         'eligible_assigned':bm['executed'],'eligible_budget_ratio':bm['ratio'],
         'all_target':all_bm['baseline'],'all_assigned':all_bm['executed'],
         'predicted_budget_ratio':all_bm['ratio'],'energy_normalization':scale,
         'waterfill_multiplier':mult}
    return a,rec


def synthetic_trace(steps=4,blocks=4):
    doc={'schema':'h3-causal-layer-budget-v1','status':'sampling','expected_sampling_steps':steps,
         'started_calls':steps*blocks,'completed_calls':steps*blocks,'native_override_calls':steps*blocks,
         'routed_calls':steps*blocks,'completed_forward_calls':steps,'calls_by_forward':[blocks]*steps,
         'routed_by_forward':[blocks]*steps,'calls_by_block':[steps]*blocks,'routed_by_block':[steps]*blocks,
         'step_interval_half_open':[0,steps],'block_interval_half_open':[0,blocks],
         'full_dit_forward_calls_added':0,'intermediate_vae_decode_calls':0,
         'current_step_exact_budget_conservation':False,
         'metric_scope':'previous-step pre-Wo local relative correction energy on selected output queries',
         'feature_config':{'mode':'layer_budget','alpha_prior':.25,'alpha_max':.5,'probes':8,'basis':'centered','relative_floor':1e-8},
         'first_attention':{'dtype':'torch.float64','heads':2},
         'feature_forward_summaries':[],'layer_budget_summaries':[],'forward_summaries':[]}
    plan=[.25]*blocks;previous=[0.]*blocks
    for step in range(steps):
        rows=[];actual=[];energies=[];quality=[];eligible=[]
        for block in range(blocks):
            raw=not(step==2 and block==1);low=step==3 and block==0
            a,b=(1.,1.) if step==0 else ((1/3,1.) if block%2==0 else (3.,1.))
            if low:a=b=1e-10
            if not raw:a=b=0.
            created=step==0;used=step>0 and raw and not low
            qu=.5 if created or not used else a/(a+b)
            eligible.append(created or used);quality.append(qu)
            d2=1.+block/10;o2=2.+step*(block+1)/10;e=d2/o2;energies.append(e)
            alpha=plan[block] if raw else .25;actual.append(alpha)
            cal={'temporal_energy':a,'complement_energy':b,'valid_probe_count':12 if raw else 0,
                 'inputs_valid':raw,'normalized_temporal':a/(a+b) if a+b else 0.,
                 'normalized_complement':b/(a+b) if a+b else 0.,'anchor_temporal':1.,'anchor_complement':1.,
                 'anchor_step':0,'anchor_created':created,'initialized':True,'used_anchor':used,
                 'fallback':not created and not used,'low_current_energy':low or not raw,
                 'effective_collateral':3.,'prior_weight':1.,'step_index':step,'layer_index':block}
            rows.append({'mode':'layer_budget','block':block,'forward':step,'plan_source_forward':step-1,
                'plan_for_forward':step,'applied':True,'finite_output':True,'attention_calls':5,
                'boundary_probes_excluded':True,'alpha':[alpha,alpha],'requested_alpha':plan[block],
                'alpha_mean':alpha,'alpha_min':alpha,'alpha_max':alpha,'head_energy':[d2/2,d2/2],
                'correction_energy':d2,'native_energy':o2,'applied_energy':d2*alpha**2,
                'relative_energy_valid':True,'relative_correction_energy':e,
                'raw_probe_evidence_valid':raw,'current_evidence_valid':raw,'local_fallback_to_prior':not raw,
                'quality_calibration':cal,'current_anchor_evidence_valid':created or used,
                'anchor_low_current_energy':low or not raw,'next_plan_eligible':created or used,
                'allocation_eligible':created or used,'allocation_quality':qu,'reference_mass_mean':.5,
                'controller_gpu_dispatch_seconds':.001})
        next_plan,alloc=allocation(quality,energies,eligible)
        doc['feature_forward_summaries'].append({'forward':step,'layers':rows})
        doc['forward_summaries'].append({'forward_index':step,'completed_blocks':blocks,'routed_blocks':blocks})
        doc['layer_budget_summaries'].append({'forward':step,'plan_source_forward':step-1,'plan_for_forward':step,
             'planned_alpha':plan[:],'actual_alpha':actual,'previous_relative_energy':previous[:],
             'current_relative_energy':energies,'current_quality':quality,'current_eligible':eligible,
             'predicted_plan_budget':measure(previous,plan),'predicted_executed_budget':measure(previous,actual),
             'current_actual_drift':measure(energies,actual),'next_plan_for_forward':step+1,'next_alpha':next_plan,
             'allocation':alloc,'statistics_transfer_seconds':.001,'waterfill_cpu_seconds':.001,
             'finish_controller_host_seconds':.002,'statistics_transfer_bytes':blocks*64})
        previous,plan=energies,next_plan
    return doc


class LayerAuditTests(unittest.TestCase):
    def check(self,d):return check_layer_budget(d,expected_steps=4,blocks=4)
    def reject(self,mutation):
        d=synthetic_trace();mutation(d)
        with self.assertRaises((LayerAuditError,KeyError,TypeError,ValueError)):self.check(d)
    def test_full_twenty_by_fifty(self):
        r=check_layer_budget(synthetic_trace(20,50));self.assertEqual(r['layer_calls'],1000)
        self.assertEqual(len(r['step_curves']),20);self.assertEqual(len(r['layer_alpha_mean']),50)
    def test_dynamic_fixture_current_drift_and_fallback(self):
        d=synthetic_trace();r=self.check(d);self.assertEqual(r['local_fallback_count'],1)
        self.assertGreater(r['alpha_max']-r['alpha_min'],.1)
        self.assertNotEqual(r['step_curves'][2]['executed_previous_metric_ratio'],r['step_curves'][2]['planned_previous_metric_ratio'])
        self.assertNotEqual(r['step_curves'][2]['current_actual_ratio'],1.)
    def test_low_anchor_signal_not_retroactive_fallback(self):
        d=synthetic_trace();r=d['feature_forward_summaries'][3]['layers'][0]
        self.assertTrue(r['anchor_low_current_energy']);self.assertFalse(r['local_fallback_to_prior'])
        self.assertNotEqual(r['alpha_mean'],.25);self.assertFalse(r['next_plan_eligible']);self.check(d)
    def test_counterfactual_and_failed_rejected(self):
        for k,v in [('status','failed'),('offline_counterfactual',True)]:self.reject(lambda d,k=k,v=v:d.update({k:v}))
    def test_incomplete_counts(self):self.reject(lambda d:d.update(completed_calls=15))
    def test_wrong_source_forward(self):self.reject(lambda d:d['layer_budget_summaries'][2].update(plan_source_forward=0))
    def test_duplicate_layer(self):self.reject(lambda d:d['feature_forward_summaries'][1]['layers'][1].update(block=0))
    def test_nonfinite_and_alpha_bound(self):
        for value in (float('nan'),float('inf'),.6):self.reject(lambda d,v=value:d['feature_forward_summaries'][2]['layers'][0]['alpha'].__setitem__(0,v))
    def test_head_scalar_mismatch(self):self.reject(lambda d:d['feature_forward_summaries'][2]['layers'][0]['alpha'].__setitem__(1,.2))
    def test_first_two_step_tamper(self):self.reject(lambda d:d['layer_budget_summaries'][1]['planned_alpha'].__setitem__(0,.3))
    def test_immutable_anchor(self):self.reject(lambda d:d['feature_forward_summaries'][2]['layers'][0]['quality_calibration'].update(anchor_temporal=2.))
    def test_normalized_quality_corrupted(self):self.reject(lambda d:d['feature_forward_summaries'][2]['layers'][0]['quality_calibration'].update(normalized_temporal=.4))
    def test_current_next_mask_conflation(self):self.reject(lambda d:d['feature_forward_summaries'][3]['layers'][0].update(local_fallback_to_prior=True))
    def test_actual_alpha_changed_without_request(self):self.reject(lambda d:d['feature_forward_summaries'][2]['layers'][1].update(requested_alpha=.25))
    def test_budget_value_corrupted(self):
        for key in ('predicted_plan_budget','predicted_executed_budget','current_actual_drift'):
            self.reject(lambda d,k=key:d['layer_budget_summaries'][2][k].update(ratio=1.234))
    def test_previous_energy_and_next_plan_continuity(self):
        self.reject(lambda d:d['layer_budget_summaries'][2]['previous_relative_energy'].__setitem__(0,4.))
        self.reject(lambda d:d['layer_budget_summaries'][2]['planned_alpha'].__setitem__(0,.25))
    def test_energy_applied_reduction(self):self.reject(lambda d:d['feature_forward_summaries'][2]['layers'][0].update(applied_energy=7.))
    def test_zero_previous_budget_is_null(self):
        d=synthetic_trace();self.assertIsNone(d['layer_budget_summaries'][0]['predicted_plan_budget']['ratio'])
        self.reject(lambda x:x['layer_budget_summaries'][0]['predicted_plan_budget'].update(ratio=0.))
    def test_unsupported_mask_and_config(self):
        self.reject(lambda d:d['feature_config'].update(alpha_prior=.3))
        self.reject(lambda d:d.update(current_step_exact_budget_conservation=True))
    def test_cap_and_zero_quality_degeneracy(self):
        for u,e,valid in [([1.,0.],[1.,100.],[True,True]),([0.,0.],[1.,2.],[True,True]),([.2,.8],[1.,2.],[False,False]),([.01,.1,.4,1.],[20.,20.,1.,.1],[True]*4)]:
            a,r=allocation(u,e,valid);check_allocation(r,u,e,valid,a)
    def test_feasible_but_wrong_direction_fails_kkt(self):
        u,e,v=[.2,.8],[1.,1.],[True,True];a,r=allocation(u,e,v);wrong=a[::-1];r['alpha']=wrong
        with self.assertRaisesRegex(LayerAuditError,'KKT|multiplier'):check_allocation(r,u,e,v,wrong)
    def test_unspent_positive_utility_rejected(self):
        u,e,v=[.2,.8],[1.,1.],[True,True];a,r=allocation(u,e,v);r['alpha']=[x/2 for x in a]
        bm=measure(e,r['alpha']);r.update(eligible_assigned=bm['executed'],all_assigned=bm['executed'],eligible_budget_ratio=bm['ratio'],predicted_budget_ratio=bm['ratio'])
        with self.assertRaisesRegex(LayerAuditError,'binding'):check_allocation(r,u,e,v,r['alpha'])
    def test_bad_branch_and_fabricated_cap_reason(self):
        u,e,v=[.2,.8],[1.,1.],[True,True];a,r=allocation(u,e,v);r['reason']='uniform_quality_prior'
        with self.assertRaises(LayerAuditError):check_allocation(r,u,e,v,a)
    def test_false_cap_limited_branch_rejected(self):
        u,e,v=[.2,.8],[1.,1.],[True,True];a,r=allocation(u,e,v);r['reason']='positive_quality_cap_limited'
        with self.assertRaisesRegex(LayerAuditError,'cap-limited'):check_allocation(r,u,e,v,a)
    def test_unidentifiable_initial_anchor_and_delayed_creation(self):
        c=synthetic_trace()['feature_forward_summaries'][0]['layers'][0]['quality_calibration']
        c.update(temporal_energy=1.,complement_energy=0.,normalized_temporal=1.,normalized_complement=0.,
                 anchor_temporal=0.,anchor_complement=0.,anchor_step=-1,anchor_created=False,initialized=False,
                 used_anchor=False,fallback=True,low_current_energy=False)
        state,eligible,quality,low=check_calibration(c,None,0,0,True,1e-8)
        self.assertIsNone(state);self.assertFalse(eligible);self.assertFalse(low)
        c.update(step_index=3,temporal_energy=2.,complement_energy=4.,normalized_temporal=.5,normalized_complement=.5,
                 anchor_temporal=2.,anchor_complement=4.,anchor_step=3,anchor_created=True,initialized=True,fallback=False)
        state,eligible,quality,low=check_calibration(c,None,3,0,True,1e-8)
        self.assertEqual(state,(2.,4.,3));self.assertTrue(eligible);self.assertEqual(quality,.5)
    def test_no_evidence_before_any_anchor(self):
        c=synthetic_trace()['feature_forward_summaries'][0]['layers'][0]['quality_calibration']
        c.update(temporal_energy=0.,complement_energy=0.,valid_probe_count=0,inputs_valid=False,
                 normalized_temporal=0.,normalized_complement=0.,anchor_temporal=0.,anchor_complement=0.,
                 anchor_step=-1,anchor_created=False,initialized=False,used_anchor=False,fallback=True,low_current_energy=True)
        state,eligible,_,low=check_calibration(c,None,0,0,False,1e-8)
        self.assertIsNone(state);self.assertFalse(eligible);self.assertTrue(low)
    def test_cli_stdin_success_and_failure_exit(self):
        cmd=[sys.executable,str(Path(__file__).with_name('layer_audit.py')),'-']
        good=subprocess.run(cmd,input=json.dumps(synthetic_trace(20,50)),text=True,capture_output=True)
        self.assertEqual(good.returncode,0,good.stderr);self.assertTrue(json.loads(good.stdout)['passed'])
        bad=subprocess.run(cmd,input='null',text=True,capture_output=True)
        self.assertEqual(bad.returncode,1);self.assertFalse(json.loads(bad.stdout)['passed'])
    def test_no_input_mutation(self):
        d=synthetic_trace();before=copy.deepcopy(d);self.check(d);self.assertEqual(d,before)


if __name__=='__main__':unittest.main()
