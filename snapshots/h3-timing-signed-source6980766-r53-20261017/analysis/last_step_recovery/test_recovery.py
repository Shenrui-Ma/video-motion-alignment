import copy,hashlib,os,unittest
from pathlib import Path
import common as c

class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.peer={'pid':47798,'uid':os.getuid(),'start_ticks':2626383913,'cmdline_sha256':'a'*64}
        self.registry={'schema':'r53-recovery-root-admission-v1','root_approved':True,'gpu_uuid':'GPU-selected','permitted_peers':[{'gpu_uuid':'GPU-peer','identity':self.peer}]}
        self.rows=[{'pid':47798,'gpu_uuid':'GPU-peer'}]
        self.lookup=lambda pid:self.peer if pid==47798 else {'pid':pid,'uid':os.getuid(),'start_ticks':2,'cmdline_sha256':'b'*64}
    def test_exact_peer_and_second_card_pass(self):
        self.assertEqual(c.assert_peers('GPU-selected',self.registry,self.rows,self.lookup,os.getuid()),['GPU-peer','GPU-selected'])
    def test_changed_peer_identity_rejected(self):
        with self.assertRaisesRegex(ValueError,'unregistered or reused'):
            c.assert_peers('GPU-selected',self.registry,self.rows,lambda _:dict(self.peer,start_ticks=9),os.getuid())
    def test_busy_selected_gpu_rejected(self):
        with self.assertRaisesRegex(ValueError,'active compute'):
            c.assert_peers('GPU-selected',self.registry,self.rows+[{'pid':1,'gpu_uuid':'GPU-selected'}],self.lookup,os.getuid())
    def test_unregistered_owned_peer_rejected(self):
        with self.assertRaisesRegex(ValueError,'unregistered'):
            c.assert_peers('GPU-selected',self.registry,self.rows+[{'pid':2,'gpu_uuid':'GPU-other'}],self.lookup,os.getuid())
    def test_third_owned_card_rejected_even_if_registered(self):
        registry=copy.deepcopy(self.registry);registry['permitted_peers'].append({'gpu_uuid':'GPU-other','identity':self.lookup(2)})
        with self.assertRaisesRegex(ValueError,'two owned'):
            c.assert_peers('GPU-selected',registry,self.rows+[{'pid':2,'gpu_uuid':'GPU-other'}],self.lookup,os.getuid())
    def test_other_user_on_unrelated_card_allowed(self):
        lookup=lambda pid:self.peer if pid==47798 else {'uid':os.getuid()+1}
        self.assertEqual(c.assert_peers('GPU-selected',self.registry,self.rows+[{'pid':2,'gpu_uuid':'GPU-other'}],lookup,os.getuid()),['GPU-peer','GPU-selected'])
    def test_wrong_root_gpu_or_missing_approval_rejected(self):
        for change in ({'gpu_uuid':'GPU-wrong'},{'root_approved':False}):
            with self.assertRaises(ValueError):c.assert_peers('GPU-selected',dict(self.registry,**change),self.rows,self.lookup,os.getuid())
    def test_frozen_decoder_is_imported_without_changes(self):
        live=c.load_live()
        self.assertEqual(Path(live.__file__),c.PRODUCER/'scripts/decode_live_child.py')
        self.assertEqual(c.sha(c.PRODUCER/'deploy_manifest.json'),c.PRODUCER_MANIFEST_SHA)
        self.assertTrue(callable(live.load_snapshot) and callable(live.install_fallback_guard) and callable(live.write_video))

if __name__=='__main__':unittest.main()
