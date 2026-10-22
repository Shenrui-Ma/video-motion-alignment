import ast, copy, hashlib, importlib.util, json, math, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
import numpy as np
import torch
from H3AutomaticWindowRouter.selector import Controller, ARMS, FEATURES, observation_rows
from H3AutomaticWindowRouter.geometry import Geometry
from H3AutomaticWindowRouter.dynamic_support import make_gain, bins_for
from H3AutomaticWindowRouter.dependencies import router
from H3AutomaticWindowRouter.automatic_window_policy import Policy
from H3AutomaticWindowRouter import transport
import H3AutomaticWindowRouter.core as core
import scan_current_pose as scan
import arm_features
import timing_metrics
G=Geometry(1312,736,90,24,74)

def measurement(index,kind='unknown',feature='left_arm_direction',gain=.8,lag=5):
 rows=[]
 for w in G.windows():
  for f in FEATURES:
   r={'window':w,'feature':f,'baseline':'unknown','status':'baseline_unknown'}
   if w==[20,35] and f==feature and kind!='unknown':
    if kind=='aligned':r.update(baseline='aligned',status='baseline_aligned')
    else:
     r.update(baseline='delayed_candidate' if lag>0 else 'advanced_candidate',status='measured',min_gain=gain,comparison={str(c):{'proposal_lag':lag,'null_comparisons':[{'proposal_cost':.1,'null_cost':.5} for _ in range(5)]} for c in (.3,.5)})
     if kind=='gain_unknown':r['status']='unknown'
   rows.append(r)
 return {'status':'complete','physical_index':index,'request_sha256':'a'*64,'response_sha256':'b'*64,'observer':{'schema':'r27-whole-timeline-observation-v1','physical_index':index,'status':'measured','windows':rows,'observation_domain':G.domain_record,'complete_scan':{'descriptor_version':'r56-arm-bone-unit-v1','expected_rows':len(rows),'actual_rows':len(rows),'complete':True}}}

def advance(c,end,kind='unknown',**kwargs):
 return [c.select(n,measurement(n,kind,**kwargs) if c.needs_observation else None) for n in range(c.last_index+1,end+1)]

