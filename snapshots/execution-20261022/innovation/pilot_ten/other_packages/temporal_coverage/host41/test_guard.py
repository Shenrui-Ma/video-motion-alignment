from pathlib import Path
import importlib.util,unittest,json,copy,tempfile,os
from unittest import mock
P=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('g',P/'coverage_pilots_handoff.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
class Checks(unittest.TestCase):
 def audit(self):
  c={'radius':2,'entropy':.5,'temporal_penalty':.25,'iterations':128,'tolerance':.0002,'min_quality_span':.001,'minimum_mean_gap':0.}
  calls=[dict(forward=f,block=b,applied=True,reason='balanced',row_error=1e-7,column_error=1e-7,quality_span=.5,transport_fraction=1.) for f in range(20) for b in range(50)]
  return dict(schema='h3-temporal-coverage-v1',status='sampling',completed_forward_calls=20,completed_calls=1000,native_override_calls=1000,alpha=.25,step_interval_half_open=[0,20],block_interval_half_open=[0,50],coverage_config=c,coverage_calls=calls,routed_calls=1000,forward_summaries=[{'layer_stats':[{'finite':True,'correction_ratio':.03} for _ in range(50)]} for _ in range(20)])
 def test_target(self):self.assertEqual(len(g.merge_manifest(g.REQ['base'],g.REQ['pilots'])['jobs']),48)
 def test_all_ten_gate(self):self.assertEqual(len(g.REQ['prerequisite_ids']),10);self.assertFalse(g.preceding_status({},g.REQ['prerequisite_ids']))
 def test_failed_prerequisite(self):
  with self.assertRaises(RuntimeError):g.preceding_status({'x':{'status':'failed'}},['x'])
 def test_valid_audit(self):self.assertEqual(g.verify_coverage_audit(self.audit())['effective_routed_calls'],1000)
 def test_no_effect_rejected(self):
  a=self.audit();a['routed_calls']=0
  with self.assertRaises(AssertionError):g.verify_coverage_audit(a)
 def test_nonfinite_rejected(self):
  a=self.audit();a['forward_summaries'][0]['layer_stats'][0]['correction_ratio']=float('nan')
  with self.assertRaises(AssertionError):g.verify_coverage_audit(a)
 def test_budget_error_rejected(self):
  a=self.audit();a['coverage_calls'][0]['column_error']=.1
  with self.assertRaises(AssertionError):g.verify_coverage_audit(a)
 def test_exact_graph(self):
  D=P.parents[2]/'direction_package/host41'
  for j in g.REQ['pilots']['jobs']:
   d=json.loads((P/j['graph']).read_text());o=json.loads((D/'graphs'/j['graph'].split('/')[-1].replace('temporal_coverage','direction_gated')).read_text())
   for key in set(d)-{'14','50'}:self.assertEqual(d[key],o[key])
   self.assertEqual(d['50']['inputs']['step_end'],20);self.assertEqual(d['50']['inputs']['alpha'],.25);self.assertEqual(d['50']['inputs']['model'],['41',0])
 def process(self,state='Z',ticks='12'):
  tmp=tempfile.TemporaryDirectory();root=Path(tmp.name);proc=root/'123';proc.mkdir();(proc/'stat').write_text('123 (child) '+' '.join([state,str(os.getpid())]+['0']*17+[ticks]));(proc/'cmdline').write_bytes(b'');return tmp,root
 def test_matching_zombie_exited(self):
  tmp,root=self.process()
  with tmp:self.assertEqual(g.identity({'pid':123,'start_ticks':'12'},'worker',root)['state'],'exited')
 def test_mismatched_zombie_stays_mismatch(self):
  tmp,root=self.process()
  with tmp:self.assertEqual(g.identity({'pid':123,'start_ticks':'13'},'worker',root)['state'],'identity_mismatch')
 def test_wrong_uid_stays_mismatch(self):
  tmp,root=self.process()
  with tmp:self.assertEqual(g.identity({'pid':123,'start_ticks':'12'},'worker',root,os.getuid()+1)['state'],'identity_mismatch')
 def test_reap_only_nonblocking(self):
  with mock.patch.object(g.os,'waitpid',side_effect=[(123,0),(0,0)]) as wait:g.reap_finished_children();self.assertEqual(wait.call_count,2);wait.assert_called_with(-1,os.WNOHANG)
if __name__=='__main__':unittest.main()
