import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import followup_cpu_watch as watch

class Watch(unittest.TestCase):
 def test_busy_retries_then_returns_actual(self):
  rows=[SimpleNamespace(returncode=75,stdout='CPU_LOCK_BUSY_OR_ONLINE_PRIORITY'),SimpleNamespace(returncode=0,stdout=json.dumps({'status':'busy'})),SimpleNamespace(returncode=0,stdout=json.dumps({'status':'case_ready'}))]
  with patch.object(watch,'invoke',side_effect=rows),patch.object(watch.time,'sleep') as pause:
   _,v=watch.retry_busy(['unused'])
   self.assertEqual(v,{'status':'case_ready'});self.assertEqual(pause.call_count,2)
 def test_technical_exception_does_not_retry(self):
  with patch.object(watch,'invoke',side_effect=RuntimeError('actual failure')),patch.object(watch.time,'sleep') as pause:
   with self.assertRaises(RuntimeError):watch.retry_busy(['unused'])
   pause.assert_not_called()
 def test_completed_fixed_run_returns(self):
  state={'status':'pending_or_running','completed':['wanted'],'current':'next'}
  with patch.object(watch,'invoke',return_value=SimpleNamespace(stdout=json.dumps(state))),patch.object(watch.time,'sleep') as pause:
   self.assertEqual(watch.wait_completed('wanted'),state);pause.assert_not_called()
 def test_failed_producer_hard_stops(self):
  with patch.object(watch,'invoke',return_value=SimpleNamespace(stdout=json.dumps({'status':'failed'}))):
   with self.assertRaises(RuntimeError):watch.wait_completed('wanted')

if __name__=='__main__':unittest.main()
