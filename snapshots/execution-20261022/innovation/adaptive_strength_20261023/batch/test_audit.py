"""Synthetic-only audit contracts. No model, remote host, or real run evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from audit import AuditError, check_feature, check_coverage_blend


def common(steps=2, blocks=3):
    return {'synthetic_test_only': True, 'status': 'sampling',
            'completed_forward_calls': steps, 'started_calls': steps*blocks,
            'completed_calls': steps*blocks, 'native_override_calls': steps*blocks,
            'calls_by_forward': [blocks]*steps, 'calls_by_block': [steps]*blocks,
            'step_interval_half_open': [0,steps], 'block_interval_half_open': [0,blocks],
            'routed_calls': steps*blocks, 'routed_by_forward': [blocks]*steps,
            'routed_by_block': [steps]*blocks, 'alpha': .25,
            'forward_summaries': [{'forward_index': n, 'completed_blocks': blocks,
                                   'routed_blocks': blocks} for n in range(steps)]}


def feature(mode='dynamic_strength_dof', steps=2, blocks=3):
    a = common(steps, blocks)
    a.update(schema='h3-feature-guidance-v1', full_dit_forward_calls_added=0,
             intermediate_vae_decode_calls=0, effective_collateral=3.,
             feature_config={'mode': mode, 'alpha_prior': .25, 'alpha_max': .5,
                             'prior_weight': 1., 'collateral': 1., 'basis': 'centered'},
             feature_forward_summaries=[])
    for n in range(steps):
        rows=[]
        for b in range(blocks):
            c={'alpha': .25, 'fallback': False, 'valid_probe_count': 8,
               'temporal_energy': 1., 'complement_energy': 3., 'total_energy': 4.,
               'objective_at_prior': .75, 'objective_at_selected': .75,
               'temporal_variance': 1., 'complement_variance': 1., 'overall_variance': 1.,
               'feature_dimension': 4, 'basis': 'centered',
               'calibration': 'equal_variance_per_degree_of_freedom'}
            row={'block': b, 'forward': n, 'mode': mode, 'applied': True,
                 'attention_calls': 5, 'finite_output': True, 'alpha': [.25,.25],
                 'alpha_mean': .25, 'alpha_min': .25, 'alpha_max': .25,
                 'head_energy': [2.,2.], 'correction_energy': 4., 'applied_energy': .25,
                 'reference_mass_mean': .4, 'controller_host_dispatch_seconds': .001,
                 'control': c}
            if mode == 'fixed':
                row.update(control={}, attention_calls=3)
            elif mode == 'heads_budget':
                row.update(alpha=[.5,0.], alpha_min=0., alpha_max=.5, head_energy=[1.,3.])
                row['control']={'alpha': [.5,0.], 'fallback': False,
                    'exact_full_correction_budget': True, 'requested_energy': .25,
                    'allocated_energy': .25, 'energy_error': 0., 'utility': .5,
                    'uniform_utility': .25}
            rows.append(row)
        a['feature_forward_summaries'].append({'forward': n, 'layers': rows})
    return a


def coverage(steps=2, blocks=3):
    a=common(steps, blocks)
    a.update(schema='h3-temporal-coverage-blend', coverage_config={
        'coverage_mix': .25, 'solver': 'damped_newton_cpu_float64',
        'fallback_policy': 'same_time_weak', 'iterations': 64, 'tolerance': .0002},
        coverage_calls=[], coverage_solved_calls=steps*blocks-1,
        same_time_fallback_calls=1, solver_wall_seconds=steps*blocks*.01)
    for n in range(steps):
        a['forward_summaries'][n].update(sampled_finite=True, layer_stats=[])
        for b in range(blocks):
            fallback=(n,b)==(steps-1, blocks-1)
            a['coverage_calls'].append({'forward': n, 'block': b, 'applied': True,
                'coverage_mix': .25, 'mean_diagonal_probability': 1. if fallback else .8,
                'min_diagonal_probability': 1. if fallback else .76,
                'solver_iterations': 3, 'solver_seconds': .01, 'row_error': 1e-5,
                'column_error': 1e-5, 'routing_solved': not fallback,
                'reason': 'same_time_fallback' if fallback else 'solved',
                'fallback_reason': 'low_signal' if fallback else None})
            a['forward_summaries'][n]['layer_stats'].append({'block':b, 'finite':True,'correction_ratio':.02})
    return a


class FeatureAuditTests(unittest.TestCase):
    def test_dof_curves_and_host_timing(self):
        result=check_feature(feature(),2,3)
        self.assertEqual(result['alpha'], {'mean':.25,'min':.25,'max':.25,'count':12})
        self.assertEqual(len(result['alpha_by_step']),2)
        self.assertEqual(len(result['alpha_by_layer']),3)
        self.assertAlmostEqual(result['controller_host_dispatch_seconds']['total'],.006)
        self.assertIn('not GPU',result['timing_scope'])

    def test_default_twenty_by_fifty(self):
        result=check_feature(feature(steps=20,blocks=50))
        self.assertEqual(result['routed_calls'],1000)

    def test_head_budget(self):
        result=check_feature(feature('heads_budget'),2,3)
        self.assertEqual(result['head_budget_relative_error']['max'],0)
        self.assertEqual(result['alpha']['max'],.5)

    def test_fixed_stronger_control(self):
        a=feature('fixed');a['alpha']=.375;a['feature_config']['alpha_prior']=.375
        for f in a['feature_forward_summaries']:
            for r in f['layers']:
                r.update(alpha=[.375,.375],alpha_mean=.375,alpha_min=.375,alpha_max=.375,
                         applied_energy=4*.375**2)
        self.assertEqual(check_feature(a,2,3)['alpha']['mean'],.375)

    def test_inactive_blocks_and_steps(self):
        a=feature();a['step_interval_half_open']=[0,1];a['block_interval_half_open']=[1,3]
        a.update(routed_calls=2,routed_by_forward=[2,0],routed_by_block=[0,1,1])
        for n,f in enumerate(a['feature_forward_summaries']):
            a['forward_summaries'][n]['routed_blocks']=2 if n==0 else 0
            for b,r in enumerate(f['layers']):
                if not (n==0 and b>=1):
                    f['layers'][b]={'block':b,'forward':n,'mode':'dynamic_strength_dof',
                                    'applied':False,'attention_calls':1}
        result=check_feature(a,2,3)
        self.assertEqual(result['alpha_by_step'][1]['count'],0)

    def test_zero_signal_fallback(self):
        a=feature()
        r=a['feature_forward_summaries'][0]['layers'][0]
        for k in ('temporal_energy','complement_energy','total_energy','temporal_variance',
                  'complement_variance','overall_variance','objective_at_prior','objective_at_selected'):
            r['control'][k]=0.
        r['control'].update(fallback=True,valid_probe_count=0)
        self.assertEqual(check_feature(a,2,3)['fallback_count'],1)

    def test_excluded_boundaries_can_have_no_valid_probes(self):
        a=feature();a['boundary_probes_excluded']=True
        for f in a['feature_forward_summaries']:
            for r in f['layers']:
                c=r['control']
                for key in ('temporal_energy','complement_energy','total_energy',
                            'temporal_variance','complement_variance','overall_variance',
                            'objective_at_prior','objective_at_selected'):
                    c[key]=0.
                c.update(fallback=True,valid_probe_count=0,boundary_probes_excluded=8)
        result=check_feature(a,2,3)
        self.assertIs(result['boundary_probes_excluded'],True)
        self.assertEqual(result['fallback_count'],6)
        self.assertEqual(len(result['boundary_exclusion_records']),6)

    def test_incomplete_or_bad_counters_rejected(self):
        for key,value in [('completed_forward_calls',1),('started_calls',7),('routed_calls',5),
                           ('calls_by_block',[2,2,1]),('routed_by_forward',[3,2])]:
            a=feature();a[key]=value
            with self.subTest(key=key),self.assertRaises(AuditError):check_feature(a,2,3)

    def test_bad_row_and_nonfinite_rejected(self):
        for key,value in [('finite_output',False),('alpha',[.6,.25]),('reference_mass_mean',float('nan')),
                           ('applied_energy',.3),('attention_calls',6),('block',2)]:
            a=feature();a['feature_forward_summaries'][0]['layers'][0][key]=value
            with self.subTest(key=key),self.assertRaises(AuditError):check_feature(a,2,3)

    def test_bad_dof_statistics_rejected(self):
        for key,value in [('temporal_variance',2.),('calibration','unknown'),('feature_dimension',1),
                           ('valid_probe_count',0),('alpha',.3),('objective_at_selected',2.)]:
            a=feature();a['feature_forward_summaries'][0]['layers'][0]['control'][key]=value
            with self.subTest(key=key),self.assertRaises(AuditError):check_feature(a,2,3)

    def test_head_budget_corruption_rejected(self):
        for key,value in [('allocated_energy',.3),('requested_energy',.3),('energy_error',.1),
                           ('exact_full_correction_budget',False)]:
            a=feature('heads_budget');a['feature_forward_summaries'][0]['layers'][0]['control'][key]=value
            with self.subTest(key=key),self.assertRaises(AuditError):check_feature(a,2,3)

    def test_missing_duplicate_layers_rejected(self):
        for drop in [True,False]:
            a=feature();rows=a['feature_forward_summaries'][0]['layers']
            if drop:rows.pop()
            else:rows[1]=copy.deepcopy(rows[0])
            with self.assertRaises(AuditError):check_feature(a,2,3)

    def test_malformed_nested_records_rejected(self):
        for key in ('feature_config','feature_forward_summaries','forward_summaries'):
            a=feature();a[key]=None
            with self.subTest(key=key),self.assertRaises(AuditError):check_feature(a,2,3)
        a=feature();a['feature_forward_summaries'][0]['layers'][0]=None
        with self.assertRaises(AuditError):check_feature(a,2,3)


class CoverageAuditTests(unittest.TestCase):
    def test_blend_solved_and_fallback(self):
        result=check_coverage_blend(coverage(),2,3)
        self.assertEqual(result['solved_calls'],5)
        self.assertEqual(result['same_time_fallback_calls'],1)
        self.assertEqual(result['diagonal_check_scope'],'every call minimum')

    def test_old_mean_only_audit_is_honest(self):
        a=coverage()
        for r in a['coverage_calls']:del r['min_diagonal_probability']
        self.assertIn('incompletely',check_coverage_blend(a,2,3)['diagonal_check_scope'])

    def test_bad_mix_minimum_and_solver_rejected(self):
        for key,value in [('coverage_mix',.5),('mean_diagonal_probability',.74),
                           ('min_diagonal_probability',.74),('row_error',.001),
                           ('solver_seconds',float('inf')),('routing_solved',False)]:
            a=coverage();a['coverage_calls'][0][key]=value
            with self.subTest(key=key),self.assertRaises(AuditError):check_coverage_blend(a,2,3)

    def test_missing_finite_evidence_rejected(self):
        a=coverage();a['forward_summaries'][0]['layer_stats'].pop()
        with self.assertRaises(AuditError):check_coverage_blend(a,2,3)


class CLITests(unittest.TestCase):
    def test_cli_valid_and_failed_exit(self):
        script=Path(__file__).with_name('audit.py')
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'synthetic_audit.json';src.write_text(json.dumps(feature()))
            command=[sys.executable,str(script),str(src),'--steps','2','--blocks','3']
            good=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(good.returncode,0,good.stderr)
            self.assertEqual(json.loads(good.stdout)['status'],'passed')
            src.write_text('[]')
            bad=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(bad.returncode,1)
            self.assertEqual(json.loads(bad.stderr)['status'],'failed')


if __name__=='__main__':
    unittest.main()
