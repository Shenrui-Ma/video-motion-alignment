import copy
import sys
import tempfile
from pathlib import Path
import unittest

import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
from verify_completed import checked_snapshot
from H3X0Readout.core import tensor_signature


class SnapshotTests(unittest.TestCase):
    def test_actual_tensor_metadata_and_inventory_record_agree(self):
        torch.set_num_threads(1)
        video=torch.zeros(1,24,42,46,82)
        audio=torch.zeros(1,32,2,235)
        metadata={'video':tensor_signature(video),'audio':tensor_signature(audio),
                  'step_zero_based':11,'snapshot_kind':'x0_estimate'}
        record=dict(metadata,file='x0_step011.pt',capture_seconds=.1)
        payload={'video':video,'audio':audio,'metadata':metadata}
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/record['file'];torch.save(payload,path)
            checked_snapshot(path,record)
            bad=copy.deepcopy(record);bad['step_zero_based']=12
            with self.assertRaisesRegex(ValueError,'metadata'):checked_snapshot(path,bad)
            payload['video'][0,0,0,0,0]=1;torch.save(payload,path)
            with self.assertRaisesRegex(ValueError,'disagree'):checked_snapshot(path,record)
            payload['video'][0,0,0,0,0]=float('nan');torch.save(payload,path)
            with self.assertRaisesRegex(ValueError,'invalid actual'):checked_snapshot(path,record)

    def test_extra_payload_and_wrong_shape_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'bad.pt'
            torch.save({'video':torch.zeros(1),'audio':torch.zeros(1),'metadata':{},'extra':1},path)
            with self.assertRaisesRegex(ValueError,'schema'):checked_snapshot(path,{})
            torch.save({'video':torch.zeros(1),'audio':torch.zeros(1),'metadata':{}},path)
            with self.assertRaisesRegex(ValueError,'invalid actual'):checked_snapshot(path,{})


if __name__=='__main__':unittest.main()
