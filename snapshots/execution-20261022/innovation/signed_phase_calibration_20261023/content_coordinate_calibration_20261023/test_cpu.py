import copy
import hashlib
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import numpy as np
import core
import provenance

HERE=Path(__file__).resolve().parent
POLICY=json.loads((HERE/'POLICY.json').read_text())
VALID=np.array(POLICY['valid_bins'],dtype=bool)
SPANS=np.array(POLICY['physical_frame_spans_inclusive'])
P=core.PERMUTATION.copy()


def probability(identity=None,h=56,probes=8):
    identity=np.arange(32) if identity is None else np.asarray(identity)
    p=np.zeros((h,32,probes,32),dtype=np.float64)
    for t in range(31):p[:,t,:,identity[t]]=1
    return p


def analyze(old,new):return core.analyze_probabilities(old,new,VALID,P,SPANS)


class Construction(unittest.TestCase):
    def test_permutation_bijection_involution_role_and_boundary(self):
        self.assertEqual(sorted(P.tolist()),list(range(32)))
        np.testing.assert_array_equal(P[P],np.arange(32))
        np.testing.assert_array_equal(P%5,np.arange(32)%5)
        self.assertEqual(P[31],31);self.assertEqual(np.sum(P[:31]!=np.arange(31)),10)

    def test_slice_copy_no_alias_and_inverse(self):
        z=np.arange(1*3*32*4*6,dtype=np.float32).reshape(1,3,32,4,6)
        out=core.swap_reference(z)
        self.assertFalse(np.shares_memory(z,out));np.testing.assert_array_equal(out[:,:,5:10],z[:,:,10:15])
        np.testing.assert_array_equal(core.swap_reference(out),z)
        out[0,0,0,0,0]=-4;self.assertEqual(z[0,0,0,0,0],0)

    def test_changed_or_cyclic_permutation_rejected(self):
        for perm in [np.roll(np.arange(32),5),np.arange(32),P.astype(float),P[:-1]]:
            with self.assertRaises(ValueError):core.validate_permutation(perm)

    def test_patchify_matches_explicit_pixels(self):
        z=np.arange(2*3*2*4*6,dtype=np.float32).reshape(2,3,2,4,6)
        expected=[]
        for b in range(2):
            for t in range(2):
                for h in range(0,4,2):
                    for w in range(0,6,2):expected.append(z[b,:,t,h:h+2,w:w+2].reshape(-1))
        np.testing.assert_array_equal(core.patchify_video(z),expected)

    def test_coordinate_noise_not_swapped(self):
        z=np.zeros((1,1,32,2,2),np.float32)
        noise=np.arange(32*4,dtype=np.float32).reshape(32,4)
        old=core.coordinate_augmented_rows(z,noise)
        new=core.coordinate_augmented_rows(core.swap_reference(z),noise)
        np.testing.assert_array_equal(old,new)
        self.assertFalse(np.array_equal(new,old[P]))
        np.testing.assert_array_equal(noise,np.arange(128,dtype=np.float32).reshape(32,4))

    def test_noise_must_be_sampled_in_patch_row_geometry(self):
        z=np.zeros((1,2,32,2,2),np.float32)
        with self.assertRaises(ValueError):core.coordinate_augmented_rows(z,np.zeros_like(z))
        rows=np.zeros((32,8),np.float32)
        self.assertEqual(core.coordinate_augmented_rows(z,rows).shape,(32,8))

    def test_construct_all_channels_independent_and_frozen(self):
        policy=copy.deepcopy(POLICY)
        policy.update(reference_shape=[1,1,32,2,2],condition_noise_shape=[32,4],position_shape=[12,3],target_packed_shape=[1,1,100],conditioning_embedding_shape=[1,3,4],conditioning_tags_shape=[3])
        a={'reference':np.arange(128,dtype=np.float32).reshape(1,1,32,2,2),'coordinate_noise':np.ones((32,4),np.float32),'position_ids':np.ones((12,3),np.float64),'target_packed_x':np.ones((1,1,100),np.float32),'conditioning_embedding':np.ones((1,3,4),np.float32),'conditioning_tags':np.zeros(3,np.int64),'sample_sigmas_video':np.array(POLICY['original_native_metadata'][0]['forward_identity']['sample_sigmas_video'],np.float32)}
        out=core.construct_frozen_inputs(a,POLICY['sigma_by_step']['9'],policy)
        for k in a:
            self.assertFalse(any(np.shares_memory(out[k],v) for v in a.values()))
            if k!='reference':np.testing.assert_array_equal(a[k],out[k])
        out['conditioning_embedding'][0,0,0]=2;self.assertEqual(a['conditioning_embedding'][0,0,0],1)
        a['sample_sigmas_video'][9]=0
        with self.assertRaises(ValueError):core.construct_frozen_inputs(a,POLICY['sigma_by_step']['9'],policy)

    def test_nonfinite_or_wrong_reference_rejected(self):
        for x in [np.zeros((1,1,31,2,2),np.float32),np.zeros((1,1,32,2,2)),np.full((1,1,32,2,2),np.nan,np.float32)]:
            with self.assertRaises(ValueError):core.swap_reference(x)


