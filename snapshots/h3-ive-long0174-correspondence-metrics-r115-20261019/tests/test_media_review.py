import copy,sys,unittest,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import read
from media import ROLES,TRIPLET_ROLES,LABELS,TRIPLET_LABELS,caption,check_time
from review import ROLES as REVIEW_ROLES,COMPONENTS,validate_completed,delay_interval
from PIL import Image

class Tests(unittest.TestCase):
    def fixture(self):
        plan=read(R/'configs/PREREGISTERED_EVENTS.json')
        return {'all_valid_frames_inspected':True,'examined_frames_by_role':{r:list(range(145)) for r in REVIEW_ROLES},
            'reviewer':'SYNTHETIC UNIT TEST','task_acceptance':{r:{'status':'PASS',**dict.fromkeys(COMPONENTS,'PASS')} for r in REVIEW_ROLES},
            'motion_preservation':{r:{'action_content':'PASS','motion_amplitude':'PASS'} for r in REVIEW_ROLES},
            'quality':{r:{'status':'ACCEPTABLE'} for r in REVIEW_ROLES},
            'events':[{**row,**{r:{'status':'OBSERVED','frames':row['source_frames'],'notes':''} for r in REVIEW_ROLES}} for row in plan['events']],
            'terminal_motion':{**plan['terminal_motion'],**{r:{'status':'OBSERVED','notes':''} for r in REVIEW_ROLES}}}
    def test_four_roles_and_readable_triplet(self):
        self.assertEqual(ROLES,('source','native','fixed_one_bin','matched_one_bin'))
        self.assertEqual(TRIPLET_ROLES,('source','native','matched_one_bin'))
    def test_caption_dimensions(self):
        with tempfile.TemporaryDirectory() as folder:
            for labels,width in [(LABELS,5120),(TRIPLET_LABELS,3840)]:
                p=Path(folder)/'caption.png';caption(p,labels)
                with Image.open(p) as image:self.assertEqual(image.size,(width,88))
    def test_physical_time(self):
        d={'width':5120,'height':808,'avg_frame_rate':'24/1','pts_s':[i/24 for i in range(145)]}
        check_time(d,145,5120,808);d['pts_s'][32]+=1/24
        with self.assertRaises(ValueError):check_time(d,145,5120,808)
    def test_source_event_keeps_joint_definition(self):
        x=self.fixture();x['events'][2]['definition']='arm only'
        with self.assertRaises(ValueError):validate_completed(x)
    def test_full_review_and_comparisons(self):
        result=validate_completed(self.fixture());self.assertEqual(len(result['events']),3)
        self.assertTrue(result['events'][0]['comparisons']['fixed_one_bin__matched_one_bin']['primary_timing_comparison_eligible'])
    def test_native_values_not_prefilled_from_old_annotations(self):
        plan=read(R/'configs/PREREGISTERED_EVENTS.json')
        self.assertFalse(plan['historical_generated_event_times_used'])
        self.assertTrue(all(set(x)=={'id','definition','source_frames'} for x in plan['events']))
    def test_task_failure_keeps_observation_but_excludes_primary(self):
        x=self.fixture();x['task_acceptance']['native']['status']='FAIL'
        result=validate_completed(x)['events'][0]
        self.assertIsNotNone(result['observed_delays']['native'])
        self.assertFalse(result['comparisons']['native__matched_one_bin']['primary_timing_comparison_eligible'])
    def test_unknown_rejects_numeric_time(self):
        x=self.fixture();x['events'][0]['matched_one_bin']['status']='UNKNOWN'
        with self.assertRaises(ValueError):validate_completed(x)
    def test_unknown_kept_with_reason(self):
        x=self.fixture();x['events'][0]['matched_one_bin']={'status':'UNKNOWN','frames':None,'notes':'occluded'}
        self.assertIsNone(validate_completed(x)['events'][0]['observed_delays']['matched_one_bin'])
    def test_missing_review_frames(self):
        x=self.fixture();x['examined_frames_by_role']['fixed_one_bin'].pop()
        with self.assertRaises(ValueError):validate_completed(x)
    def test_partial_edit_cannot_be_pass(self):
        x=self.fixture();x['task_acceptance']['native']['requested_black_clothes']='PARTIAL'
        with self.assertRaises(ValueError):validate_completed(x)
    def test_late_event_does_not_fail_basic_edit(self):
        x=self.fixture();x['events'][0]['native']['frames']=[59,65]
        result=validate_completed(x)
        self.assertEqual(result['task_acceptance']['native']['status'],'PASS')
        self.assertEqual(result['events'][0]['observed_delays']['native']['frames'],[6,18])
    def test_interval_bounds(self):
        self.assertEqual(delay_interval([47,53],[61,65])['frames'],[8,18])
        for bad in [[145,150],[20,19],[0.1,3],[True,3]]:
            with self.assertRaises(ValueError):delay_interval([47,53],bad)

if __name__=='__main__':unittest.main()
