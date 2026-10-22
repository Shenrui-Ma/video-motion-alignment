"""Reject stale conditions/legacy controls while accepting 5/6-role actual contracts."""
import copy
import unittest
from unittest.mock import patch
from common import ROOT, read, resolve_controls, schedule_spec
from ingest import validate_job, validate_batch
from test_intake import IntakeTests

class DanceIntakeTests(unittest.TestCase):
    def fixture(self, sid='firefly06', arm='native'):
        c,s,b,g=IntakeTests().fixture(sid,arm)
        g['binding_artifacts']={'configs/graphs/'+b['run_id']+'.json':b['graph']['sha256']}
        return c,s,b,g
    def test_all_17_actual_contracts(self):
        for sid in ('musk05','firefly06','sam07'):
            c=next(c for c in read(ROOT/'EVALUATION_MANIFEST.json')['cases'] if c['source_id']==sid)
            for arm in c['expected_output_roles']:
                validate_job(*self.fixture(sid,arm))
    def test_reject_wrong_cache(self):
        c,s,b,g=self.fixture();b['conditioning_sha256']='0'*64
        with self.assertRaises(ValueError):validate_job(c,s,b,g)
    def test_reject_other_actual_graph(self):
        c,s,b,g=self.fixture();g['binding_artifacts'][next(iter(g['binding_artifacts']))]='0'*64
        with self.assertRaises(ValueError):validate_job(c,s,b,g)
    def test_native_is_zero_routes_fixed_is_nine(self):
        for arm,routes in [('native',450),('fixed',0)]:
            c,s,b,g=self.fixture(arm=arm);g['routed_blocks']=routes
            with self.assertRaises(ValueError):validate_job(c,s,b,g)
    def test_no_historical_native_or_weight3_fallback(self):
        # This tests the pre-intake state even after real controls have arrived.
        from pathlib import Path
        exists = Path.exists
        with patch.object(Path, 'exists', lambda p: False if p.name == 'CONTROL.json' else exists(p)):
            for sid in ('firefly06','sam07'):
                c=next(c for c in read(ROOT/'EVALUATION_MANIFEST.json')['cases'] if c['source_id']==sid)
                self.assertIsNone(resolve_controls(c)['media']['native'])
                self.assertIsNone(resolve_controls(c)['media']['fixed'])
                self.assertTrue(c['archived_historical_media']['native'])
            c=next(c for c in read(ROOT/'EVALUATION_MANIFEST.json')['cases'] if c['source_id']=='musk05')
            self.assertTrue(resolve_controls(c)['media']['native'])
            self.assertIsNone(resolve_controls(c)['media']['fixed'])
    def test_batch_requires_all_six_same_owner(self):
        c,s,b,g=self.fixture();owner=dict(g['service_owner'],pid=999)
        runs={}
        for arm in c['expected_output_roles']:
            _,_,_,r=self.fixture(arm=arm);r['service_owner']=owner;runs[arm]=r
        g=runs['native'];gate={'schema':'r149-fixed-schedule-runtime-gate-v1','passed':True,'source_id':c['source_id'],
            'producer_seal_sha256':b['producer_seal']['sha256'],'same_persistent_service':True,'phase_displacement':0,
            'runs':runs,'service_owner':owner}
        complete={'schema':'r149-schedule-completion-v1','passed':True,'jobs':c['expected_run_ids'],'remaining':[],
            'GPU_released':True,'runtime_gate_sha256':'fixture','service_owner':owner}
        release={'owner':owner,'passed':True,'process_absent':True,'CUDA_allocation_absent':True,
                 'cleanup':{'pid':999,'process_absent':True,'own_compute_absent':True}}
        validate_batch(c,b,g,gate,complete,release,'fixture')
        bad=copy.deepcopy(gate);del bad['runs']['native']
        with self.assertRaises(ValueError):validate_batch(c,b,g,bad,complete,release,'fixture')
        bad=copy.deepcopy(gate);bad['runs']['fixed']['service_owner']=dict(owner,pid=888)
        with self.assertRaises(ValueError):validate_batch(c,b,g,bad,complete,release,'fixture')
if __name__=='__main__':unittest.main()
