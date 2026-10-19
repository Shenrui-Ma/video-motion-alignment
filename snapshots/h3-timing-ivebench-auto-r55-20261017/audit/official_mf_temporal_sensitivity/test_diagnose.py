import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import torch
import diagnose as d

class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tr=np.arange(40*3*2,dtype=np.float32).reshape(1,40,3,2)
        self.vis=np.ones((1,40,3),dtype=bool)

    def test_all_delays_keep_same_physical_domain_and_truth(self):
        for variant in ('self_common','delay_2','delay_4','delay_8'):
            s,sv,t,tv,ledger=d.transform(self.tr,self.vis,variant)
            delay=ledger['known_delay_frames']
            self.assertEqual(ledger['physical_frame_indices'],list(range(8,40)))
            self.assertEqual(ledger['target_original_content_indices'],list(range(8-delay,40-delay)))
            np.testing.assert_array_equal(s,self.tr[:,8:])
            np.testing.assert_array_equal(t,self.tr[:,8-delay:40-delay])
            self.assertAlmostEqual(ledger['known_delay_ms'],delay/24*1000)

    def test_full_self_and_no_endpoint_padding(self):
        s,sv,t,tv,ledger=d.transform(self.tr,self.vis,'self_full')
        np.testing.assert_array_equal(s,t)
        self.assertEqual(ledger['physical_frame_indices'],list(range(40)))
        self.assertEqual(len(set(d.transform(self.tr,self.vis,'delay_8')[4]['target_original_content_indices'])),32)

    def test_gap_changes_only_visibility_exactly_eight_frames(self):
        s,sv,t,tv,ledger=d.transform(self.tr,self.vis,'visibility_gap_8')
        np.testing.assert_array_equal(s,t)
        self.assertEqual(ledger['known_delay_frames'],0)
        self.assertEqual(ledger['gap']['common_indices_half_open'],[12,20])
        self.assertEqual(ledger['gap']['physical_frame_indices_half_open'],[20,28])
        self.assertEqual(np.sum(sv!=tv),8*3)
        self.assertTrue(tv[:,:12].all() and tv[:,20:].all())

    def test_official_AST_and_linear_hand_calculation(self):
        metric,hashes=d.pure_metric()
        tree=ast.parse(d.OFFICIAL.read_text())
        cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='MotionFidelityEvaluator')
        expected={x.name:hashlib.sha256(ast.dump(x,include_attributes=False).encode()).hexdigest()
                  for x in cls.body if isinstance(x,ast.FunctionDef) and x.name in d.METHODS}
        self.assertEqual(hashes,expected)
        source=np.zeros((1,20,1,2),dtype=np.float32)
        source[0,:,0,0]=np.arange(20)
        target=source.copy();target[:,:,:,0]-=2
        vis=np.ones((1,20,1),dtype=bool)
        score=metric._compute_similarity_from_tracks(*[torch.from_numpy(x) for x in (source,vis,target,vis)])
        self.assertAlmostEqual(score,.7/(1+2/19)+.3,places=12)

    def test_no_visible_points_and_identical_are_defined(self):
        metric,_=d.pure_metric()
        tr=torch.from_numpy(self.tr)
        vis=torch.from_numpy(self.vis)
        self.assertAlmostEqual(metric._compute_similarity_from_tracks(tr,vis,tr,vis),1)
        self.assertEqual(metric._compute_similarity_from_tracks(tr,vis,tr,torch.zeros_like(vis)),0)

    def test_tampered_cache_binding_fails(self):
        with tempfile.TemporaryDirectory(dir=d.HERE) as folder:
            p=Path(folder)/'x.npz';p.write_bytes(b'changed')
            r=Path(folder)/'report.json';r.write_text('{}')
            with self.assertRaisesRegex(ValueError,'binding changed'):
                d.load_bound({'file':str(p),'sha256':'0'*64,'report':str(r),'report_sha256':d.sha(r),'N':40})

if __name__=='__main__':
    unittest.main()
