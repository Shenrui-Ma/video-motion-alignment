"""Independent CPU re-computation of already produced live-pair NPZ; no models."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

PAIRS = ('qn_kn', 'qw_kw', 'qw_kn', 'qn_kw', 'qrn_kn', 'qrw_kw')
EVENTS = [('bottle_lowered', [14,18]), ('bottle_reaches_lips', [37,40]), ('bottle_leaves_lips', [80,84])]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def stats(a):
    a=np.asarray(a,dtype=np.float64)
    return dict(mean=float(a.mean()),median=float(np.median(a)),std=float(a.std()),min=float(a.min()),max=float(a.max()),p10=float(np.quantile(a,.1)),p90=float(np.quantile(a,.9)))

def check(folder):
    folder=Path(folder);s=json.loads((folder/'summary.json').read_text());status=json.loads((folder/'STATUS.json').read_text())
    assert status['status']=='complete' and status['results_written'] is True
    assert status['summary_sha256']==sha(folder/'summary.json')
    assert s['status']=='complete' and s['case']=='short_0358'
    assert s['semantic_phase_validated'] is False and s['alpha_control_deployed'] is False and s['extra_gpu_calls']==0
    assert [r['step_zero_based'] for r in s['steps']]==[9,19]
    spans=[];start=0
    for t in range(32):
        width=(1,4,4,4,4)[t%5];spans.append([start,start+width-1]);start+=width
    spans=np.asarray(spans);valid=np.arange(32)<31;centers=spans.mean(1)
    result={'schema':'h3-live-paired-independent-array-check-v1','summary_sha256':sha(folder/'summary.json'),'status_sha256':sha(folder/'STATUS.json'),'all_steps_heads_probes_retained':True,'steps':[]}
    for step,row in zip([9,19],s['steps']):
        path=folder/f'step{step:03d}_all_probabilities.npz';assert sha(path)==s['npz_files'][path.name]
        with np.load(path,allow_pickle=False) as data:
            p={k:data[k] for k in PAIRS}
            assert np.array_equal(data['valid_bins'],valid) and np.array_equal(data['physical_frame_spans_inclusive'],spans)
            assert np.array_equal(data['spatial_ids'],[0,135,269,404,538,673,807,942])
            for a in p.values():
                assert a.shape==(56,32,8,32) and np.isfinite(a).all() and (a>=0).all()
                assert np.all(a[:,~valid]==0) and np.all(a[...,~valid]==0)
                np.testing.assert_allclose(a[:,valid].sum(-1),1,rtol=0,atol=1e-12)
            mu={k:(a*centers).sum(-1) for k,a in p.items()}
            delta=mu['qw_kw']-mu['qn_kn'];drift=mu['qrw_kw']-mu['qrn_kn']
            dq=.5*((mu['qw_kn']-mu['qn_kn'])+(mu['qw_kw']-mu['qn_kw']))
            dk=.5*((mu['qn_kw']-mu['qn_kn'])+(mu['qw_kw']-mu['qw_kn']))
            expected={'native_mean':mu['qn_kn'],'weak_mean':mu['qw_kw'],'weak_minus_native':delta,'paired_total':delta,'reference_self_drift':drift,'self_drift_subtracted':delta-drift,'time_constant_bias_removed':delta-delta[:,valid].mean(1,keepdims=True),'query_contribution':dq,'key_contribution':dk}
            for k,a in expected.items():np.testing.assert_allclose(data[k],a,rtol=0,atol=1e-12)
            np.testing.assert_allclose(dq+dk,delta,rtol=0,atol=1e-12)
            assert [e['event_id'] for e in row['paired']['events']]==[e[0] for e in EVENTS]
            stepout={'step':step,'npz_sha256':sha(path),'max_decomposition_error':float(np.max(np.abs(dq+dk-delta))),'all_valid_primary':stats(delta[:,valid]),'all_valid_reference_self_drift':stats(drift[:,valid]),'events':[]}
            for (eid,interval),r in zip(EVENTS,row['paired']['events']):
                bins=np.flatnonzero(valid&(spans[:,0]<=interval[1])&(spans[:,1]>=interval[0]))
                assert r['source_interval']==interval and r['common_query_bins']==bins.tolist()
                ent={};pmax={}
                for key in ('qn_kn','qw_kw'):
                    q=p[key][:,bins];positive=q>0;terms=np.zeros_like(q);terms[positive]=-q[positive]*np.log(q[positive])
                    ent[key]=stats(terms.sum(-1)/np.log(valid.sum()));pmax[key]=stats(q.max(-1))
                measures={'primary':delta,'reference_self_drift':drift,'self_drift_subtracted':delta-drift,'time_constant_bias_removed':expected['time_constant_bias_removed'],'query_contribution':dq,'key_contribution':dk}
                event={'id':eid,'source_interval':interval,'query_bins':bins.tolist(),**{k:stats(a[:,bins]) for k,a in measures.items()},'all56_head_primary_means':delta[:,bins].mean((1,2)).tolist(),'all8_probe_primary_means':delta[:,bins].mean((0,1)).tolist(),'primary_fraction_positive':float((delta[:,bins]>0).mean()),'normalized_entropy':ent,'max_probability':pmax}
                for our,key in [('primary','weak_minus_native_reference_mean_frames'),('reference_self_drift','reference_self_drift_frames'),('self_drift_subtracted','self_drift_subtracted_diagnostic'),('time_constant_bias_removed','time_constant_bias_removed_diagnostic')]:
                    assert abs(event[our]['mean']-r[key]['mean'])<1e-12
                stepout['events'].append(event)
            result['steps'].append(stepout)
    result['status']='passed';return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--folder',required=True);args=ap.parse_args()
    print(json.dumps(check(args.folder),ensure_ascii=False,indent=2,allow_nan=False))