class Counterexamples(unittest.TestCase):
    def test_pure_position_passes_zero_but_swap_stays_at_coordinate(self):
        p=probability();zero=core.analyze_probabilities(p,p,VALID,np.arange(32),SPANS)
        self.assertTrue(np.all(np.diag(zero['nearest_mask'])))
        s=core.summarize(analyze(p,p),9)
        self.assertEqual(s['swapped_unique_coordinate'],10);self.assertEqual(s['swapped_unique_source'],0)
        self.assertEqual(s['correlated_bins'],31);self.assertEqual(s['unchanged_bins'],21)

    def test_pure_content_tracks_all_swapped_sources(self):
        s=core.summarize(analyze(probability(),probability(P)),19)
        self.assertEqual(s['swapped_unique_source'],10);self.assertEqual(s['swapped_unique_coordinate'],0)
        self.assertTrue(all(r['coordinate_minus_source_margin']>0 for r in s['per_bin'] if r['swapped']))

    def test_mixture_reports_ties_and_signed_competition(self):
        old=probability();content=probability(P)
        for amount,prefer in [(.25,'coordinate'),(.75,'source')]:
            s=core.summarize(analyze(old,amount*content+(1-amount)*old),9)
            self.assertEqual(s['swapped_unique_'+prefer],10)
        r=analyze(old,.5*old+.5*content)
        for t in range(5,15):self.assertEqual(set(np.flatnonzero(r['nearest_mask'][t])),{t,int(P[t])})

    def test_periodic_role_has_multiple_legitimate_candidates(self):
        p=probability(np.arange(32)%5);r=analyze(p,p)
        self.assertTrue(np.all(r['nearest_mask'].sum(-1)>=6))
        s=core.summarize(r,9);self.assertEqual(s['swapped_unique_source'],0)
        self.assertEqual(s['swapped_unique_coordinate'],0)

    def test_fixed_noise_cue_identifies_position_with_static_content(self):
        # A static content representation plus a fixed coordinate-specific residual
        # may generate this positional fingerprint: the mathematical ambiguity remains.
        p=probability();s=core.summarize(analyze(p,p),9)
        self.assertEqual(s['swapped_unique_coordinate'],10)
        self.assertFalse(s['natural_shift_validated'])

    def test_latent_channel_rotation_is_not_appearance_only(self):
        # Channel 0 may encode temporal variation and channel 1 a constant.
        # A time-invariant orthogonal channel swap moves all motion into channel 1.
        z=np.stack([np.arange(32,dtype=float),np.ones(32)],axis=0)
        rotation=np.array([[0.,1.],[1.,0.]])
        changed=rotation@z
        self.assertGreater(np.var(z[0]),0)
        self.assertEqual(np.var(changed[0]),0)
        self.assertGreater(np.var(changed[1]),0)

    def test_global_context_changes_unmoved_bins(self):
        old=probability();new=probability(P)
        new[:,20,:,:]=0;new[:,20,:,21]=1
        r=analyze(old,new);s=core.summarize(r,9)
        self.assertFalse(s['per_bin'][20]['swapped']);self.assertFalse(s['per_bin'][20]['unique_coordinate'])
        self.assertGreater(r['coordinate_distance'][20],1.99)

    def test_joint_query_probe_identity_preserved(self):
        rng=np.random.default_rng(2);p=np.zeros((2,32,3,32),np.float64)
        x=rng.random((2,31,3,31));x/=x.sum(-1,keepdims=True);p[:,:31,:,:31]=x
        r=analyze(p,p[:,:,::-1,:]);self.assertTrue(np.all(r['coordinate_distance']>0))

    def test_joint_key_permutation_preserves_distances(self):
        rng=np.random.default_rng(4);old=np.zeros((2,32,2,32));a=rng.random((2,31,2,31));a/=a.sum(-1,keepdims=True);old[:,:31,:,:31]=a
        new=old[:,P].copy();perm=np.r_[rng.permutation(31),31]
        np.testing.assert_allclose(analyze(old,new)['squared_distances'],analyze(old[:,:,:,perm],new[:,:,:,perm])['squared_distances'],atol=1e-14,rtol=0)

    def test_all_heads_and_probes_equal_weight_direct_loop_oracle(self):
        rng=np.random.default_rng(8);old=np.zeros((2,32,3,32));x=rng.random((2,31,3,31));x/=x.sum(-1,keepdims=True);old[:,:31,:,:31]=x
        new=old[:,P].copy();r=analyze(old,new)
        for q,k in [(5,10),(5,5),(20,21)]:
            expected=sum((np.sqrt(new[h,q,p,j])-np.sqrt(old[h,k,p,j]))**2 for h in range(2) for p in range(3) for j in range(31))/6
            self.assertAlmostEqual(r['squared_distances'][q,k],expected,places=14)
        self.assertGreaterEqual(r['squared_distances'].min(),0);self.assertLessEqual(r['squared_distances'].max(),2+core.ETA)

    def test_invalid_probability_and_labels_rejected(self):
        good=probability(h=1,probes=1)
        for mutation in ['nan','negative','unnormalized','padding']:
            bad=good.copy()
            if mutation=='nan':bad[0,0,0,0]=np.nan
            if mutation=='negative':bad[0,0,0,1]=-.1
            if mutation=='unnormalized':bad[0,0,0,0]=.5
            if mutation=='padding':bad[0,31,0,0]=1
            with self.assertRaises(ValueError):analyze(good,bad)
        with self.assertRaises(ValueError):core.analyze_probabilities(good,good,VALID,np.roll(np.arange(32),1),SPANS)

    def test_report_retains_all_bins_and_missing_step_is_pending(self):
        s=core.summarize(analyze(probability(),probability(P)),9)
        self.assertEqual([x['query_bin'] for x in s['per_bin']],list(range(31)))
        self.assertIsNone(core.summarize_pair({9:s})['summary'])
        full=core.summarize_pair({9:s,19:{**s,'step_zero_based':19}})
        self.assertEqual(full['tested_correlated_bins'],62);self.assertEqual(full['swapped_bins'],20)

    def test_pair_rejects_duplicated_or_swapped_steps(self):
        s9=core.summarize(analyze(probability(),probability(P)),9)
        s19={**s9,'step_zero_based':19}
        for values in [{9:s9,19:s9},{9:s19,19:s9},{9:s9,19:s19,20:s19},{20:s19}]:
            with self.assertRaises(ValueError):core.summarize_pair(values)

    def test_pair_checks_per_bin_coverage_labels_and_counts(self):
        s9=core.summarize(analyze(probability(),probability(P)),9)
        s19={**s9,'step_zero_based':19}
        for mutation in ['missing','duplicate','wrong_source','wrong_moved','wrong_count','wrong_winners']:
            bad=copy.deepcopy(s19)
            if mutation=='missing':bad['per_bin']=bad['per_bin'][:-1]
            if mutation=='duplicate':bad['per_bin'][1]=bad['per_bin'][0].copy()
            if mutation=='wrong_source':bad['per_bin'][5]['source_bin']=5
            if mutation=='wrong_moved':bad['per_bin'][5]['swapped']=False
            if mutation=='wrong_count':bad['swapped_bins']=9
            if mutation=='wrong_winners':bad['swapped_unique_source']=0
            with self.assertRaises(ValueError):core.summarize_pair({9:s9,19:bad})


