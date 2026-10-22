"""Synthetic-only collector tests; all fixtures live in temporary directories."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import collect
import remote_probe
import test_audit
import test_summarize
import test_field_audit
import test_layer_audit
import test_paired_cohorts


def uniform_document():
    """Synthetic old-field proof augmented by a separately checkable RMS."""
    doc = test_field_audit.document()
    doc.update(run_id='uniform__a1', schema='h3-temporal-gain-field-uniform-energy-v1',
               independent_field_trajectory_energy_matched=False)
    doc['feature_config']['mode'] = 'gain_field_uniform_energy'
    for forward in doc['feature_forward_summaries']:
        for row in forward['layers']:
            a, e, mask = row['alpha'], row['bin_energy'], row['control']['solver_succeeded']
            denominator = sum(x for x, selected in zip(e, mask) if selected)
            selected = sum(x*y*y for x, y, active in zip(e, a, mask) if active)
            total = sum(x*y*y for x, y in zip(e, a))
            row.update(candidate_alpha=a[:], alpha_mean=.25, alpha_min=.25, alpha_max=.25,
                uniform_energy=dict(modifiable_mask=mask[:], uniform_alpha=.25,
                    candidate_alpha=a[:], applied_alpha=a[:], modifiable_energy=denominator,
                    candidate_modifiable_energy=selected, applied_modifiable_energy=selected,
                    candidate_total_energy=total, applied_total_energy=total,
                    energy_error=0., energy_relative_error=0., energy_floor=2**-126,
                    near_zero_energy_fallback=(denominator == 0), no_modifiable_bins=not any(mask),
                    accumulation_dtype='float64', applied_dtype='torch.float32'))
    return doc


def fixed_budget_document():
    """Synthetic constant-QP proof; no actual inference result is fabricated."""
    doc = test_field_audit.document()
    doc.update(run_id='budget__a1', schema='h3-temporal-gain-field-fixed-budget-v1',
               independent_field_trajectory_energy_matched=False)
    doc['feature_config']['mode'] = 'gain_field_fixed_budget'
    for forward in doc['feature_forward_summaries']:
        for row in forward['layers']:
            a, e, mask = row['alpha'], row['bin_energy'], row['control']['solver_succeeded']
            selected = sum(x for x, m in zip(e, mask) if m); total = sum(e); active = any(mask)
            row.update(candidate_alpha=a[:], alpha_mean=.25, alpha_min=.25, alpha_max=.25,
                fixed_budget=dict(modifiable_mask=mask[:], candidate_alpha=a[:], applied_alpha=a[:],
                    energy_floor=2**-126, applied_dtype='torch.float32', accumulation_dtype='float64',
                    fallback_reason=None if active else 'no_modifiable_bins', fallback_to_prior=not active,
                    no_modifiable_bins=not active, normalized_positive_support_capacity=.25 if active else 0.,
                    normalized_target=.0625, zero_candidate_with_positive_energy=0,
                    solver='uncapped_closed_form' if active else 'fixed_prior_fallback', iterations=0,
                    log_scale=0. if active else None, scale=1. if active else None,
                    scale_representation='float64', normalized_solver_residual=0.,
                    cap_mask=[False]*len(a), modifiable_energy=selected, source_total_energy=total,
                    target_modifiable_energy=.0625*selected, target_total_energy=.0625*total,
                    candidate_modifiable_energy=.0625*selected, candidate_total_energy=.0625*total,
                    applied_modifiable_energy=.0625*selected, applied_total_energy=.0625*total,
                    energy_error=0., energy_relative_error=0.))
    return doc


class CollectorTests(unittest.TestCase):
    def test_fixed_budget_complete_requires_result_and_media(self):
        doc=fixed_budget_document();self.assertEqual(collect.check_live(doc),[])
        plan={'id':'budget','metadata':{'task_id':'test_case','method':'temporal_gain_field_fixed_budget'}}
        row={'actual_attempt_id':'budget__a1','audit':{'data':doc}}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertEqual(collect.inspect_row(plan,{},'synthetic',root)['status'],'pending')
            self.assertEqual(collect.inspect_row(plan,row,'synthetic',root)['status'],'in_progress')
            row['result']={'data':{'job_id':'budget','attempt_id':'budget__a1'}}
            self.assertEqual(collect.inspect_row(plan,row,'synthetic',root)['status'],'attention_required')
            row['media']=[{'status':'verified'}]
            result=collect.inspect_row(plan,row,'synthetic',root)
        self.assertEqual(result['status'],'verified')
        self.assertTrue(result['complete_audit']['applied_fixed_budget_verified'])
        self.assertEqual(result['complete_audit']['budget_fallbacks'],50)
        self.assertEqual(result['live_alpha_statistics']['fallback_layer_fraction'],.05)

    def test_fixed_budget_partial_curve_separates_candidate_and_actual(self):
        doc=fixed_budget_document();doc['feature_forward_summaries']=doc['feature_forward_summaries'][:2]
        doc['completed_forward_calls']=2
        plan={'id':'budget','metadata':{'task_id':'test_case','method':'temporal_gain_field_fixed_budget'}}
        row={'actual_attempt_id':'budget__a1','audit':{'data':doc},'queue_state':{'status':'running'}}
        with tempfile.TemporaryDirectory() as tmp:
            result=collect.inspect_row(plan,row,'synthetic',Path(tmp))
        self.assertEqual(result['status'],'in_progress');self.assertNotIn('complete_audit',result)
        probe=doc['feature_forward_summaries'][1]['layers'][0]
        probe['candidate_alpha']=[.25,.4,.25];probe['alpha']=[.25,.25,.25]
        point=collect.curves(doc)['points'][50]
        self.assertEqual(point['candidate_alpha'],[.25,.4,.25])
        self.assertEqual(point['alpha'],[.25,.25,.25]);self.assertEqual(point['alpha_mean'],.25)
        self.assertEqual(point['bin_energy'],probe['bin_energy'])
        self.assertEqual(point['fixed_budget'],probe['fixed_budget'])
        self.assertIn('candidate_alpha only',point['qp_scope'])

    def test_fixed_budget_schema_mode_and_target_fail_closed(self):
        plan={'id':'budget','metadata':{'task_id':'test_case','method':'temporal_gain_field_fixed_budget'}}
        for fault in ('schema','mode','target','future_claim'):
            doc=fixed_budget_document()
            if fault=='schema':doc['schema']='h3-temporal-gain-field-v1'
            elif fault=='mode':doc['feature_config']['mode']='gain_field'
            elif fault=='target':doc['feature_forward_summaries'][1]['layers'][0]['fixed_budget']['target_total_energy']*=2
            else:doc['independent_field_trajectory_energy_matched']=True
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as tmp:
                out=collect.inspect_row(plan,{'actual_attempt_id':'budget__a1','audit':{'data':doc}},'synthetic',Path(tmp))
                self.assertEqual(out['status'],'attention_required')

    def test_fixed_budget_overflow_is_an_issue_not_collector_crash(self):
        doc=fixed_budget_document();row=doc['feature_forward_summaries'][1]['layers'][0]
        row['bin_energy']=[1e308]*3
        self.assertTrue(collect.check_live(doc))
        row['bin_energy']=[float('nan'),1.,1.]
        self.assertTrue(collect.check_live(doc))

    def test_fixed_budget_remote_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('queue_state','graphs','audit/feature_gain_field_fixed_budget'):(root/name).mkdir(parents=True)
            job={'id':'budget','graph':'graphs/b.json','metadata':{'method':'temporal_gain_field_fixed_budget'}}
            (root/'jobs.json').write_text(json.dumps({'jobs':[job]}))
            (root/'queue_state/state.json').write_text(json.dumps({'jobs':{'budget':{'attempts':1}}}))
            (root/'graphs/b.json').write_text('{}')
            (root/'audit/feature_gain_field_fixed_budget/budget__a1.json').write_text('{"synthetic_test_only":true}')
            row=remote_probe.inference({'run_root':str(root),'jobs':[job]})['jobs'][0]
        self.assertEqual(row['audit']['status'],'read')
        self.assertIn('/feature_gain_field_fixed_budget/',row['audit']['path'])

    def test_fixed_budget_four_cases_keep_two_cohorts_and_pending_denominator(self):
        args=test_paired_cohorts.fixture();method='temporal_gain_field_fixed_budget'
        for row in args[0]['jobs']+args[1]['cases']:row['method']=method
        for v in args[4].values():v['annotation']['method']=method;v['provenance']['method']=method
        report=test_paired_cohorts.mod.summarize(*args)
        first=report['cohorts']['original_pilots']['methods'][method]
        extension=report['cohorts']['book_handkerchief_extension']['methods'][method]
        self.assertEqual(first['mean_absolute_event_offset_frames']['complete_mean'],3.)
        self.assertEqual(extension['mean_absolute_event_offset_frames']['complete_mean'],35.)
        args[0]['jobs'][3]['status']='pending'
        report=test_paired_cohorts.mod.summarize(*args)
        first=report['cohorts']['original_pilots']['methods'][method]['metrics']['motion_fidelity']
        extension=report['cohorts']['book_handkerchief_extension']['methods'][method]['metrics']['motion_fidelity']
        self.assertEqual(first['n_done'],2);self.assertIsNotNone(first['complete_mean'])
        self.assertEqual((extension['n_done'],extension['n_expected']),(1,2))
        self.assertIsNone(extension['complete_mean']);self.assertIsNotNone(extension['partial_mean'])

    def test_fixed_budget_new_owner_does_not_take_old_case_jobs(self):
        jobs={'jobs':[{'id':i,'metadata':{'task_id':t}} for i,t in
                      [('old_a','a'),('old_b','b'),('budget_a','a'),('budget_b','b'),('budget_c','c'),('budget_d','d')]]}
        sources={'sources':[{'name':'oldhost','task_id':'a','exclude_job_ids':['budget_a']},
                   {'name':'oldhost_b','task_id':'b','exclude_job_ids':['budget_b']},
                   {'name':'newhost','job_ids':['budget_a','budget_b','budget_c','budget_d']}]}
        owners=collect.assign_sources(jobs,sources)
        self.assertEqual(owners['old_a'],'oldhost');self.assertEqual(owners['old_b'],'oldhost_b')
        self.assertEqual(sum(x=='newhost' for x in owners.values()),4)
        sources['sources'][0]['exclude_job_ids']=[]
        with self.assertRaisesRegex(ValueError,'duplicate producer'):collect.assign_sources(jobs,sources)

    def test_uniform_full_trace_and_candidate_applied_audit(self):
        doc = uniform_document()
        self.assertEqual(collect.check_live(doc), [])
        plan = {'id':'uniform','metadata':{'task_id':'test_case','method':'temporal_gain_field_uniform_energy'}}
        row = {'queue_state':{'status':'completed','attempts':1},'actual_attempt_id':'uniform__a1',
               'result':{'data':{'job_id':'uniform','attempt_id':'uniform__a1'}},
               'audit':{'data':doc},'media':[{'status':'verified'}]}
        with tempfile.TemporaryDirectory() as tmp:
            out = collect.inspect_row(plan,row,'synthetic',Path(tmp))
        self.assertEqual(out['status'],'verified')
        self.assertTrue(out['complete_audit']['candidate_qp_verified'])
        self.assertTrue(out['complete_audit']['applied_uniform_energy_verified'])
        self.assertEqual(out['complete_audit']['uniform_energy_fallbacks'],50)

    def test_uniform_partial_stays_in_progress_and_curves_use_applied(self):
        doc = uniform_document();doc['feature_forward_summaries'] = doc['feature_forward_summaries'][:2]
        doc['completed_forward_calls'] = 2
        plan = {'id':'uniform','metadata':{'task_id':'test_case','method':'temporal_gain_field_uniform_energy'}}
        row = {'queue_state':{'status':'running','attempts':1},'actual_attempt_id':'uniform__a1','audit':{'data':doc}}
        with tempfile.TemporaryDirectory() as tmp:
            out = collect.inspect_row(plan,row,'synthetic',Path(tmp))
        self.assertEqual(out['status'],'in_progress')
        self.assertNotIn('complete_audit',out)
        # Curve extraction itself preserves differing candidate/application vectors.
        probe = doc['feature_forward_summaries'][1]['layers'][0]
        probe['candidate_alpha'] = [.25,.12,.25]
        probe['alpha'] = [.25,.2,.25];probe['alpha_mean'] = sum(probe['alpha'])/3
        point = collect.curves(doc)['points'][50]
        self.assertEqual(point['alpha'],[.25,.2,.25])
        self.assertEqual(point['candidate_alpha'],[.25,.12,.25])
        self.assertEqual(point['alpha_mean'],sum(probe['alpha'])/3)
        self.assertIn('candidate_alpha only',point['qp_scope'])

    def test_uniform_schema_and_mode_cannot_be_substituted(self):
        plan = {'id':'uniform','metadata':{'task_id':'test_case','method':'temporal_gain_field_uniform_energy'}}
        for key in ('schema','mode'):
            doc = uniform_document()
            if key == 'schema':doc['schema'] = 'h3-temporal-gain-field-v1'
            else:doc['feature_config']['mode'] = 'gain_field'
            row = {'actual_attempt_id':'uniform__a1','audit':{'data':doc}}
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                out = collect.inspect_row(plan,row,'synthetic',Path(tmp))
                self.assertEqual(out['status'],'attention_required')

    def test_uniform_coherent_candidate_output_energy_forgery_rejected(self):
        doc = uniform_document();row = doc['feature_forward_summaries'][1]['layers'][0]
        a = [.25,.4,.25];u = row['uniform_energy'];e = row['bin_energy']
        row['alpha'] = a[:];row['candidate_alpha'] = a[:];row['control']['alpha'] = a[:]
        u['candidate_alpha'] = a[:];u['applied_alpha'] = a[:];u['uniform_alpha'] = .4
        total = sum(x*y*y for x,y in zip(e,a));selected = e[1]*a[1]**2
        u.update(candidate_modifiable_energy=selected,applied_modifiable_energy=selected,
                 candidate_total_energy=total,applied_total_energy=total)
        row['applied_energy'] = total
        self.assertTrue(any('KKT' in error for error in collect.check_live(doc)))
        doc = uniform_document()
        doc['feature_forward_summaries'][1]['layers'][0]['uniform_energy']['applied_modifiable_energy'] += 1
        self.assertTrue(any('modifiable energy' in error for error in collect.check_live(doc)))

    def test_uniform_remote_audit_path_uses_actual_isolated_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('queue_state','graphs','audit/feature_gain_field_uniform_energy'):
                (root/name).mkdir(parents=True)
            job = {'id':'uniform','graph':'graphs/u.json','metadata':{'method':'temporal_gain_field_uniform_energy'}}
            (root/'jobs.json').write_text(json.dumps({'jobs':[job]}))
            (root/'queue_state/state.json').write_text(json.dumps({'jobs':{'uniform':{'attempts':1}}}))
            (root/'graphs/u.json').write_text('{}')
            (root/'audit/feature_gain_field_uniform_energy/uniform__a1.json').write_text('{"synthetic_test_only":true}')
            row = remote_probe.inference({'run_root':str(root),'jobs':[job]})['jobs'][0]
        self.assertEqual(row['audit']['status'],'read')
        self.assertIn('/feature_gain_field_uniform_energy/',row['audit']['path'])

    def test_uniform_unique_owner_preserves_other_same_task_jobs(self):
        jobs = {'jobs':[{'id':jid,'metadata':{'task_id':task}} for jid,task in
                       [('old_air','a'),('old_drink','b'),('uniform_drink','b'),('uniform_air','a')]]}
        sources = {'sources':[{'name':'host41','task_id':'a','exclude_job_ids':['uniform_air']},
                   {'name':'host60','task_id':'b','exclude_job_ids':['uniform_drink']},
                   {'name':'host81_uniform','job_ids':['uniform_drink','uniform_air']}]}
        owners = collect.assign_sources(jobs,sources)
        self.assertEqual(owners,{'old_air':'host41','old_drink':'host60',
                                 'uniform_drink':'host81_uniform','uniform_air':'host81_uniform'})
        sources['sources'][1]['exclude_job_ids'] = []
        with self.assertRaisesRegex(ValueError,'duplicate producer'):
            collect.assign_sources(jobs,sources)

    def test_role5_method_requires_its_schema_and_valid_neighbor_evidence(self):
        doc=test_field_audit.document();doc['run_id']='role5__a1'
        doc['schema']='h3-temporal-gain-field-role5-v1'
        doc['shadow_schedule']={'steps':[0,9,19],'layers':[8,25,42]}
        for forward in doc['feature_forward_summaries']:
            for row in forward['layers']:
                n=len(row['alpha']);self.assertEqual(n,3)
                row.update(latent_bin_indices=list(range(n)),role5_mask=[False]*n,
                           neighbor_previous=[0,0,1],neighbor_following=[1,2,2],
                           shadow_attention_calls=0,seam_bin_indices=[],seam_statistics=[])
        self.assertEqual(collect.check_live(doc),[])
        plan={'id':'role5','metadata':{'task_id':'test_case','method':'temporal_gain_field_role5'}}
        row={'queue_state':{'status':'completed','attempts':1},'actual_attempt_id':'role5__a1',
             'result':{'data':{'job_id':'role5','attempt_id':'role5__a1'}},'audit':{'data':doc},
             'media':[{'status':'verified'}]}
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(collect.inspect_row(plan,row,'synthetic',Path(tmp))['status'],'verified')
            bad=copy.deepcopy(row);bad['audit']['data']['schema']='h3-temporal-gain-field-v1'
            self.assertEqual(collect.inspect_row(plan,bad,'synthetic',Path(tmp))['status'],'attention_required')
            bad=copy.deepcopy(row);bad['audit']['data']['feature_forward_summaries'][2]['layers'][0]['neighbor_previous'][1]=1
            self.assertEqual(collect.inspect_row(plan,bad,'synthetic',Path(tmp))['status'],'attention_required')

    def test_layer_full_trace_and_live_noncausal_failure(self):
        doc=test_layer_audit.synthetic_trace(steps=20,blocks=50);doc['run_id']='layer__a1'
        self.assertEqual(collect.check_live(doc),[])
        self.assertEqual(len(collect.curves(doc)['layer_budget_summaries']),20)
        plan={'id':'layer','metadata':{'task_id':'test_case','method':'causal_layer_budget'}}
        row={'queue_state':{'status':'completed','attempts':1},'actual_attempt_id':'layer__a1',
             'result':{'data':{'job_id':'layer','attempt_id':'layer__a1'}},'audit':{'data':doc},
             'media':[{'status':'verified'}]}
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(collect.inspect_row(plan,row,'synthetic',Path(tmp))['status'],'verified')
            doc['feature_forward_summaries'][3]['layers'][0]['plan_source_forward']=1
            bad=collect.inspect_row(plan,row,'synthetic',Path(tmp))
            self.assertEqual(bad['status'],'attention_required')
            self.assertTrue(any('noncausal' in x for x in bad['issues']))

    def test_explicit_single_job_transfer_preserves_other_task_jobs(self):
        jobs={'jobs':[{'id':i,'metadata':{'task_id':t}} for i,t in
                      [('air','a'),('drink_old','b'),('drink_new','b')]]}
        sources={'sources':[{'name':'host41','task_id':'a','job_ids':['drink_new']},
                            {'name':'host60','task_id':'b','exclude_job_ids':['drink_new']}]}
        self.assertEqual(collect.assign_sources(jobs,sources),
                         {'air':'host41','drink_old':'host60','drink_new':'host41'})
        sources['sources'][1]['exclude_job_ids']=[]
        with self.assertRaisesRegex(ValueError,'duplicate producer'):
            collect.assign_sources(jobs,sources)

    def test_explicit_selection_rejects_unknown_conflicting_and_stale_ownership(self):
        jobs={'jobs':[self.plan()]};source={'name':'host','task_id':'test_case'}
        for extra in ({'job_ids':['typo']},{'exclude_job_ids':['typo']},
                      {'job_ids':['example'],'exclude_job_ids':['example']}):
            with self.assertRaisesRegex(ValueError,'invalid explicit'):
                collect.assign_sources(jobs,{'sources':[dict(source,**extra)]})
        jobs['collection_plan']={'ownership':{'example':'old_host'}}
        with self.assertRaisesRegex(ValueError,'configured producers differ'):
            collect.assign_sources(jobs,{'sources':[source]})

    def test_field_live_curves_and_completed_audit(self):
        doc=test_field_audit.document();doc['run_id']='field__a1'
        self.assertEqual(collect.check_live(doc),[])
        curve=collect.curves(doc)
        self.assertEqual(len(curve['points']),1000)
        self.assertEqual(curve['points'][50]['anchor_temporal'],[1.,2.,1.])
        plan={'id':'field','metadata':{'task_id':'test_case','method':'temporal_gain_field'}}
        row={'queue_state':{'status':'completed','attempts':1},'actual_attempt_id':'field__a1',
             'result':{'data':{'job_id':'field','attempt_id':'field__a1'}},'audit':{'data':doc},
             'media':[{'status':'verified'}]}
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(collect.inspect_row(plan,row,'synthetic',Path(tmp))['status'],'verified')
            doc['feature_forward_summaries'][4]['layers'][0]['alpha'][1]=.3
            self.assertEqual(collect.inspect_row(plan,row,'synthetic',Path(tmp))['status'],'attention_required')

    def plan(self):
        return {'id':'example','metadata':{'task_id':'test_case','method':'dynamic_dof'}}

    def test_missing_evidence_stays_pending_without_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=collect.inspect_row(self.plan(),{},'synthetic',Path(tmp))
        self.assertEqual(result['status'],'pending')
        self.assertIsNone(result['actual_attempt_id'])
        self.assertIsNone(result['timing'])
        self.assertNotIn('complete_audit',result)

    def test_live_formula_and_nonfinite_anomalies(self):
        doc=test_audit.feature()
        self.assertEqual(collect.check_live(doc),[])
        bad=copy.deepcopy(doc)
        bad['feature_forward_summaries'][0]['layers'][0]['finite_output']=False
        self.assertTrue(any('nonfinite' in p for p in collect.check_live(bad)))
        bad=copy.deepcopy(doc)
        bad['feature_forward_summaries'][0]['layers'][0]['control']['alpha']=.4
        self.assertTrue(any('alpha' in p for p in collect.check_live(bad)))

    def test_curves_keep_actual_layer_step_head_values(self):
        curve=collect.curves(test_audit.feature())
        self.assertEqual(len(curve['points']),6)
        self.assertEqual(curve['points'][3]['step'],1)
        self.assertEqual(curve['points'][3]['layer'],0)
        self.assertEqual(curve['points'][3]['alpha'],[.25,.25])

    def test_complete_audit_requires_media_hash(self):
        row={'queue_state':{'status':'completed','attempts':1},'actual_attempt_id':'example__a1',
             'result':{'data':{'job_id':'example','attempt_id':'example__a1'}},
             'audit':{'data':test_audit.feature(steps=20,blocks=50)}}
        row['audit']['data']['run_id']='example__a1'
        with tempfile.TemporaryDirectory() as tmp:
            missing=collect.inspect_row(self.plan(),row,'synthetic',Path(tmp))
            row['media']=[{'status':'verified'}]
            ready=collect.inspect_row(self.plan(),row,'synthetic',Path(tmp))
        self.assertEqual(missing['status'],'attention_required')
        self.assertEqual(ready['status'],'verified')

    def test_wrong_attempt_or_mode_alerts_immediately(self):
        doc=test_audit.feature();doc['run_id']='wrong_attempt'
        row={'actual_attempt_id':'example__a1','audit':{'data':doc}}
        with tempfile.TemporaryDirectory() as tmp:
            wrong_id=collect.inspect_row(self.plan(),row,'synthetic',Path(tmp))
            doc['run_id']='example__a1';doc['feature_config']['mode']='fixed'
            wrong_mode=collect.inspect_row(self.plan(),row,'synthetic',Path(tmp))
        self.assertEqual(wrong_id['status'],'attention_required')
        self.assertTrue(any('planned method' in x for x in wrong_mode['issues']))

    def test_incremental_hydration_requires_matching_version(self):
        previous={'jobs':[{'audit':{'path':'p','version':[1,2],'data':{'a':1},'sha256':'abc'}}]}
        current={'jobs':[{'audit':{'path':'p','version':[1,2],'status':'unchanged'}}]}
        self.assertEqual(collect.hydrate(current,previous)['jobs'][0]['audit']['data'],{'a':1})
        current['jobs'][0]['audit']['version']=[1,3]
        with self.assertRaises(ValueError):collect.hydrate(current,previous)

    def test_probe_missing_changed_and_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'audit.json'
            self.assertEqual(remote_probe.read_json(path,{})['status'],'missing')
            path.write_text('{"synthetic_test_only":true}')
            first=remote_probe.read_json(path,{})
            again=remote_probe.read_json(path,{str(path):first['version']})
        self.assertEqual(first['status'],'read')
        self.assertEqual(again['status'],'unchanged')
        self.assertNotIn('data',again)

    def test_remote_probe_uses_actual_attempt_and_producer_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for folder in ['queue_state/results','graphs','audit/feature_guidance','audit/timing','output']:
                (root/folder).mkdir(parents=True)
            plan=dict(self.plan(),graph='graphs/example.json')
            (root/'jobs.json').write_text(json.dumps({'jobs':[plan]}))
            (root/'queue_state/state.json').write_text(json.dumps({'jobs':{'example':{
                'status':'submitted','attempts':2,'attempt_id':'example__a2','prompt_id':'pid'}}}))
            (root/'graphs/example.json').write_text('{}')
            (root/'audit/feature_guidance/example__a2.json').write_text('{"synthetic_test_only":true}')
            out=remote_probe.inference({'run_root':str(root),'jobs':[plan]})
            row=out['jobs'][0]
        self.assertEqual(row['actual_attempt_id'],'example__a2')
        self.assertTrue(row['audit']['path'].endswith('example__a2.json'))
        self.assertEqual(row['result']['status'],'missing')

    def test_merge_anchor_and_hold_preserves_canonical(self):
        base={'jobs':[self.plan()]};original=copy.deepcopy(base)
        anchor={'id':'anchor','graph':'graphs/anchor.json','metadata':{'task_id':'test_case','method':'dynamic_anchor'}}
        sources=[{'name':'owner','task_id':'test_case'}]
        hold={'job_id':'example','status':'research_hold_saturation_diagnostic','unsubmitted_verified':True}
        receipt={'status':'ready','owner_host':'owner','pilots':{'jobs':[anchor]}}
        combined=collect.merge_plans(base,[{'jobs':[anchor]}],[hold],[receipt],sources)
        self.assertEqual(base,original)
        self.assertEqual(len(combined['jobs']),2)
        self.assertEqual(combined['collection_plan']['holds'],['example'])
        self.assertEqual(combined['collection_plan']['ownership'],{'example':'owner','anchor':'owner'})
        self.assertEqual(combined['jobs'][0]['collection_hold']['status'],'research_hold')

    def test_duplicate_sources_receipts_and_methods_rejected(self):
        base={'jobs':[self.plan()]};source={'name':'one','task_id':'test_case'}
        with self.assertRaisesRegex(ValueError,'duplicate producer'):
            collect.assign_sources(base,{'sources':[source,dict(source,name='two')]})
        with self.assertRaisesRegex(ValueError,'duplicate extra'):
            collect.merge_plans(base,[base])
        alias=copy.deepcopy(self.plan());alias['id']='other'
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            collect.merge_plans(base,[{'jobs':[alias]}])
        anchor={'id':'anchor','metadata':{'task_id':'test_case','method':'dynamic_anchor'}}
        receipt={'status':'ready','owner_host':'wrong','pilots':{'jobs':[anchor]}}
        with self.assertRaisesRegex(ValueError,'owner differs'):
            collect.merge_plans(base,[{'jobs':[anchor]}],receipts=[receipt],sources=[source])
        with self.assertRaisesRegex(ValueError,'receipt coverage'):
            collect.merge_plans(base,[{'jobs':[anchor]}],receipts=[dict(receipt,pilots={'jobs':[]})],sources=[source])

    def test_research_hold_is_separate_and_conflicting_execution_alerts(self):
        plan=self.plan();plan['collection_hold']={'status':'research_hold','reason':'research_hold_saturation_diagnostic'}
        with tempfile.TemporaryDirectory() as tmp:
            held=collect.inspect_row(plan,{},'synthetic',Path(tmp))
            conflict=collect.inspect_row(plan,{'queue_state':{'status':'submitted'}},'synthetic',Path(tmp))
        self.assertEqual(held['status'],'research_hold');self.assertEqual(held['issues'],[])
        self.assertEqual(conflict['status'],'attention_required')

    def test_live_anchor_validates_prior_state_and_exports_energy_curve(self):
        doc=test_audit.anchored()
        self.assertEqual(collect.check_live(doc),[])
        points=collect.curves(doc)['points']
        self.assertEqual(points[0]['anchor_temporal'],2.)
        self.assertEqual(points[2]['temporal_energy'],4.)
        self.assertEqual(points[2]['anchor_step'],0)
        self.assertTrue(points[2]['used_anchor'])
        bad=copy.deepcopy(doc);bad['feature_forward_summaries'][1]['layers'][0]['control']['anchor_temporal']=4.
        self.assertTrue(any('anchor' in x for x in collect.check_live(bad)))
        offline=copy.deepcopy(doc);offline['offline_counterfactual']=True
        self.assertTrue(any('counterfactual' in x for x in collect.check_live(offline)))

    def test_complete_anchor_requires_real_result_audit_and_media(self):
        plan=self.plan();plan['metadata']['method']='dynamic_anchor'
        doc=test_audit.anchored(steps=20,blocks=50);doc['run_id']='example__a1'
        row={'actual_attempt_id':'example__a1','audit':{'data':doc},
             'result':{'data':{'job_id':'example','attempt_id':'example__a1'}},
             'media':[{'status':'verified'}]}
        with tempfile.TemporaryDirectory() as tmp:
            ready=collect.inspect_row(plan,row,'synthetic',Path(tmp))
        self.assertEqual(ready['status'],'verified')
        self.assertEqual(ready['complete_audit']['anchor_created_count'],50)

    def test_remote_probe_anchor_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('queue_state','graphs','audit/feature_anchor'):(root/name).mkdir(parents=True)
            plan=dict(self.plan(),graph='graphs/example.json');plan['metadata']['method']='dynamic_anchor'
            (root/'jobs.json').write_text(json.dumps({'jobs':[plan]}))
            (root/'queue_state/state.json').write_text(json.dumps({'jobs':{'example':{'attempts':1,'status':'submitted'}}}))
            (root/'graphs/example.json').write_text('{}')
            (root/'audit/feature_anchor/example__a1.json').write_text('{"synthetic_test_only":true}')
            row=remote_probe.inference({'run_root':str(root),'jobs':[plan]})['jobs'][0]
        self.assertEqual(row['audit']['status'],'read')
        self.assertIn('/feature_anchor/',row['audit']['path'])

    def test_metrics_use_only_completed_media_and_exclude_hold(self):
        plans,manifest,evaluation=test_summarize.fixtures(methods=('dynamic_dof','dynamic_anchor'))
        rows=[]
        for j in plans['jobs']:
            status='verified' if j['metadata']['task_id']=='a' else 'pending'
            if j['id']=='adapt_b_dynamic_dof':
                j['collection_hold']={'status':'research_hold','reason':'synthetic_hold'};status='research_hold'
            rows.append({'job_id':j['id'],'status':status,'reason':'synthetic'})
        scores=collect.completed_metrics(plans,rows,{'manifest':manifest,'evaluation':evaluation})
        self.assertEqual(scores['n_planned'],2)
        self.assertEqual(scores['methods']['dynamic_dof']['metrics']['motion_fidelity']['n_expected'],1)
        self.assertEqual(scores['collection_selection']['total_planned'],4)
        self.assertEqual(scores['collection_selection']['research_hold'],1)
        self.assertEqual(len(scores['collection_selection']['excluded']),2)
        self.assertEqual(scores['methods']['dynamic_anchor']['metrics']['motion_fidelity']['mean'],.8)

    def test_no_verified_media_does_not_reuse_existing_scores(self):
        plans,manifest,evaluation=test_summarize.fixtures()
        rows=[{'job_id':j['id'],'status':'pending','reason':'synthetic'} for j in plans['jobs']]
        scores=collect.completed_metrics(plans,rows,{'manifest':manifest,'evaluation':evaluation})
        self.assertEqual(scores['cases'],[]);self.assertEqual(scores['methods'],{})
        self.assertEqual(scores['n_planned'],0)


if __name__=='__main__':unittest.main()
