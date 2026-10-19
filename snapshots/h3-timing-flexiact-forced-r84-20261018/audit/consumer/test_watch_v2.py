import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('watch_v2',Path(__file__).with_name('watch_v2.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class PassiveWait(unittest.TestCase):
 def test_only_explicit_transports_are_transient(self):
  self.assertTrue(m.transient_status_error(subprocess.TimeoutExpired(['ssh'],10)))
  self.assertTrue(m.transient_status_error(subprocess.CalledProcessError(1,['ssh'],output=b'TimeoutError: timed out')))
  self.assertTrue(m.transient_status_error(subprocess.CalledProcessError(255,['ssh'],output=b'Connection timed out during banner exchange')))
  for text in (b'job belongs to another service instance',b'CUDA out of memory',b'actual job failed'):
   self.assertFalse(m.transient_status_error(subprocess.CalledProcessError(1,['ssh'],output=text)))

 def local_remote(self,code,timeout=120):
  out=io.StringIO()
  with contextlib.redirect_stdout(out):exec(code,{})
  return out.getvalue()

 def test_no_HTTP_during_incomplete_saved_sampling(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);run='r84_'+m.SOURCES[0]+'_seed2026101701_forced';(p/'logs').mkdir();(p/'audit/x0'/run).mkdir(parents=True)
   (p/'logs'/(run+'_job.json')).write_text(json.dumps({'status':'pending_or_running'}))
   (p/'audit/x0'/run/'manifest.json').write_text(json.dumps({'callback_count':19}))
   with patch.object(m,'REMOTE',d),patch.object(m,'remote',side_effect=self.local_remote),patch.object(subprocess,'run') as run_call:
    self.assertFalse(m.completed(m.SOURCES[0]));run_call.assert_not_called()

 def test_unsubmitted_second_run_never_calls_status(self):
  with tempfile.TemporaryDirectory() as d:
   with patch.object(m,'REMOTE',d),patch.object(m,'remote',side_effect=self.local_remote),patch.object(subprocess,'run') as run_call:
    self.assertFalse(m.completed(m.SOURCES[1]));run_call.assert_not_called()

 def test_saved_success_is_used_without_HTTP(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);run='r84_'+m.SOURCES[0]+'_seed2026101701_forced';(p/'logs').mkdir()
   (p/'logs'/(run+'_job.json')).write_text(json.dumps({'status':'success'}))
   (p/'logs'/(run+'_history.json')).write_text(json.dumps({'status':{'completed':True,'status_str':'success'}}))
   with patch.object(m,'REMOTE',d),patch.object(m,'remote',side_effect=self.local_remote),patch.object(subprocess,'run') as run_call:
    self.assertTrue(m.completed(m.SOURCES[0]));run_call.assert_not_called()

 def test_real_job_failure_stays_failure(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);run='r84_'+m.SOURCES[0]+'_seed2026101701_forced';(p/'logs').mkdir()
   (p/'logs'/(run+'_job.json')).write_text(json.dumps({'status':'error'}))
   with patch.object(m,'REMOTE',d),patch.object(m,'remote',side_effect=self.local_remote),self.assertRaises(RuntimeError):m.completed(m.SOURCES[0])

if __name__=='__main__':unittest.main()
