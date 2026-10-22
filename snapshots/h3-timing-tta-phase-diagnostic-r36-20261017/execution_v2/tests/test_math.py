import ast,copy,json,sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from math_core import *
from contract import validate_pose

def motion(delay=0):
    time=np.arange(141);angles=.0007*time**2+.04*time+.3*np.sin(time*.13)
    value=np.stack([np.stack([np.cos(angles),np.sin(angles)],-1),np.stack([np.cos(angles*1.13+.2),np.sin(angles*1.13+.2)],-1)],1)
    s=np.repeat(value[None],3,axis=0);sc=np.ones(s.shape[:-1]);t=np.full_like(s,np.nan);tc=np.zeros_like(sc)
    src=time-delay;good=(src>=0)&(src<141);t[:,good]=s[:,src[good]];tc[:,good]=1
    return s,t,sc,tc

def cost_fixture():
    a=np.asarray(LAGS);curve=.1+.002*(a-4)**2
    return {'status':'measured','costs':np.broadcast_to(curve,(3,3,49)).copy().tolist()}

class MathTests(unittest.TestCase):
    def test_known_signed_shifts_both_thresholds(self):
        for d in (0,-2,2,-4,4,-8,8):
            for threshold in (.3,.5):
                with self.subTest(d=d,threshold=threshold):
                    s,t,sc,tc=motion(d);cost=common_costs(s,t,sc,tc,(50,65),threshold);decision=decisions(cost)
                    self.assertEqual(cost['status'],'measured');self.assertEqual(decision['candidate_lag'],d)
                    expected='ALIGNED' if abs(d)<=2 else ('ON' if d>0 else 'ADVANCED')
                    self.assertEqual(decision['arms']['E']['status'],expected)
    def test_inverse_flip_anatomical_labels(self):
        xy=np.array([[i*9+200,i*7+100] for i in range(17)],float);sc=np.arange(17)/20+.1
        flipped=xy[list(COCO_FLIP)].copy();flipped[:,0]=1311-flipped[:,0]
        x,c,_,valid=inverse_points(flipped,sc[list(COCO_FLIP)],'flip',1312,736)
        np.testing.assert_array_equal(x,xy);np.testing.assert_array_equal(c,sc);self.assertTrue(valid.all())
    def test_integer_padding_and_original_content_exact(self):
        rgb=np.arange(7*11*3,dtype=np.uint8).reshape(7,11,3);v=transform_rgb(rgb,'pad16')
        np.testing.assert_array_equal(v[16:23,16:27],rgb);self.assertEqual(v.shape,(39,43,3));self.assertEqual(int(v[:16].sum()),0)
        xy=np.tile([100.,200.],(17,1));x,c,_,_=inverse_points(xy+16,np.ones(17),'pad16',1312,736);np.testing.assert_array_equal(x,xy)
    def test_flip_pixel_involution(self):
        rgb=np.arange(7*11*3,dtype=np.uint8).reshape(7,11,3);np.testing.assert_array_equal(transform_rgb(transform_rgb(rgb,'flip'),'flip'),rgb)
    def test_outside_content_is_missing_not_zero_pose(self):
        xy=np.tile([10.,10.],(17,1));x,c,raw,inside=inverse_points(xy,np.ones(17),'pad16',1312,736)
        self.assertTrue((x==-6).all());self.assertTrue((c==0).all());self.assertTrue((raw==1).all());self.assertFalse(inside.any())
    def test_boxes_inverse_continuous_edges(self):
        np.testing.assert_array_equal(inverse_box([1112,50,1212,250],'flip',1312),[100,50,200,250]);self.assertEqual(iou([1,2,5,7],[1,2,5,7]),1)
    def test_low_visibility_in_any_view_has_one_shared_mask(self):
        s,t,sc,tc=motion(4);tc[2,50]=0
        c=common_costs(s,t,sc,tc,(50,65),.3);self.assertEqual(c['status'],'UNKNOWN_common_support')
    def test_boundaries_not_clamped_to_manufacture_support(self):
        s,t,sc,tc=motion(0)
        for window in [(0,15),(124,139)]:self.assertEqual(common_costs(s,t,sc,tc,window,.3)['status'],'UNKNOWN_common_support')
    def test_raw_confidence_above_one_legal_and_clipped(self):
        s,t,sc,tc=motion(4);a=common_costs(s,t,sc,tc,(50,65),.3);b=common_costs(s,t,sc*1.245323181,tc*1.245323181,(50,65),.3)
        np.testing.assert_allclose(a['costs'],b['costs'],atol=0,rtol=0);np.testing.assert_array_equal(b['common_weights'],1)
    def test_nonfinite_confidence_is_technical_error(self):
        s,t,sc,tc=motion(4);tc[0,30,0]=np.nan
        with self.assertRaises(ValueError):common_costs(s,t,sc,tc,(50,65),.3)
    def test_static_unknown(self):
        s,t,sc,tc=motion(0);s[:]=[1,0];t[:]=[1,0];d=decisions(common_costs(s,t,sc,tc,(50,65),.3));self.assertEqual(d['arms']['E']['status'],'UNKNOWN')
    def test_identical_views_expose_threshold_relaxation(self):
        d=decisions(cost_fixture());self.assertEqual(d['candidate_lag'],4)
        self.assertEqual(d['arms']['A']['status'],'NO_ON');self.assertEqual(d['arms']['B']['status'],'NO_ON')
        self.assertTrue(all(d['arms'][k]['status']=='ON' for k in 'CDE'))
    def test_mean_positive_but_view_envelope_unknown(self):
        c=cost_fixture();v=np.asarray(c['costs']);v[0,0,26]=.07;c['costs']=v.tolist();d=decisions(c)
        self.assertEqual(d['candidate_lag'],4);self.assertEqual(d['arms']['D']['status'],'ON');self.assertEqual(d['arms']['E']['status'],'UNKNOWN');self.assertLess(d['arms']['E']['advantage_or_gain'],0)
    def test_one_candidate_for_every_view_and_arm(self):
        c=cost_fixture();v=np.asarray(c['costs']);v[0,0,26]=.07;c['costs']=v.tolist();d=decisions(c)
        self.assertEqual(d['candidate_lag'],4);self.assertEqual(d['identity_argmin_descriptive_only'],2)
    def test_view_order_invariance_of_mean_and_envelope(self):
        c=cost_fixture();v=np.asarray(c['costs']);v[2,1,26]=.08;c['costs']=v.tolist();a=decisions(c);c['costs']=v[[2,0,1]][:,[1,2,0]].tolist();b=decisions(c)
        self.assertEqual(a['candidate_lag'],b['candidate_lag'])
        for arm in 'BDE':self.assertEqual(a['arms'][arm]['status'],b['arms'][arm]['status'])
    def test_dual_threshold_disagreement_unknown(self):
        a=decisions(cost_fixture());b=copy.deepcopy(a);b['candidate_lag']=8
        self.assertTrue(all(x['status']=='UNKNOWN' for x in combine_thresholds(a,b).values()))
    def test_exact186_scan_and_original4_windows(self):
        self.assertEqual(len(all_windows())*3,186);self.assertEqual(all_windows()[0],(0,15));self.assertEqual(all_windows()[-1],(109,140))
        p=json.loads((ROOT/'PROTOCOL.json').read_text());self.assertEqual(p['evaluation']['fixed_windows'],[[50,65],[69,81],[80,92],[99,111]])
    def test_frozen_pose_functions_and_batch_implementation_unchanged(self):
        def functions(path):
            return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(path.read_text())) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        a=functions(ROOT/'vendor/pose_probe_frozen.py');b=functions(ROOT/'scripts/pose_probe_tta.py')
        for name in ['detect','flush_batch','select_person','iou','import_file']:
            self.assertEqual(a[name],b[name],name)
    def test_pose_finite_time_and_fps_gate(self):
        raw={'schema':'h3_cpu_pose_v1','video':{'width':1312,'height':736,'container_frame_count':141,'fps':24},'frames':[{'frame':i,'time_s':i/24,'persons':[],'selected_person':None} for i in range(141)]}
        validate_pose(raw)
        for value in [float('nan'),float('inf'),float('-inf')]:
            v=copy.deepcopy(raw);v['frames'][5]['time_s']=value
            with self.assertRaises(ValueError):validate_pose(v)
    def test_point_nonfinite_refused(self):
        xy=np.zeros((17,2));xy[1,0]=np.inf
        with self.assertRaises(ValueError):inverse_points(xy,np.ones(17),'flip',1312,736)

if __name__=='__main__':unittest.main()
