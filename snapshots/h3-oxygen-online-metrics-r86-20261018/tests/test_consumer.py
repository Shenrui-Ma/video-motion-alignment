"""Synthetic CPU records are not online experiment results."""
import copy,sys,unittest,subprocess,tempfile,base64,hashlib,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common as c
import media_utils as media
import make_showcase as show
import bind_execution as binding
import remote
class ConsumerTests(unittest.TestCase):
 def gate(self,mask=(2,7)):
  cfg=c.config();mask=list(mask);owner={'pid':101,'identity':{'uid':1016,'start_ticks':'123','cmdline':'fixture'}};nfe=20+len(mask);end=mask[0]+1 if mask else 20
  case={'run':c.RUN,'arm':'visible_only','mask':mask,'first_on':mask[0] if mask else None,'NFE':nfe,'updates':20,'observations':20,'all_OFF_final_exact':not bool(mask),'independent_parent_inputs':{'actual_clean_inputs_equal':True,'initial_video_audio_noise_equal':True,'clean_tensor_pairs':[{'tensor_equal':True}]*6},'independent_native_prefix':[{'physical_index':i,'actual_video_audio_tensor_equal':True} for i in range(end)],'decision_records':{'status':'DECISIONS_AND_TRANSACTION_RECORDS_PASS','active_indices':mask,'first_intervention':mask[0] if mask else None}}
  g={'schema':'r86-online-runtime-gate-v1','passed':True,'status':'pass','producer_manifest_sha256':cfg['producer_seal_sha256'],'protocol_sha256':cfg['protocol_sha256'],'service_record':owner,'cleanup_verified':True,'partial_batch':False,'planned_denominator':1,'planned_sources':1,'new_arms':1,'Native_reused_from_R73':True,'runtime_integrity_only':True,'new_method_claim':False,'cases':[case],'verified_runs':[c.RUN],'video':{'file':cfg['producer_remote']+'/output/fixture.mp4','sha256':'fixture','properties':{'width':1312,'height':736,'avg_frame_rate':'24/1','nb_read_frames':'107'}},'valid_frames':98,'spatial_selection':'source-specified xcenter .40-.75','automatic_scope':'online temporal window/start/stop','raw_filtered_pose_binding':[{'index':i} for i in range(20)],'efficiency':{'NFE':nfe,'per_step':[{'index':i} for i in range(20)]}}
  return g,owner
 def audit(self,mask=(2,7)):
  mask=list(mask);nfe=20+len(mask);steps=[];ms=[]
  for i in range(20):
   on=i in mask;d={'index':i,'arm':'visible_only','chosen_full':on,'observation_complete':True,'control_state':'visible' if on else 'native','route_alpha':1. if on else 0.,'spatial_support':'all_spatial_queries','physical_intervals':[[20,35]] if on else [],'latent_bins':[6,7] if on else [],'all_unknown':False,'selected':[{'window':[20,35]}] if on else [],'candidate_groups':1,'bin_coverage':[],'reason':'persistent_signed_error' if on else 'awaiting_persistence','reliable_rows':5,'total_rows':120,'measurement_status':'measured'}
   steps.append({'physical_index':i,'decision':d,'callback_observed_once':True,'selected_branch':'full' if on else 'native'})
   ms.append({'physical_index':i,'status':'complete','observer':{'physical_index':i},'request_sha256':'r','response_sha256':'s'})
  return {'status':'complete','completed_forward_calls':nfe,'completed_calls':50*nfe,'routed_calls':50*len(mask),'counterfactual':{'policy':'visible_only','full_physical_indices':mask,'actual_model_nfe':nfe,'actual_euler_updates':20,'callback_count':20,'steps':steps,'measurements':ms,'branches':[{} for _ in range(nfe)]}}
 def test_actual_on_gate_and_audit(self):
  g,owner=self.gate();case=c.verify_gate(g,owner);out=c.read_decisions(self.audit(),case);self.assertEqual(out['actual_ON_indices'],[2,7]);self.assertEqual(out['actual_ON_denoising_intervals_inclusive'],[[2,2],[7,7]]);self.assertEqual(out['rows'][2]['physical_intervals'],[[20,35]])
 def test_all_off_remains_valid_runtime_not_effect(self):
  g,owner=self.gate(());case=c.verify_gate(g,owner);out=c.read_decisions(self.audit(()),case);self.assertEqual(out['actual_ON_indices'],[]);self.assertEqual(out['effectiveness'],'UNREVIEWED');self.assertEqual(case['NFE'],20)
 def test_contiguous_intervals_from_actual_mask(self):
  mask=[1,2,3,12,13,19];g,owner=self.gate(mask);out=c.read_decisions(self.audit(mask),c.verify_gate(g,owner));self.assertEqual(out['actual_ON_denoising_intervals_inclusive'],[[1,3],[12,13],[19,19]])
 def test_offline_mask_not_substituted(self):
  g,owner=self.gate();audit=self.audit();audit['counterfactual']['full_physical_indices']=[2,3,6,7,10,11,12,13,14,15,16,17,18,19]
  with self.assertRaises(ValueError):c.read_decisions(audit,c.verify_gate(g,owner))
 def test_missing_actual_cleanup_rejected(self):
  g,o=self.gate();g['cleanup_verified']=False
  with self.assertRaises(ValueError):c.verify_gate(g,o)
 def test_wrong_service_generation(self):
  g,o=self.gate();other=copy.deepcopy(o);other['identity']['start_ticks']='new'
  with self.assertRaises(ValueError):c.verify_gate(g,other)
 def test_pending_or_partial_gate_rejected(self):
  for field,value in [('passed',False),('status','pending'),('partial_batch',True)]:
   g,o=self.gate();g[field]=value
   with self.assertRaises(ValueError):c.verify_gate(g,o)
 def test_missing_parent_noise_equality(self):
  g,o=self.gate();g['cases'][0]['independent_parent_inputs']['initial_video_audio_noise_equal']=False
  with self.assertRaises(ValueError):c.verify_gate(g,o)
 def test_requires_six_clean_inputs(self):
  g,o=self.gate();g['cases'][0]['independent_parent_inputs']['clean_tensor_pairs'].pop()
  with self.assertRaises(ValueError):c.verify_gate(g,o)
 def test_causal_prefix_stops_at_first_ON_inclusive(self):
  g,o=self.gate();self.assertEqual(len(c.verify_gate(g,o)['independent_native_prefix']),3);g['cases'][0]['independent_native_prefix'].pop()
  with self.assertRaises(ValueError):c.verify_gate(g,o)
 def test_alloff_full20_prefix_required(self):
  g,o=self.gate(());g['cases'][0]['independent_native_prefix'].pop()
  with self.assertRaises(ValueError):c.verify_gate(g,o)
 def test_wrong_NFE_rejected(self):
  g,o=self.gate();g['cases'][0]['NFE']=20
  with self.assertRaises(ValueError):c.verify_gate(g,o)
 def test_20_observations_required(self):
  g,o=self.gate();g['cases'][0]['observations']=19
  with self.assertRaises(ValueError):c.verify_gate(g,o)
 def test_unknown_cannot_activate_visible_only(self):
  g,o=self.gate();a=self.audit();a['counterfactual']['steps'][2]['decision']['all_unknown']=True
  with self.assertRaises(ValueError):c.read_decisions(a,c.verify_gate(g,o))
 def test_padding_window_rejected(self):
  g,o=self.gate();a=self.audit();a['counterfactual']['steps'][2]['decision']['physical_intervals']=[[90,106]]
  with self.assertRaises(ValueError):c.read_decisions(a,c.verify_gate(g,o))
 def test_missing_measurement_rejected(self):
  g,o=self.gate();a=self.audit();a['counterfactual']['measurements'].pop()
  with self.assertRaises(ValueError):c.read_decisions(a,c.verify_gate(g,o))
 def test_manual_actor_bounds_required(self):
  g,o=self.gate();g['spatial_selection']='fully automatic person'
  with self.assertRaises(ValueError):c.verify_gate(g,o)
 def test_frame_geometry_and_crop(self):
  g,o=self.gate();g['valid_frames']=107
  with self.assertRaises(ValueError):c.verify_gate(g,o)
  cmd=media.command(['s','n','o'],'c','out',98,'ffmpeg',98);f=cmd[cmd.index('-filter_complex')+1];self.assertEqual(f.count('crop=1280:720:16:8'),3);self.assertEqual(f.count('end_frame=98'),3);self.assertNotIn('fps=',f)
 def test_physical_time_preserved(self):
  v={'width':1312,'height':736,'count':107,'avg_frame_rate':'24/1','pts_s':[i/24 for i in range(107)]};media.check_time(v,107,1312,736);v['pts_s'][50]+=.2
  with self.assertRaises(ValueError):media.check_time(v,107,1312,736)
 def test_online_label_distinct_from_fixed(self):
  import render_online
  self.assertEqual(media.LABELS[2],'3.在线检测与时序引导');self.assertEqual(render_online.FIXED_LABELS[2],'3.固定时序引导')
 def test_pending_no_predicted_success(self):
  with patch('pathlib.Path.exists',return_value=False):r=show.summary()
  self.assertEqual(r['planned_denominator'],1);self.assertEqual(r['GPU_validation'],'PENDING');self.assertIsNone(r['actual_ON_indices']);self.assertEqual(r['task_success'],'UNREVIEWED')
 def test_path_escape_rejected(self):
  for value in ['/tmp/foreign.json',c.config()['producer_remote']+'/audit/../x']:
   with self.assertRaises(ValueError):c.safe_remote(value,'audit')
 def test_old_STARTED_schema_rejected(self):
  cfg=c.config();root=Path(cfg['producer_remote']);names=['deploy_manifest.json','configs/scientific_contract.json','configs/runtime.json','configs/protocol.json'];keys=['producer_seal_sha256','producer_contract_sha256','producer_runtime_sha256','protocol_sha256'];data={str(root/n):{'sha256':cfg[k],'value':{}} for n,k in zip(names,keys)};data[str(root/'audit/root_trial/STARTED.json')]={'value':{'owner':{},'controller':{}}};data[str(root/'processes/service.json')]={'value':{}}
  with patch.object(binding,'read_paths',return_value=data),self.assertRaises(ValueError):binding.bind('root_trial')
 def test_batch_json_exact_byte_transfer(self):
  data=b'{ "physical_index": 1 }\n';digest=hashlib.sha256(data).hexdigest();rp=c.config()['producer_remote']+'/audit/fixture.json';out=json.dumps({rp:{'sha256':digest,'bytes_b64':base64.b64encode(data).decode()}})
  with tempfile.TemporaryDirectory(dir=c.ROOT/'audit') as temp:
   dst=Path(temp)/'actual.json'
   with patch('remote.subprocess.run',return_value=subprocess.CompletedProcess(['ssh'],0,stdout=out)):
    remote.fetch_json_batch([{'remote':rp,'local':dst,'sha256':digest}]);self.assertEqual(dst.read_bytes(),data)
 def test_batch_json_wrong_SHA_rejected(self):
  data=b'{}';rp=c.config()['producer_remote']+'/audit/fixture.json';out=json.dumps({rp:{'sha256':hashlib.sha256(data).hexdigest(),'bytes_b64':base64.b64encode(data).decode()}})
  with tempfile.TemporaryDirectory(dir=c.ROOT/'audit') as temp,patch('remote.subprocess.run',return_value=subprocess.CompletedProcess(['ssh'],0,stdout=out)),self.assertRaises(ValueError):remote.fetch_json_batch([{'remote':rp,'local':Path(temp)/'x','sha256':'different'}])
 def test_static_parent_video_and_gate_hashes(self):
  cfg=c.validate_static();gate=c.read(c.ROOT/'configs/PARENT_PAIR_GATE.json');self.assertEqual(c.sha(c.ROOT/'configs/PARENT_PAIR_GATE.json'),cfg['parent_gate_sha256'])
  for role in ['native','forced']:self.assertEqual(c.sha(c.ROOT/cfg['assets'][role]['file']),gate['runs'][role]['video']['sha256'])
if __name__=='__main__':unittest.main()
