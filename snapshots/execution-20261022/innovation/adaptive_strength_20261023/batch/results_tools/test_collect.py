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


class CollectorTests(unittest.TestCase):
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
