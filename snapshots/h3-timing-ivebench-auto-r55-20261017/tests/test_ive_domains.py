"""Five valid prefixes, complete positional bins and two-GPU ownership guards."""
import copy,hashlib,json,math,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
from H3AutomaticWindowRouter.geometry import Geometry
from H3AutomaticWindowRouter.dynamic_support import bins_for,bin_coverage,make_gain
from H3AutomaticWindowRouter.selector import Controller
from H3AutomaticWindowRouter import transport as t
from pose_domain import features
from r55_contract import cases,validate_job
import timing_metrics as m

def pose(g):
 rows=[]
 for i in range(g.frames):
  xy=[[10.,10.] for _ in range(17)];xy[5],xy[6],xy[11],xy[12]=[100.,100.],[200.,100.],[110.,210.],[190.,210.]
  for shoulder,elbow,wrist,sign in ((5,7,9,1),(6,8,10,-1)):
   a=.02*i+.00015*i*i+sign*.31;xy[elbow]=[xy[shoulder][0]+35*math.cos(a),xy[shoulder][1]+35*math.sin(a)];xy[wrist]=[xy[elbow][0]+27*math.cos(a*1.1),xy[elbow][1]+27*math.sin(a*1.1)]
  rows.append({'frame':i,'time_s':i/24,'selected_person':0,'persons':[{'coco17_xy':xy,'coco17_score':[.9]*17}]})
 return {'video':dict(g.video_geometry,container_frame_count=g.frames),'frames':rows}

def measurement(i,g,w):
 comparison={str(c):{'proposal_lag':5,'null_comparisons':[{'proposal_cost':.1,'null_cost':.5} for _ in range(5)]} for c in (.3,.5)}
 return {'status':'complete','observer':{'schema':'r27-whole-timeline-observation-v1','physical_index':i,'status':'measured','observation_domain':g.domain_record,'windows':[{'window':w,'feature':'arm_direction','status':'measured','baseline':'delayed_candidate','min_gain':.8,'comparison':comparison}]}}

class Domains(unittest.TestCase):
 def test_exact_original_graph_transformations(self):
  for c in cases():
   validate_job(c['run_id'],inputs=False)
   self.assertEqual(c['prompt'],c['original_task']['edit_prompt'])
   self.assertEqual(c['reference_image_count'],0)
 def test_all_five_prefix_windows_and_shapes(self):
  self.assertEqual([c['valid_frame_count'] for c in cases()],[87,86,74,78,89])
  for c in cases():
   g=Geometry.from_case(c)
   self.assertEqual(g.stream_shapes,((1,24,27,46,82),(1,32,2,150)))
   self.assertEqual(g.frame_rows,943)
   self.assertTrue(all(0<=a<=b<g.valid_frames for a,b in g.windows()))
   self.assertIn([g.valid_frames-16,g.valid_frames-1],list(g.windows()))
   with self.assertRaises(ValueError):bins_for([[g.valid_frames,g.frames-1]],g)
 def test_padding_cannot_change_features_or_lag_cost(self):
  for c in cases():
   g=Geometry.from_case(c);a=pose(g);b=copy.deepcopy(a)
   for row in b['frames'][g.valid_frames:]:row['persons'][0]['coco17_xy']=[[1e8,-1e8]]*17
   for threshold in (.3,.5):
    x,y=features(a,g,threshold),features(b,g,threshold)
    for key in x:
     if isinstance(x[key],np.ndarray):self.assertTrue(np.array_equal(x[key],y[key],equal_nan=True),key)
    self.assertEqual(x['scale'],y['scale'])
    w=[g.valid_frames-16,g.valid_frames-1]
    self.assertEqual(m.clean(m.local_diagnostic(x,x,w,24,'arm_direction')),m.clean(m.local_diagnostic(x,y,w,24,'arm_direction')))
    self.assertEqual(len(x['raw']['frames']),90);self.assertEqual(len(x['frames']),g.valid_frames)
 def test_decision_keeps_complete_bins_and_reports_spillover(self):
  for c in cases():
   g=Geometry.from_case(c);w=[g.valid_frames-2,g.valid_frames-1];control=Controller(g)
   self.assertFalse(control.select(0,measurement(0,g,w))['chosen_full'])
   d=control.select(1,measurement(1,g,w));self.assertTrue(d['chosen_full'])
   self.assertEqual(d['bin_coverage'],bin_coverage(d['latent_bins'],g))
   mask=make_gain(d['latent_bins'],geometry=g).tensor.reshape(g.gain_shape)
   self.assertEqual(tuple(mask.shape),(27,23,41))
   for i in d['latent_bins']:self.assertTrue(torch.equal(mask[i],torch.ones((23,41))))
   if c['source_id']=='short_0263':self.assertIn({'bin':22,'nominal_frames_inclusive':[73,76],'padding_spillover_frames':[74,75,76]},d['bin_coverage'])
 def test_pair_gate_accepts_only_single_video_inventory(self):
  from H3AutomaticWindowRouter.pair_gate import condition_audit_matches
  keys=('prompt','input_video','qwen_presentation','tokenization_before_vision_expansion','conditioning_embedding','token_tags','target_latent_shapes','packed_layout')
  old={k:('fixture-'+k) for k in keys};old['native_vae_calls']=[{'latent':{'sha256':'fixture'}}]
  condition_audit_matches(old,copy.deepcopy(old))
  two=copy.deepcopy(old);two['native_vae_calls']*=2
  with self.assertRaises(ValueError):condition_audit_matches(two,two)
  changed=copy.deepcopy(old);changed['prompt']='changed instruction'
  with self.assertRaises(ValueError):condition_audit_matches(changed,old)
 def test_gpu_layout_gate_uses_all_five_single_video_parents(self):
  from prelaunch_gates import check_layout_cases
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'configs').mkdir();registered=[];results=[]
   for i,c in enumerate(cases()):
    text=100+i;rows=27*943;n=text+2*rows+150
    parent={'packed_layout':{'seq_len':n,'segments':[[0,text,'text'],[text,text+rows,'ref_img'],[text+rows,text+2*rows,'video'],[text+2*rows,n,'audio']]}}
    path='configs/condition_'+str(i)+'.json';(root/path).write_text(json.dumps(parent));registered.append(dict(c,parent_conditioning=path))
    results.append({'case_run':c['run_id'],'actual_shape':True,'shape':[1,56,n,128],'plan':{'seq_len':n,'frame_rows':943,'latent_interval_half_open':[0,27],'query_interval_half_open':[text+rows,text+2*rows],'reference_video_segment':[text,text+rows]},'passed':True,'checks':{'fixture':True}})
   (root/'configs/protocol.json').write_text(json.dumps({'cases':registered}))
   check_layout_cases({'cases':results},root)
   with self.assertRaises(ValueError):check_layout_cases({'cases':results[:-1]},root)
   bad=copy.deepcopy(results);bad[0]['plan']['frame_rows']=864
   with self.assertRaises(ValueError):check_layout_cases({'cases':bad},root)
 def test_metadata_preflight_matches_actual_parent_state(self):
  from preflight import check
  ready=json.loads((ROOT/'configs/PARENT_CLOSURE.json').read_text())['ready']
  if ready:self.assertTrue(check(ROOT,metadata_only=True)['pass'])
  else:
   with self.assertRaisesRegex(ValueError,'WAITING_R54'):check(ROOT,metadata_only=True)
 def test_actual_parent_closure_requires_frozen_policy(self):
  p=json.loads((ROOT/'configs/protocol.json').read_text());ready=json.loads((ROOT/'configs/PARENT_CLOSURE.json').read_text())['ready']
  if ready:
   self.assertTrue(t.require_parent_closure()['ready']);self.assertEqual(p['policy_choice']['status'],'FROZEN_BY_ROOT')
  else:
   with self.assertRaisesRegex(ValueError,'WAITING_R54'):t.require_parent_closure()
 def test_numerical_components_unchanged(self):
  for rel,row in json.loads((ROOT/'configs/NUMERICAL_INHERITANCE.json').read_text()).items():
   self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(),row['current_sha256'])
   if row['exact']:self.assertEqual(row['current_sha256'],row['parent_sha256'])
   else:self.assertEqual(rel,'extensions/H3AutomaticWindowRouter/pair_gate.py')

