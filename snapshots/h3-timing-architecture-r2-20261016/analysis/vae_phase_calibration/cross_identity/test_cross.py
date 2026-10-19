import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import torch
import evaluate_cross as target


class TestFrozenCross(unittest.TestCase):
    def fixture(self, root, stage='after_process_latent_out'):
        z=torch.arange(1*24*42*46*82,dtype=torch.float32).reshape(1,24,42,46,82)
        metadata={'normalization_stage':stage}
        path=Path(root)/'x.pt'
        torch.save({'video':z,'metadata':metadata},path)
        return z,dict(path=str(path),file_sha256=target.sha(path),metadata=metadata,
                      tensor=dict(shape=list(z.shape),dtype=str(z.dtype),sha256=hashlib.sha256(z.view(torch.uint8).numpy()).hexdigest()))

    def test_snapshot_and_roi_order(self):
        with tempfile.TemporaryDirectory() as root:
            z,item=self.fixture(root)
            loaded=target.load_tensor(item,True,torch)
            self.assertTrue(torch.equal(loaded,z))
            arr=target.region_array(loaded,[5,28,22,58])
            self.assertEqual(arr.shape,(42,24*23*36))
            self.assertEqual(arr[4,0],float(z[0,0,4,5,22]))
            self.assertEqual(arr[4,-1],float(z[0,23,4,27,57]))

    def test_invalid_normalization_refused(self):
        with tempfile.TemporaryDirectory() as root:
            _,item=self.fixture(root,'before_process_latent_out')
            with self.assertRaisesRegex(ValueError,'normalization'):
                target.load_tensor(item,True,torch)

    def test_tampered_raw_hash_refused(self):
        with tempfile.TemporaryDirectory() as root:
            _,item=self.fixture(root)
            item['tensor']['sha256']='bad'
            with self.assertRaisesRegex(ValueError,'content'):
                target.load_tensor(item,True,torch)

    def test_tampered_file_refused(self):
        with tempfile.TemporaryDirectory() as root:
            _,item=self.fixture(root)
            item['file_sha256']='bad'
            with self.assertRaisesRegex(ValueError,'file changed'):
                target.load_tensor(item,True,torch)

    def test_protocol_pinned(self):
        self.assertEqual(target.sha(target.HERE/'PROTOCOL.json'),target.PROTOCOL_SHA)
        p=json.loads((target.HERE/'PROTOCOL.json').read_text())
        self.assertEqual(p['methods'],['phase_mean_centering','same_phase_gap5'])
        self.assertEqual(p['sources']['07']['windows_inclusive'],[[54,69],[75,88],[98,111]])


if __name__=='__main__':
    torch.set_num_threads(1)
    unittest.main()
