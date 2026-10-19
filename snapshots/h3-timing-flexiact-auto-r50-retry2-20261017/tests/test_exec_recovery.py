import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('candidate_transport',Path(__file__).resolve().parents[1]/'extensions/H3AutomaticWindowRouter/transport.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)

class FakeClock:
 def __init__(self):self.time=0
 def now(self):return self.time
 def sleep(self,seconds):self.time+=max(seconds,.25)

class Child:
 pid=1234;returncode=None
 def poll(self):return self.returncode

class Recovery(unittest.TestCase):
 def setUp(self):
  self.command=['/usr/bin/python3','/test.py','--value','two words']
  self.expected={'pid':1234,'uid':os.getuid(),'start_ticks':456,'cmdline_sha256':hashlib.sha256(b'\0'.join(os.fsencode(v) for v in self.command)+b'\0').hexdigest()}
 def bind(self,lookup):
  clock=FakeClock()
  return t.bind_launched_child(Child(),self.command,lookup=lookup,clock=clock.now,sleep=clock.sleep)
 def test_empty_then_actual_command(self):
  values=iter([None,self.expected]);self.assertEqual(self.bind(lambda pid:next(values)),self.expected)
 def test_fork_parent_command_then_actual_command(self):
  values=iter([dict(self.expected,cmdline_sha256='parent-command'),self.expected])
  self.assertEqual(self.bind(lambda pid:next(values)),self.expected)
 def test_wrong_command_same_generation_never_accepted(self):
  with self.assertRaisesRegex(ValueError,'complete expected argv'):
   self.bind(lambda pid:dict(self.expected,cmdline_sha256='wrong'))
 def test_changed_process_generation_never_accepted(self):
  values=iter([dict(self.expected,cmdline_sha256='parent'),dict(self.expected,start_ticks=457)])
  with self.assertRaisesRegex(ValueError,'generation changed'):self.bind(lambda pid:next(values))
 def test_empty_proc_cmdline_not_live_identity(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'1234';p.mkdir()
   tail=['S']+['0']*18+['456']
   (p/'stat').write_text('1234 (python) '+' '.join(tail));(p/'cmdline').write_bytes(b'')
   with patch.object(t,'Path',side_effect=lambda path:root if path=='/proc' else Path(path)):
    self.assertIsNone(t.identity(1234))
    (p/'cmdline').write_bytes(b'python\0test.py\0')
    self.assertEqual(t.identity(1234)['cmdline_sha256'],hashlib.sha256(b'python\0test.py\0').hexdigest())
 def test_primary_error_survives_cleanup_error(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);d=root/'audit/observations/step0';d.mkdir(parents=True);marker=d/'marker.json'
   def start(*args,**kwargs):
    marker.write_text(json.dumps({'schema':'h3-child-execution-start-v1','identity':dict(self.expected,cmdline_sha256='wrong'),'started_monotonic':0}))
    return Child()
   with patch.object(t,'ROOT',root),patch.object(t,'alive',return_value=True),patch.object(t,'bind_launched_child',return_value=self.expected),patch.object(t.subprocess,'Popen',side_effect=start),patch.object(t,'terminate_owned',side_effect=subprocess.TimeoutExpired('decoder',10)):
    with self.assertRaisesRegex(ValueError,'execution marker identity differs'):
     t.run_child(self.command,{},d,'decoder',60,self.expected,execution_started_path=marker,execution_timeout=60)
   exit_record=json.loads((d/'decoder.exit.json').read_text())
   self.assertIn('TimeoutExpired',exit_record['cleanup_error'])

if __name__=='__main__':unittest.main()
