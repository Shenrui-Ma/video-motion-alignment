import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from import_motion_fidelity import enrich, verify_score, verify_early_score, B

class BindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items=json.loads((Path(__file__).parent/'flexiact.json.before').read_text())['items']
        cls.item=next(x for x in cls.items if x['id']=='flex_r65_one_leg_fixed')

    def test_all_actual_pairs(self):
        rows=enrich(copy.deepcopy(self.items))
        self.assertEqual(sum(x['status']=='complete' for x in rows),15)
        self.assertTrue(all(x['delta']==x['guided']-x['native'] for x in rows if x['guided'] is not None))

    def test_new_same_name_output_rejected(self):
        x=copy.deepcopy(self.item)
        new=next(x for x in self.items if x['id']=='flex_r85_one_leg__movie_man_9_fixed')
        x['ordinary_video_path']=new['ordinary_video_path']
        x['media_sha256']['ordinary_video_path']=new['media_sha256']['ordinary_video_path']
        with self.assertRaises(AssertionError):verify_score(x,B/'h3-flexiact-forced-metrics-r65-20261018','one_leg','one_leg','native',65)

    def test_wrong_source_rejected(self):
        x=copy.deepcopy(self.item);x['input_reference_video_sha256']='0'*64
        with self.assertRaises(AssertionError):verify_score(x,B/'h3-flexiact-forced-metrics-r65-20261018','one_leg','one_leg','native',65)

    def test_wrong_valid_prefix_rejected(self):
        x=copy.deepcopy(self.item);x['valid_frames']=158
        with self.assertRaises(AssertionError):verify_score(x,B/'h3-flexiact-forced-metrics-r65-20261018','one_leg','one_leg','native',65)

    def test_missing_not_zero_or_prompt_guidance(self):
        rows=enrich(copy.deepcopy(self.items))
        for x in rows:
            if x['status']=='pending':self.assertEqual([x['native'],x['guided'],x['delta']],[None]*3)

    def test_alloff_reuse_binds_exact_other_output(self):
        item=copy.deepcopy(next(x for x in self.items if x['id']=='flex_r50_chest_auto'))
        native,guided,_=verify_early_score(item)
        self.assertEqual(native,guided)
        item['guided_video_path']=self.item['guided_video_path']
        item['media_sha256']['guided_video_path']=self.item['media_sha256']['guided_video_path']
        with self.assertRaises(AssertionError):verify_early_score(item)

if __name__=='__main__':unittest.main()
