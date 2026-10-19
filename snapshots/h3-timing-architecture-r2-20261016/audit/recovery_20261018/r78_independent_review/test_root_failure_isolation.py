"""Independent lifecycle regression: fake preCUDA mismatch and receipt I/O failure."""
from pathlib import Path
import hashlib,importlib.util,io,json,subprocess,sys,tempfile,unittest
from unittest.mock import Mock,patch
ROOT=Path('/Users/researcher/DevProjects/h3-timing-local-edit-protocol-r78-20261018')
SCRIPT=ROOT/'audit/root_run_pair.py'
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('r78_root_lifecycle_review',SCRIPT)
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class RootFailureIsolation(unittest.TestCase):
 def scenario(self,fail_receipt,fail_cleanup):
  with tempfile.TemporaryDirectory(prefix='r78-lifecycle-mock-') as d:
   root=Path(d)
   for n in ['audit','configs','processes']:(root/n).mkdir()
   owner={'pid':111,'identity':{'uid':501,'start_ticks':'10','cmdline':'mock'},'gpu_uuid':'mockgpu','port':8546}
   ready={'pid':111,'identity':{'mismatch':True},'supervisor':{'pid':222,'identity':{'start_ticks':'20'}}}
   def subproc(argv,**kwargs):
    if 'scripts/launch_remote.py' in argv:
     (root/'processes/service.json').write_text(json.dumps(owner));(root/'processes/cuda_gate_ready.json').write_text(json.dumps(ready))
    return subprocess.CompletedProcess(argv,0)
   def write(path,value):
    if fail_receipt and Path(path).name=='FAILURE.json':raise OSError('injected receipt write failure')
    Path(path).write_text(json.dumps(value))
   stop=Mock(side_effect=RuntimeError('secondary cleanup failure') if fail_cleanup else None)
   error=None
   with patch.object(runner,'ROOT',root),patch.object(runner.service,'RUNTIME',{'remote_root':str(root)}),patch.object(runner,'live_peers',return_value=[]),patch.object(runner.service,'write_json',side_effect=write),patch.object(runner.service,'check_admission'),patch.object(runner.service,'compute_processes',return_value=[]),patch.object(runner.subprocess,'run',side_effect=subproc),patch.object(runner.service,'assert_owned'),patch.object(runner.service,'external_identity',return_value={'actual':True}),patch.object(runner.service,'current_identity',return_value=owner['identity']),patch.object(runner.service,'stop',stop),patch.object(sys,'argv',[str(SCRIPT),'--execute','--attempt','mock']):
    try:runner.main()
    except BaseException as e:error=e
   self.assertIsInstance(error,ValueError)
   self.assertIn('preCUDA child identity mismatch',str(error))
   stop.assert_called_once_with(expected_record=owner)
 def test_receipt_failure_does_not_skip_cleanup(self):self.scenario(True,False)
 def test_cleanup_failure_preserves_primary(self):self.scenario(False,True)
 def test_receipt_and_cleanup_failure_preserve_primary(self):self.scenario(True,True)
if __name__=='__main__':
 before=hashlib.sha256(SCRIPT.read_bytes()).hexdigest();s=io.StringIO();r=unittest.TextTestRunner(stream=s,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RootFailureIsolation));after=hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
 here=Path(__file__).parent;(here/'INDEPENDENT_FAILURE_TESTS.log').write_text(s.getvalue())
 rec={'passed':r.wasSuccessful() and before==after,'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'script_sha256':before,'source_unchanged_during_test':before==after,'real_subprocesses':0,'real_signals':0,'GPU_calls':0};(here/'INDEPENDENT_FAILURE_TESTS.json').write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps(rec));sys.exit(0 if rec['passed'] else 1)
