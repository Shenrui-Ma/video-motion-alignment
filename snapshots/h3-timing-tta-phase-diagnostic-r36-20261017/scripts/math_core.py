"""Frozen finite-view diagnostic. No model, image IO, or controller imports."""
import numpy as np

LAGS = tuple(range(-24, 25))
NULLS = (-2, -1, 0, 1, 2)
EPS = 1e-12
COCO_FLIP = (0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15)


def transform_rgb(rgb, view):
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise ValueError('Expected RGB uint8 HWC')
    if view == 'identity':
        return rgb.copy()
    if view == 'flip':
        return np.ascontiguousarray(rgb[:, ::-1])
    if view == 'pad16':
        return np.pad(rgb, ((16, 16), (16, 16), (0, 0)), constant_values=0)
    raise ValueError('Unregistered view')


def inverse_points(xy, scores, view, width, height):
    xy = np.array(xy, dtype=float, copy=True)
    scores = np.array(scores, dtype=float, copy=True)
    if xy.shape != (17, 2) or scores.shape != (17,) or not np.isfinite(xy).all() or not np.isfinite(scores).all():
        raise ValueError('Nonfinite or malformed model coordinates/scores')
    if view == 'flip':
        xy[:, 0] = width - 1 - xy[:, 0]
        xy, scores = xy[list(COCO_FLIP)], scores[list(COCO_FLIP)]
    elif view == 'pad16':
        xy -= 16
    elif view != 'identity':
        raise ValueError('Unregistered view')
    raw_scores = scores.copy()
    inside = ((xy[:, 0] >= 0) & (xy[:, 0] < width) &
              (xy[:, 1] >= 0) & (xy[:, 1] < height))
    scores[~inside] = 0
    return xy, scores, raw_scores, inside


def inverse_box(box, view, width):
    b = np.asarray(box, dtype=float).copy()
    if b.shape != (4,) or not np.isfinite(b).all():
        raise ValueError('Invalid box')
    if view == 'flip':
        b = np.array([width - b[2], b[1], width - b[0], b[3]])
    elif view == 'pad16':
        b -= 16
    elif view != 'identity':
        raise ValueError('Unregistered view')
    return b


def iou(a, b):
    inter = max(0., min(a[2], b[2])-max(a[0], b[0])) * max(0., min(a[3], b[3])-max(a[1], b[1]))
    aa = max(0., a[2]-a[0])*max(0., a[3]-a[1])
    bb = max(0., b[2]-b[0])*max(0., b[3]-b[1])
    return inter/max(aa+bb-inter, 1e-12)


def all_windows():
    return [(a, a+n-1) for n in (16, 32)
            for a in sorted(set(range(0, 141-n+1, 4)) | {141-n})]


def common_costs(source, target, source_conf, target_conf, window, threshold):
    """All49 lags/all9 view-pairs share an identical frame/limb mask and weights."""
    s, t = np.asarray(source), np.asarray(target)
    sc, tc = np.asarray(source_conf), np.asarray(target_conf)
    if s.shape != t.shape or s.ndim != 4 or s.shape[:2] != (3, 141) or s.shape[-1] != 2:
        raise ValueError('Expected three views x141 xlimbs x2')
    if sc.shape != s.shape[:-1] or tc.shape != t.shape[:-1] or not np.isfinite(sc).all() or not np.isfinite(tc).all():
        raise ValueError('Invalid raw confidence; finite >1 is legal')
    a, b = window
    if not (isinstance(a, int) and isinstance(b, int) and 0 <= a <= b < 141):
        raise ValueError('Invalid inclusive window')
    frames = np.arange(a, b+1)
    valid = np.isfinite(s[:, frames]).all(axis=(0, 3)) & (sc[:, frames] >= threshold).all(axis=0)
    weights = sc[:, frames].min(axis=0)
    for d in LAGS:
        idx = frames+d
        inside = (idx >= 0) & (idx < 141)
        ti = np.clip(idx, 0, 140)
        valid &= inside[:, None] & np.isfinite(t[:, ti]).all(axis=(0, 3)) & (tc[:, ti] >= threshold).all(axis=0)
        weights = np.minimum(weights, tc[:, ti].min(axis=0))
    weights = np.where(valid, weights.clip(0, 1), 0)
    denom = float(weights.sum())
    record = {'window':list(window), 'coverage':float(valid.mean()),
              'valid_frames':int((weights.sum(axis=-1)>0).sum()),
              'valid_vectors':int(valid.sum()), 'weight_sum':denom,
              'source_frames':frames.tolist(), 'common_mask':valid.tolist(),
              'common_weights':weights.tolist(), 'lags':list(LAGS)}
    if valid.mean() < .8 or record['valid_frames'] < 8 or denom <= 0:
        return record | {'status':'UNKNOWN_common_support', 'costs':None}
    costs = np.empty((3,3,len(LAGS)), dtype=float)
    for vi in range(3):
        for vj in range(3):
            for k, d in enumerate(LAGS):
                ti = np.clip(frames+d, 0, 140)
                delta = np.linalg.norm(s[vi,frames]-t[vj,ti], axis=-1)
                costs[vi,vj,k] = (np.where(valid, np.nan_to_num(delta), 0)*weights).sum()/denom
    if not np.isfinite(costs).all():
        raise ValueError('Nonfinite common cost')
    return record | {'status':'measured', 'costs':costs.tolist()}