class Readout(unittest.TestCase):
    def test_fixed_original_key_used_for_both_branches(self):
        rng=np.random.default_rng(9);q=rng.normal(size=(32,2,2,4)).astype(np.float32);k=rng.normal(size=q.shape).astype(np.float32);w=np.ones((2,4),np.float32)
        q_before=q.copy();k_before=k.copy()
        r=core.fixed_dictionary_readout(q,k,q[P],w,w,VALID,P,SPANS)
        np.testing.assert_allclose(r['new_probability'],r['original_probability'][:,P],atol=1e-14,rtol=0)
        s=core.summarize(r,9);self.assertEqual(s['swapped_unique_source'],10)
        np.testing.assert_array_equal(q,q_before);np.testing.assert_array_equal(k,k_before)
        wrong_dictionary=core.retrieval_probabilities(core.normalized_content(q[P],w),core.normalized_content(k[P],w),VALID)
        self.assertFalse(np.allclose(r['new_probability'],wrong_dictionary))
        self.assertNotIn('new_key',inspect.signature(core.fixed_dictionary_readout).parameters)

    def test_retrieval_matches_independent_nested_loop(self):
        rng=np.random.default_rng(10);q=rng.normal(size=(3,2,2,4));k=rng.normal(size=q.shape);valid=np.ones(3,bool)
        p=core.retrieval_probabilities(q,k,valid)
        for h in range(2):
            for t in range(3):
                for probe in range(2):
                    masses=np.array([sum(np.exp(sum(q[t,probe,h,d]*k[j,r,h,d] for d in range(4))/2) for r in range(2))/2 for j in range(3)])
                    np.testing.assert_allclose(p[h,t,probe],masses/masses.sum(),atol=2e-15)

    def test_rms_normalization_and_overflow_fail_closed(self):
        x=np.ones((2,2,2,4),np.float32);w=np.ones(4,np.float32)
        np.testing.assert_array_equal(core.normalized_content(x,w),x/np.sqrt(np.float32(1+1e-5)))
        with self.assertRaises(ValueError):core.normalized_content(np.full_like(x,1e30),w)
        with self.assertRaises(ValueError):core.normalized_content(x,w,0)

    def test_frozen_shape_and_probe_order_reject(self):
        a={k:np.zeros((2,2,2,4),np.float32) for k in ['original_Q_R','original_K_R','new_Q_R']}
        a.update(q_norm_weight=np.ones(128,np.float32),k_norm_weight=np.ones(128,np.float32),valid_bins=VALID,physical_frame_spans_inclusive=SPANS,spatial_ids=np.array(POLICY['spatial_ids']))
        with self.assertRaises(ValueError):core.analyze_frozen_step(a,9,POLICY)
        for name in ('original_Q_R','original_K_R','new_Q_R'):
            a[name]=np.broadcast_to(np.float32(0),POLICY['raw_qk_shape'])
        a['spatial_ids']=a['spatial_ids'][::-1].copy()
        with mock.patch('core.fixed_dictionary_readout',side_effect=AssertionError('must reject first')):
            with self.assertRaises(ValueError):core.analyze_frozen_step(a,9,POLICY)