class Decisions(unittest.TestCase):
 def test_visible_only_all_unknown_stays_native(self):
  c=Controller(G,arm='visible_only');d=advance(c,19)
  self.assertTrue(all(not x['chosen_full'] for x in d));self.assertEqual(c.policy.previous,[])
 def test_fallback_exact_schedule_all27_bins_padding_logged(self):
  c=Controller(G,arm='visible_fallback');d=advance(c,19)
  self.assertEqual([i for i,x in enumerate(d) if x['chosen_full']],list(range(6,15)))
  self.assertTrue(all(x['route_alpha']==.25 and x['latent_bins']==list(range(27)) for x in d[6:15]))
  self.assertTrue(any(x['padding_spillover_frames'] for x in d[6]['bin_coverage']))
  self.assertEqual(c.policy.previous,[])
  self.assertTrue(all(x['selected']==[] and x['physical_intervals']==[] for x in d))
 def test_weak_and_native_do_not_request_observer(self):
  for arm in ('native','weak_only'):
   c=Controller(G,arm=arm);self.assertFalse(c.needs_observation)
   d=advance(c,19);self.assertEqual(c.policy.last_index,-1)
   self.assertEqual([i for i,x in enumerate(d) if x['chosen_full']],list(range(6,15)) if arm=='weak_only' else [])
   self.assertTrue(all(x['measurement_status']=='not_requested' for x in d))
 def test_unrequested_observer_rejected(self):
  for arm in ('native','weak_only'):
   with self.assertRaisesRegex(ValueError,'do not consume'):Controller(G,arm=arm).select(0,measurement(0))
 def test_reliable_aligned_partial_visibility_no_fallback(self):
  d=advance(Controller(G,arm='visible_fallback'),19,'aligned')
  self.assertTrue(all(not x['chosen_full'] and x['reliable_rows']==1 for x in d))
 def test_gain_insufficient_no_fallback(self):
  d=advance(Controller(G,arm='visible_fallback'),19,'candidate',gain=.5)
  self.assertTrue(all(not x['chosen_full'] and not x['all_unknown'] for x in d))
 def test_reliable_lag_common_support_unknown_no_fallback(self):
  d=advance(Controller(G,arm='visible_fallback'),19,'gain_unknown')
  self.assertTrue(all(not x['chosen_full'] for x in d))
 def test_persistence_wait_no_fallback_then_visible_alpha1(self):
  c=Controller(G,arm='visible_fallback');advance(c,5)
  a=c.select(6,measurement(6,'candidate'));b=c.select(7,measurement(7,'candidate'))
  self.assertEqual(a['reason'],'awaiting_persistence');self.assertFalse(a['chosen_full'])
  self.assertEqual(b['control_state'],'visible');self.assertEqual(b['route_alpha'],1)
  self.assertNotEqual(b['latent_bins'],list(range(27)))
 def test_arm_must_match_across_persistence(self):
  c=Controller(G,arm='visible_only');a=c.select(0,measurement(0,'candidate',feature='left_arm_direction'));b=c.select(1,measurement(1,'candidate',feature='right_arm_direction'))
  self.assertFalse(a['chosen_full']);self.assertFalse(b['chosen_full'])
 def test_original_signed_policy_exact_on_valid_complete_rows(self):
  old=Policy(.5);c=Controller(G,arm='visible_only')
  for i in range(20):
   m=measurement(i,'candidate' if i%5<3 else 'aligned',lag=-7 if i>9 else 5)
   a=old.update(i,m['observer']['windows']);b=c.select(i,m)
   for k in a:self.assertEqual(a[k],b[k],(i,k))
   self.assertEqual(b['latent_bins'],bins_for(a['physical_intervals'],G)[0])
 def test_fallback_does_not_fabricate_persistence(self):
  c=Controller(G,arm='visible_fallback');advance(c,6)
  self.assertEqual(c.policy.previous,[])
  a=c.select(7,measurement(7,'candidate'));self.assertFalse(a['chosen_full'])
  b=c.select(8,measurement(8,'candidate'));self.assertTrue(b['chosen_full'])
  c.select(9,measurement(9));self.assertEqual(c.policy.previous,[])
  self.assertFalse(c.select(10,measurement(10,'candidate'))['chosen_full'])
 def test_missing_technical_response_hard(self):
  for value in (None,{}, {'status':'failed'}, {'status':'timeout'}):
   c=Controller(G,arm='visible_fallback')
   with self.assertRaises(ValueError):c.select(0,value)
   self.assertEqual(c.last_index,-1);self.assertEqual(c.policy.last_index,-1)
 def test_missing_duplicate_and_stale_scan_hard(self):
  changes=[lambda m:m['observer']['windows'].pop(),lambda m:m['observer']['windows'].__setitem__(0,m['observer']['windows'][1]),lambda m:m['observer'].__setitem__('physical_index',1),lambda m:m.__setitem__('physical_index',1),lambda m:m['observer'].__setitem__('observation_domain',{}),lambda m:m['observer']['complete_scan'].__setitem__('complete',False)]
  for change in changes:
   c=Controller(G,arm='visible_fallback');m=measurement(0);change(m)
   with self.assertRaises(ValueError):c.select(0,m)
   self.assertEqual(c.policy.last_index,-1)
 def test_legacy_empty_visibility_does_not_authorize_fallback(self):
  m=measurement(0);m['observer'].update(status='unknown_visibility',windows=[])
  with self.assertRaisesRegex(ValueError,'enumeration'):Controller(G,arm='visible_fallback').select(0,m)
 def test_unknown_visibility_with_full_enumeration_valid(self):
  c=Controller(G,arm='visible_fallback')
  for i in range(7):
   m=measurement(i);m['observer']['status']='unknown_visibility';d=c.select(i,m)
  self.assertEqual(d['control_state'],'weak_fallback')
 def test_sequence_mandatory(self):
  c=Controller(G,arm='weak_only')
  with self.assertRaises(ValueError):c.select(1)
  c.select(0)
  with self.assertRaises(ValueError):c.select(0)

