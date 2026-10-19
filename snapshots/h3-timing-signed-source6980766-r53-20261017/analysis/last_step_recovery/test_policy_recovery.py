import copy,sys,unittest
import common as c
from pose_and_decision import validate_context

class ContextTests(unittest.TestCase):
    def setUp(self):
        self.context={'schema':'r53-final-observation-recovery-context-v1','prior19_replayed_exact':True,'original_request_sha256':c.REQUEST_SHA,'failure_inventory_sha256':c.INVENTORY_SHA,'failure_audit_sha256':c.AUDIT_SHA,'frozen_producer_manifest_sha256':c.PRODUCER_MANIFEST_SHA,'x19_proof_sha256':c.REPLAY_SHA,'x19_sha256':c.X19_SHA,'original_run_completed':False,'GPU_arithmetic_unverified':True,'prior19':[{'index':i} for i in range(19)]}
    def test_exact_context(self):validate_context(self.context)
    def test_missing_or_reordered_prefix(self):
        for rows in (self.context['prior19'][:-1],list(reversed(self.context['prior19']))):
            with self.assertRaisesRegex(ValueError,'prior19'):validate_context(dict(self.context,prior19=rows))
    def test_source_binding_tampering(self):
        for key in ('failure_audit_sha256','frozen_producer_manifest_sha256','x19_proof_sha256','x19_sha256'):
            with self.assertRaisesRegex(ValueError,'binding'):validate_context(dict(self.context,**{key:'0'*64}))
    def test_completion_cannot_be_claimed(self):
        for key,value in (('original_run_completed',True),('GPU_arithmetic_unverified',False)):
            with self.assertRaisesRegex(ValueError,'completion'):validate_context(dict(self.context,**{key:value}))
    def test_real_prior19_observer_inputs_and_final_unknown_off(self):
        t=c.frozen_runtime();items=c.inventory();sys.path.insert(0,str(c.PRODUCER/'extensions'))
        from H3AutomaticWindowRouter.selector import Controller
        controller=Controller();rows=[]
        for index in range(19):
            reqs=list((c.ARCHIVE/'audit/observations').glob(f'step{index:03d}_*/request.json'));self.assertEqual(len(reqs),1)
            req=c.read(reqs[0]);res_path=reqs[0].with_name('response.json');res=c.read(c.archived(res_path.relative_to(c.ARCHIVE).as_posix(),items));t.validate_response(res,req,c.sha(reqs[0]))
            obs=c.read(c.archived(c.relative_original(res['observer']['file']),items))
            decision=controller.select(index,{'status':'complete','observer':obs,'request_sha256':c.sha(reqs[0]),'response_sha256':c.sha(res_path)})
            rows.append(decision['chosen_full'])
        self.assertEqual(len(rows),19)
        final=controller.select(19,{'status':'complete','observer':{'schema':'r27-whole-timeline-observation-v1','physical_index':19,'status':'unknown_visibility','windows':[],'reasons':['synthetic_fixture']}})
        self.assertFalse(final['chosen_full']);self.assertEqual(final['reason'],'unknown_visibility')

if __name__=='__main__':unittest.main()