class Provenance(unittest.TestCase):
    def test_all_source_hashes_checked_before_any_array_decode(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'a.npz';np.savez(p,x=np.ones(2))
            with mock.patch('provenance.np.load',side_effect=AssertionError('must not decode')):
                with self.assertRaises(ValueError):provenance.verified_npz({'a':p,'b':p},{'a':provenance.sha256(p),'b':'0'*64},{'a':['x'],'b':['x']})
            self.assertEqual(sorted(x.name for x in Path(root).iterdir()),['a.npz'])

    def test_verified_load_and_key_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'a.npz';np.savez(p,x=np.ones(2));sha=provenance.sha256(p)
            a=provenance.verified_npz({'a':p},{'a':sha},{'a':['x']});np.testing.assert_array_equal(a['a']['x'],np.ones(2))
            with self.assertRaises(ValueError):provenance.verified_npz({'a':p},{'a':sha},{'a':['new_key']})
            self.assertEqual(len(list(Path(root).iterdir())),1)

    def test_frozen_original_state_sha_contract_used(self):
        with mock.patch('provenance.verify_sources',return_value={}) as verify:
            provenance.verify_original_native_states({'placeholder':'no-read'},POLICY)
        expected=verify.call_args.args[1]
        self.assertEqual(set(expected),{'step009_state','step009_qk','step019_state','step019_qk'})
        self.assertEqual(expected['step009_state'],'7b458342c46e20bec78defbb737e290d78d7a693ba78105b459e3ec229924507')

    def test_missing_or_additional_source_and_object_rejected(self):
        with self.assertRaises(ValueError):provenance.verify_sources({}, {'x':'0'*64})
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'object.npz';np.savez(p,x=np.array([{}],object))
            with self.assertRaises(ValueError):provenance.verified_npz({'a':p},{'a':provenance.sha256(p)},{'a':['x']})

    def test_gpu_forward_explicitly_pending_even_with_fake_gate(self):
        with self.assertRaises(provenance.PendingRuntime):provenance.request_model_forward(gate={'passed':True})

    def test_frozen_policy_denominators_and_pending_runtime(self):
        self.assertEqual(POLICY['planned_correlated_query_bins'],62)
        self.assertEqual(POLICY['planned_swapped_query_bins'],20)
        self.assertEqual(POLICY['planned_unchanged_query_bins'],42)
        self.assertFalse(POLICY['gpu_allowed']);self.assertFalse(POLICY['real_forward_deployment_authorized'])
        self.assertEqual(POLICY['real_noise_recovery'],'pending');self.assertFalse(POLICY['old_historical_REPLAY_GATE'])


if __name__=='__main__':unittest.main()
