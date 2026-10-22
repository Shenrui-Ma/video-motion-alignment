"""Common-support, source-scaled rescore of an existing temporal proposal."""
import numpy as np

CONF = {'arm_direction':'arm_conf', 'left_arm_direction':'left_arm_conf',
        'right_arm_direction':'right_arm_conf'}

def align(pose, times, feature):
    """Nearest physical frame, preserving an explicit out-of-range mask."""
    right = np.searchsorted(pose['times'], times).clip(0, len(pose['times'])-1)
    left = np.maximum(0, right-1)
    index = np.where(abs(pose['times'][left]-times) < abs(pose['times'][right]-times), left, right)
    good = abs(pose['times'][index]-times) <= .501/pose['raw']['video']['fps']
    values = pose[feature][index].copy()
    weights = pose[CONF[feature]][index].copy()
    values[~good] = np.nan
    weights[~good] = 0
    return values, weights

def rescore(source, edited, window, lag, feature, tolerance=2):
    selected = (source['frames'] >= window[0]) & (source['frames'] <= window[1])
    times = source['times'][selected]
    fps = source['raw']['video']['fps']
    base = source[feature][selected]
    sequences = {'source':(base,source[CONF[feature]][selected])}
    for offset in range(-tolerance,tolerance+1):
        sequences[f'edited_{offset}'] = align(edited,times+offset/fps,feature)
        if offset:
            sequences[f'source_{offset}'] = align(source,times+offset/fps,feature)
    sequences['proposal'] = align(edited,times+lag/fps,feature)
    valid = np.ones(base.shape[:-1],dtype=bool)
    weights = np.ones(base.shape[:-1])
    for values, confidence in sequences.values():
        valid &= np.isfinite(values).all(axis=-1)
        weights = np.minimum(weights, confidence)
    weights = np.where(valid,weights.clip(0,1),0)
    coverage = float(valid.mean()) if valid.size else 0.
    frames = int((weights.sum(axis=1)>0).sum())
    result = {'lag_frames':int(lag),'coverage':coverage,'valid_frames':frames,
              'valid_vectors':int(valid.sum()),'expected_vectors':int(valid.size),
              'common_weight_sum':float(weights.sum()),'costs':{}}
    if coverage < .8 or frames < 8 or weights.sum() <= 0:
        return result | {'status':'unknown_common_support'}
    for name,(values,_) in sequences.items():
        distance=np.linalg.norm(base-values,axis=-1)
        result['costs'][name]=float((np.nan_to_num(distance)*weights).sum()/weights.sum())
    null=min(result['costs'][f'edited_{e}'] for e in range(-tolerance,tolerance+1))
    tau=max(result['costs'][f'source_{e}'] for e in range(-tolerance,tolerance+1) if e)
    candidate=result['costs']['proposal']
    result.update(null_cost=null,proposal_cost=candidate,source_tolerance=tau,
                  benefit=null-candidate,excess=null-candidate-tau)
    if tau<=1e-6:result['status']='unknown_static_source'
    elif candidate>.5:result['status']='unknown_residual_shape'
    elif null-candidate>tau:result['status']='above_source_tolerance'
    else:result['status']='below_source_tolerance'
    return result
