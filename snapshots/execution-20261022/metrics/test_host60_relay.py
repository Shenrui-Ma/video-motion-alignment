import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import watch_outputs as relay
class Host60Relay(unittest.TestCase):
 def test_preserves_previous_producers_and_adds_host60(self):
  self.assertEqual(len(relay.PRODUCERS),8)
  self.assertIn(('H3_HOST_SECONDARY','/home/research-user/h3_runs/adaptive_role5_20261023'),relay.PRODUCERS)
  self.assertIn(('H3_HOST_RTX4090','/data/research-user/h3_inference_20261023/run_uniform_energy'),relay.PRODUCERS)
  self.assertIn(('H3_HOST_AUXILIARY','/data4/research-user/h3_inference_20261023/run'),relay.PRODUCERS)
  self.assertEqual([h for h,p in relay.PRODUCERS[:3]],['H3_HOST_PRIMARY','H3_HOST_SECONDARY','H3_HOST_SECONDARY'])
 def test_canonical_jobs_keep_cohort_and_method(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=root/'innovation/adaptive_strength_20261023/batch/jobs.json';p.parent.mkdir(parents=True)
   jobs=[dict(id='adapt41_short_0358_'+m,metadata=dict(task_id='short_0358',benchmark='IVEBench',method=m,cohort='adaptive_research_20261023')) for m in ['fixed0375','dynamic_dof','heads_budget','coverage_blend25']]
   p.write_text(json.dumps({'jobs':jobs}))
   with patch.object(relay,'ROOT',root/'metrics'):rows=relay.expected_jobs({'jobs':[]})
   actual={x['id']:x for x in rows}
   for j in jobs:
    self.assertEqual(actual[j['id']]['cohort'],j['metadata']['cohort']);self.assertEqual(actual[j['id']]['method'],j['metadata']['method'])
   self.assertEqual(len(rows),5)
 def test_anchor_manifest_is_added_without_dropping_original(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);b=root/'innovation/adaptive_strength_20261023/batch';(b/'anchor_pilots').mkdir(parents=True)
   def job(method):return dict(id='adapt41_short_0358_'+method,metadata=dict(task_id='short_0358',benchmark='IVEBench',method=method,cohort='adaptive_research_20261023'))
   original=job('fixed0375');anchor=job('dynamic_anchor')
   (b/'jobs.json').write_text(json.dumps({'jobs':[original]}));(b/'anchor_pilots/jobs.json').write_text(json.dumps({'jobs':[anchor]}))
   with patch.object(relay,'ROOT',root/'metrics'):rows=relay.expected_jobs({'jobs':[]})
   ids=[x['id'] for x in rows]
   self.assertEqual(ids.count(original['id']),1);self.assertEqual(ids.count(anchor['id']),1)
   self.assertEqual(next(x['method'] for x in rows if x['id']==anchor['id']),'dynamic_anchor')
 def test_field_keeps_original_and_anchor(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);b=root/'innovation/adaptive_strength_20261023/batch'
   for child,method in [('', 'fixed0375'),('anchor_pilots','dynamic_anchor'),('field_pilots','temporal_gain_field'),('layer_pilots','causal_layer_budget')]:
    p=b/child/'jobs.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'jobs':[dict(id='job_'+method,metadata=dict(task_id='short_0252',benchmark='IVEBench',method=method,cohort='adaptive_research_20261023'))]}))
   with patch.object(relay,'ROOT',root/'metrics'):rows=relay.expected_jobs({'jobs':[]})
   self.assertEqual({r['method'] for r in rows},{'fixed0375','dynamic_anchor','temporal_gain_field','causal_layer_budget','source'})
 def test_field_extension_is_registered_once(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=root/'innovation/adaptive_strength_20261023/batch/field_extension_two/jobs.json';p.parent.mkdir(parents=True)
   j=dict(id='adapt41_long_0059_temporal_gain_field',metadata=dict(task_id='long_0059',benchmark='IVEBench',method='temporal_gain_field',cohort='adaptive_research_20261023'))
   p.write_text(json.dumps({'jobs':[j]}))
   with patch.object(relay,'ROOT',root/'metrics'):rows=relay.expected_jobs({'jobs':[]})
   self.assertEqual(sum(x['id']==j['id'] for x in rows),1)
 def test_role5_is_separate_expected_method(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=root/'innovation/adaptive_strength_20261023/batch/role5_pilots/jobs.json';p.parent.mkdir(parents=True)
   p.write_text(json.dumps({'jobs':[dict(id='role5',metadata=dict(task_id='short_0252',benchmark='IVEBench',method='temporal_gain_field_role5',cohort='adaptive_research_20261023'))]}))
   with patch.object(relay,'ROOT',root/'metrics'):rows=relay.expected_jobs({'jobs':[]})
   self.assertEqual(next(r for r in rows if r['id']=='role5')['method'],'temporal_gain_field_role5')
 def test_uniform_expected_once(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=root/'innovation/adaptive_strength_20261023/batch/uniform_pilots/jobs.json';p.parent.mkdir(parents=True)
   j=dict(id='uniform',metadata=dict(task_id='short_0358',benchmark='IVEBench',method='temporal_gain_field_uniform_energy',cohort='adaptive_research_20261023'))
   p.write_text(json.dumps({'jobs':[j]}))
   with patch.object(relay,'ROOT',root/'metrics'):rows=relay.expected_jobs({'jobs':[]})
   self.assertEqual(sum(x['id']=='uniform' for x in rows),1)
 def test_fixed_budget_separate_cohort(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=root/'innovation/feature_gain_field_fixed_budget/pilots/jobs.json';p.parent.mkdir(parents=True)
   p.write_text(json.dumps({'jobs':[dict(id='fb',metadata=dict(task_id='long_0059',benchmark='IVEBench',method='temporal_gain_field_fixed_budget',cohort='fixed_budget_original_four'))]}))
   with patch.object(relay,'ROOT',root/'metrics'):rows=relay.expected_jobs({'jobs':[]})
   self.assertEqual(next(r for r in rows if r['id']=='fb')['cohort'],'fixed_budget_original_four')
 def test_live_pair_separate_cohort_without_duplicate_ids(self):
  self.assertIn(('H3_HOST_RTX4090','/data/research-user/h3_inference_20261023/live_phase_pair_20261023'),relay.PRODUCERS)
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=root/'supervision/live_phase_pair_20261023/jobs.json';p.parent.mkdir(parents=True)
   j=dict(id='live_native',metadata=dict(task_id='short_0358',benchmark='IVEBench',method='native',cohort='phase_calibration_pair'))
   p.write_text(json.dumps({'jobs':[j]}))
   with patch.object(relay,'ROOT',root/'metrics'):rows=relay.expected_jobs({'jobs':[dict(id='live_native',task_id='short_0358',dataset='IVEBench',method='native',cohort='phase_calibration_pair') ]})
   self.assertEqual(sum(r['id']=='live_native' for r in rows),1)
   self.assertEqual(next(r for r in rows if r['id']=='live_native')['cohort'],'phase_calibration_pair')
if __name__=='__main__':unittest.main()
