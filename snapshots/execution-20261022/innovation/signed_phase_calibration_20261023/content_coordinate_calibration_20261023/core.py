"""CPU construction and fixed-key readout. No model, sampler, or GPU imports."""
from __future__ import annotations
import numpy as np

ETA = 64 * np.finfo(np.float64).eps
PERMUTATION = np.array([t + 5 if 5 <= t < 10 else t - 5 if 10 <= t < 15 else t
                        for t in range(32)], dtype=np.int64)


def finite_real(a, name):
    a = np.asarray(a)
    if a.dtype.kind not in 'fiu' or not np.isfinite(a).all():
        raise ValueError(name + ' must be finite real numeric')
    return a


def validate_permutation(permutation):
    p = np.asarray(permutation)
    if p.dtype.kind not in 'iu' or p.shape != (32,) or not np.array_equal(p, PERMUTATION):
        raise ValueError('only frozen [5,10) <-> [10,15) permutation is allowed')
    return p.copy()


def swap_reference(reference, permutation=PERMUTATION):
    z = finite_real(reference, 'reference')
    if z.ndim != 5 or z.shape[2] != 32 or min(z.shape) <= 0 or z.dtype != np.float32:
        raise ValueError('reference must be nonempty float32 B,C,32,H,W')
    return np.take(z, validate_permutation(permutation), axis=2).copy()


