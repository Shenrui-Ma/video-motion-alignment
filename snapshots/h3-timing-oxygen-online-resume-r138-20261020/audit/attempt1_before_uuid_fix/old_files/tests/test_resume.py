import ast,copy,json,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
from H3AutomaticWindowRouter import resume_state as rs
from H3AutomaticWindowRouter import transport as t

class Recovery(unittest.TestCase):
 def setup_replay(self):
  r=object.__new__(rs.ResumeState);r.start=9;r.replayed_callbacks=[];r.first_restored_native_checked=False
  grid=torch.linspace(1,0,21);x=torch.tensor([[[.3,.7,-.2,.9]]]);initial=x.clone();bs={};steps=[];endpoints={}
  for i in range(9):
   name='full' if i in (1,3,4) else 'native';den=x*.2+.03;endpoints[i]=den.clone()
   sig=rs.readout.tensor_signature(x);bs[i,'native']={'same_input':sig};bs[i,name]=dict(bs[i,'native'],file=str(i),raw_stream_signatures=[rs.readout.tensor_signature(q) for q in den.split(2,-1)])
   steps.append({'selected_branch':name});x=rs.euler_update(x,den,grid,i)
  r.old_branches=bs;r.old={'counterfactual':{'steps':steps}};r.state9=x.clone()
  r.state=SimpleNamespace(raw=lambda v:list(v.split(2,-1)),audit={'counterfactual':{'resume':{}}})
  return r,grid,initial,endpoints
 def test_archival_prefix_has_zero_predictions_and_restores_exact_state(self):
  r,grid,x,ends=self.setup_replay();calls=[];callbacks=[]
  def callback(v):
   callbacks.append(v['i'])
   if v['i']<9:r.replay_callback(v['i'],v['denoised'],v['x'],20)
  def original(model,current,sigmas,extra_args=None,callback=None,disable=None,**opts):
   self.assertTrue(torch.equal(current,r.state9));self.assertTrue(torch.equal(sigmas,grid[9:]))
   for i in range(len(sigmas)-1):
    calls.append(i+9);den=current*.2+.03;callback({'i':i,'x':current,'denoised':den});current=rs.euler_update(current,den,sigmas,i)
   return current
  with patch.object(rs,'packed_endpoint',side_effect=lambda b:ends[int(b['file'])]):
   r.sampler_function(original)(None,x,grid,callback=callback)
  self.assertEqual(calls,list(range(9,20)));self.assertEqual(callbacks,list(range(20)));self.assertTrue(r.state.audit['counterfactual']['resume']['prefix_reconstruction_exact'])
 def test_changed_prefix_noisy_state_rejected_before_model(self):
  r,grid,x,ends=self.setup_replay();x=x+1e-6
  with patch.object(rs,'packed_endpoint',side_effect=lambda b:ends[int(b['file'])]),self.assertRaisesRegex(ValueError,'prefix Euler'):
   r.sampler_function(lambda *a,**kw:self.fail('model called'))(None,x,grid,callback=lambda _:None)
 def test_changed_saved_state9_rejected(self):
  r,grid,x,ends=self.setup_replay();r.state9+=1e-5
  def cb(v):r.replay_callback(v['i'],v['denoised'],v['x'],20)
  with patch.object(rs,'packed_endpoint',side_effect=lambda b:ends[int(b['file'])]),self.assertRaisesRegex(ValueError,'full prefix'):
   r.sampler_function(lambda *a,**kw:self.fail('model called'))(None,x,grid,callback=cb)
 def test_restored_native_requires_same_input_and_endpoint(self):
  r,_,_,_=self.setup_replay();old={'physical_index':9,'branch':'native','same_input':{'sha256':'a'},'normalized_stream_signatures':['v','a']};r.old_branches[9,'native']=old
  r.check_native(copy.deepcopy(old));self.assertTrue(r.first_restored_native_checked)
  for key in ('same_input','normalized_stream_signatures'):
   wrong=dict(old);wrong[key]='bad'
   with self.assertRaises(ValueError):r.check_native(wrong)
 def test_actual_nfe_includes_discarded_prediction(self):
  r,_,_,_=self.setup_replay();r.first_restored_native_checked=True;c=r.state.audit['counterfactual'];c['branches']=[{'physical_index':i} for i in range(20)]+[{'physical_index':i} for i in (1,3,4,10)];c['resume']['old_actual_executed_model_nfe']=13
  r.finish();self.assertEqual(c['resume']['logical_model_nfe'],24);self.assertEqual(c['resume']['actual_new_model_nfe'],12);self.assertEqual(c['resume']['actual_all_generations_model_nfe'],25)
 def test_original_frozen_algorithm_bytes(self):
  old=json.loads((ROOT/'audit/R133_FROZEN_SOURCE.json').read_text())
  files=old.get('files',old.get('source_manifest',{}).get('files',{}))
  if not files:files=json.loads((ROOT.parent/'h3-timing-oxygen-online-r133-20261020/deploy_manifest.json').read_text())['files']
  for rel in ['extensions/H3AutomaticWindowRouter/automatic_window_policy.py','extensions/H3AutomaticWindowRouter/selector.py','extensions/H3AutomaticWindowRouter/delayed_window_policy.py','extensions/H3AutomaticWindowRouter/dynamic_support.py','extensions/H3TemporalRouter/core.py','scripts/scan_current_pose.py','scripts/arm_features.py']:
   self.assertEqual(t.sha(ROOT/rel),files[rel]['sha256'])

