import copy,json,shlex,sys,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import watch
import test_consume
class ReceiptTests(unittest.TestCase):
 def fixture(self):
  _,g=test_consume.ConsumerContract().fixture();owner={'pid':123,'identity':{'uid':1,'start_ticks':'456','cmdline':'own'},'gpu_uuid':'GPU-REDACTED','port':8548}
  return {'phase':'COMPLETE','start':{'owner':owner,'run_id':watch.RUN,'single_service_trial':True},'current_owner':owner,'start_sha256':'start','gate_sha256':'gate','gate':g,'complete':{'passed':True,'run_id':watch.RUN,'GPU_released':True,'fitness_submitted':False,'pair_gate_sha256':'gate'},'release':{'passed':True,'owner':owner,'process_absent':True,'CUDA_allocation_absent':True}}
 def test_success_requires_actual_pair_and_release(self):self.assertEqual(watch.validate(self.fixture(),'start'),'start')
 def test_changed_start_rejected(self):
  with self.assertRaises(ValueError):watch.validate(self.fixture(),'old')
 def test_changed_owner_rejected(self):
  p=self.fixture();p['current_owner']=dict(p['current_owner'],pid=321)
  with self.assertRaises(ValueError):watch.validate(p,'start')
 def test_failed_release_or_gate_rejected(self):
  for kind in ['release','gate']:
   p=self.fixture();p[kind]['passed']=False
   with self.assertRaises(ValueError):watch.validate(p,'start')
 def test_root_failure_terminal(self):
  p=self.fixture();p.update(phase='ROOT_FAILURE',failure={'error':'test'})
  with self.assertRaises(RuntimeError):watch.validate(p,'start')
 def test_missing_start_pending(self):self.assertIsNone(watch.validate({'phase':'WAIT_START'}))
 def test_remote_code_bound_and_no_http(self):
  with patch.object(watch.subprocess,'check_output',return_value=b'{"phase":"WAIT_START"}\n') as call:watch.observe()
  command=call.call_args.args[0];code=shlex.split(command[-1])[-1]
  compile(code,'<remote>','exec');self.assertIn(watch.ATTEMPT,code);self.assertIn(watch.RUN,code);self.assertIn(watch.SOURCE,code)
  self.assertNotIn('urlopen',code);self.assertNotIn('job.py',code)
if __name__=='__main__':unittest.main()
