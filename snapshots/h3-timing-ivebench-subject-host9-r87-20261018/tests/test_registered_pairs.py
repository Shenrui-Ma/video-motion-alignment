import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r87_contract as c


class RegisteredPairs(unittest.TestCase):
    def test_storage_floor(self):
        from collections import namedtuple
        from check_storage import check
        Space=namedtuple('Space','total used free')
        self.assertTrue(check(ROOT,usage=lambda p:Space(100*2**30,50*2**30,50*2**30))['passed'])
        with self.assertRaisesRegex(ValueError,'filesystem headroom'):
            check(ROOT,usage=lambda p:Space(100*2**30,90*2**30,10*2**30))

    def test_exact_fourteen_pair_order_and_prompt(self):
        jobs,order=c.registry(ROOT)
        self.assertEqual(len(order),14)
        for source,n,f in zip(c.SOURCES,order[::2],order[1::2]):
            self.assertEqual((jobs[n]['source_id'],jobs[f]['source_id']),(source,source))
            self.assertEqual(jobs[n]['case']['prompt'],jobs[f]['case']['prompt'])
            self.assertEqual(jobs[n]['case']['prompt_version'],'P1-local-v1')
            self.assertEqual(jobs[n]['case']['video_sha256'],jobs[f]['case']['video_sha256'])

    def test_changed_prompt_rejected(self):
        original=c.read
        def read(p):
            v=original(p)
            if Path(p).name=='scientific_contract.json':v['cases'][1]['prompt']+=' Extra intervention instruction.'
            return v
        with patch.object(c,'read',side_effect=read):
            with self.assertRaisesRegex(ValueError,'P1 prompt'):c.registry(ROOT)

    def test_changed_shape_rejected(self):
        original=c.read
        def read(p):
            v=original(p)
            if Path(p).name=='scientific_contract.json':v['cases'][0]['geometry']['frames']=90
            return v
        with patch.object(c,'read',side_effect=read):
            with self.assertRaisesRegex(ValueError,'geometry'):c.registry(ROOT)

    def test_changed_physical_mask_rejected(self):
        original=c.read
        def read(p):
            v=original(p)
            if Path(p).name=='r87_short_0131_seed2026101701_forced.json':v['50']['inputs']['end_frame']=106
            return v
        with patch.object(c,'read',side_effect=read):
            with self.assertRaisesRegex(ValueError,'graph numerical'):c.registry(ROOT)


if __name__=='__main__':unittest.main()
