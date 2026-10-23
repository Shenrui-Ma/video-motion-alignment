import io,json,tempfile,unittest,contextlib
from pathlib import Path
import activate_after_finish as a
import remote_ops as ops
class Boundary(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.r=Path(self.tmp.name);self.weak='expand_short_0131_global_weak';self.native='expand_short_0131_native';self.out=self.r/'output'/self.native/'a.mp4';self.out.parent.mkdir(parents=True);self.out.write_bytes(b'');self.boot=self.r/'boot';self.boot.write_text('bootid')
  self.man={'jobs':[{'id':self.native},{'id':self.weak},{'id':'completed_current'}]}
  ops.atomic(self.r/'jobs.json',self.man);ops.atomic(self.r/'innovation_handoff/original_manifest.json',self.man)
  ops.atomic(self.r/'innovation_handoff/parked_manifest.json',{'jobs':[]});ops.atomic(self.r/'queue_state/state.json',{'jobs':{self.native:{'status':'completed'},self.weak:{'status':'submission_unknown'},'completed_current':{'status':'completed'}}})
  ops.atomic(self.r/'queue_state/results'/f'{self.native}.json',{'files':[{'path':str(self.out),'sha256':'expected'}]});ops.atomic(self.r/'innovation_handoff/reboot_abort_evidence.json',dict(submitted_before_current_boot=True,history_matches=[],queue_matches=[],output_files=[],result_exists=False,boot_id='bootid'))
 def tearDown(self):self.tmp.cleanup()
 def execute(self,ready=True):
  snap=dict(worker={'state':'exited' if ready else 'owned_alive'},service={'state':'exited'},locks={'worker':False},port_listening=False,worker_status={'event':'finished','cleanup_code':0})
  ns=dict(vars(ops));ns.update(ROOT=str(self.r),snapshot=lambda _:snap,Path=lambda x: self.boot if str(x)=='/proc/sys/kernel/random/boot_id' else Path(x))
  with contextlib.redirect_stdout(io.StringIO()):exec(a.RECONCILE,ns)
 def test_waits_without_mutation(self):
  with self.assertRaises(SystemExit) as ex:self.execute(False)
  self.assertEqual(ex.exception.code,75);self.assertEqual(json.loads((self.r/'jobs.json').read_text()),self.man)
 def test_archives_and_defers_both_losses(self):
  self.execute();state=json.loads((self.r/'queue_state/state.json').read_text())['jobs'];self.assertEqual(state[self.native]['resolution'],'output_lost_after_reboot');self.assertEqual(state[self.weak]['resolution'],'aborted_by_host_reboot');self.assertEqual(state['completed_current']['status'],'completed')
  self.assertEqual(json.loads((self.r/'jobs.json').read_text())['jobs'],[{'id':'completed_current'}]);self.assertFalse((self.r/'queue_state/results'/f'{self.native}.json').exists());self.assertTrue((self.r/'innovation_handoff/invalid_results'/f'{self.native}.json').exists())
 def test_reconciliation_retry_preserves_archive(self):
  self.execute();self.execute();p=json.loads((self.r/'innovation_handoff/parked_manifest.json').read_text());self.assertEqual(len(p['jobs']),2)
 def test_nonzero_output_requires_recovery_review(self):
  self.out.write_bytes(b'recovery candidate')
  with self.assertRaises(AssertionError):self.execute()
  self.assertTrue((self.r/'queue_state/results'/f'{self.native}.json').exists())
if __name__=='__main__':unittest.main()
