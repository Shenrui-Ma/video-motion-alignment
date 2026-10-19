import copy
import unittest
import working_set_proposal as w


class WorkingSetProposal(unittest.TestCase):
    def value(self):
        return {'uid': 1004, 'ancestors': [{
            'path': '/user.slice', 'current_bytes': 80*w.GIB,
            'high_bytes': 100*w.GIB, 'max_bytes': 112*w.GIB,
            'stat': {'anon': 25*w.GIB, 'file': 54*w.GIB, 'shmem': w.GIB,
                     'active_file': 29*w.GIB, 'inactive_file': 24*w.GIB,
                     'file_mapped': w.GIB, 'file_dirty': 0, 'file_writeback': 0},
            'pressure': {'some': {'avg10': 0.0}, 'full': {'avg10': 0.0}},
            'events': {'high': 100857758, 'max': 0, 'oom': 0, 'oom_kill': 0}}]}

    def assess(self, value=None, host=200*w.GIB):
        return w.assess(value or self.value(), host)

    def test_all_exclusions_and_cache_retention(self):
        s=self.value()['ancestors'][0]['stat'];s.update(file_dirty=w.GIB,file_writeback=2*w.GIB)
        self.assertEqual(w.file_credit(s, 8*w.GIB), (49*w.GIB,41*w.GIB))

    def test_exact_high_and_hard_boundaries(self):
        v=self.value();r=self.assess(v);self.assertTrue(r['admitted'])
        self.assertEqual(r['bounded_ancestors'][0]['headroom_bytes'],{'high':64*w.GIB,'max':76*w.GIB})
        v['ancestors'][0]['current_bytes']+=1;self.assertFalse(self.assess(v)['admitted'])

    def test_hard_limit_guard_independent_of_high(self):
        v=self.value();p=copy.deepcopy(w.POLICY);p['minimum_high_headroom_bytes']=1
        v['ancestors'][0]['current_bytes']+=1
        self.assertFalse(w.assess(v,200*w.GIB,p)['admitted'])

    def test_missing_stat_rejected(self):
        for key in w.STAT_KEYS:
            v=self.value();del v['ancestors'][0]['stat'][key]
            with self.assertRaises(ValueError):self.assess(v)

    def test_invalid_stat_rejected(self):
        for invalid in (-1, None, 1.5, True):
            v=self.value();v['ancestors'][0]['stat']['file']=invalid
            with self.assertRaises(ValueError):self.assess(v)

    def test_no_credit_for_shmem_or_mapped_files(self):
        for key in ('shmem','file_mapped'):
            v=self.value();v['ancestors'][0]['stat'][key]=54*w.GIB
            self.assertFalse(self.assess(v)['admitted'])

    def test_dirty_and_writeback_excluded(self):
        for key in ('file_dirty','file_writeback'):
            v=self.value();v['ancestors'][0]['stat'][key]=w.GIB
            self.assertFalse(self.assess(v)['admitted'])

    def test_low_cache_no_negative_credit(self):
        s=self.value()['ancestors'][0]['stat'];s['file']=2*w.GIB
        self.assertEqual(w.file_credit(s,8*w.GIB),(0,0))

    def test_smaller_lru_counter_caps_credit(self):
        s=self.value()['ancestors'][0]['stat'];s.update(active_file=2*w.GIB,inactive_file=2*w.GIB)
        self.assertEqual(w.file_credit(s,8*w.GIB),(3*w.GIB,0))

    def test_tighter_descendant_limit_applies(self):
        v=self.value();child=copy.deepcopy(v['ancestors'][0]);child.update(path='/user.slice/child',high_bytes=90*w.GIB,max_bytes=None);v['ancestors'].append(child)
        self.assertFalse(self.assess(v)['admitted'])

    def test_unbounded_root_need_not_have_stats(self):
        v=self.value();v['ancestors'].append({'path':'/','high_bytes':None,'max_bytes':None,'current_bytes':None})
        self.assertTrue(self.assess(v)['admitted'])

    def test_uid_parent_limits_fail_closed(self):
        for field in ('uid','parent','high','max'):
            v=self.value()
            if field=='uid':v['uid']=1016
            elif field=='parent':v['ancestors'][0]['path']='/other'
            else:v['ancestors'][0][field+'_bytes']=None
            with self.assertRaises(ValueError):self.assess(v)

    def test_host_ram_guard_preserved(self):
        self.assertTrue(self.assess(host=64*w.GIB)['admitted'])
        self.assertFalse(self.assess(host=64*w.GIB-1)['admitted'])

    def test_pressure_unknown_or_active_rejected(self):
        for x in (None,float('nan')):
            v=self.value();v['ancestors'][0]['pressure']['full']['avg10']=x
            with self.assertRaises(ValueError):self.assess(v)
        v=self.value();v['ancestors'][0]['pressure']['full']['avg10']=1.01
        self.assertFalse(self.assess(v)['admitted'])

    def test_historical_high_events_do_not_veto(self):
        self.assertTrue(self.assess()['admitted'])

    def test_input_snapshot_unchanged(self):
        v=self.value();before=copy.deepcopy(v);self.assess(v);self.assertEqual(v,before)


if __name__ == '__main__':unittest.main()
