import copy
import contextlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import build_reports as b


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.p = Path(self.t.name)
        self.c = dict(schema='ive-six-setting-report-v1', case_id=b.NEW, cohort='interval_short0177_20261024',
            title='fixture', prompt='fixture prompt', seed=1, geometry=dict(width=1312,height=736,sampled_frames=73,valid_frames=60,fps=24,crop_xywh=[16,8,1280,720]),
            display_summary='fixture summary', job_ids={r:'metric_'+r for r in b.ROLES}, inference_job_ids={r:'infer_'+r for r in b.METHODS},
            video_sha256={r:format(i,'064x') for i,r in enumerate(b.ROLES)},result_files={},router_files={},metrics_manifest='manifest.json',metrics_rows='metrics.json',annotation='annotation.json',presentation='PRESENTATION.json')
        for r in b.METHODS:
            result=dict(job_id='infer_'+r,attempt_id='infer_'+r+'__a1',metadata=dict(task_id=b.NEW,method=r,cohort=self.c['cohort'],seed=1,prompt='fixture prompt',valid_frames=60,fps=24),files=[dict(path=r+'.mp4',sha256=self.c['video_sha256'][r])])
            audit=dict(run_id=result['attempt_id'],completed_forward_calls=20,completed_calls=1000,calls_by_forward=[50]*20,schedule=r,step_set_zero_based=b.STEPS[r],routed_calls=len(b.STEPS[r])*50,routed_by_forward=[50 if i in b.STEPS[r] else 0 for i in range(20)],mode='native' if r=='native' else 'mass_preserve',alpha=.25 if r=='global_weak' else 1,pixel_interval_inclusive=[0,59],block_interval_half_open=[0,50])
            self.c['result_files'][r]='result_'+r+'.json';self.c['router_files'][r]='audit_'+r+'.json'
            b.write(self.p/self.c['result_files'][r],result);b.write(self.p/self.c['router_files'][r],audit)
        jobs=[dict(id='metric_'+r,task_id=b.NEW,method=r,cohort=self.c['cohort'],sha256=self.c['video_sha256'][r],valid_frames=60,fps=24,crop_xywh=[16,8,1280,720]) for r in b.ROLES]
        b.write(self.p/'manifest.json',dict(jobs=jobs))
        rows=[dict(job_id='metric_'+r,task_id=b.NEW,method=r,cohort=self.c['cohort'],metric=k,status='done',score=.8) for r in b.ROLES for k in b.NUMERIC]
        b.write(self.p/'metrics.json',dict(rows=rows))
        a=dict(case_id=b.NEW,fps=24,valid_frames=60,video_sha256=self.c['video_sha256'],review_completed=True,annotation_source='fixture',events=[dict(id='event',label='event',**{r:[10,12] for r in b.ROLES})])
        b.write(self.p/'annotation.json',a)
        for name in ['comparison.mp4','same_frame.jpg']:(self.p/name).write_bytes(b'fixture')
        pres=dict(task_id=b.NEW,roles=b.ROLES,valid_frames=60,full_decode_frames=60,fps=24,width=1920,height=1232,screenshot_frame=30,inputs={r:dict(job=self.c['job_ids'][r],sha256=self.c['video_sha256'][r]) for r in b.ROLES},files={name:b.sha(self.p/name) for name in ['comparison.mp4','same_frame.jpg']})
        b.write(self.p/'PRESENTATION.json',pres);self.path=self.p/'INPUT.json';b.write(self.path,self.c)

    def tearDown(self): self.t.cleanup()

    def test_complete_contract(self):
        self.assertEqual(b.validate(self.path)[4]['mean_absolute_offset']['native'],0)

    def test_old_cohort_rejected(self):
        p=self.p/'result_native.json';x=b.load(p);x['metadata']['cohort']='expansion';b.write(p,x)
        with self.assertRaisesRegex(ValueError,'cohort'):b.validate(self.path)

    def test_incomplete_forward_rejected(self):
        p=self.p/'audit_fixed.json';x=b.load(p);x['completed_forward_calls']=19;b.write(p,x)
        with self.assertRaisesRegex(ValueError,'20×50'):b.validate(self.path)

    def test_metric_video_mismatch_rejected(self):
        p=self.p/'manifest.json';x=b.load(p);x['jobs'][1]['sha256']='a'*64;b.write(p,x)
        with self.assertRaisesRegex(ValueError,'scored video'):b.validate(self.path)

    def test_missing_metric_rejected(self):
        p=self.p/'metrics.json';x=b.load(p);x['rows'].pop();b.write(p,x)
        with self.assertRaisesRegex(ValueError,'missing numeric'):b.validate(self.path)

    def test_all_old_cases_preserved_and_flex_separate(self):
        original=b.R150.read_text();data=b.augment(original,b.validate(self.path))
        self.assertEqual(len(data['cases']),15)
        self.assertEqual(sum(c['main_cohort'] for c in data['cases']),10)
        old=json.loads(b.re.search(r'<script id="data" type="application/json">(.*?)</script>',original,b.re.S).group(1))
        for before in old['cases']:
            after=next(c for c in data['cases'] if c['source_id']==before['source_id'])
            for key in ['overview','events','official_metrics','event_offsets','mean_absolute_offset']:
                self.assertEqual(after.get(key),before.get(key),(before['source_id'],key))
        flex=next(c for c in data['cases'] if c['source_id']==b.FLEX)
        self.assertFalse(flex['main_cohort']);self.assertEqual(flex['display_group'],'FlexiAct')
        self.assertEqual(data['metric_scopes']['main_IVEBench']['native']['motion_fidelity']['n_done'],10)
        rendered=b.render_r150(original,data)
        self.assertIn('IVEBench 10条混合子集',rendered)
        v11=b.V11.read_text();new=b.render_v11(v11,data,self.c)
        restored=b.re.sub('<!-- BEGIN IVE10 ADDITION 20261024 -->.*?<!-- END IVE10 ADDITION 20261024 -->','',new,flags=b.re.S)
        self.assertEqual(restored,v11)
        self.assertEqual(b.render_v11(new,data,self.c),new)

    def assert_zero_common_events(self, annotation):
        b.write(self.p/'annotation.json', annotation)
        validated=b.validate(self.path);measurement=validated[4]
        self.assertEqual(measurement['common_events'], [])
        self.assertEqual(measurement['mean_absolute_offset'], dict.fromkeys(b.ROLES))
        original=b.R150.read_text();data=b.augment(original,validated)
        previous=[c for c in data['cases'] if c['source_id'] in b.MAIN9 and all(isinstance(c['mean_absolute_offset'][r],(int,float)) for r in b.METHODS)]
        self.assertEqual(len(previous),6)
        expected={r:b.statistics.mean(c['mean_absolute_offset'][r] for c in previous) for r in b.ROLES}
        rendered=b.render_r150(original,data)
        script=b.re.search(r'<script>\s*([\s\S]*?)</script>',rendered).group(1)
        payload=copy.deepcopy(data)
        for case in payload['cases']:case.pop('overview',None)
        js="""const fs=require('fs'),vm=require('vm');
const p=JSON.parse(fs.readFileSync(0,'utf8'));
const elements={data:{textContent:JSON.stringify(p.data)},outcomes:{innerHTML:''},'metric-scope':{value:'main_IVEBench'}};
const context={document:{getElementById:id=>elements[id]}};vm.createContext(context);
vm.runInContext(p.script.slice(0,p.script.lastIndexOf('outcomeTable();')),context);
const summary=vm.runInContext("actionOffsetSummary(D.cases,'main_IVEBench')",context);
const empty=vm.runInContext("actionOffsetSummary([D.cases[0]],'main_IVEBench')",context);
const table=vm.runInContext('table(D.cases[0])',context);
const oldNullTable=vm.runInContext("table({...D.cases[0],cohort:'legacy'})",context);vm.runInContext('outcomeTable()',context);
process.stdout.write(JSON.stringify({summary,empty,table,oldNullTable,outcomes:elements.outcomes.innerHTML}));"""
        output=subprocess.run(['node','-e',js],input=json.dumps(dict(script=script,data=payload)),text=True,capture_output=True,check=True)
        display=json.loads(output.stdout)
        self.assertEqual((display['summary']['count'],display['summary']['total']),(6,10))
        for role in b.ROLES:self.assertAlmostEqual(display['summary']['means'][role],expected[role])
        self.assertEqual(display['empty']['means'],dict.fromkeys(b.ROLES))
        self.assertIn('自定义 · 6/10组',display['outcomes'])
        self.assertIn('自定义动作偏移采用6/10组',display['outcomes'])
        self.assertIn('可定位事件数',display['table'])
        self.assertIn('动作未出现',display['table'])
        self.assertIn('平均绝对偏移 ↓',display['table'])
        self.assertEqual(display['table'].count('<td>无共同事件</td>'),7)
        self.assertNotIn('平均绝对偏移 ↓',display['oldNullTable'])
        self.assertNotIn('无共同事件',display['oldNullTable'])
        for role in b.ROLES:self.assertIn(f"<td>{measurement['coverage'][role]}/2</td>",display['table'])
        self.assertNotIn('NaN',display['outcomes']);self.assertNotIn('undefined',display['table'])
        v11=b.render_v11(b.V11.read_text(),data,self.c)
        self.assertEqual(v11.count('无共同可定位事件'),6)
        # Exercise the actual staging summary without touching either published file.
        stage=self.p/'report';stage.mkdir()
        shutil.copyfile(b.ROOT/'showcase_template.html',stage/'showcase_template.html')
        with patch.object(b,'ROOT',stage),contextlib.redirect_stdout(io.StringIO()):b.build(self.path)
        summary=b.load(stage/'staging/ACTION_OFFSET_SUMMARY.json')['scopes']['main_IVEBench']
        self.assertEqual((summary['measured'],summary['checked']),(6,10))
        self.assertNotIn(b.NEW,summary['case_ids'])
        for role in b.ROLES:self.assertAlmostEqual(summary['means'][role],expected[role])
        return measurement

    def test_missing_native_events_keep_mae_null_and_six_of_ten_denominator(self):
        annotation=b.load(self.p/'annotation.json')
        annotation['events']=[dict(id='event_'+str(i),label='event',**{r:[10+i*20,12+i*20] for r in b.ROLES}) for i in range(2)]
        for event in annotation['events']:
            event['native']=None;event['status_by_role']={'native':'missing_action'}
        measured=self.assert_zero_common_events(annotation)
        self.assertEqual(measured['coverage']['native'],0)
        self.assertEqual(measured['coverage']['global_weak'],2)
        self.assertEqual(measured['available_event_means']['global_weak'],0)
        self.assertIsNone(measured['mean_absolute_offset']['global_weak'])

    def test_disjoint_visible_events_do_not_become_paired_mae(self):
        annotation=b.load(self.p/'annotation.json')
        annotation['events']=[dict(id='event_'+str(i),label='event',source=[10+i*20,12+i*20],status_by_role={}) for i in range(2)]
        for index,role in enumerate(b.METHODS):
            for i,event in enumerate(annotation['events']):
                event[role]=[11+i*20,13+i*20] if index%2==i else None
                if event[role] is None:event['status_by_role'][role]='missing_action'
        measured=self.assert_zero_common_events(annotation)
        for role in b.METHODS:
            self.assertEqual(measured['coverage'][role],1)
            self.assertEqual(measured['available_event_means'][role],1)
            self.assertIsNone(measured['mean_absolute_offset'][role])


if __name__=='__main__':unittest.main()
