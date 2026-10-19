import unittest,copy
import numpy as np
import support as m

class Geometry(unittest.TestCase):
    def skeleton(self):
        return {5:np.array([300.,200.]),6:np.array([380.,200.]),11:np.array([310.,340.]),12:np.array([370.,340.]),7:np.array([260.,250.]),9:np.array([230.,290.])}
    def test_grid(self):
        self.assertEqual(m.CENTERS.shape,(943,2));np.testing.assert_array_equal(m.CENTERS[0],[16,16]);np.testing.assert_array_equal(m.CENTERS[-1],[1296,720])
    def test_span(self):
        self.assertEqual(m.spans(),{13:(43,46),14:(47,50),15:(51,51),16:(52,55),17:(56,59)})
    def test_capsule(self):np.testing.assert_allclose(m.capsule([0,32,48,64,80]),[1,1,.5,0,0],atol=1e-15)
    def test_segment(self):np.testing.assert_allclose(m.distance_segment(np.array([[1,1],[3,0],[0,0]]),[0,0],[2,0]),[1,1,0])
    def test_degenerate_segment(self):np.testing.assert_allclose(m.distance_segment(np.array([[3,4]]),[0,0],[0,0]),[5])
    def test_identity(self):
        s=self.skeleton();d,meta=m.align(s,s)
        for k in [5,7,9]:np.testing.assert_allclose(d[k],s[k],atol=1e-12)
        self.assertAlmostEqual(meta['scale'],1)
        du,dl,err=m.sweep_distance(s,s);np.testing.assert_allclose(du,m.bone_distance(s));np.testing.assert_allclose(dl,du);self.assertEqual(err,0)
    def test_similarity(self):
        s=self.skeleton();theta=.3;R=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
        y={k:1.2*R@v+np.array([80.,10.]) for k,v in s.items()};d,meta=m.align(s,y)
        self.assertAlmostEqual(meta['scale'],1.2)
        np.testing.assert_allclose(meta['rotation'],R,atol=1e-12)
        for k in [5,7,9]:np.testing.assert_allclose(d[k],y[k],atol=1e-12)
    def test_nonreflective(self):
        s=self.skeleton();y={k:np.array([900-v[0],v[1]]) for k,v in s.items()};d,meta=m.align(s,y)
        self.assertGreater(np.linalg.det(meta['rotation']),.9999)
        self.assertGreater(meta['anchor_rms_px'],0)
    def test_collinear_unknown(self):
        s=self.skeleton()
        for i,k in enumerate(m.ANCHORS):s[k]=np.array([300.+i,200.])
        self.assertIsNone(m.align(s,s)[0])
    def test_sweep_bridge(self):
        s={5:np.array([0.,0.]),7:np.array([10.,0.]),9:np.array([20.,0.])}
        d={k:v+np.array([0.,10.]) for k,v in s.items()};pts=np.array([[5.,5.],[15.,5.],[25.,5.]])
        du,dl,e=m.sweep_distance(s,d,pts);np.testing.assert_allclose(du,[0,0,5],atol=1e-9);self.assertTrue(np.all(dl<=du))
    def test_sweep_bounds_fine_oracle(self):
        s={5:np.array([0.,0.]),7:np.array([10.,0.]),9:np.array([20.,0.])};d={5:np.array([2.,3.]),7:np.array([8.,15.]),9:np.array([2.,20.])}
        pts=np.array([[5.5,7.2],[12.1,8.3],[30.,30.],[1.,1.]])
        du,dl,e=m.sweep_distance(s,d,pts);fine,_,_=m.sweep_distance(s,d,pts,4097)
        self.assertTrue(np.all(dl<=fine+1e-10));self.assertTrue(np.all(fine<=du+1e-10))
    def test_matching(self):
        a=np.array([1,.5,0,.2,0]);x=m.matched(a,np.array([5,3,1,0,2]));np.testing.assert_array_equal(np.sort(a),np.sort(x));self.assertEqual(np.count_nonzero(x),3)
    def test_match_tie(self):
        np.testing.assert_array_equal(m.matched(np.array([0.,.3,1.]),np.zeros(3)),[1,.3,0])
    def test_zero_unknown(self):self.assertIsNone(m.pairwise({n:np.zeros(943) for n in m.NAMES})['raw_source__current_target']['binary_iou'])
    def test_pose_score_and_halfpixel(self):
        frame={'frame':0,'time_s':0,'selection_ambiguous':False,'selected_person':0,'persons':[{'coco17_xy':[[100.,100.]]*17,'coco17_score':[1.1]*17}]};p={'frames':[frame]}
        q,why=m.pose_frame(p,0);self.assertIsNone(why);np.testing.assert_array_equal(q[5],[100.5,100.5])
        p['frames'][0]['persons'][0]['coco17_score'][7]=.499;self.assertIsNone(m.pose_frame(p,0)[0])
    def test_missing_no_fill(self):
        p={'frames':[{'frame':0,'time_s':0,'selection_ambiguous':False,'selected_person':None}]};self.assertEqual(m.pose_frame(p,0),(None,'missing_person'))
    def test_coverage_coordinates(self):
        a=np.zeros(943);a[0]=.3;p={5:np.array([.5,.5]),7:np.array([31.5,31.5]),9:np.array([16.,16.])};c=m.coverage(a,[p]);self.assertEqual(c['point_count'],42);self.assertAlmostEqual(c['mean_alpha'],.3)

if __name__=='__main__':unittest.main(verbosity=2)
