import copy,hashlib,json,unittest
import numpy as np
from evaluate90 import *
from pose90 import validate_metadata,validate_pose

def raw_pose(delay=0):
    n=90;t=np.arange(n);xy=np.zeros((n,17,2));xy[:,5]=[-.4,0];xy[:,6]=[.4,0];xy[:,11]=[-.3,1];xy[:,12]=[.3,1]
    for j in (7,8,9,10):xy[:,j,0]=np.sin(t*.075+j*.7)+j*.01;xy[:,j,1]=np.cos(t*.113+j*.2)
    if delay>0:xy=np.concatenate([xy[:1].repeat(delay,axis=0),xy[:-delay]])
    elif delay<0:xy=np.concatenate([xy[-delay:],xy[-1:].repeat(-delay,axis=0)])
    return {'video':dict(P['geometry'],container_frame_count=90,sha256='video'),
            'provenance':P['expected_pose_provenance'],
            'frames':[{'frame':i,'time_s':i/24,'selected_person':0,'persons':[{'coco17_xy':xy[i].tolist(),'coco17_score':[1.]*17}]} for i in range(n)]}

class NumericTests(unittest.TestCase):
    def test_inherited_bytes(self):
        for rel,digest in P['inherited_files'].items():self.assertEqual(hashlib.sha256((HERE/rel).read_bytes()).hexdigest(),digest)
    def test_signed_lags_and_error(self):
        s=valid_view(raw_pose(),87,.3)
        for delay in (7,-5):
            e=valid_view(raw_pose(delay),87,.3);d=metrics.local_diagnostic(s,e,[32,63],24,'arm_direction')
            self.assertEqual(d['reliable_lag_frames'],delay);self.assertLess(d['best']['error'],1e-10)
    def test_boundary_unknown(self):
        s=valid_view(raw_pose(),89,.3);e=valid_view(raw_pose(24),89,.3)
        d=metrics.local_diagnostic(s,e,[0,31],24,'arm_direction');self.assertIsNone(d['reliable_lag_frames']);self.assertIn('best_at_search_boundary',d['flags'])
    def test_static_unknown(self):
        raw=raw_pose()
        for row in raw['frames']:row['persons']=copy.deepcopy(raw['frames'][0]['persons'])
        s=valid_view(raw,87,.3);self.assertIsNone(metrics.local_diagnostic(s,s,[32,63],24,'arm_direction')['reliable_lag_frames'])
    def test_occlusion_unknown(self):
        raw=raw_pose(7)
        for r in raw['frames'][25:75]:r['selected_person']=None
        s=valid_view(raw_pose(),87,.3);e=valid_view(raw,87,.3)
        self.assertIsNone(metrics.local_diagnostic(s,e,[32,63],24,'arm_direction')['reliable_lag_frames'])
    def test_padding_excluded(self):
        for n in [87,86,74,78,89]:
            a=raw_pose();b=copy.deepcopy(a)
            for row in b['frames'][n:]:row['persons'][0]['coco17_xy']=(np.asarray(row['persons'][0]['coco17_xy'])*10000).tolist()
            x,y=valid_view(a,n,.3),valid_view(b,n,.3)
            self.assertEqual(len(x['frames']),n);self.assertEqual(x['scale'],y['scale']);np.testing.assert_allclose(x['arm_direction'],y['arm_direction'])
    def test_reject_timestamp_nonfinite_geometry(self):
        for change in ['time','coordinate','shape']:
            raw=raw_pose()
            if change=='time':raw['frames'][2]['time_s']=.5
            elif change=='coordinate':raw['frames'][2]['persons'][0]['coco17_xy'][0][0]=float('nan')
            else:raw['video']['width']=1280
            with self.assertRaises(ValueError):valid_view(raw,87,.3)
    def test_common_support_and_pair_output(self):
        s=valid_view(raw_pose(),87,.3);a=valid_view(raw_pose(7),87,.3)
        c=common_error(s,{'native':a,'auto':s},[32,63],'arm_direction');self.assertEqual(c['same_time_error']['auto'],0);self.assertGreater(c['same_time_error']['native'],0)
        r=evaluate(raw_pose(),raw_pose(7),raw_pose(),'short_0210');self.assertEqual(len(r['paired_lag_summary']),12)
        middle=next(x for x in r['paired_lag_summary'] if x['window']==[32,63] and x['feature']=='arm_direction')
        self.assertEqual(middle['methods']['native']['lag_frames_at_confidence_03_05'],[7,7]);self.assertEqual(middle['methods']['auto']['lag_frames_at_confidence_03_05'],[0,0])
    def test_metadata_rejects_source_method_prefix(self):
        c=P['cases'][0];r={'pair_id':c['pair_id'],'edited':{'native':{}},'source_prepared_video':{'sha256':c['video_sha256']},'source_preparation_record':{'sha256':c['provenance_sha256']},'score_frame_indices':list(range(87))}
        validate_metadata(r,c['pair_id'],'native')
        for key,val in [('pair_id','short_0230'),('edited',{'auto':{}}),('score_frame_indices',list(range(90))),('source_prepared_video',{'sha256':'wrong'})]:
            x=copy.deepcopy(r);x[key]=val
            with self.assertRaises(ValueError):validate_metadata(x,c['pair_id'],'native')
    def test_runtime_provenance_rejection(self):
        raw=raw_pose();validate_pose(raw,'video',87);raw['provenance']=dict(raw['provenance'],threads=8)
        with self.assertRaises(ValueError):validate_pose(raw,'video',87)
if __name__=='__main__':unittest.main()