class Attention(unittest.TestCase):
 @staticmethod
 def dense(q,k,v):
  z=q@k.transpose(-1,-2)/math.sqrt(q.shape[-1]);return z.softmax(-1)@v,z.logsumexp(-1)
 def test_alpha025_actual_block_formula_and_alpha0_exact(self):
  torch.manual_seed(7);n=27
  q=torch.randn(1,2,n*2,4);k=torch.randn_like(q);v=torch.randn_like(q)
  plan={'query_interval_half_open':[n,n*2],'reference_video_segment':[0,n],'latent_interval_half_open':[0,n],'frame_rows':1}
  native=router.route_attention(q,k,v,2,plan,mode='native',attention=self.dense)
  zero=router.route_attention(q,k,v,2,plan,mode='mass_preserve',alpha=0,attention=self.dense)
  self.assertTrue(torch.equal(native,zero))
  full=router.route_attention(q,k,v,2,plan,mode='mass_preserve',alpha=1,attention=self.dense)
  weak=router.route_attention(q,k,v,2,plan,mode='mass_preserve',alpha=.25,query_gain=make_gain(list(range(27)),(1,1),geometry=G),attention=self.dense)
  torch.testing.assert_close(weak,native+.25*(full-native),rtol=1e-5,atol=1e-7)
  self.assertTrue(torch.equal(weak[:,:n],native[:,:n]));self.assertGreater(float((weak-native).abs().max()),0)
 def test_local_time_gain_leaves_other_queries_bit_exact(self):
  q=torch.arange(108,dtype=torch.float32).reshape(1,1,54,2)/100;k=q.flip(-2);v=q.sin();plan={'query_interval_half_open':[27,54],'reference_video_segment':[0,27],'latent_interval_half_open':[0,27],'frame_rows':1}
  a=router.route_attention(q,k,v,1,plan,mode='native',attention=self.dense)
  b=router.route_attention(q,k,v,1,plan,mode='mass_preserve',query_gain=make_gain([8,9],(1,1),geometry=G),attention=self.dense)
  inactive=[i for i in range(54) if i not in (35,36)];self.assertTrue(torch.equal(a[:,inactive],b[:,inactive]))

class FeaturesAndScanner(unittest.TestCase):
 @staticmethod
 def raw(missing=()):
  n=90;t=np.arange(n);xy=np.zeros((n,17,2));conf=np.ones((n,17))
  xy[:,5],xy[:,6],xy[:,11],xy[:,12]=[200,200],[500,200],[250,500],[450,500]
  for j in (7,8,9,10):xy[:,j,0]=350+100*np.sin(t*.075+j*.7);xy[:,j,1]=300+100*np.cos(t*.113+j*.2)
  conf[:,list(missing)]=0
  return {'video':{'fps':24,'width':1312,'height':736,'container_frame_count':90},'frames':[{'frame':int(i),'time_s':float(i/24),'selected_person':0,'persons':[{'coco17_xy':x.tolist(),'coco17_score':c.tolist()}]} for i,(x,c) in enumerate(zip(xy,conf))]}
 def test_feature_bytes_frozen_R56(self):
  self.assertEqual(hashlib.sha256((ROOT/'scripts/arm_features.py').read_bytes()).hexdigest(),'3545628c490e88047a284c0d56487246d5909f830e13ac8640c83f6804efeb2b')
 def test_missing_hips_preserves_original_six_arm_fields(self):
  a=self.raw();b=self.raw((11,12))
  for threshold in (.3,.5):
   old=arm_features.features(a,G,threshold);new=arm_features.features(b,G,threshold)
   for key in arm_features.ARM_FIELDS:np.testing.assert_array_equal(old[key],new[key])
 def test_missing_one_arm_other_remains_finite(self):
  f=arm_features.features(self.raw((5,7,9,11,12)),G,.5)
  self.assertTrue(np.isnan(f['left_arm_direction']).all());self.assertTrue(np.isfinite(f['right_arm_direction']).all())
 def test_real_scanner_without_hips_or_one_arm(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'pose.json';p.write_text(json.dumps(self.raw((5,7,9,11,12))))
   result=scan.observe(p,p,0,G)
   self.assertEqual(result['complete_scan']['actual_rows'],len(list(G.windows()))*3)
   self.assertTrue(any(r['baseline']=='aligned' and r['feature']=='right_arm_direction' for r in result['windows']))
   self.assertTrue(all(r['baseline']=='unknown' for r in result['windows'] if r['feature']=='left_arm_direction'))
 def test_original_scanner_rows_exact_when_torso_visible(self):
  spec=importlib.util.spec_from_file_location('r55_old_scan',ROOT/'source_snapshot/original/scan_current_pose.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'pose.json';p.write_text(json.dumps(self.raw()))
   a=old.observe(p,p,0,G);b=scan.observe(p,p,0,G)
   self.assertEqual(a['windows'],b['windows'])
 def test_pose_intake_nonfinite_remains_hard(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'pose.json';raw=self.raw();raw['frames'][0]['persons'][0]['coco17_xy'][7][0]=float('nan');p.write_text(json.dumps(raw))
   with self.assertRaises(ValueError):scan.observe(p,p,0,G)

