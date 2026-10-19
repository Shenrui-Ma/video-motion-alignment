import copy,gzip,hashlib,importlib.util,json,math,sys,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions'),str(ROOT/'tests/fixtures')]
import torch
from r86_contract import registry,expected_graph,RUN,read,sha
from adult_selector import adult_only
from H3AutomaticWindowRouter.selector import Controller
from H3AutomaticWindowRouter.geometry import Geometry
from H3AutomaticWindowRouter.dynamic_support import make_gain,bins_for
from H3AutomaticWindowRouter.dependencies import router
from H3AutomaticWindowRouter.pair_gate import HistoricalPairGate
import r73_router.core as old_router
import root_run_online as root_run
from observer_import import t
G=Geometry(1312,736,107,24,98)

def dense(q,k,v):
 z=q.float()@k.float().transpose(-1,-2)/math.sqrt(q.shape[-1]);return (z.softmax(-1)@v.float()).to(q.dtype),z.logsumexp(-1)

class OxygenScience(unittest.TestCase):
 def test_only_current_case_registered(self):
  rows,order=registry();self.assertEqual(order,[RUN]);self.assertEqual(rows[RUN]['arm'],'visible_only')
 def test_parent_graph_exact_authorized_delta(self):
  old=read(ROOT/'configs/PARENT_GRAPH.json');new=expected_graph()
  for key in old:
   if key not in ('5','6','14','50','51','52'):self.assertEqual(old[key],new[key])
  self.assertEqual(old['5']['inputs']['prompt'],new['5']['inputs']['prompt'])
  self.assertEqual(old['6']['inputs']['pair_id'],new['6']['inputs']['pair_id'])
  self.assertNotIn('physical_window',new['50']['inputs']);self.assertNotIn('step_start',new['50']['inputs'])
 def test_person_filter_matches_actual_R81(self):
  filtered,rejected=adult_only(read(ROOT/'design/source_raw.pose.json'),G.video_geometry)
  self.assertEqual(filtered,read(ROOT/'configs/source.pose.json'))
 def test_person_filter_does_not_switch_to_other_person(self):
  raw=read(ROOT/'design/source_raw.pose.json');row=next(x for x in raw['frames'] if x['selected_person'] is not None);i=row['selected_person'];row['persons'][i]['box_xyxy']=[0,0,10,10]
  filtered,rejected=adult_only(raw,G.video_geometry);self.assertIsNone(filtered['frames'][row['frame']]['selected_person']);self.assertIn(row['frame'],rejected)
 def test_online_controller_replays_all_actual_R81_observations(self):
  old=read(ROOT/'design/R81_PARITY.json');c=Controller(G,arm='visible_only');result=[]
  for n in range(20):
   file=ROOT/f'tests/fixtures/r81/step{n:03d}.json.gz';observer=json.load(gzip.open(file,'rt'))['observation'];record=old['input_evidence'][n]
   self.assertEqual(sha(file),record['sha256'])
   m={'status':'complete','physical_index':n,'request_sha256':'a'*64,'response_sha256':'b'*64,'observer':observer};decision=c.select(n,m)
   expected=old['results']['visible_only'][n];self.assertEqual({k:decision[k] for k in expected},expected);result.append(decision)
  self.assertEqual([i for i,d in enumerate(result) if d['chosen_full']],old['ON_indices']['visible_only'])
  self.assertEqual(result[2]['latent_bins'],[13,14,15,16,17])
 def test_R73_full_and_R59_gain_all_one_exact(self):
  for dtype in (torch.float32,torch.bfloat16):
   torch.manual_seed(2);n=32;q=torch.randn(1,2,n*2,4).to(dtype);k=torch.randn_like(q);v=torch.randn_like(q)
   plan={'query_interval_half_open':[n,n*2],'reference_video_segment':[0,n],'latent_interval_half_open':[0,n],'frame_rows':1}
   original=old_router.route_attention(q,k,v,2,plan,mode='mass_preserve',alpha=1,attention=dense)
   actual=router.route_attention(q,k,v,2,plan,mode='mass_preserve',alpha=1,query_gain=make_gain(list(range(n)),(1,1),geometry=G),attention=dense)
   self.assertTrue(torch.equal(original,actual))
 def test_selected_time_changes_only_eligible_query_rows(self):
  torch.manual_seed(3);n=32;q=torch.randn(1,2,n*2,4);k=torch.randn_like(q);v=torch.randn_like(q);plan={'query_interval_half_open':[n,n*2],'reference_video_segment':[0,n],'latent_interval_half_open':[0,n],'frame_rows':1}
  native=old_router.route_attention(q,k,v,2,plan,mode='native',attention=dense);full=old_router.route_attention(q,k,v,2,plan,mode='mass_preserve',attention=dense)
  actual=router.route_attention(q,k,v,2,plan,mode='mass_preserve',query_gain=make_gain(list(range(13,18)),(1,1),geometry=G),attention=dense)
  self.assertTrue(torch.equal(actual[:,45:50],full[:,45:50]));self.assertTrue(torch.equal(actual[:,:45],native[:,:45]));self.assertTrue(torch.equal(actual[:,50:],native[:,50:]))
 def test_prefix_qualification_never_restarts_after_OFF(self):
  gate=HistoricalPairGate();self.assertTrue(gate.native_comparable(19));state=type('S',(),{'audit':{'counterfactual':{}}})()
  gate.decision(state,2,{'chosen_full':True});gate.decision(state,3,{'chosen_full':False})
  self.assertTrue(gate.native_comparable(2));self.assertFalse(gate.native_comparable(3));self.assertFalse(gate.native_comparable(19))
 def test_geometry_padding_boundaries(self):
  self.assertEqual(G.latent_bins,32);self.assertEqual(bins_for([[44,59]],G)[0],list(range(13,18)))
  with self.assertRaises(ValueError):bins_for([[97,98]],G)
 def test_pending_parent_blocks_launch(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'configs').mkdir();(root/'configs/PARENT_CLOSURE.json').write_text(json.dumps({'ready':False,'status':'PENDING'}))
   with self.assertRaisesRegex(ValueError,'materialization pending'):t.require_parent_closure(root)
 def test_pending_root_blocks_decoder_trial(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'configs').mkdir();(root/'configs/decoder_memory_profile.json').write_bytes((ROOT/'configs/decoder_memory_profile.json').read_bytes())
   with patch.object(t,'ROOT',root):
    with self.assertRaises(FileNotFoundError):t.decoder_memory_profile()

