import copy
import json
from pathlib import Path
import tempfile
import unittest
from review_wait import review_wait, exempt_idle, sha


class ReviewWaitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.memory = {}
        self.owner = {'pid': 17, 'identity': {'uid': 1016, 'start_ticks': '123', 'cmdline': 'service '}, 'started_unix': 50}
        self.controller = {'pid': 18, 'identity': {'uid': 1016, 'start_ticks': '124', 'cmdline': 'controller '}, 'role': 'controller', 'service_pid': 17, 'service_identity': self.owner['identity']}
        self.identities = {17: self.owner['identity'], 18: self.controller['identity']}
        self.write('deploy_manifest.json', {'seal': 'frozen'})
        self.write('processes/service.json', self.owner)
        self.write('processes/controller.json', self.controller)
        self.write('configs/scientific_contract.json', {'cases': [{'run_id': 'run_native', 'arm': 'native', 'source_id': 'sam07'}], 'condition_recovery': {'requires_shared_cache_native': True}})
        self.gate = {'schema': 'r149-schedule-job-gate-v1', 'passed': True, 'role': 'native', 'run_id': 'run_native', 'service_owner': self.owner, 'producer_seal_sha256': sha(self.root/'deploy_manifest.json'), 'video': {'sha256': 'video', 'file': '/output/native.mp4'}}
        self.write('analysis/postrun/sam07/run_native_GATE.json', self.gate)
        self.request = {'schema': 'r150-native-visual-review-request-v1', 'source_id': 'sam07', 'run_id': 'run_native', 'created_unix': 100., 'timeout_seconds': 600, 'native_gate': str(self.root/'analysis/postrun/sam07/run_native_GATE.json'), 'native_gate_sha256': sha(self.root/'analysis/postrun/sam07/run_native_GATE.json'), 'video': '/output/native.mp4', 'video_sha256': 'video', 'producer_seal_sha256': sha(self.root/'deploy_manifest.json'), 'review_file': str(self.root/'audit/NATIVE_VISUAL_REVIEW.json')}
        self.write('audit/NATIVE_VISUAL_REVIEW_REQUEST.json', self.request)
        self.write('logs/controller_state.json', {'status': 'waiting_native_visual_review', 'current': None, 'completed': ['run_native']})

    def write(self, rel, obj):
        path = self.root/rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(obj))

    def check(self, wall=130., mono=1000.):
        return review_wait(self.root, self.owner, wall, mono, self.memory, self.identities.get)

    def test_valid_boundaries(self):
        self.assertTrue(self.check(100.)['active']); self.assertTrue(self.check(699.999,1599.999)['active'])
        self.assertFalse(self.check(700.,1600.)['active'])

    def test_future_nan_and_changed_timeout(self):
        for field, value in [('created_unix', 131), ('created_unix', float('nan')), ('timeout_seconds', 601), ('timeout_seconds', float('inf'))]:
            changed = dict(self.request); changed[field] = value; self.write('audit/NATIVE_VISUAL_REVIEW_REQUEST.json', changed)
            self.assertFalse(self.check()['active'])

    def test_reused_service_or_controller_pid(self):
        for pid in (17,18):
            prior=self.identities[pid]; self.identities[pid]=dict(prior,start_ticks='999')
            self.assertFalse(self.check()['active']); self.identities[pid]=prior

    def test_wrong_uid_or_command(self):
        for key,value in [('uid',1025),('cmdline','unrelated ' )]:
            self.identities[17]=dict(self.owner['identity'],**{key:value}); self.assertFalse(self.check()['active'])

    def test_failed_gate_and_wrong_owner(self):
        for change in ({'passed': False}, {'service_owner': dict(self.owner,pid=99)}, {'role':'fixed'}):
            gate=dict(self.gate,**change);self.write('analysis/postrun/sam07/run_native_GATE.json',gate)
            request=dict(self.request,native_gate_sha256=sha(self.root/'analysis/postrun/sam07/run_native_GATE.json'));self.write('audit/NATIVE_VISUAL_REVIEW_REQUEST.json',request)
            self.assertFalse(self.check()['active'])

    def test_hash_and_state_mismatch(self):
        self.write('logs/controller_state.json', {'status':'pending_or_running','current':'next','completed':['run_native']})
        self.assertFalse(self.check()['active'])
        self.write('logs/controller_state.json', {'status':'waiting_native_visual_review','current':None,'completed':['run_native']})
        self.write('deploy_manifest.json', {'seal':'different'});self.assertFalse(self.check()['active'])

    def test_rewrite_cannot_extend_and_clock_rollback(self):
        self.assertTrue(self.check()['active'])
        self.assertFalse(self.check(130.,1570.)['active'])
        self.request['created_unix']=140.;self.write('audit/NATIVE_VISUAL_REVIEW_REQUEST.json',self.request)
        self.assertFalse(self.check(150.,1020.)['active'])

    def test_only_idle_reason_is_exempt(self):
        self.assertIsNone(exempt_idle('bounded_idle_review_expired',{'active':True}))
        for reason in ('bounded_service_lifetime_expired','bounded_job_timeout','actual_registered_job_failure',None):
            self.assertEqual(exempt_idle(reason,{'active':True}),reason)
        self.assertEqual(exempt_idle('bounded_idle_review_expired',{'active':False}),'bounded_idle_review_expired')


if __name__ == '__main__':
    unittest.main()
