import unittest
import numpy as np
from bindings import BASE,SYNTH,solve
import profile_v4 as p
import synthetic_v4 as syn

class CandidateTests(unittest.TestCase):
    def test_family(self):
        a,b=p.family();self.assertEqual(len(a),9045);self.assertTrue(np.all(b-a+1>=8))
    def test_cross_threshold_preference(self):
        ew,dw=p.edge_from_rms(np.array([[.30],[.05]]),np.array([[.18],[.17]]),np.array([True]))
        self.assertTrue(ew[0]);self.assertFalse(dw[0])
    def test_graph_cycle_and_unknown(self):
        edges=np.zeros((4,1),np.uint64);edges[0,0]=2;edges[1,0]=4;edges[2,0]=1
        d,c=p.graph_geometry(edges);self.assertTrue(c[0]);self.assertTrue(d[3,0])
        edges[2,0]=0;d,c=p.graph_geometry(edges);self.assertFalse(c[0]);self.assertEqual(np.flatnonzero(d[:,0]).tolist(),[0,3])
    def test_prefix_direct_and_complete_loss(self):
        x=SYNTH.features('identifiable');y=SYNTH.features('identifiable',6)
        ctx=p.context(x,y,'left_arm',.3);a=np.array([30,40]);b=np.array([60,72])
        got=p.stats(ctx,[30,24],a,b)
        grid=BASE.grid(x,y,'left_arm',.3)
        for k,(s,e) in enumerate(zip(a,b)):
            np.testing.assert_allclose(got['loss'][:,k],grid['loss'][[30,24],s,e],atol=2e-14,rtol=0)
        reverse=p.stats(ctx,[24,30],a,b)
        np.testing.assert_array_equal(got['mask'],reverse['mask']);np.testing.assert_array_equal(got['raw_weight'],reverse['raw_weight'])
        np.testing.assert_array_equal(got['loss'],reverse['loss'][::-1])
    def test_missing_finite_and_witness_hole(self):
        x=SYNTH.features('identifiable');y=SYNTH.features('identifiable',6)
        y['directions'][60]=np.nan;y['confidence'][60]=0;y['confidence'][80,0]=np.inf
        ctx=p.context(x,y,'left_arm',.3);a=np.array([30]);b=np.array([90])
        pair=p.stats(ctx,[30,24],a,b);w=p.stats(ctx,[30,*p.NULL],a,b,True)
        self.assertTrue(pair['support'][0]);self.assertFalse(w['support'][0]);self.assertTrue(np.isfinite(pair['loss']).all())
        self.assertFalse(ctx['vy'][24,80,0]);self.assertFalse(ctx['vy'][0,0].any())
    def test_100_mask_zero_property_fixed_interval(self):
        rng=np.random.default_rng(2026101707);a=np.array([32]);b=np.array([95])
        for _ in range(100):
            x=SYNTH.features('identifiable');angle=rng.uniform(-.099,.099,(141,4))+np.array([.25,-.35,.6,-.8])
            z=x['directions'][...,0]+1j*x['directions'][...,1];z*=np.exp(1j*angle)
            y={'directions':np.stack((z.real,z.imag),axis=-1),'confidence':np.ones((141,4)),'times':x['times'].copy()}
            mask=rng.random((141,4))<rng.uniform(0,.3);y['confidence'][mask]=0;y['directions'][mask]=np.nan
            for part in p.PARTS:
                contexts=[p.context(x,y,part,h) for h in p.HS]
                for d in range(49):
                    if d==24:continue
                    blocks=[p.stats(c,[24,d],a,b) for c in contexts]
                    rms=np.sqrt(np.stack([v['loss'] for v in blocks]));valid=np.logical_and.reduce([v['support'] for v in blocks])
                    zero_loses,_=p.edge_from_rms(rms[:,0],rms[:,1],valid)
                    self.assertFalse(zero_loses.any())
    def test_narrow_analyze_shapes(self):
        x=SYNTH.features('identifiable');y=SYNTH.features('identifiable',6)
        result,evidence=p.analyze_part(x,y,'left_arm',np.array([30]),np.array([70]))
        self.assertEqual(evidence['witness_bone_weight'].shape,(49,2,1,2))
        self.assertEqual(evidence['witness_mask'].shape,(49,2,141,2))
        self.assertEqual(evidence['phase_membership'].shape,(49,1))
        self.assertEqual(result['counts']['all_intervals'],1)
    def test_frozen_selector_wide_set_cost(self):
        rows=[dict(part='left_arm',start=0,end=9,lag=3,phase_set=[3,4,5],value=1.),
              dict(part='left_arm',start=10,end=19,lag=3,phase_set=[3,4,5],value=1.)]
        self.assertEqual(solve(rows)['K'],1)
    def test_case_identity_masks(self):
        cases=syn.cases();self.assertEqual(len(cases),55);self.assertEqual(len({x['id'] for x in cases}),55)
        for case in cases[43:]:
            x,y,truth,plateaus=syn.build(case)
            count=np.isnan(y['directions'][...,0]).sum()
            self.assertEqual(count,56 if case['mask']=='A' else 12)

if __name__=='__main__':unittest.main()