class RootReadOnlyWait(unittest.TestCase):
 def test_HTTP_timeout_returns_UNKNOWN(self):
  with patch.object(root_run.service,'assert_owned'),patch.object(root_run.job,'status',side_effect=TimeoutError('network')):
   done,row=root_run.completed({});self.assertFalse(done);self.assertEqual(row['status'],'UNKNOWN')
 def test_unknown_missing_keeps_waiting(self):
  with patch.object(root_run.service,'assert_owned'),patch.object(root_run.job,'status',return_value={'status':'unknown_missing'}):self.assertFalse(root_run.completed({})[0])
 def test_actual_history_failure_is_hard(self):
  with patch.object(root_run.service,'assert_owned'),patch.object(root_run.job,'status',return_value={'status':{'status_str':'error'}}):
   with self.assertRaises(RuntimeError):root_run.completed({})
 def test_unknown_does_not_reset_deadline(self):
  now=[0.];clock=lambda:now[0]
  def sleep(dt):now[0]+=dt
  with tempfile.TemporaryDirectory() as folder:
   with self.assertRaises(TimeoutError):root_run.wait_completed({},40,Path(folder)/'wait.jsonl',clock=clock,sleep=sleep,check=lambda _: (False,{'status':'UNKNOWN'}))
  self.assertEqual(now[0],40)
 def test_success_after_transient_UNKNOWN(self):
  now=[0.];results=iter([(False,{'status':'UNKNOWN'}),(True,{'status':'success'})])
  with tempfile.TemporaryDirectory() as folder:
   result=root_run.wait_completed({},40,Path(folder)/'wait.jsonl',clock=lambda:now[0],sleep=lambda dt:now.__setitem__(0,now[0]+dt),check=lambda _:next(results))
  self.assertEqual(result['status'],'success');self.assertEqual(now[0],20)

