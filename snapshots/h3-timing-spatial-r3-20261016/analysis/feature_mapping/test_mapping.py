"""Synthetic correctness and rejection checks; never reads real target features."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import torch

p=Path(__file__).with_name('evaluate_mapping.py')
spec=importlib.util.spec_from_file_location('mapping',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def make_bin_locator():
    spans=[];start=0
    for i in range(42):
        n=(1,4,4,4,4)[i%5];spans.append({'latent_bin':i,'position_bin_frames_inclusive':[start,start+n-1]});start+=n
    return {'position_mapping':spans}


class MappingTests(unittest.TestCase):
    def setUp(self):torch.set_num_threads(1)

    def test_frozen_split_tile_and_nonuniform_time(self):
        self.assertEqual(len(m.TILES),91);self.assertEqual(len(m.NEIGHBORS),8)
        self.assertNotIn((0,0),m.NEIGHBORS)
        self.assertEqual(m.CALIB,(0,2,4,6,8));self.assertEqual(m.SPLITS['val'],(10,11,12))
        tau,spans=m.bin_times(make_bin_locator())
        self.assertEqual(spans[-1],(137,140));self.assertAlmostEqual(float(tau[1]-tau[0]),2.5/24)
        self.assertAlmostEqual(float(tau[2]-tau[1]),4/24)
        self.assertTrue(set(m.CALIB).isdisjoint(set(m.SPLITS['val'])|set(m.SPLITS['event'])|set(m.SPLITS['post'])))

    def test_known_cross_channel_map_generalizes_beyond_identity_diagonal(self):
        gen=torch.Generator().manual_seed(9)
        r=torch.randn(40,8,generator=gen,dtype=torch.float64)
        g=torch.eye(8,dtype=torch.float64).roll(1,0)*1.7
        y=r@g.T+3.
        fit,info=m.fit_map(r,y);self.assertEqual(info['rank'],8)
        delta=torch.randn(12,8,generator=gen,dtype=torch.float64);truth=delta@g.T
        pred=delta@fit['r'].T@fit['coeff'];d=delta*fit['diag']
        self.assertLess(float((pred-truth).square().sum()/truth.square().sum()),1e-4)
        self.assertGreater(float((d-truth).square().sum()/truth.square().sum()),.5)
        self.assertGreater(float((delta-truth).square().sum()/truth.square().sum()),.5)
        self.assertAlmostEqual(info['lambda'],1e-3*float((r-r.mean(0)).square().sum())/40)

    def test_ridge_is_equivariant_under_independent_orthogonal_coordinates(self):
        gen=torch.Generator().manual_seed(10)
        r=torch.randn(40,8,generator=gen,dtype=torch.float64);y=torch.randn(40,8,generator=gen,dtype=torch.float64)
        u=torch.linalg.qr(torch.randn(8,8,generator=gen,dtype=torch.float64)).Q
        w=torch.linalg.qr(torch.randn(8,8,generator=gen,dtype=torch.float64)).Q
        a,_=m.fit_map(r,y);b,_=m.fit_map(r@u.T,y@w.T)
        dr=torch.randn(8,generator=gen,dtype=torch.float64)
        expected=(dr@a['r'].T@a['coeff'])@w.T
        actual=(dr@u.T)@b['r'].T@b['coeff']
        torch.testing.assert_close(actual,expected,atol=2e-12,rtol=2e-12)

    def test_zero_calibration_rank_and_nonfinite_rejected(self):
        r=torch.arange(320,dtype=torch.float64).reshape(40,8)
        for rc,yc,reason in ((torch.zeros_like(r),r,'zero_or_nonfinite_source_calibration_energy'),(r,torch.zeros_like(r),'rank_zero_target_calibration')):
            fit,info=m.fit_map(rc,yc);self.assertIsNone(fit);self.assertEqual(info['reason'],reason)
        r[0,0]=float('nan');self.assertIsNone(m.fit_map(r,torch.ones_like(r))[0])

    def test_linear_advection_uses_start_only_and_rejects_large_motion(self):
        gen=torch.Generator().manual_seed(11)
        calibration=torch.randn(40,4,generator=gen,dtype=torch.float64);fit,_=m.fit_map(calibration,calibration)
        a=torch.tensor([1.,0.,0.,0.],dtype=torch.float64);b=torch.tensor([0.,1.,0.,0.],dtype=torch.float64)
        r=torch.stack([torch.stack([x*a+y*b for x in (-1,0,1)]) for y in (-1,0,1)])
        g=torch.diag(torch.tensor([2.,3.,1.,1.],dtype=torch.float64));y=r@g.T
        dr=-(a*.2+b*.1)
        pred,info=m.predict_edge(r,r,y,dr,1.,fit)
        self.assertEqual(info['advection_status'],'valid')
        torch.testing.assert_close(pred['A'],dr@g.T,atol=5e-4,rtol=.002)
        _,bad=m.predict_edge(r,r,y,dr*10,1.,fit)
        self.assertEqual(bad['advection_status'],'unknown')
        self.assertEqual(bad['advection_reason'],'advection_outside_one_token_linear_range')
        # Target future is not even an input to predict_edge; edge-start heldout Y is allowed.
        self.assertNotIn('y1',m.predict_edge.__code__.co_varnames)

    def test_advection_zero_gradient_cases(self):
        fit,_=m.fit_map(torch.eye(4,dtype=torch.float64),torch.eye(4,dtype=torch.float64))
        z=torch.zeros(3,3,4,dtype=torch.float64)
        p,info=m.predict_edge(z,z,z,torch.zeros(4,dtype=torch.float64),1.,fit)
        self.assertTrue(torch.equal(p['A'],torch.zeros(4,dtype=torch.float64)))
        p,info=m.predict_edge(z,z,z,torch.ones(4,dtype=torch.float64),1.,fit)
        self.assertIsNone(p['A']);self.assertEqual(info['advection_reason'],'zero_source_gradient_nonzero_change')

    def test_shared_support_and_zero_energy_are_not_zero_error(self):
        valid={'status':'valid','target_projected_energy':1.,'target_full_energy':2.,
               'methods':{k:{'sse':.1,'full_sse':.2,'pred_energy':1.,'cosine':1.} for k in m.METHODS}}
        summary=m.summarize([valid,{'status':'unknown'}],2)
        self.assertEqual(summary['common_count'],1);self.assertFalse(summary['support_gate'])
        zero={'status':'valid','target_projected_energy':0.,'target_full_energy':0.,
               'methods':{k:{'sse':0.,'full_sse':0.,'pred_energy':0.,'cosine':None} for k in m.METHODS}}
        summary=m.summarize([zero],1)
        self.assertEqual(summary['status'],'unknown');self.assertIsNone(summary['methods']['M']['nmse'])
        low=dict(valid,target_projected_energy=.1,target_full_energy=1.)
        self.assertFalse(m.summarize([low],1)['support_gate'])

    def test_summed_nmse_not_mean_of_per_edge_ratios(self):
        rows=[]
        for energy,sse in ((1.,1.),(100.,1.)):
            rows.append({'status':'valid','target_projected_energy':energy,'target_full_energy':energy,
                         'methods':{k:{'sse':sse,'full_sse':sse,'pred_energy':energy,'cosine':1.} for k in m.METHODS}})
        self.assertAlmostEqual(m.summarize(rows,2)['methods']['M']['nmse'],2/101)

    def test_full_grid_zero_signal_pipeline_is_unknown_not_success(self):
        # Expanded synthetic zeros, not real H3 data. No calibration information.
        z=torch.zeros(1,1,1,1,1,1,dtype=torch.bfloat16).expand(1,4,42,23,41,128)
        data={'reference':z,'target':z,'metadata':{'forward_index':6}}
        tau,_=m.bin_times(make_bin_locator())
        with tempfile.TemporaryDirectory() as folder:
            result=m.evaluate_checkpoint(data,tau,{'status':'unavailable'},Path(folder))
            self.assertIsNone(result['high_change_val_post_gate'])
            for split in ('val','event','post'):
                summary=result['summaries']['all'][split]
                self.assertFalse(summary['candidate_gate'])
                self.assertIsNone(summary['equal_head_nmse']['M'])
                self.assertTrue(all(row['common_count']==0 for row in summary['per_head'].values()))

    def test_nonfinite_heldout_is_json_safe_unknown(self):
        gen=torch.Generator().manual_seed(22)
        cal=torch.randn(40,4,generator=gen,dtype=torch.float64);fit,_=m.fit_map(cal,cal)
        r=torch.zeros(42,3,3,4,dtype=torch.float64);y=r.clone();y[11,1,1,0]=float('nan')
        tau,_=m.bin_times(make_bin_locator())
        row=m.edge_record(r,y,tau,fit,10)
        self.assertEqual(row['status'],'unknown');self.assertEqual(row['reason'],'nonfinite_heldout_feature')
        json.dumps(row,allow_nan=False)

    def test_source_groups_ties_and_tampered_roi(self):
        meta={'shape':[141,736,1312,3]}
        group={'source_only':True,'target_features_read':False,'prepared_tensor_expected':meta,
               'tiles':[list(t) for t in m.TILES],'status':'available',
               'scores':[{'center':list(t),'score':0.} for t in m.TILES],
               'high':[list(t) for t in m.TILES[:23]],'low':[list(t) for t in m.TILES[:23]]}
        m.validate_groups(group,meta)
        group['high'][0]=list(m.TILES[-1])
        with self.assertRaisesRegex(ValueError,'frozen ranking'):m.validate_groups(group,meta)

    def test_feature_file_hash_rejected_before_tensor_load(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'fake.pt';path.write_bytes(b'no tensor')
            with self.assertRaisesRegex(ValueError,'file SHA mismatch'):m.load_feature(path,{'sha256':'0'*64},{})


if __name__=='__main__':unittest.main()
