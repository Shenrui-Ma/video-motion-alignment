"""Small synthetic fixtures; these are not measured experiment results."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from summarize import COHORT, OFFICIAL_NINE, SummaryError, markdown, summarize


def fixtures(methods=('dynamic_dof',),tasks=('a','b')):
    plan={'jobs':[]};manifest={'jobs':[]};evaluation={'rows':[], 'means':{'must_be_ignored':999}}
    def row(job,metric,score):
        return {'job_id':job['id'],'task_id':job['task_id'],'dataset':job['dataset'],
                'method':job['method'],'cohort':job.get('cohort','main'),'metric':metric,
                'status':'done','score':score,'official_commit':'synthetic-fixture-only','evaluation_seed':0}
    for task in tasks:
        meta={'category':'subject_editing','subcategory':'replace existing subject'}
        for method in ('native','global_weak','source'):
            j={'id':task+'__'+method,'task_id':task,'dataset':'IVEBench','method':method,
               'metadata':dict(meta),'cohort':'main','sha256':'test-'+task+'-'+method}
            manifest['jobs'].append(j)
            for metric in OFFICIAL_NINE:
                value={'native':.6,'global_weak':.7,'source':.98}[method]
                evaluation['rows'].append(row(j,metric,value))
        for method in methods:
            jid='adapt_'+task+'_'+method
            plan['jobs'].append({'id':jid,'metadata':{'task_id':task,'benchmark':'IVEBench',
                'method':method,'cohort':COHORT,'title':task,'evaluation_metadata':dict(meta)}})
            j={'id':jid,'task_id':task,'dataset':'IVEBench','method':method,'metadata':dict(meta),'cohort':COHORT,
               'timing':{'sampling_seconds':40.,'sampling_step_seconds':[1.,3.],
                         'mean_sampling_step_seconds':2.,'scope':'current_without_x0_capture','host':'test-host'}}
            manifest['jobs'].append(j)
            for metric in OFFICIAL_NINE:evaluation['rows'].append(row(j,metric,.8 if task=='a' else .9))
    return plan,manifest,evaluation


class SummaryTests(unittest.TestCase):
    def test_full_pairing_and_measured_reference(self):
        report=summarize(*fixtures());g=report['methods']['dynamic_dof']
        self.assertEqual(report['n_planned'],2)
        mf=g['metrics']['motion_fidelity']
        self.assertAlmostEqual(mf['mean'],.85);self.assertEqual(mf['n_done'],2)
        pair=g['paired_against_controls']['motion_fidelity']
        self.assertEqual(pair['n_paired'],2)
        self.assertAlmostEqual(pair['mean_delta_from_global_weak'],.15)
        self.assertAlmostEqual(pair['method_means']['native'],.6)
        self.assertAlmostEqual(g['motion_fidelity_delta_from_reference']['mean'],-.13)

    def test_missing_result_keeps_planned_denominator(self):
        p,m,e=fixtures()
        m['jobs']=[j for j in m['jobs'] if j['id']!='adapt_b_dynamic_dof']
        e['rows']=[r for r in e['rows'] if r['job_id']!='adapt_b_dynamic_dof']
        r=summarize(p,m,e);g=r['methods']['dynamic_dof'];mf=g['metrics']['motion_fidelity']
        self.assertEqual((mf['n_expected'],mf['n_done'],mf['n_pending']),(2,1,1))
        self.assertEqual(r['n_registered'],1)
        self.assertEqual(g['paired_against_controls']['motion_fidelity']['n_paired'],1)
        self.assertEqual(g['timing']['n_sampling'],1)
        self.assertEqual(g['timing']['n_pending'],1)

    def test_metric_specific_paired_subset(self):
        p,m,e=fixtures()
        e['rows']=[r for r in e['rows'] if not(r['job_id']=='b__native' and r['metric']=='motion_fidelity')]
        g=summarize(p,m,e)['methods']['dynamic_dof']
        self.assertEqual(g['metrics']['motion_fidelity']['n_done'],2)
        q=g['paired_against_controls']['motion_fidelity']
        self.assertEqual((q['n_expected'],q['n_paired'],q['n_pending']),(2,1,1))
        self.assertAlmostEqual(q['method_means']['dynamic_dof'],.8)
        self.assertEqual(g['paired_against_controls']['semantic_fidelity']['n_paired'],2)

    def test_failed_not_applicable_and_pending_separated(self):
        p,m,e=fixtures(tasks=('a','b','c','d'))
        for r in e['rows']:
            if r['method']=='dynamic_dof' and r['metric']=='semantic_fidelity':
                if r['task_id']=='b':r.update(status='failed',score=None,error='synthetic failure')
                if r['task_id']=='c':r.update(status='not_applicable',score=None,reason='synthetic applicability')
                if r['task_id']=='d':r.update(status='running',score=None)
        x=summarize(p,m,e)['methods']['dynamic_dof']['metrics']['semantic_fidelity']
        self.assertEqual([x[k] for k in ('n_expected','n_done','n_failed','n_not_applicable','n_pending')],[4,1,1,1,1])
        self.assertEqual(x['n_applicable'],3)

    def test_official_motion_exclusion_without_score(self):
        p,m,e=fixtures(tasks=('a',))
        p['jobs'][0]['metadata']['evaluation_metadata']['category']='subject_motion_editing'
        for j in m['jobs']:j['metadata']['category']='subject_motion_editing'
        e['rows']=[r for r in e['rows'] if r['metric']!='motion_fidelity']
        g=summarize(p,m,e)['methods']['dynamic_dof']
        self.assertEqual(g['metrics']['motion_fidelity']['n_not_applicable'],1)
        self.assertEqual(g['paired_against_controls']['motion_fidelity']['n_paired'],0)

    def test_awq_two_pending_qa_separate(self):
        r=summarize(*fixtures());g=r['methods']['dynamic_dof']
        self.assertEqual(set(r['awq_metrics']),{'instruction_satisfaction','content_fidelity'})
        for v in g['awq_metrics'].values():
            self.assertIsNone(v['mean']);self.assertEqual(v['n_pending'],2)
        self.assertEqual(g['quantity_accuracy']['n_not_applicable'],2)
        self.assertEqual(len(g['metrics']),9)

    def test_actual_awq_rows_can_be_joined(self):
        p,m,e=fixtures(tasks=('a',))
        row=copy.deepcopy(next(r for r in e['rows'] if r['method']=='dynamic_dof'))
        row.update(metric='instruction_satisfaction',score=.42);e['rows'].append(row)
        self.assertEqual(summarize(p,m,e)['methods']['dynamic_dof']['awq_metrics']['instruction_satisfaction']['mean'],.42)

    def test_ambiguous_control_rejected(self):
        p,m,e=fixtures();j=copy.deepcopy(m['jobs'][0]);j['id']='second_native';m['jobs'].append(j)
        with self.assertRaisesRegex(SummaryError,'ambiguous'):summarize(p,m,e)

    def test_duplicate_metric_row_rejected(self):
        p,m,e=fixtures();e['rows'].append(copy.deepcopy(e['rows'][0]))
        with self.assertRaisesRegex(SummaryError,'duplicate'):summarize(p,m,e)

    def test_unregistered_alternative_result_rejected(self):
        p,m,e=fixtures();j=copy.deepcopy(e['rows'][0]);j['job_id']='old_native';e['rows'].append(j)
        with self.assertRaisesRegex(SummaryError,'ambiguous'):summarize(p,m,e)

    def test_bad_frozen_control_hash_rejected(self):
        p,m,e=fixtures();p['jobs'][0]['metadata']['comparison_outputs']={'native':{'sha256':'wrong'}}
        with self.assertRaisesRegex(SummaryError,'sha256'):summarize(p,m,e)

    def test_nan_or_done_with_wrong_identity_rejected(self):
        for change in ({'score':float('nan')},{'task_id':'other'}):
            p,m,e=fixtures();e['rows'][0].update(change)
            with self.subTest(change=change),self.assertRaises(SummaryError):summarize(p,m,e)

    def test_timings_measured_and_scope_preserved(self):
        p,m,e=fixtures()
        j=next(j for j in m['jobs'] if j['id']=='adapt_b_dynamic_dof')
        del j['timing']['mean_sampling_step_seconds']
        native=next(j for j in m['jobs'] if j['id']=='a__native')
        native['timing']={'sampling_seconds':100,'mean_sampling_step_seconds':5,
                         'scope':'historical_with_x0_capture','original_record':{'per_step_seconds':[4,6]}}
        r=summarize(p,m,e)
        self.assertEqual(r['cases'][1]['timing']['mean_step_seconds'],2.)
        self.assertEqual(r['cases'][0]['controls']['native']['timing']['scope'],'historical_with_x0_capture')
        self.assertEqual(r['cases'][0]['controls']['native']['timing']['per_step_seconds'],[4.,6.])
        self.assertEqual(r['methods']['dynamic_dof']['timing']['n_sampling'],2)

    def test_no_timing_estimate_and_no_old_aggregate(self):
        p,m,e=fixtures()
        for j in m['jobs']:j.pop('timing',None)
        r=summarize(p,m,e)
        self.assertIsNone(r['methods']['dynamic_dof']['timing']['mean_sampling_seconds'])
        self.assertNotIn('must_be_ignored',json.dumps(r))
        self.assertIn('MF-reference',markdown(r))

    def test_methods_keep_separate_expected_counts(self):
        p,m,e=fixtures(methods=('dynamic_dof','heads_budget'))
        p['jobs']=[j for j in p['jobs'] if j['id']!='adapt_b_heads_budget']
        m['jobs']=[j for j in m['jobs'] if j['id']!='adapt_b_heads_budget']
        e['rows']=[r for r in e['rows'] if r['job_id']!='adapt_b_heads_budget']
        groups=summarize(p,m,e)['methods']
        self.assertEqual(groups['dynamic_dof']['n_planned'],2)
        self.assertEqual(groups['heads_budget']['n_planned'],1)

    def test_cli_requires_explicit_summary_and_writes_reports(self):
        script=Path(__file__).with_name('summarize.py')
        missing=subprocess.run([sys.executable,str(script)],capture_output=True,text=True)
        self.assertNotEqual(missing.returncode,0)
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp);paths=[d/n for n in ('jobs.json','manifest.json','summary.json')]
            for path,data in zip(paths,fixtures()):path.write_text(json.dumps(data))
            out=d/'report.json';md=d/'report.md'
            cmd=[sys.executable,str(script),'--jobs',str(paths[0]),'--manifest',str(paths[1]),
                 '--summary',str(paths[2]),'--output',str(out),'--markdown',str(md)]
            p=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            report=json.loads(out.read_text());self.assertEqual(report['n_planned'],2)
            self.assertIn('sha256',report['inputs']['evaluation_summary'])
            self.assertTrue(md.read_text().startswith('# Adaptive'))


if __name__=='__main__':
    unittest.main()
