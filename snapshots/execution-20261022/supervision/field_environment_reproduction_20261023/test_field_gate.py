import unittest,sys,json,copy,importlib.util,tempfile,hashlib
from pathlib import Path
from unittest.mock import patch
D=Path(__file__).parent;E=D.parents[1];sys.path.insert(0,str(E/'innovation/adaptive_strength_20261023/batch'))
from field_gate import first_forward,backend_check,verify_inputs
class Gates(unittest.TestCase):
 def backend(self):
  ops={b+'.'+o:{'registry_resolves_wrapper':True,'attempted_calls':0,'successful_calls':0,'failed_calls':0} for b in ['cuda','triton','eager'] for o in ['int8_linear','w4a8_int8_linear']}
  ops['triton.int8_linear'].update(attempted_calls=4000,successful_calls=4000)
  return {'pid':42,'logging_errors':[],'operations':ops}
 def test_missing_backend(self):
  b=self.backend();del b['operations']['eager.int8_linear'];self.assertRaises(AssertionError,backend_check,b,42,True)
 def test_complete_backend(self):self.assertIn('triton.int8_linear',backend_check(self.backend(),42,True))
 def test_wrong_pid(self):self.assertRaises(AssertionError,backend_check,self.backend(),41,True)
 def test_failed_kernel(self):b=self.backend();b['operations']['triton.int8_linear']['failed_calls']=1;self.assertRaises(AssertionError,backend_check,b,42,True)
 def test_incomplete(self):b=self.backend();b['operations']['triton.int8_linear']['successful_calls']=3999;self.assertRaises(AssertionError,backend_check,b,42,True)
 def test_wrong_backend(self):b=self.backend();b['operations']['cuda.int8_linear']['attempted_calls']=1;self.assertRaises(AssertionError,backend_check,b,42,True)
 def test_first_waits(self):self.assertIsNone(first_forward({'feature_forward_summaries':[]}))
 def test_first_shape(self):
  d={'feature_forward_summaries':[{'forward':0,'layers':[{'forward':0,'block':x,'alpha':[.25]} for x in range(50)]}]}
  with patch('field_gate.check_layer') as c:self.assertTrue(first_forward(d)['finite']);self.assertEqual(c.call_count,50)
 def test_duplicate_block(self):
  d={'feature_forward_summaries':[{'forward':0,'layers':[{'forward':0,'block':0,'alpha':[.25]}]*50}]};self.assertRaises(AssertionError,first_forward,d)
 def test_first_not_prior(self):
  d={'feature_forward_summaries':[{'forward':0,'layers':[{'forward':0,'block':x,'alpha':[.3]} for x in range(50)]}]}
  with patch('field_gate.check_layer'):self.assertRaises(AssertionError,first_forward,d)
 def test_single_attempt_supervisor(self):
  s=(D/'field_supervisor.py').read_text();self.assertIn("assert not (d/'SUBMISSION_INTENT.json').exists()",s);self.assertIn("for method in ['temporal_gain_field']",s);self.assertNotIn("for method in ['native'",s)
class InputChecks(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.r=Path(self.t.name)/'run';self.r.mkdir();(self.r/'graphs').mkdir();(self.r.parent/'core').mkdir()
  for n in ['manifest','payload','noise','model']:(self.r/n).write_bytes(n.encode())
  (self.r.parent/'core/code.py').write_bytes(b'code');h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();st=(self.r/'model').stat()
  x={'cache_manifest_sha256':h(self.r/'manifest'),'payloads':[{'path':str(self.r/'payload'),'sha256':h(self.r/'payload')}],'noise_file_sha256':h(self.r/'noise'),'core_source_shas':{'code.py':h(self.r.parent/'core/code.py')},'model_current_stat_matches_full_sha':{'path':str(self.r/'model'),'inode':st.st_ino,'mtime_ns':st.st_mtime_ns,'bytes':st.st_size}}
  (self.r/'INPUT_IDENTITY.json').write_text(json.dumps(x));(self.r/'graphs/temporal_gain_field_graph.json').write_text(json.dumps({'5':{'inputs':{'cache_manifest':str(self.r/'manifest')}},'6':{'inputs':{'noise_file':str(self.r/'noise')}}}))
 def tearDown(self):self.t.cleanup()
 def test_exact(self):self.assertTrue(verify_inputs(self.r))
 def test_noise_change(self):(self.r/'noise').write_bytes(b'changed');self.assertRaises(AssertionError,verify_inputs,self.r)
 def test_payload_change(self):(self.r/'payload').write_bytes(b'changed');self.assertRaises(AssertionError,verify_inputs,self.r)
 def test_model_change(self):(self.r/'model').write_bytes(b'changed');self.assertRaises(AssertionError,verify_inputs,self.r)
if __name__=='__main__':unittest.main()