def decisions(cost_record):
    """One d* and shared identifiability gates, five deliberately isolated arms."""
    unknown = lambda reason: {x:{'status':'UNKNOWN','reason':reason} for x in 'ABCDE'}
    if cost_record['status'] != 'measured':
        return {'candidate_lag':None,'shared_gate':cost_record['status'],'arms':unknown(cost_record['status'])}
    c = np.asarray(cost_record['costs'],dtype=float)
    if c.shape != (3,3,49) or not np.isfinite(c).all() or (c<0).any():
        raise ValueError('Invalid cost cube')
    mean = c.mean(axis=(0,1))
    k = int(np.argmin(mean)); d = LAGS[k]
    remote = [i for i,l in enumerate(LAGS) if abs(l-d)>=4]
    gap = (float(mean[remote].min())-float(mean[k]))/max(float(mean[k]),1e-8)
    improvement = (float(mean[24])-float(mean[k]))/max(float(mean[24]),1e-8)
    flags=[]
    if abs(d)==24: flags.append('search_boundary')
    if gap<.05: flags.append('flat_or_multiple_phases')
    if d!=0 and improvement<.05: flags.append('little_gain_over_same_frame')
    if float(c[:,:,k].max())>.5: flags.append('large_residual_in_at_least_one_view')
    out={'candidate_lag':d,'candidate_from':'nine-view mean; shared by all arms',
         'identity_argmin_descriptive_only':LAGS[int(np.argmin(c[0,0]))],
         'mean_curve':mean.tolist(),'distinct_gap':gap,'same_frame_improvement':improvement,
         'shared_flags':flags}
    if flags: return out | {'shared_gate':'UNKNOWN','arms':unknown(','.join(flags))}
    if abs(d)<=2: return out | {'shared_gate':'ALIGNED','arms':{x:{'status':'ALIGNED'} for x in 'ABCDE'}}
    if d<0: return out | {'shared_gate':'ADVANCED','arms':{x:{'status':'ADVANCED'} for x in 'ABCDE'}}
    if d==3: return out | {'shared_gate':'UNKNOWN','arms':unknown('lag3_indeterminate')}
    ni=[l+24 for l in NULLS]
    ident=c[0,0]; ia=ident[ni]-ident[k]; ma=mean[ni]-mean[k]
    all_adv=c[:,:,ni]-c[:,:,k,None]
    vals={'A':float(np.min(ia/np.maximum(ident[ni],1e-8))),
          'B':float(np.min(ma/np.maximum(mean[ni],1e-8))),
          'C':float(ia.min()),'D':float(ma.min()),'E':float(all_adv.min())}
    arms={}
    for name,value in vals.items():
        limit=.5 if name in 'AB' else 0.
        arms[name]={'status':'ON' if value>limit+EPS else ('UNKNOWN' if name=='E' else 'NO_ON'),
                    'advantage_or_gain':value,'decision_limit':limit,
                    'reason':'positive_margin' if value>limit+EPS else 'insufficient_margin_not_alignment'}
    arms['E']['upper_envelope']=float(all_adv.min(axis=-1).max())
    return out | {'shared_gate':'DELAY_ELIGIBLE','arms':arms}


def combine_thresholds(low, high):
    result={}
    for arm in 'ABCDE':
        a,b=low['arms'][arm]['status'],high['arms'][arm]['status']
        la,lb=low['candidate_lag'],high['candidate_lag']
        agree=la is not None and lb is not None and abs(la-lb)<=2
        result[arm]={'status':a if agree and a==b and a in ('ON','ALIGNED','ADVANCED','NO_ON') else 'UNKNOWN',
                     'threshold_statuses':[a,b], 'candidate_lags':[la,lb]}
    return result
