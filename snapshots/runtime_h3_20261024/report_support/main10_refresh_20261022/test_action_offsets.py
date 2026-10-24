import unittest
from copy import deepcopy
from action_offsets import measure, ROLES

class MeasurementTests(unittest.TestCase):
    def fixture(self):
        event={'id':'raise','source':[10,12],'status_by_role':{}}
        event.update({r:[14,16] for r in ROLES[1:]})
        return {'events':[event], 'valid_frames':30}
    def test_signed_and_interval(self):
        a=self.fixture();a['events'][0]['early']=[7,9]
        result=measure(a)
        self.assertEqual(result['event_offsets']['raise']['early'],-3)
        self.assertEqual(result['offset_intervals']['raise']['native'],[2,6])
        self.assertEqual(result['mean_absolute_offset']['early'],3)
    def test_common_event_denominator(self):
        a=self.fixture();e=deepcopy(a['events'][0]);e['id']='lower';e['native']=None;e['status_by_role']['native']='missing';e['early']=[20,22];a['events'].append(e)
        result=measure(a)
        self.assertEqual(result['common_events'],['raise'])
        self.assertEqual(result['mean_absolute_offset']['early'],4)
        self.assertEqual(result['coverage']['native'],1)
        self.assertEqual(result['coverage']['early'],2)
    def test_no_matched_events_is_not_zero(self):
        a=self.fixture();a['events'][0]['fixed']=None;a['events'][0]['status_by_role']['fixed']='missing'
        self.assertTrue(all(v is None for v in measure(a)['mean_absolute_offset'].values()))
    def test_reject_bad_bounds(self):
        a=self.fixture();a['events'][0]['fixed']=[29,30]
        with self.assertRaises(AssertionError):measure(a)
    def test_null_requires_reason(self):
        a=self.fixture();a['events'][0]['fixed']=None
        with self.assertRaises(AssertionError):measure(a)

if __name__=='__main__':unittest.main()
