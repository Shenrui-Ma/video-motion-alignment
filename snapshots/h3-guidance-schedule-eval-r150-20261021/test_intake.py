"""Synthetic gate checks against real frozen R150 bindings; no generated result claim."""
import copy,unittest
from common import ROOT,read,case_and_schedule,expected_router
from ingest import validate_job
class IntakeTests(unittest.TestCase):
 def fixture(self,sid='long_0039',arm='early'):
  _,c,s=case_and_schedule(sid,arm);s=dict(s,id=arm);b=read(ROOT/'runtime'/sid/(arm+'.json'));r=expected_router(c,s)
  g={'schema':'r149-schedule-job-gate-v1','passed':True,'producer_seal_sha256':b['producer_seal']['sha256'],'run_id':b['run_id'],'role':arm,
   'NFE':20,'Euler_updates':20,'routed_blocks':50*len(s['steps_0based']),'alpha':r['alpha'],'phase_displacement':0,'actual_routed_steps_zero_based':s['steps_0based'],
   'valid_frames':c['geometry']['valid_frames'],'evaluation_crop_xywh':c['geometry']['crop_xywh'],'physical_query_window':[r['start_frame'],r['end_frame']],
   'noise_sha256':c['historical_initial_noise']['sha256'],'sampler_timing':{'passed':True,'run_id':b['run_id'],'sampler_wall_seconds':1,'callback_steps':[{'step_zero_based':i} for i in range(20)]},
   'binding_artifacts':{'fixture':'not_actual'},'final_latent':{'fixture':'not_actual'},'service_owner':{'gpu_uuid':b['gpu_uuid'],'port':b['port']},
   'video':{'file':b['remote_root']+'/output/fixture.mp4'}}
  return c,s,b,g
 def test_sixteen_contracts(self):
  for sid in ['long_0039','long_0059','short_0085','short_0274']:
   for a in ['early','late','split','global_weak']:
    c,s,b,g=self.fixture(sid,a);validate_job(c,s,b,g)
 def test_reject_wrong_evidence(self):
  for key,value in [('run_id','r149_long_0039_seed2026101701_early'),('producer_seal_sha256','0'*64),('noise_sha256','0'*64),('valid_frames',105),('routed_blocks',1000),('passed',False)]:
   c,s,b,g=self.fixture();g[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):validate_job(c,s,b,g)
 def test_reject_other_output_root(self):
  c,s,b,g=self.fixture();g['video']['file']='/tmp/other.mp4'
  with self.assertRaises(ValueError):validate_job(c,s,b,g)
 def test_preservation_phases_do_not_claim_timing_boundaries(self):
  for sid in ['short_0085','short_0274']:
   _,c,_=case_and_schedule(sid,'early')
   for e in c['events']:
    self.assertEqual(e['measurement_kind'],'previously_reviewed_broad_phase_interval')
    self.assertIsNone(e['source'])
    self.assertIsNone(e['native'])
    self.assertTrue(e['source_phase_interval'])
if __name__=='__main__':unittest.main()
