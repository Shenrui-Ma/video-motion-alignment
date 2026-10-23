"""Independent small tensor oracle for runner orchestration, not trained-model evidence."""
import copy
import unittest
import numpy as np
import torch
import run

class RunnerIndependent(unittest.TestCase):
    def fixture(self, constant=False):
        env=run.dependencies()
        env['plan']=dict(env['plan'], events=[{'id':'fixed','source_interval_frames':[2,3]}])
        spans=[[i,i] for i in range(6)]
        captures={}
        for step in (9,19):
            gen=torch.Generator().manual_seed(step+195)
            for method in ('native','global_weak'):
                raw={k:torch.randn(6,2,3,4,generator=gen).to(torch.bfloat16) for k in ('raw_Q_C','raw_Q_R','raw_K_R')}
                if constant:raw['raw_Q_C'].fill_(1);raw['raw_K_R'].fill_(1)
                captures[(method,step)]={**raw,'q_norm_weight':torch.tensor([1.,.9,1.1,.8]),'k_norm_weight':torch.tensor([.9,1.2,.8,1.]),'q_norm_eps':1e-5,'k_norm_eps':1e-5,'valid_bins':[True]*5+[False],'physical_frame_spans_inclusive':spans,'spatial_ids':[0,1]}
        ann={'case_id':'short_0358','events':[{'id':'fixed','source':[2,3],'native':{'status':'observed','interval':[0,1]},'global_weak':{'status':'observed','interval':[3,4]}}]}
        return {'captures':captures,'annotations':ann,'provenance':{}},env

    def dense(self,q,k,valid):
        # Explicit flattened-key softmax, independent of grouped LSE code.
        t,p,h,d=q.shape
        out=np.zeros((h,t,p,t));ids=np.flatnonzero(valid)
        for head in range(h):
            flat=k[ids,:,head,:].astype(np.float64).reshape(-1,d)
            for ti in ids:
                for pi in range(p):
                    score=flat@q[ti,pi,head,:].astype(np.float64)/np.sqrt(d)
                    value=np.exp(score-score.max());value/=value.sum()
                    out[head,ti,pi,ids]=value.reshape(len(ids),p).sum(1)
        return out

    def test_all_six_pairings_match_dense_oracle_and_cross_identity(self):
        data,env=self.fixture();summary,archives=run.analyze(data,env)
        for row in summary['steps']:
            step=row['step_zero_based'];features={}
            for method in ('native','global_weak'):
                c=data['captures'][(method,step)]
                features[method]={name:env['base'].normalized_content(c[key].float().numpy(),c[weight].numpy(),c[eps]) for name,key,weight,eps in [('q','raw_Q_C','q_norm_weight','q_norm_eps'),('r','raw_Q_R','q_norm_weight','q_norm_eps'),('k','raw_K_R','k_norm_weight','k_norm_eps')]}
            n,w=features['native'],features['global_weak'];valid=np.array([True]*5+[False]);pairs={'qn_kn':(n['q'],n['k']),'qw_kw':(w['q'],w['k']),'qw_kn':(w['q'],n['k']),'qn_kw':(n['q'],w['k']),'qrn_kn':(n['r'],n['k']),'qrw_kw':(w['r'],w['k'])}
            expected={key:self.dense(*pair,valid) for key,pair in pairs.items()}
            for key in pairs:np.testing.assert_allclose(archives[step][key],expected[key],rtol=1e-12,atol=1e-12)
            mu={k:np.einsum('htpj,j->htp',v,np.arange(6)) for k,v in expected.items()}
            dq=.5*((mu['qw_kn']-mu['qn_kn'])+(mu['qw_kw']-mu['qn_kw']))
            dk=.5*((mu['qn_kw']-mu['qn_kn'])+(mu['qw_kw']-mu['qw_kn']))
            np.testing.assert_allclose(archives[step]['query_contribution'],dq,atol=1e-13)
            np.testing.assert_allclose(archives[step]['key_contribution'],dk,atol=1e-13)
            np.testing.assert_allclose(dq+dk,archives[step]['paired_total'],atol=1e-13)
            self.assertEqual(row['paired']['events'][0]['common_query_bins'],[2,3])
            self.assertFalse(row['paired']['semantic_phase_validated'])

    def test_uniform_pair_cannot_turn_changed_output_labels_into_repair(self):
        data,env=self.fixture(constant=True);summary,archives=run.analyze(data,env)
        for row in summary['steps']:
            step=row['step_zero_based']
            np.testing.assert_array_equal(archives[step]['paired_total'],0)
            self.assertEqual(row['paired']['events'][0]['weak_minus_native_reference_mean_frames']['mean'],0)
            descriptions=row['event_selected_descriptive_only']
            a=descriptions['native']['events'][0]['signed_phase_frames']['mean'];b=descriptions['global_weak']['events'][0]['signed_phase_frames']['mean']
            self.assertEqual(b-a,3)
        self.assertFalse(summary['semantic_phase_validated'])

if __name__=='__main__':unittest.main()
