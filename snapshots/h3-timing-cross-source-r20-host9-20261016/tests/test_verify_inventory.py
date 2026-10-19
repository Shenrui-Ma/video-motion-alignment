import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
import verify_pair as v

class InventoryTests(unittest.TestCase):
    def test_snapshot_metadata_tensor_and_path_negative_cases(self):
        with tempfile.TemporaryDirectory() as d,patch.object(v,'SHAPES',{'video':(1,2),'audio':(1,3)}):
            root=Path(d);video=torch.ones(1,2);audio=torch.ones(1,3)
            record={'file':'sample.pt','run_id':'run','video':v.signature(video),'audio':v.signature(audio)}
            payload={'video':video,'audio':audio,'metadata':{k:x for k,x in record.items() if k!='file'}}
            torch.save(payload,root/'sample.pt')
            self.assertEqual(v.checked_snapshot(root,record,'run')[1]['bytes'],(root/'sample.pt').stat().st_size)
            with self.assertRaises(ValueError):v.checked_snapshot(root,record,'wrong')
            bad=copy.deepcopy(payload);bad['video'][0,0]=2;torch.save(bad,root/'sample.pt')
            with self.assertRaises(ValueError):v.checked_snapshot(root,record,'run')
            torch.save(payload,root/'sample.pt')
            bad=copy.deepcopy(record);bad['audio']['sha256']='bad'
            with self.assertRaises(ValueError):v.checked_snapshot(root,bad,'run')
            with self.assertRaises(ValueError):v.safe_file(root,'../escape')
            (root/'linked.pt').symlink_to(root/'sample.pt')
            with self.assertRaises(ValueError):v.safe_file(root,'linked.pt')

    def test_missing_extra_duplicate_inventory_reject_before_tensor_load(self):
        grid=torch.linspace(1,0,21).tolist();run='run'
        m={'status':'complete','callback_count':20,'expected_callback_count':20,'run_id':run,
           'capture_steps_zero_based':list(v.CAPTURES),'captures':[{'file':f'x0_step{i:03d}.pt','step_zero_based':i,'snapshot_kind':'x0_estimate'} for i in v.CAPTURES],
           'sigmas_video':grid,'seed':2026101311,'sampler':'sample_euler','audio_scale':4,'video_latent_scale_factor':1,
           'normalization_stage':'after_process_latent_out','geometry':{'width':1312,'height':736,'frames':141,'fps':24},
           'target_latent_shapes':[list(v.SHAPES[k]) for k in ('video','audio')],
           'final_sampler_result':{'file':'sampler_final.pt','snapshot_kind':'sampler_final','sigma_video':0.,'sigma_audio':0.,'step_zero_based':19}}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'manifest.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'inventory'):v.inspect_capture(root,run,grid)
            for name in [f'x0_step{i:03d}.pt' for i in v.CAPTURES]+['sampler_final.pt','unexpected.pt']:(root/name).touch()
            with self.assertRaisesRegex(ValueError,'inventory'):v.inspect_capture(root,run,grid)
            (root/'unexpected.pt').unlink();bad=copy.deepcopy(m);bad['captures'][1]['file']=bad['captures'][0]['file'];(root/'manifest.json').write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,'inventory'):v.inspect_capture(root,run,grid)
            bad=copy.deepcopy(m);bad['final_sampler_result']['sigma_video']=.1;(root/'manifest.json').write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,'semantics'):v.inspect_capture(root,run,grid)

if __name__=='__main__':unittest.main()