def patchify_video(reference):
    z = finite_real(reference, 'reference')
    if z.ndim != 5 or z.dtype != np.float32 or z.shape[3] % 2 or z.shape[4] % 2:
        raise ValueError('patchify requires float32 B,C,T,evenH,evenW')
    b, c, t, h, w = z.shape
    return z.reshape(b, c, t, 1, h//2, 2, w//2, 2).transpose(0,2,4,6,1,3,5,7).reshape(-1,c*4).copy()


def coordinate_augmented_rows(reference, coordinate_noise):
    """Noise stays at its original coordinates; never permute it with Z."""
    rows = patchify_video(reference)
    noise = finite_real(coordinate_noise, 'coordinate noise')
    if noise.shape != rows.shape or noise.dtype != np.float32:
        raise ValueError('coordinate noise geometry/dtype differs')
    # The same scalar-to-FP32 behavior is to be checked in the future Torch adapter.
    out = np.float32(.999)*rows + np.float32(1.0-.999)*noise
    if not np.isfinite(out).all():
        raise ValueError('nonfinite condition augmentation')
    return out


def construct_frozen_inputs(arrays, sigma, policy):
    """Pure CPU candidate only. Every returned array owns memory separately."""
    needed = {'reference','coordinate_noise','position_ids','target_packed_x',
              'conditioning_embedding','conditioning_tags','sample_sigmas_video'}
    if set(arrays) != needed:
        raise ValueError('all frozen input channels required, with no unknown keys')
    geometry = {'reference':policy['reference_shape'],
                'coordinate_noise':policy['condition_noise_shape'],
                'position_ids':policy['position_shape'],
                'target_packed_x':policy['target_packed_shape'],
                'conditioning_embedding':policy['conditioning_embedding_shape'], 'conditioning_tags':policy['conditioning_tags_shape'],
                'sample_sigmas_video':[21]}
    expected_dtype = {'position_ids':np.dtype('float64'), 'conditioning_tags':np.dtype('int64')}
    for key, shape in geometry.items():
        a = finite_real(arrays[key], key)
        if list(a.shape) != shape or a.dtype != expected_dtype.get(key, np.dtype('float32')):
            raise ValueError('frozen shape/dtype differs: '+key)
    s = float(sigma)
    if not np.isfinite(s) or s not in policy['sigma_by_step'].values():
        raise ValueError('only fixed actual native sigma allowed')
    actual_schedule = np.asarray(policy['original_native_metadata'][0]['forward_identity']['sample_sigmas_video'], dtype=np.float32)
    if not np.array_equal(arrays['sample_sigmas_video'], actual_schedule):
        raise ValueError('actual full schedule differs')
    output = {k:np.array(v,copy=True) for k,v in arrays.items()}
    output['reference'] = swap_reference(arrays['reference'], policy['source_index_by_query'])
    if any(np.shares_memory(output[k],v) for k in output for v in arrays.values()):
        raise AssertionError('output aliases original input')
    return output


def normalized_content(raw, weight, epsilon=1e-5):
    """Same pre-RoPE FP32 RMS definition as the signed upstream readout."""
    x = finite_real(raw, 'raw Q/K')
    w = finite_real(weight, 'norm weight')
    if x.ndim != 4 or min(x.shape)<=0 or w.shape not in ((x.shape[-1],),x.shape[-2:]):
        raise ValueError('invalid time,probe,head,dimension or RMS weight shape')
    if not np.isfinite(epsilon) or epsilon <= 0:
        raise ValueError('positive epsilon required')
    x, w = x.astype(np.float32), w.astype(np.float32)
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        rms2 = np.mean(x*x,axis=-1,keepdims=True)+np.float32(epsilon)
        y = x*(1/np.sqrt(rms2))*w
    if not np.isfinite(rms2).all() or not np.isfinite(y).all():
        raise ValueError('FP32 normalization overflow/nonfinite')
    return y


def retrieval_probabilities(query, original_key, valid):
    q, k = finite_real(query,'Q'), finite_real(original_key,'original K')
    valid = np.asarray(valid)
    if q.ndim!=4 or q.shape!=k.shape or valid.dtype!=np.bool_ or valid.shape!=(q.shape[0],) or valid.sum()<2:
        raise ValueError('matching Q/K geometry and boolean support required')
    t, probes, heads, dim=q.shape
    out=np.zeros((heads,t,probes,t),dtype=np.float64)
    vi=np.flatnonzero(valid)
    for h in range(heads):
        # Group only key probes; query probe identity remains explicit.
        logits=np.einsum('qpd,krd->qpkr',q[vi,:,h].astype(np.float64),k[vi,:,h].astype(np.float64))/np.sqrt(dim)
        if not np.isfinite(logits).all(): raise ValueError('nonfinite retrieval logits')
        m=logits.max(-1,keepdims=True)
        grouped=m[...,0]+np.log(np.exp(logits-m).mean(-1))
        grouped-=grouped.max(-1,keepdims=True)
        p=np.exp(grouped);p/=p.sum(-1,keepdims=True)
        for i,qi in enumerate(vi):out[h,qi][:,vi]=p[i]
    return out


def fingerprint(p,valid):
    p=np.asarray(p);valid=np.asarray(valid)
    if p.dtype!=np.float64 or p.ndim!=4 or valid.dtype!=np.bool_:
        raise ValueError('float64 H,T,P,T and bool mask required')
    h,t,probes,keys=p.shape
    if min(h,probes)<1 or keys!=t or valid.shape!=(t,) or valid.sum()<2:
        raise ValueError('invalid probability geometry')
    if not np.isfinite(p).all() or (p<0).any() or np.any(p[:,~valid]) or np.any(p[...,~valid]):
        raise ValueError('invalid probability or nonzero invalid support')
    if not np.allclose(p[:,valid].sum(-1),1,atol=1e-12,rtol=0):
        raise ValueError('probabilities not normalized')
    vi=np.flatnonzero(valid)
    return np.sqrt(p[:,vi][:,:,:,vi]).transpose(1,0,2,3).reshape(len(vi),-1)/np.sqrt(h*probes)


def analyze_probabilities(original_p,new_p,valid,source_index,spans):
    """Labels affect evaluation only; the readout searches every valid old bin."""
    a,b=fingerprint(original_p,valid),fingerprint(new_p,valid)
    if a.shape!=b.shape:raise ValueError('fingerprint geometry differs')
    vi=np.flatnonzero(valid);n=len(vi)
    src=np.asarray(source_index);spans=finite_real(spans,'spans')
    if src.dtype.kind not in 'iu' or src.shape!=(len(valid),) or spans.shape!=(len(valid),2):
        raise ValueError('source labels or physical spans differ')
    if not set(src[vi]).issubset(set(vi)) or np.any(spans[:,1]<spans[:,0]) or np.any(spans[1:,0]<=spans[:-1,1]):
        raise ValueError('invalid source support or overlapping/reversed spans')
    col={int(t):i for i,t in enumerate(vi)}
    source_cols=np.array([col[int(src[t])] for t in vi])
    d=np.empty((n,n),dtype=np.float64)
    for i in range(n):
        delta=a-b[i];d[i]=np.sum(delta*delta,axis=-1,dtype=np.float64)
    if not np.isfinite(d).all() or np.any(d<0) or np.any(d>2+ETA):raise ValueError('distance outside [0,2]')
    nearest=d<=d.min(-1,keepdims=True)+ETA
    coord=d[np.arange(n),np.arange(n)];content=d[np.arange(n),source_cols]
    other_content=d.copy();other_content[np.arange(n),source_cols]=np.inf
    other_coord=d.copy();np.fill_diagonal(other_coord,np.inf)
    return {'squared_distances':d,'nearest_mask':nearest,'valid_indices':vi,
            'source_indices':src[vi].copy(),'swapped_mask':src[vi]!=vi,
            'coordinate_distance':coord,'source_distance':content,
            'coordinate_minus_source_margin':coord-content,
            'source_unique_margin':other_content.min(-1)-content,
            'coordinate_unique_margin':other_coord.min(-1)-coord,
            'nominal_frame_centers':spans[vi].mean(-1)}


def fixed_dictionary_readout(original_q,original_k,new_q,q_weight,k_weight,valid,source_index,spans,epsilon=1e-5):
    """There is intentionally no new-key argument: both branches use original K."""
    k=normalized_content(original_k,k_weight,epsilon)
    q0=normalized_content(original_q,q_weight,epsilon)
    q1=normalized_content(new_q,q_weight,epsilon)
    original_p=retrieval_probabilities(q0,k,valid)
    new_p=retrieval_probabilities(q1,k,valid)
    result=analyze_probabilities(original_p,new_p,valid,source_index,spans)
    result.update(original_probability=original_p,new_probability=new_p)
    return result


def summarize(result,step):
    rows=[];vi=result['valid_indices']
    for i,t in enumerate(vi):
        near=vi[result['nearest_mask'][i]]
        source=int(result['source_indices'][i]);moved=bool(result['swapped_mask'][i])
        unique_source=len(near)==1 and int(near[0])==source and result['source_unique_margin'][i]>ETA
        unique_coord=len(near)==1 and int(near[0])==int(t) and result['coordinate_unique_margin'][i]>ETA
        rows.append({'query_bin':int(t),'source_bin':source,'swapped':moved,
                     'nearest_dictionary_bins':near.tolist(),
                     'coordinate_squared_distance':float(result['coordinate_distance'][i]),
                     'source_squared_distance':float(result['source_distance'][i]),
                     'coordinate_minus_source_margin':float(result['coordinate_minus_source_margin'][i]),
                     'source_unique_margin':float(result['source_unique_margin'][i]),
                     'coordinate_unique_margin':float(result['coordinate_unique_margin'][i]),
                     'unique_source':bool(unique_source),'unique_coordinate':bool(unique_coord)})
    moved=[r for r in rows if r['swapped']]
    return {'step_zero_based':step,'correlated_bins':len(rows),'swapped_bins':len(moved),
            'unchanged_bins':len(rows)-len(moved),'swapped_unique_source':sum(r['unique_source'] for r in moved),
            'swapped_unique_coordinate':sum(r['unique_coordinate'] for r in moved),'per_bin':rows,
            'interpretation':'Sensitivity of this encoded-reference pathway only; unchanged multimodal conditioning, target state, positional code and coordinate noise remain possible coordinate cues.',
            'natural_shift_validated':False,'controller_released':False}


def summarize_pair(by_step):
    if set(by_step)-{9,19}:
        raise ValueError('unknown step in paired report')
    if set(by_step)!={9,19}:
        return {'status':'pending','planned_correlated_bins':62,'summary':None}
    for step,report in by_step.items():
        if report.get('step_zero_based')!=step:
            raise ValueError('reported step differs from pair key')
        rows=report.get('per_bin')
        if not isinstance(rows,list) or len(rows)!=31:
            raise ValueError('all 31 query rows required')
        for query,row in enumerate(rows):
            if not isinstance(row,dict) or type(row.get('query_bin')) is not int or row['query_bin']!=query:
                raise ValueError('query bin order/coverage differs')
            if type(row.get('source_bin')) is not int or row['source_bin']!=int(PERMUTATION[query]):
                raise ValueError('source labels differ from frozen permutation')
            if row.get('swapped') is not bool(PERMUTATION[query]!=query):
                raise ValueError('swapped-bin label differs')
            if type(row.get('unique_source')) is not bool or type(row.get('unique_coordinate')) is not bool:
                raise ValueError('uniqueness flags must be explicit booleans')
        moved=[r for r in rows if r['swapped']]
        counts={'correlated_bins':len(rows),'swapped_bins':len(moved),'unchanged_bins':len(rows)-len(moved),
                'swapped_unique_source':sum(r['unique_source'] for r in moved),
                'swapped_unique_coordinate':sum(r['unique_coordinate'] for r in moved)}
        if any(report.get(k)!=v for k,v in counts.items()) or len(moved)!=10:
            raise ValueError('reported counts differ from full per-bin rows')
    return {'status':'complete_cpu_readout','planned_correlated_bins':62,'tested_correlated_bins':62,
            'swapped_bins':20,'unchanged_bins':42,'steps':[by_step[9],by_step[19]],
            'gpu_forward_gate_implied':False,'controller_released':False}


def analyze_frozen_step(arrays,step,policy):
    """Frozen full-head/probe entry; upstream file hashes must be checked first."""
    expected={'original_Q_R','original_K_R','new_Q_R','q_norm_weight','k_norm_weight','valid_bins','physical_frame_spans_inclusive','spatial_ids'}
    if set(arrays)!=expected or step not in policy['steps']:
        raise ValueError('input roles or fixed step differs')
    for name in ('original_Q_R','original_K_R','new_Q_R'):
        x=np.asarray(arrays[name])
        if list(x.shape)!=policy['raw_qk_shape'] or x.dtype!=np.float32:
            raise ValueError('all 56 heads/8 probes and FP32 decoded raw Q/K required')
    for name in ('valid_bins','physical_frame_spans_inclusive','spatial_ids'):
        if not np.array_equal(arrays[name],np.asarray(policy[name])):
            raise ValueError('frozen metadata differs: '+name)
    if np.asarray(arrays['valid_bins']).dtype!=np.bool_ or np.asarray(arrays['spatial_ids']).dtype.kind not in 'iu':
        raise ValueError('support/probe identity dtype differs')
    result=fixed_dictionary_readout(arrays['original_Q_R'],arrays['original_K_R'],arrays['new_Q_R'],arrays['q_norm_weight'],arrays['k_norm_weight'],arrays['valid_bins'],policy['source_index_by_query'],arrays['physical_frame_spans_inclusive'],policy['norm_eps'])
    return result,summarize(result,step)
