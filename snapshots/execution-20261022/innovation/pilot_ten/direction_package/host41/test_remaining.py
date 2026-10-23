import contextlib,hashlib,io,json,math,sys,tempfile,unittest
from pathlib import Path
import activate_remaining as module
from unittest.mock import patch
from types import SimpleNamespace
class GuardTests(unittest.TestCase):
 def fixture(self,root):
  state={'jobs':{}}
  for task in ['short_0252','short_0358']:
   jid='innov41_'+task+'_direction_gated';attempt=jid+'__a1'
   state['jobs'][jid]={'status':'completed','attempt_id':attempt}
   data=b'test output';video=root/(jid+'.mp4');video.write_bytes(data)
   docs={f'audit/direction/{attempt}.json':{'routed_calls':1000,'native_override_calls':1000,'direction_forward_summaries':[{}]*20,'intermediate_vae_decode_calls':0,'full_dit_forward_calls_added':0,'cumulative_applied_correction_energy':1},f'audit/timing/{attempt}.json':{'steps':[{'seconds':2}]*20},f'queue_state/results/{jid}.json':{'files':[{'path':str(video),'sha256':hashlib.sha256(data).hexdigest()}]}}
   for name,value in docs.items():p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))
  p=root/'queue_state/state.json';p.write_text(json.dumps(state));return state
 def runcheck(self,root):
  out=io.StringIO()
  with contextlib.redirect_stdout(out):exec(module.CHECK,dict(Path=Path,ROOT=str(root),read=lambda p:json.loads(p.read_text()),json=json,math=math,hashlib=hashlib,sys=sys))
  return json.loads(out.getvalue())
 def test_ssh_transport_retryable(self):
  with patch.object(module.subprocess,'run',return_value=SimpleNamespace(returncode=255,stderr='banner timeout')):
   self.assertEqual(module.remote('read only')['status'],'not_ready')
 def test_valid_pair(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);self.fixture(r);self.assertEqual(self.runcheck(r)['status'],'pilots_verified')
 def test_partial_waits_and_failed_raises(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);s=self.fixture(r);k=list(s['jobs'])[-1];s['jobs'][k]['status']='submitted';p=r/'queue_state/state.json';p.write_text(json.dumps(s))
   with self.assertRaises(SystemExit) as e:self.runcheck(r)
   self.assertEqual(e.exception.code,75)
   s['jobs'][k]['status']='failed';p.write_text(json.dumps(s))
   with self.assertRaises(RuntimeError):self.runcheck(r)
 def test_corrupt_output_fails(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);self.fixture(r);next(r.glob('*.mp4')).write_bytes(b'')
   with self.assertRaises(AssertionError):self.runcheck(r)
 def test_no_intervention_fails(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);self.fixture(r);p=next((r/'audit/direction').glob('*.json'));a=json.loads(p.read_text());a['cumulative_applied_correction_energy']=0;p.write_text(json.dumps(a))
   with self.assertRaises(AssertionError):self.runcheck(r)
if __name__=='__main__':unittest.main()