class Resources(unittest.TestCase):
 def test_main_service_allows_foreign_and_checks_own_identity(self):
  import service
  admission={'permitted_compute_processes':[],'scope':'own_user_video_jobs'};empty={'queue_running':[],'queue_pending':[]}
  from observer_import import t as production_transport
  with patch.object(production_transport,'admission_document',return_value=admission),patch.object(service,'proc_uid',return_value=os.getuid()+1):
   service.check_admission(admission,[{'gpu_uuid':'GPU-other-user','pid':88}],empty)
   service.check_admission(admission,[{'gpu_uuid':service.RUNTIME['decoder_uuid'],'pid':88}],empty)
  with patch.object(production_transport,'admission_document',return_value=admission),patch.object(service,'proc_uid',return_value=os.getuid()),patch.object(service,'external_identity',return_value={}):
   with self.assertRaisesRegex(RuntimeError,'Unexpected own compute identity'):
    service.check_admission(admission,[{'gpu_uuid':'GPU-third','pid':77}],empty)
 def test_isolated_decoder_requires_measured_capacity_and_exact_main(self):
  parent={'uid':os.getuid(),'pid':1,'start_ticks':1,'cmdline_sha256':'fixture'};other={'uid':os.getuid(),'pid':2};lookup=lambda pid:{1:parent,2:other}.get(pid)
  gpu={'uuid':t.DECODER_UUID,'memory_used_mib':646,'memory_free_mib':48494,'utilization_percent':0};process=[{'gpu_uuid':t.MAIN_UUID,'pid':1}]
  profile={'required_free_bytes':16*1024**3,'profile_sha256':'fixture','profile_scope':'fixture'}
  with patch.object(t,'decoder_memory_profile',return_value=profile):
   result=t.validate_separate_decoder(parent,t.DECODER_UUID,gpu,process,lookup);self.assertEqual(len(result['planned_owned_GPUs']),2)
   for bad in (process+[{'gpu_uuid':'GPU-third','pid':2}],[],[{'gpu_uuid':t.MAIN_UUID,'pid':2}]):
    with self.assertRaises(ValueError):t.validate_separate_decoder(parent,t.DECODER_UUID,gpu,bad,lookup)
   with self.assertRaises(ValueError):t.validate_separate_decoder(parent,t.MAIN_UUID,gpu,process,lookup)
   with self.assertRaises(ValueError):t.validate_separate_decoder(parent,t.DECODER_UUID,dict(gpu,memory_free_mib=16383),process,lookup)

if __name__=='__main__':torch.set_num_threads(1);unittest.main()
