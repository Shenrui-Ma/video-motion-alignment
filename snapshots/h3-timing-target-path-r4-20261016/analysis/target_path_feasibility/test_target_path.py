import copy
import hashlib
import json
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
import numpy as np
import evaluate_target_path as m


class PathTests(unittest.TestCase):
    def setUp(self):
        self.centres = m.load_frozen_inputs()[-1]
        self.fit = [0, 1]
        self.hold = [2, 3]

    def fixture(self):
        rng = np.random.default_rng(42)
        base = rng.normal(size=(42, 32))
        y = np.broadcast_to(base[None, :, None, :], (4, 42, 4, 32)).copy()
        y *= np.arange(1, 5)[:, None, None, None]
        return y

    def test_fixed_source_partition_is_spatially_disjoint(self):
        _, _, _, positions, fit, hold, centres = m.load_frozen_inputs()
        self.assertEqual((len(positions),len(fit),len(hold)), (207,108,99))
        self.assertFalse(set(fit) & set(hold))
        self.assertEqual(len(set(positions)),207)
        np.testing.assert_array_equal(centres[m.EVENT+4]-centres[m.EVENT], [13,14.5,14.5,13,13,13])

    def test_zero_cost_ties_choose_identity(self):
        path, cost = m.solve_path(np.zeros((16,16)))
        self.assertEqual(path,m.W.tolist())
        self.assertEqual(cost,0)

    def test_known_monotone_path_exact_recovery(self):
        desired = [10,12,14,16,18,19,20,21,22,23,23,23,23,23,24,25]
        cost = np.full((16,16),100.0)
        cost[np.arange(16),np.array(desired)-10] = 0
        actual, value = m.solve_path(cost)
        self.assertEqual(actual,desired)
        self.assertEqual(value,0)
        self.assertTrue(m.valid_path(actual))

    def test_crossing_cost_cannot_create_crossing_path(self):
        desired = m.W.tolist()
        desired[6],desired[7] = 20,13
        cost = np.full((16,16),20.0)
        cost[np.arange(16),np.array(desired)-10] = 0
        path, value = m.solve_path(cost)
        self.assertTrue(m.valid_path(path))
        self.assertNotEqual(path,desired)
        self.assertGreater(value,0)

    def test_out_of_band_boundary_and_jump_checks(self):
        path = m.W.tolist()
        self.assertTrue(m.valid_path(path))
        for i,v in [(0,11),(15,24),(4,20),(5,13)]:
            invalid=path.copy();invalid[i]=v
            self.assertFalse(m.valid_path(invalid))
        with self.assertRaises(ValueError):m.solve_path(np.full((16,16),np.nan))

    def test_identity_is_unknown_no_artificial_positive(self):
        y=self.fixture(); r=m.evaluate_arrays(y,y[:,m.EVENT].copy(),self.fit,self.hold,self.centres)
        self.assertEqual(r['status'],'unknown')
        self.assertEqual(r['main']['path'],m.W.tolist())
        self.assertEqual(r['main']['reason'],'near_zero_proposal_denominator')

    def test_near_zero_proposal_is_unknown(self):
        y=self.fixture(); c=y[:,m.EVENT].copy()+1e-12
        r=m.evaluate_arrays(y,c,self.fit,self.hold,self.centres)
        self.assertEqual(r['status'],'unknown')
        self.assertEqual(r['main']['reason'],'near_zero_proposal_denominator')

    def test_constant_target_is_unknown(self):
        y=np.ones((4,42,4,8));c=np.ones((4,6,4,8))*2
        r=m.evaluate_arrays(y,c,self.fit,self.hold,self.centres)
        self.assertEqual(r['status'],'unknown')
        self.assertEqual(r['main']['reason'],'near_constant_target_path')

    def test_known_forward_target_states_pass_with_negative_controls(self):
        y=self.fixture();c=y[:,m.EVENT+2].copy()
        yc=y.copy();cc=c.copy()
        r=m.evaluate_arrays(y,c,self.fit,self.hold,self.centres)
        self.assertEqual(r['status'],'advance_to_generation_test')
        self.assertGreaterEqual(r['main']['pooled_gain'],.25)
        self.assertGreaterEqual(r['main']['event_median_advance_frames'],4)
        self.assertTrue(all(z['gain']>0 for z in r['main']['held_out_heads']))
        self.assertTrue(all(z['status']=='reject' for z in r['negative_controls'].values()))
        np.testing.assert_array_equal(y,yc);np.testing.assert_array_equal(c,cc)

    def test_time_inversion_rejected(self):
        y=self.fixture();c=y[:,m.EVENT[::-1]].copy()
        r=m.evaluate_arrays(y,c,self.fit,self.hold,self.centres)
        self.assertEqual(r['status'],'reject')
        self.assertNotEqual(r['main']['status'],'pass')

    def test_static_offset_cannot_be_called_motion_timing(self):
        y=np.broadcast_to(np.arange(42,dtype=float)[None,:,None,None],(4,42,4,3)).copy()
        c=y[:,m.EVENT]+4
        r=m.evaluate_arrays(y,c,self.fit,self.hold,self.centres)
        self.assertEqual(r['main']['status'],'pass')
        self.assertEqual(r['negative_controls']['event_time_constant_correction']['status'],'pass')
        self.assertEqual(r['status'],'reject')
        self.assertEqual(r['reason'],'negative_control_also_passed')

    def test_heldout_values_never_choose_path(self):
        y=self.fixture();c=y[:,m.EVENT+2].copy()
        a=m.evaluate_branch(y,c,self.fit,self.hold,self.centres)
        bad=c.copy();bad[m.HOLD_HEADS]=0
        b=m.evaluate_branch(y,bad,self.fit,self.hold,self.centres)
        self.assertEqual(a['path'],b['path'])
        self.assertNotEqual(a['pooled_gain'],b['pooled_gain'])
        # Same rule for held-out spatial positions even on fit heads.
        bad=c.copy();bad[:,:,self.hold]=100
        b=m.evaluate_branch(y,bad,self.fit,self.hold,self.centres)
        self.assertEqual(a['path'],b['path'])

    def test_boundary_cost_is_in_main_score(self):
        y=self.fixture();c=y[:,m.EVENT+2].copy()
        r=m.evaluate_branch(y,c,self.fit,self.hold,self.centres)
        self.assertGreater(sum(h['boundary_cost'] for h in r['held_out_heads']),0)
        denominator=sum(h['E0'] for h in r['held_out_heads'])
        expected=1-sum(h['Epath']+h['boundary_cost'] for h in r['held_out_heads'])/denominator
        self.assertAlmostEqual(r['pooled_gain'],expected)
        event_only=1-sum(h['Epath'] for h in r['held_out_heads'])/denominator
        self.assertLess(r['pooled_gain'],event_only)

    def test_nonfinite_is_unknown_no_dropped_support(self):
        y=self.fixture();c=y[:,m.EVENT+2].copy();c[1,0,2,0]=np.nan
        r=m.evaluate_arrays(y,c,self.fit,self.hold,self.centres)
        self.assertEqual(r['status'],'unknown')
        self.assertLess(r['main']['common_support'],1)
        self.assertGreater(r['main']['common_support'],.99)
        self.assertFalse(r['negative_controls'])

    def test_joint_path_not_better_than_free_NN_lower_bound(self):
        y=self.fixture();c=y[:,m.EVENT+2].copy()
        r=m.evaluate_branch(y,c,self.fit,self.hold,self.centres)
        for head in r['held_out_heads']:
            self.assertGreaterEqual(head['Epath']+1e-10,head['free_NN_lower_bound'])

    def test_overlap_rejected_and_output_not_overwritten(self):
        y=self.fixture()
        with self.assertRaises(ValueError):m.evaluate_arrays(y,y[:,m.EVENT],[0,1],[1,2],self.centres)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'result.json';m.write_json_exclusive(path,{'one':1})
            before=path.read_bytes()
            with self.assertRaises(FileExistsError):m.write_json_exclusive(path,{'two':2})
            self.assertEqual(path.read_bytes(),before)


class ProductionFormatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        torch.set_num_threads(1)
        cls.torch=torch
        y=torch.zeros((1,4,42,23,41,128),dtype=torch.bfloat16)
        c=torch.zeros((1,4,6,23,41,128),dtype=torch.bfloat16)
        mass=torch.ones((1,4,6,23,41),dtype=torch.float32)*.25
        layout={'target_video_segment':[47986,87592],'frame_rows':943,
                'latent_interval_half_open':[14,20],'query_interval_half_open':[61188,66846],
                'signature':[6960,42,46,82,235]}
        meta={'schema':'h3-target-path-candidate-v1','run_id':'synthetic_only',
              'forward_index':6,'block_index':25,'head_indices':[0,14,28,42],
              'grid':[42,23,41],'candidate_latent_interval_half_open':[14,20],
              'tensor_axis_order':['batch','head','time','y','x','channel'],
              'layout':layout,'tensors':{k:m._tensor_signature(t) for k,t in
                                       [('target',y),('candidate',c),('reference_mass',mass)]}}
        cls.payload={'target':y,'candidate':c,'reference_mass':mass,'metadata':meta}
        cls.record={'metadata':copy.deepcopy(meta)};cls.layout=layout

    def condition_fixture(self):
        r2=m.read_json(m.HERE/'source_runtime_evidence.json')['source_conditions']['r2']['actual_fields']
        return {'run_id':'synthetic_only','input_video':copy.deepcopy(r2['input_video']),
                'native_vae_calls':copy.deepcopy(r2['native_vae_calls']),
                'pair_snapshot':{'verified':True,'actual':{
                    'references':[{'reference_index':1,'kind':'video',
                                   'clean_latent':copy.deepcopy(r2['native_vae_calls'][1]['latent'])}]}}}

    def test_pinned_R3_tiles_allow_only_frozen_R2_runtime_source(self):
        _,groups,locator,_,_,_,_=m.load_frozen_inputs()
        evidence=m.read_json(m.HERE/'source_runtime_evidence.json')
        condition=self.condition_fixture()
        result=m.validate_source_runtime(evidence,condition,groups,locator)
        self.assertFalse(result['groups_recomputed_from_current_RGB'])
        self.assertFalse(result['prepared_RGB_matches_selection'])
        self.assertFalse(result['reference_latent_matches_selection'])
        self.assertNotEqual(result['selection_prepared_RGB']['sha256'],result['current_prepared_RGB']['sha256'])
        for key in ('source_sha256','full_native_yuv_sha256'):
            bad=copy.deepcopy(evidence);bad['decode_conversion']['r2_actual'][key]='0'*64
            with self.assertRaisesRegex(ValueError,'identity'):
                m.validate_source_runtime(bad,condition,groups,locator)
        bad=copy.deepcopy(evidence);bad['decode_conversion']['r2_actual']['frame_count']=140
        with self.assertRaisesRegex(ValueError,'complete source'):
            m.validate_source_runtime(bad,condition,groups,locator)
        for key in ('input_video','prepared_frames','latent','clean_latent'):
            bad=copy.deepcopy(condition)
            value=(bad['input_video'] if key=='input_video' else
                   bad['pair_snapshot']['actual']['references'][0]['clean_latent'] if key=='clean_latent' else
                   bad['native_vae_calls'][1][key])
            value['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'actual source'):
                m.validate_source_runtime(evidence,bad,groups,locator)

    def test_index_selection_preserves_head_time_space_and_channel_values(self):
        _,_,_,positions,_,_,_=m.load_frozen_inputs()
        yy=[x[0] for x in positions];xx=[x[1] for x in positions]
        y=self.payload['target'];c=self.payload['candidate']
        try:
            for h in range(4):
                for j in (0,1,206):
                    y[0,h,14,yy[j],xx[j],h]=16*h+j+1
                    c[0,h,0,yy[j],xx[j],h]=16*h+j+2
            selected_y=y[0,:,:,yy,xx,:];selected_c=c[0,:,:,yy,xx,:]
            for h in range(4):
                for j in (0,1,206):
                    self.assertEqual(float(selected_y[h,14,j,h]),16*h+j+1)
                    self.assertEqual(float(selected_c[h,0,j,h]),16*h+j+2)
                    self.assertEqual(float(selected_y[h,13,j,h]),0)
        finally:
            y.zero_();c.zero_()

    def test_actual_BF16_full_grid_and_safe_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'capture.pt'
            self.torch.save(self.payload,path)
            p=self.torch.load(path,map_location='cpu',weights_only=True,mmap=True)
            meta=m.validate_payload(p,self.record,self.layout,'synthetic_only')
            self.assertEqual(meta['grid'],[42,23,41])
            _,_,_,positions,_,_,_=m.load_frozen_inputs()
            yy=[x[0] for x in positions];xx=[x[1] for x in positions]
            self.assertEqual(tuple(p['target'][0,:,:,yy,xx,:].shape),(4,42,207,128))
            self.assertEqual(tuple(p['candidate'][0,:,:,yy,xx,:].shape),(4,6,207,128))

    def test_changed_tensor_bytes_rejected_not_just_metadata(self):
        tensor=self.payload['candidate']
        tensor[0,0,0,0,0,0]=1
        try:
            with self.assertRaisesRegex(ValueError,'hash/finite'):
                m.validate_payload(self.payload,self.record,self.layout,'synthetic_only')
        finally:tensor[0,0,0,0,0,0]=0

    def test_bad_head_interval_and_foreign_run_rejected(self):
        for field,value in [('head_indices',[0,1,2,3]),('candidate_latent_interval_half_open',[13,19]),('run_id','other')]:
            p=dict(self.payload);p['metadata']=copy.deepcopy(self.payload['metadata'])
            p['metadata'][field]=value
            with self.assertRaises(ValueError):
                m.validate_payload(p,{'metadata':copy.deepcopy(p['metadata'])},self.layout,'synthetic_only')

    def test_three_checkpoint_cli_entry_and_final_primary_unknown(self):
        _,groups,locator,_,_,_,_=m.load_frozen_inputs()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);capture=root/'captures';capture.mkdir()
            layout=copy.deepcopy(self.layout)
            layout['seq_len']=87592
            layout['segments']=[[0,6960,'text'],[6960,7910,'ref_img'],[7910,47516,'ref_img'],[47516,47986,'audio'],[47986,87592,'video']]
            records=[]
            sigmas=[1-i/20 for i in range(21)]
            for step in m.CALLS:
                payload=dict(self.payload);meta=copy.deepcopy(self.payload['metadata'])
                meta.update(forward_index=step,layout=layout,sampler_sigma_video=sigmas[step])
                payload['metadata']=meta
                path=capture/f'block25_step{step:03d}.pt';self.torch.save(payload,path)
                records.append({'path':'/synthetic_only/'+path.name,'sha256':m.file_sha(path),'bytes':path.stat().st_size,'metadata':meta})
            router={'run_id':'synthetic_only','mode':'native','routed_calls':0,'completed_calls':1000,
                    'completed_forward_calls':20,'native_override_calls':1000,
                    'validated_layout':layout,'sample_sigmas':sigmas,'target_path_feature_captures':records}
            condition=self.condition_fixture()
            condition['pair_snapshot']['actual']['packed_layout']={'seq_len':layout['seq_len'],'segments':layout['segments']}
            noise={'run_id':'synthetic_only','actual_noise_streams':{'synthetic_only':True}}
            for name,value in [('router',router),('condition',condition),('noise',noise)]:
                m.write_json_exclusive(root/(name+'.json'),value)
            args=SimpleNamespace(router=root/'router.json',condition=root/'condition.json',noise=root/'noise.json',capture_dir=capture,output=root/'out')
            result=m.run(args)
            self.assertEqual(result['status'],'unknown')
            self.assertEqual(result['primary_call'],6)
            self.assertFalse(result['uses_late_calls_to_override_primary'])
            self.assertEqual(sorted(result['results']),['10','14','6'])
            self.assertTrue((args.output/'frozen_input_audit.json').exists())
            audit=m.read_json(args.output/'frozen_input_audit.json')
            self.assertTrue(audit['source_groups_validated_before_target_load'])
            self.assertFalse(audit['real_target_read_yet'])
            before={p.name:m.file_sha(p) for p in args.output.iterdir()}
            with self.assertRaises(FileExistsError):m.run(args)
            self.assertEqual(before,{p.name:m.file_sha(p) for p in args.output.iterdir()})
            wrong=copy.deepcopy(router);wrong['target_path_feature_captures'][1]['metadata']['forward_index']=6
            with self.assertRaises(ValueError):m.validate_run_metadata(wrong,condition,noise,groups,locator)
            wrong=copy.deepcopy(condition);wrong['run_id']='other'
            with self.assertRaises(ValueError):m.validate_run_metadata(router,wrong,noise,groups,locator)
            wrong=copy.deepcopy(condition);wrong['native_vae_calls'][1]['prepared_frames']['sha256']='0'*64
            with self.assertRaises(ValueError):m.validate_run_metadata(router,wrong,noise,groups,locator)

    def test_wrong_axis_dtype_and_layout_rejected(self):
        p=dict(self.payload);p['candidate']=p['candidate'].float()
        with self.assertRaisesRegex(ValueError,'dtype'):
            m.validate_payload(p,self.record,self.layout,'synthetic_only')
        layout=copy.deepcopy(self.layout);layout['query_interval_half_open']=[61189,66847]
        with self.assertRaisesRegex(ValueError,'layout'):
            m.validate_payload(self.payload,self.record,layout,'synthetic_only')


if __name__=='__main__':unittest.main(verbosity=2)