class DecoderSelection(unittest.TestCase):
 def test_busy_first_card_chooses_next_without_model_changes(self):
  seen=[]
  def check(parent,uuid):
   seen.append(uuid)
   if uuid==t.DECODER_UUIDS[0]:raise t.ResourceUnavailable('busy',{})
   return {'uuid':uuid}
  result=t.wait_decoder_admission({},check=check,is_alive=lambda _:True)
  self.assertEqual(seen,list(t.DECODER_UUIDS[:2]));self.assertEqual(result['uuid'],t.DECODER_UUIDS[1])
 def test_fixed_child_does_not_silently_switch_cuda_device(self):
  seen=[];now=[0.]
  def check(parent,uuid):seen.append(uuid);raise t.ResourceUnavailable('busy',{})
  with self.assertRaises(TimeoutError):t.wait_decoder_admission({},t.DECODER_UUIDS[2],timeout=2,clock=lambda:now[0],sleep=lambda v:now.__setitem__(0,now[0]+v),check=check,is_alive=lambda _:True)
  self.assertEqual(set(seen),{t.DECODER_UUIDS[2]})
 def test_identity_failure_is_never_treated_as_busy(self):
  with self.assertRaises(t.AdmissionIntegrityError):t.wait_decoder_admission({},check=lambda *a:(_ for _ in ()).throw(t.AdmissionIntegrityError('stale',{})),is_alive=lambda _:True)
 def test_preserved_gpu5_and_main_not_candidates(self):
  self.assertEqual(len(set(t.DECODER_UUIDS)),4);self.assertNotIn(t.MAIN_UUID,t.DECODER_UUIDS)
  self.assertNotIn(json.loads((ROOT/'configs/runtime.json').read_text())['preserved_user_service_gpu'],t.DECODER_UUIDS)
 def test_second_decoder_process_blocks_launch(self):
  uid=t.os.getuid();main={'pid':101,'uid':uid};peer={'pid':102,'uid':uid};rows=[{'pid':101,'gpu_uuid':t.MAIN_UUID},{'pid':102,'gpu_uuid':t.DECODER_UUID}]
  with self.assertRaises(t.ResourceUnavailable):t.validate_resource_capacity(t.DECODER_UUID,{'uuid':t.DECODER_UUID,'memory_free_mib':48000},rows,16*1024**3,parent=main,lookup={101:main,102:peer}.get)
if __name__=='__main__':unittest.main()
