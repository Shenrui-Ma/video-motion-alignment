import json,tempfile,unittest,copy
from pathlib import Path
from trajectory_gate import bind,sha
class Gate(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.r=Path(self.tmp.name);r=self.r
  def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x))
  self.put=put;self.tid='live_phase_short0358_native_20261023'
  cp=r/'contracts/native_contract.json';self.c={'trajectory_id':self.tid,'case':'short_0358','method':'native','sigmas_video':list(range(21)),'noise_tensor_sha256':'a'*64};put(cp,self.c)
  put(r/'graphs/native_graph.json',{'1':{'class_type':'test'}})
  self.op=r/'audit/live_phase'/self.tid/'OBSERVATION.json';caps=[]
  for step in [9,19]:
   sp=self.op.parent/f'state{step}.pt';qp=self.op.parent/f'qk{step}.pt';sp.parent.mkdir(parents=True,exist_ok=True);sp.write_bytes(str(step).encode());qp.write_bytes(('qk'+str(step)).encode())
   fi={'trajectory_id':self.tid,'case':'short_0358','method':'native','science_contract_sha256':sha(cp),'step_zero_based':step,'layer_zero_based':25,'state_file_sha256':sha(sp),'sample_sigmas_video':self.c['sigmas_video'],'noise_sha256':'a'*64,'packed_x':{'finite':True,'dtype':'torch.float32'},'raw_packed_x0':{'finite':True,'dtype':'torch.float32'}}
   caps.append({'step_zero_based':step,'layer_zero_based':25,'state_file':str(sp),'state_file_sha256':sha(sp),'qk_file':str(qp),'qk_sha256':sha(qp),'forward_identity':fi})
  self.o={'status':'complete','science_contract_sha256':sha(cp),'callback_count':20,'actual_model_forward_count':20,'completed_blocks':1000,'extra_model_forward_calls':0,'trajectory_id':self.tid,'case':'short_0358','method':'native','original_result_returned_without_copy':True,'final_raw_result':{'finite':True},'sampling_seconds':20,'sample_sigmas_video':self.c['sigmas_video'],'noise':{'sha256':'a'*64},'captures':caps};put(self.op,self.o)
  vp=r/'output'/self.tid/'result.mp4';vp.parent.mkdir(parents=True);vp.write_bytes(b'fixture')
  self.h={'status':{'completed':True,'status_str':'success'},'prompt':[0,'id',{'1':{'class_type':'test'}}],'outputs':{'14':{'images':[{'type':'output','subfolder':self.tid,'filename':'result.mp4'}]}}}
 def test_good(self):self.assertTrue(bind(self.r,'native',self.h,{})['passed'])
 def test_missing_callbacks(self):
  self.o['callback_count']=19;self.put(self.op,self.o)
  with self.assertRaises(AssertionError):bind(self.r,'native',self.h,{})
 def test_extra_forward(self):
  self.o['extra_model_forward_calls']=1;self.put(self.op,self.o)
  with self.assertRaises(AssertionError):bind(self.r,'native',self.h,{})
 def test_capture_changed(self):
  Path(self.o['captures'][0]['qk_file']).write_bytes(b'changed')
  with self.assertRaises(AssertionError):bind(self.r,'native',self.h,{})
 def test_wrong_forward_method(self):
  self.o['captures'][0]['forward_identity']['method']='global_weak';self.put(self.op,self.o)
  with self.assertRaises(AssertionError):bind(self.r,'native',self.h,{})
 def test_output_other_trajectory(self):
  self.h['outputs']['14']['images'][0]['subfolder']='other'
  with self.assertRaises(AssertionError):bind(self.r,'native',self.h,{})
 def test_nan_time(self):
  self.o['sampling_seconds']=float('nan');self.put(self.op,self.o)
  with self.assertRaises(AssertionError):bind(self.r,'native',self.h,{})
if __name__=='__main__':unittest.main()
