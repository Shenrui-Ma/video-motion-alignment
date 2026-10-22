import json,os,shutil,subprocess,sys,tempfile,time,unittest
from pathlib import Path

class ExactPidGateTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  shutil.copyfile(Path(__file__).with_name('launch_tracking_gate.py'),self.root/'launch_tracking_gate.py')
  (self.root/'ive_mf_adapter.py').write_text('# CPU fixture\n')
  (self.root/'run_tracks.py').write_text('import json,os\nfrom pathlib import Path\nPath(__file__).with_name("executed.json").write_text(json.dumps({"pid":os.getpid()}))\n')
  for name in ['manifest.json','selection.json']:(self.root/name).write_text('{}')
  self.proc=None
 def tearDown(self):
  if self.proc and self.proc.poll() is None:self.proc.terminate();self.proc.wait(timeout=5)
  self.temp.cleanup()
 def start(self):
  self.proc=subprocess.Popen([sys.executable,str(self.root/'launch_tracking_gate.py'),'--control',str(self.root/'control'),'--','--input-manifest',str(self.root/'manifest.json'),'--selection',str(self.root/'selection.json')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
  ready=self.root/'control/ready.json';deadline=time.monotonic()+10
  while not ready.exists() and time.monotonic()<deadline:
   if self.proc.poll() is not None:self.fail(self.proc.communicate()[1])
   time.sleep(.02)
  self.assertTrue(ready.exists());record=json.loads(ready.read_text());self.assertEqual(record['pid'],self.proc.pid);self.assertFalse((self.root/'executed.json').exists());return record
 def finish(self,record):
  (self.root/'control/go.json').write_text(json.dumps(record));out,err=self.proc.communicate(timeout=10);return self.proc.returncode,err
 def test_matching_gate_enters_runner_in_same_pid(self):
  r=self.start();code,err=self.finish(r);self.assertEqual(code,0,err);self.assertEqual(json.loads((self.root/'executed.json').read_text())['pid'],r['pid'])
 def test_other_pid_cannot_start_runner(self):
  r=self.start();r['pid']+=1;code,err=self.finish(r);self.assertNotEqual(code,0);self.assertFalse((self.root/'executed.json').exists())
 def test_input_mutation_after_ready_cannot_start_runner(self):
  r=self.start();(self.root/'manifest.json').write_text('{"changed":true}');code,err=self.finish(r);self.assertNotEqual(code,0);self.assertFalse((self.root/'executed.json').exists())

if __name__=='__main__':unittest.main()
