"""Native-only post-attention feature archival contracts, CPU-only."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extensions'))
from H3TemporalRouter import core as temporal
from H3SpatialMarginalRouter import core as spatial
from H3TemporalRouter.native_features import save_native_features


def fixture():
    out=(torch.arange(31*4*8).reshape(1,31,32)%97).to(torch.bfloat16)
    plan={'seq_len':31,'signature':[3,2,4,6,2],'frame_rows':6,
          'reference_video_segment':[3,15],'target_video_segment':[19,31],
          'query_interval_half_open':[19,31],'latent_interval_half_open':[0,2]}
    return out,plan


def save(out,plan,folder,**kwargs):
    args=dict(output_dir=str(folder),run_id='native_test',step=6,block=25,sigma_video=.9655,
              num_heads=4,head_dim=8,selected_heads=(0,2),expected_grid=(2,2,3))
    args.update(kwargs)
    return save_native_features(out,plan,**args)


class NativeFeatureTests(unittest.TestCase):
    def setUp(self):torch.set_num_threads(1)

    def test_exact_head_grid_order_dtype_hash_and_input_rng_unchanged(self):
        out,plan=fixture();before=out.clone();rng=torch.get_rng_state().clone()
        with tempfile.TemporaryDirectory() as folder:
            record=save(out,plan,folder);path=Path(record['path']);payload=torch.load(path,weights_only=True)
            self.assertEqual(record['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(record['bytes'],path.stat().st_size)
            for name,start in (('reference',3),('target',19)):
                v=payload[name];self.assertEqual(tuple(v.shape),(1,2,2,2,3,8))
                self.assertEqual(v.dtype,torch.bfloat16);self.assertEqual(v.device.type,'cpu');self.assertTrue(v.is_contiguous())
                for hi,h in enumerate((0,2)):
                    for t in range(2):
                        for y in range(2):
                            for x in range(3):
                                row=start+(t*2+y)*3+x
                                self.assertTrue(torch.equal(v[0,hi,t,y,x],out[0,row,h*8:(h+1)*8]))
                self.assertEqual(record['metadata']['tensors'][name]['sha256'],hashlib.sha256(v.view(torch.uint8).numpy()).hexdigest())
            self.assertEqual(payload['metadata'],record['metadata'])
            self.assertEqual(record['metadata']['head_indices'],[0,2])
            self.assertEqual(record['metadata']['sampler_sigma_video'],.9655)
            self.assertIn('before native Attention.out_proj',record['metadata']['stage'])
            self.assertFalse(any(p.name.startswith('.') for p in path.parent.iterdir()))
        self.assertTrue(torch.equal(out,before));self.assertTrue(torch.equal(rng,torch.get_rng_state()))

    def test_repeated_name_refused_and_three_checkpoints_distinct(self):
        out,plan=fixture()
        with tempfile.TemporaryDirectory() as folder:
            one=save(out,plan,folder);saved=Path(one['path']).read_bytes()
            with self.assertRaises(FileExistsError):save(out,plan,folder)
            self.assertEqual(Path(one['path']).read_bytes(),saved)
            save(out,plan,folder,step=10);save(out,plan,folder,step=14)
            self.assertEqual(sorted(p.name for p in (Path(folder)/'native_test').iterdir()),
                ['block25_step006.pt','block25_step010.pt','block25_step014.pt'])

    def test_invalid_geometry_dtype_ids_or_checkpoint_fail_closed(self):
        out,plan=fixture()
        with tempfile.TemporaryDirectory() as folder:
            for kw in ({'run_id':'../escape'},{'step':5},{'block':24},{'selected_heads':(0,0)},
                       {'selected_heads':(0,4)},{'expected_grid':(2,2,2)},{'sigma_video':float('nan')}):
                with self.subTest(kw=kw),self.assertRaises(ValueError):save(out,plan,folder,**kw)
            with self.assertRaises(ValueError):save(out.float(),plan,folder)
            with self.assertRaises(ValueError):save(out,{**plan,'target_video_segment':[3,15]},folder)
            changed=out.clone();changed[0,3,0]=float('nan')
            with self.assertRaises(ValueError):save(changed,plan,folder)



if __name__=='__main__':unittest.main()
