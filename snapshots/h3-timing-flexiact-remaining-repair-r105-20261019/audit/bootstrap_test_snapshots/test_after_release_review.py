import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import predecessor
from r105_contract import sha

class AfterReleaseReview(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.old=self.root/'old';self.audit=self.old/'audit/attempt'
        self.owner={'pid':99,'identity':{'uid':1004,'start_ticks':'11'}}
        self.put(self.old/'deploy_manifest.json',{'files':{}});self.put(self.old/'processes/service.json',self.owner)
        self.exit={'passed':True,'owner':self.owner,'process_absent':True,'CUDA_allocation_absent':True}
        self.put(self.audit/'ROOT_EXIT_RECEIPT.json',self.exit)
        self.pending={'passed':True,'GPU_released':True,'all_sources_reviewed':False,'terminal_sources':[{'source_id':'a'}],'remaining_sources':['b']}
        self.put(self.audit/'RELEASED_PENDING_REVIEW.json',self.pending);self.put(self.old/'audit/SCREEN_LEDGER.json',{'rows':self.pending['terminal_sources']})
        self.video=self.old/'output/native.mp4';self.video.parent.mkdir();self.video.write_bytes(b'actual-output')
        self.gatepath=self.old/'analysis/postrun/b/NATIVE_RUNTIME_GATE.json'
        self.gate={'passed':True,'source_id':'b','service_owner':self.owner,'runs':{'native':{'NFE':20,'routed_blocks':0,'valid_frames':145,'video':{'file':str(self.video),'sha256':sha(self.video)}}}}
        self.put(self.gatepath,self.gate)
        self.reviewpath=self.root/'design/post_release/REVIEW.json';self.review={'source_id':'b','reviewed_frame_count':145};self.put(self.reviewpath,self.review)
        self.receiptpath=self.root/'design/post_release/AFTER_RELEASE_REVIEW.json'
        self.receipt={'schema':'r96-after-release-review-v1','root_reviewed':True,'owner':self.owner,'producer_seal_sha256':sha(self.old/'deploy_manifest.json'),'exit_sha256':sha(self.audit/'ROOT_EXIT_RECEIPT.json'),'pending_receipt_sha256':sha(self.audit/'RELEASED_PENDING_REVIEW.json'),'ledger_sha256':sha(self.old/'audit/SCREEN_LEDGER.json'),'previous_terminal_sources':self.pending['terminal_sources'],'post_release_reviews':[{'source_id':'b','native_gate_sha256':sha(self.gatepath),'review_file':str(self.reviewpath.relative_to(self.root)),'review_sha256':sha(self.reviewpath),'disposition':'reviewed_transfer_to_followup','followup_root':'/registered/r107','guided_result_pending':True}]}
        self.policy={'remote_root':str(self.old),'owner':self.owner,'producer_seal_sha256':sha(self.old/'deploy_manifest.json'),'attempt':'attempt','required_terminal_sources':['a','b']}
        self.bind()
    def put(self,p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
    def bind(self):
        self.put(self.receiptpath,self.receipt)
        self.policy['after_release_review']={'file':str(self.receiptpath.relative_to(self.root)),'sha256':sha(self.receiptpath)}
        self.put(self.root/'configs/predecessor.json',self.policy)
    def check(self,identity=None,compute=None):return predecessor.check(self.root,current_identity=lambda _:identity,compute_processes=lambda:compute or [])
    def test_valid_reviewed_transfer_preserves_pending(self):
        result=self.check();self.assertEqual(result['completion_mode'],'released_reviewed_followup_pending');self.assertEqual(result['pending_followups'][0]['source_id'],'b');self.assertFalse((self.audit/'COMPLETE.json').exists())
    def test_missing_binding_rejected(self):
        del self.policy['after_release_review'];self.put(self.root/'configs/predecessor.json',self.policy)
        with self.assertRaises(ValueError):self.check()
    def test_modified_receipt_rejected(self):
        self.receipt['root_reviewed']=False;self.put(self.receiptpath,self.receipt)
        with self.assertRaises(ValueError):self.check()
    def test_wrong_owner_rejected(self):
        self.receipt['owner']={'pid':100};self.bind()
        with self.assertRaises(ValueError):self.check()
    def test_original_ledger_mutation_rejected(self):
        self.put(self.old/'audit/SCREEN_LEDGER.json',{'rows':[]})
        with self.assertRaises(ValueError):self.check()
    def test_missing_source_review_rejected(self):
        self.receipt['post_release_reviews']=[];self.bind()
        with self.assertRaises(ValueError):self.check()
    def test_video_mutation_rejected(self):
        self.video.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.check()
    def test_review_mutation_rejected(self):
        self.review['reviewed_frame_count']=12;self.put(self.reviewpath,self.review)
        with self.assertRaises(ValueError):self.check()
    def test_incomplete_frame_coverage_rejected(self):
        self.review['reviewed_frame_count']=12;self.put(self.reviewpath,self.review);self.receipt['post_release_reviews'][0]['review_sha256']=sha(self.reviewpath);self.bind()
        with self.assertRaises(ValueError):self.check()
    def test_falsely_closed_followup_rejected(self):
        self.receipt['post_release_reviews'][0]['guided_result_pending']=False;self.bind()
        with self.assertRaises(ValueError):self.check()
    def test_live_generation_rejected(self):
        with self.assertRaises(ValueError):self.check(identity=self.owner['identity'])
    def test_old_cuda_rejected(self):
        with self.assertRaises(ValueError):self.check(compute=[{'pid':99}])
    def test_unrelated_cuda_allowed(self):self.assertTrue(self.check(compute=[{'pid':100}])['passed'])
    def test_pair_added_after_transfer_rejected(self):
        self.put(self.old/'analysis/postrun/b/PAIR_RUNTIME_GATE.json',{'passed':True})
        with self.assertRaises(ValueError):self.check()
    def test_original_incomplete_completion_not_masked_by_transfer(self):
        self.put(self.audit/'COMPLETE.json',{'passed':True,'all_sources_reviewed':False})
        with self.assertRaises(ValueError):self.check()

if __name__=='__main__':unittest.main()
