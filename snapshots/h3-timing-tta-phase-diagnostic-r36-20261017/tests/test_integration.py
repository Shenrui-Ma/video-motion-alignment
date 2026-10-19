"""Synthetic raw-COCO -> view inverse -> frozen features -> lag, no model."""
import copy,sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'vendor')]
import timing_metrics as metrics
from evaluate import feature_arrays
from view_output import inverse_pose
from math_core import COCO_FLIP,common_costs,decisions

def raw_sequence(delay=0):
    rows=[]
    for t in range(141):
        q=t-delay;angle=.0007*q*q+.04*q+.3*np.sin(q*.13)
        xy=np.tile([650.,400.],(17,1));xy[5]=[500,200];xy[6]=[600,200];xy[11]=[515,320];xy[12]=[585,320]
        for a,b,c,offset in [(5,7,9,0),(6,8,10,.7)]:
            xy[b]=xy[a]+60*np.array([np.cos(angle+offset),np.sin(angle+offset)])
            xy[c]=xy[b]+55*np.array([np.cos(angle*1.13+offset),np.sin(angle*1.13+offset)])
        score=[1.]*17 if 0<=q<141 else [0.]*17
        rows.append({'frame':t,'time_s':t/24,'selected_person':0,'selection_ambiguous':False,'persons':[{'box_xyxy':[400.,100.,750.,650.],'coco17_xy':xy.tolist(),'coco17_score':score}]})
    return {'schema':'h3_cpu_pose_v1','video':{'width':1312,'height':736,'container_frame_count':141,'fps':24},'frames':rows}

def artificial_views(raw):
    result=[]
    for name in ('identity','flip','pad16'):
        view=copy.deepcopy(raw)
        for row in view['frames']:
            for p in row['persons']:
                xy=np.array(p['coco17_xy']);sc=np.array(p['coco17_score']);box=np.array(p['box_xyxy'])
                if name=='flip':
                    xy=xy[list(COCO_FLIP)];xy[:,0]=1311-xy[:,0];sc=sc[list(COCO_FLIP)];box=np.array([1312-box[2],box[1],1312-box[0],box[3]])
                elif name=='pad16':xy+=16;box+=16
                p['coco17_xy']=xy.tolist();p['coco17_score']=sc.tolist();p['box_xyxy']=box.tolist()
        result.append(inverse_pose(view,raw,name))
    return result

class IntegrationTests(unittest.TestCase):
    def test_real_schema_inverse_feature_shift_matrix(self):
        source=artificial_views(raw_sequence())
        for d in (0,-2,2,-4,4,-8,8):
            target=artificial_views(raw_sequence(d))
            for c in (.3,.5):
                for feature in ('arm_direction','left_arm_direction','right_arm_direction'):
                    s,sc=feature_arrays(source,c,feature);t,tc=feature_arrays(target,c,feature)
                    r=decisions(common_costs(s,t,sc,tc,(50,65),c))
                    self.assertEqual(r['candidate_lag'],d,(d,c,feature))
                    self.assertEqual(r['shared_gate'],'ALIGNED' if abs(d)<=2 else ('DELAY_ELIGIBLE' if d>0 else 'ADVANCED'))
    def test_complete_support_equals_original_cost_for_every_lag(self):
        a,b=raw_sequence(),raw_sequence(4);sv,tv=artificial_views(a),artificial_views(b)
        s,sc=feature_arrays(sv,.3,'arm_direction');t,tc=feature_arrays(tv,.3,'arm_direction');cost=np.asarray(common_costs(s,t,sc,tc,(50,65),.3)['costs'])
        def feature(raw):
            xy=np.array([x['persons'][0]['coco17_xy'] for x in raw['frames']]);cf=np.array([x['persons'][0]['coco17_score'] for x in raw['frames']]);return metrics.pose_features(xy,cf,np.arange(141)/24,np.arange(141),raw,.3)
        old=np.array([metrics.pair_error(feature(a),feature(b),(50,65),d,'arm_direction')['error'] for d in range(-24,25)])
        np.testing.assert_allclose(cost,np.broadcast_to(old,cost.shape),rtol=0,atol=1e-12)
    def test_no_model_imports_in_math_or_feature_path(self):
        self.assertNotIn('torch',sys.modules);self.assertNotIn('onnxruntime',sys.modules)

if __name__=='__main__':unittest.main()
