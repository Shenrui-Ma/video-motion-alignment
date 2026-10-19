import copy,sys,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
import consume as c
class Consumer(unittest.TestCase):
    def records(self):
        owner={'pid':123,'gpu_uuid':'device','identity':{'start_ticks':'5'}}
        return ({'schema':'r110-p1-native-runtime-gate-v1','passed':True,'checks':{'actual':True},'run_id':c.RUN,'valid_frames':105,'NFE':20,'routed_blocks':0,'video':{'file':c.REMOTE+'/output/'+c.RUN+'_00001_.mp4'},'runtime_profile':{'gpu_uuid':'device'}},{'passed':True,'jobs':[c.RUN],'GPU_released':True},{'passed':True,'process_absent':True,'CUDA_allocation_absent':True,'owner':owner},{'owner':owner})
    def test_accepts_actual_contract_shape(self):self.assertTrue(c.validate_gate(*self.records()).startswith('output/'))
    def test_failed_condition_rejected(self):
        values=self.records();values[0]['checks']['actual']=False
        with self.assertRaises(ValueError):c.validate_gate(*values)
    def test_nonmatching_run_and_guidance_rejected(self):
        for key,value in [('routed_blocks',450),('run_id','other'),('valid_frames',107)]:
            values=self.records();values[0][key]=value
            with self.assertRaises(ValueError):c.validate_gate(*values)
    def test_missing_release_rejected(self):
        values=self.records();values[2]['CUDA_allocation_absent']=False
        with self.assertRaises(ValueError):c.validate_gate(*values)
    def test_wrong_process_generation_rejected(self):
        values=list(copy.deepcopy(self.records()));values[3]={'owner':{'pid':123,'gpu_uuid':'device','identity':{'start_ticks':'6'}}}
        with self.assertRaises(ValueError):c.validate_gate(*values)
    def test_real_reused_parent_and_source_bytes(self):
        self.assertEqual(c.sha(c.OLD),c.OLD_SHA)
        self.assertEqual(c.sha(c.PRODUCER/'inputs/short_0114_video.mp4'),c.SOURCE_SHA)
    def test_all105_comparison_timestamps(self):
        value={'streams':[{'width':3840,'height':808,'avg_frame_rate':'24/1'}],'frames':[{'best_effort_timestamp_time':str(i/24)} for i in range(105)]}
        self.assertEqual(c.validate_comparison_time(value)['count'],105)
        value['frames'][50]['best_effort_timestamp_time']=str(51/24)
        with self.assertRaises(ValueError):c.validate_comparison_time(value)
    def test_actual_chinese_caption_font(self):
        from PIL import ImageFont
        font=ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc',30)
        self.assertGreater(font.getlength('主体编辑'),0)
if __name__=='__main__':unittest.main()