if __name__=='__main__':unittest.main()

class RootLifecycle(unittest.TestCase):
 def test_failed_receipt_write_cannot_skip_exact_cleanup(self):
  from types import SimpleNamespace
  from contextlib import ExitStack
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'audit').mkdir();(root/'processes').mkdir();(root/'logs').mkdir()
   owner={'pid':5,'identity':{'uid':0,'start_ticks':'10','cmdline':'expected'}}
   runtime=dict(root_run.service.RUNTIME,remote_root=str(root))
   original=OSError('disk failure while STARTED receipt')
   def atomic(path,value):
    if Path(path).name in ('STARTED.json','FAILURE.json'):raise original
   child=SimpleNamespace(pid=22)
   with ExitStack() as stack:
    stack.enter_context(patch.object(root_run,'ROOT',root));stack.enter_context(patch.object(root_run,'sha',return_value='a'*64));stack.enter_context(patch.object(root_run.service,'RUNTIME',runtime));stack.enter_context(patch.object(root_run,'approval'));stack.enter_context(patch.object(root_run.t,'bindings'));stack.enter_context(patch.object(root_run.t,'admission_document',return_value={'permitted_compute_processes':[]}));stack.enter_context(patch.object(root_run.service,'wait_admission_snapshot'));stack.enter_context(patch.object(root_run.t,'standalone_decoder_admission'));stack.enter_context(patch.object(root_run.service,'current_identity',return_value={'uid':0}));stack.enter_context(patch.object(root_run.launch_remote,'launch',return_value=(owner,{})));stack.enter_context(patch.object(root_run.subprocess,'Popen',return_value=child));stack.enter_context(patch.object(root_run.service,'bind_child',return_value={'uid':0}));stack.enter_context(patch.object(root_run,'atomic',side_effect=atomic));stop=stack.enter_context(patch.object(root_run.service,'stop',return_value={'process_absent':True}));children=stack.enter_context(patch.object(root_run,'cleanup_observers',return_value={'all_exact_generations_absent':True,'all_registered_CUDA_pids_absent':True}))
    with self.assertRaisesRegex(OSError,'disk failure'):root_run.run('root_mock_attempt')
    stop.assert_called_once_with(expected_record=owner);children.assert_called_once()

 def test_watchdog_uses_pinned_service_and_controller(self):
  import lease_watchdog
  owner={'pid':22,'identity':{'start_ticks':'9'}};controller={'pid':44,'identity':{'start_ticks':'10'}}
  with patch.object(lease_watchdog,'read',side_effect=[owner,controller,owner]),patch.object(lease_watchdog.service,'current_identity',side_effect=[owner['identity'],None,owner['identity']]),patch.object(lease_watchdog.service,'stop') as stop:
   lease_watchdog.main(22,'9')
  stop.assert_called_once_with(expected_record=owner)
 def test_watchdog_refuses_replacement_registration(self):
  import lease_watchdog
  owner={'pid':23,'identity':{'start_ticks':'9'}}
  with patch.object(lease_watchdog,'read',return_value=owner),patch.object(lease_watchdog.service,'stop') as stop:
   with self.assertRaises(ValueError):lease_watchdog.main(22,'9')
  stop.assert_not_called()

class MainRelease(unittest.TestCase):
 def test_main_release_delegates_child_verification(self):
  owner={'pid':99,'identity':{'uid':0,'start_ticks':'10'}}
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'processes').mkdir();(root/'processes/service.json').write_text(json.dumps(owner))
   with patch.object(root_run.service,'RUN',root),patch.object(root_run.service,'current_identity',return_value=None),patch.object(root_run.service,'wait_cuda_release',return_value={'rows':[],'pid':99}),patch.object(root_run.service,'write_json'):
    result=root_run.service.stop(expected_record=owner)
   self.assertTrue(result['process_absent']);self.assertTrue(result['own_compute_absent']);self.assertIsNone(result['child_compute_absent'])
