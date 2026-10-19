import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('wd',Path(__file__).with_name('watchdog_v2.py'));w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
L=dict(max_service_seconds=43200,job_timeout_seconds=14400,idle_hold_seconds=1800)
EMPTY=dict(queue_running=[],queue_pending=[])
BUSY=dict(queue_running=[[0,'p']],queue_pending=[])
class Timers(unittest.TestCase):
 def initial(self):return w.initialize({'started_unix':1000},4600,10000)
 def test_original_service_elapsed_is_deducted(self):self.assertEqual(self.initial()['started'],6400)
 def test_unknown_900_seconds_does_not_stop(self):self.assertIsNone(w.update_reason(self.initial(),13000,None,L))
 def test_total_deadline_still_expires_during_unknown(self):self.assertEqual(w.update_reason(self.initial(),49600,None,L),'bounded_service_lifetime_expired')
 def test_original_active_job_deadline_survives_unknown(self):
  s=self.initial();s.update(active_run='r',active_since=7000)
  self.assertIsNone(w.update_reason(s,21000,None,L));self.assertEqual(s['active_since'],7000)
  self.assertEqual(w.update_reason(s,21400,None,L),'bounded_job_timeout')
 def test_known_active_start_reconstructed_not_restart(self):
  s=self.initial();w.update_reason(s,15000,None,L,{'active_run':'r','active_since':9000});self.assertEqual(s['active_since'],9000)
 def test_same_active_run_cannot_move_clock_forward(self):
  s=self.initial();s.update(active_run='r',active_since=7000)
  w.update_reason(s,11000,None,L,{'active_run':'r','active_since':7500});self.assertEqual(s['active_since'],7000)
 def test_observed_busy_with_old_terminal_history_preserves_clock(self):
  s=self.initial();w.update_reason(s,10000,BUSY,L,{'all_known_terminal':True})
  w.update_reason(s,11000,BUSY,L,{'all_known_terminal':True});self.assertEqual(s['active_since'],10000)
 def test_unknown_cannot_accumulate_idle(self):
  s=self.initial();w.update_reason(s,10000,EMPTY,L);w.update_reason(s,11000,None,L)
  self.assertIsNone(s['idle_since']);self.assertIsNone(w.update_reason(s,14000,EMPTY,L));self.assertEqual(s['idle_since'],14000)
 def test_observed_idle_eventually_expires(self):
  s=self.initial();w.update_reason(s,10000,EMPTY,L);self.assertEqual(w.update_reason(s,11800,EMPTY,L),'bounded_idle_review_expired')
 def test_empty_queue_does_not_erase_accepted_job(self):
  s=self.initial();s.update(active_run='r',active_since=9000);w.update_reason(s,11000,EMPTY,L)
  self.assertEqual(s['active_since'],9000);self.assertIsNone(s['idle_since'])
 def test_confirmed_success_starts_idle_hold(self):
  s=self.initial();s.update(active_run='r',active_since=9000);w.update_reason(s,11000,EMPTY,L,{'all_known_terminal':True})
  self.assertIsNone(s['active_since']);self.assertEqual(s['idle_since'],11000)
 def test_actual_failure_remains_terminal(self):self.assertEqual(w.update_reason(self.initial(),11000,None,L,{'failed':True}),'actual_registered_job_failure')
 def test_replacement_owner_is_not_matching(self):self.assertFalse(w.owner_matches({'pid':1,'identity':{'start':3}},{'pid':1,'identity':{'start':2}}))
 def test_future_start_rejected(self):
  with self.assertRaises(ValueError):w.initialize({'started_unix':5000},4000,10000)
if __name__=='__main__':unittest.main()
