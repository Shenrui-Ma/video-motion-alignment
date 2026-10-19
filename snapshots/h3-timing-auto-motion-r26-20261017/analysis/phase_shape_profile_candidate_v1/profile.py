"""Synthetic-only SO(2) profile observer. Constants are pre-registered."""
import math
import time
import numpy as np

LAGS = np.arange(-24, 25)
NULL = np.flatnonzero(np.abs(LAGS) <= 2)
THRESHOLDS = (0.3, 0.5)
PARTS = {'left_arm': (0, 1), 'right_arm': (2, 3)}
EPS = 2 * math.sin(0.05 / 2)
PAIR = 2 * EPS
NAMES = ('UNKNOWN_SUPPORT', 'UNKNOWN_ROTATION', 'UNKNOWN_RESIDUAL',
         'UNKNOWN_IDENTIFIABILITY', 'NO_SUPPORTED_TIME_DEVIATION',
         'UNKNOWN_MULTIPLE_PHASES', 'UNKNOWN_SEARCH_BOUNDARY', 'NONPOSITIVE_VALUE')


def validate(value):
    x, confidence, times = (np.asarray(value[k]) for k in ('directions', 'confidence', 'times'))
    if x.shape != (141, 4, 2) or confidence.shape != (141, 4) or times.shape != (141,):
        raise ValueError('Invalid synthetic feature dimensions')
    if not np.isfinite(times).all() or not np.allclose(times, np.arange(141)/24, rtol=0, atol=1e-10):
        raise ValueError('Invalid physical time grid')
    return x[..., 0] + 1j*x[..., 1], confidence


def interval_sums(a):
    prefix = np.concatenate((np.zeros(a.shape[:-1]+(1,), dtype=a.dtype), np.cumsum(a, axis=-1)), axis=-1)
    return prefix[..., None, 1:] - prefix[..., :-1, None]


def edge_sums(a):
    return interval_sums(a) - a[..., :, None]


def contexts(source, target, part, threshold):
    x0, xc0 = validate(source)
    y0, yc0 = validate(target)
    bones = PARTS[part]
    x, xc = x0[:, bones], xc0[:, bones]
    ys = np.full((49, 141, 2), np.nan+1j*np.nan)
    cs = np.full((49, 141, 2), np.nan)
    for i, d in enumerate(LAGS):
        target_index = np.arange(141)+d
        valid = (target_index >= 0) & (target_index < 141)
        ys[i, valid] = y0[target_index[valid]][:, bones]
        cs[i, valid] = yc0[target_index[valid]][:, bones]
    valid_x = np.isfinite(x) & np.isfinite(xc) & (xc >= threshold) & (np.abs(np.abs(x)-1) < 1e-6)
    valid_y = np.isfinite(ys) & np.isfinite(cs) & (cs >= threshold) & (np.abs(np.abs(ys)-1) < 1e-6)
    mask = valid_x & valid_y.all(axis=0)
    weight = np.where(mask, np.minimum(xc, np.min(cs, axis=0)), 0.0)
    return np.where(mask, x, 0), np.where(mask[None], ys, 0), mask, weight


def variance_grid(omega, edge_weight):
    # omega (...,bone,time), weight (bone,time); only interval-internal edges.
    w = edge_sums(edge_weight)
    a = edge_sums(omega * edge_weight)
    b = edge_sums(omega**2 * edge_weight)
    with np.errstate(divide='ignore', invalid='ignore'):
        energy = b - np.divide(a*a, w, out=np.zeros_like(a), where=w > 0)
        result = np.sum(np.maximum(energy, 0), axis=-3) / np.sum(w, axis=-3)
    return np.where(np.isfinite(result), result, 0)


def grid(source, target, part, threshold):
    x, ys, mask, w = contexts(source, target, part, threshold)
    wb = interval_sums(w.T)
    total_w = wb.sum(axis=0)
    correlation = interval_sums((x[None] * ys.conj() * w[None]).transpose(0, 2, 1))
    with np.errstate(divide='ignore', invalid='ignore'):
        losses = 2*(total_w[None] - np.abs(correlation).sum(axis=1))/total_w[None]
        concentration = np.min(np.abs(correlation)/wb[None], axis=1)
    losses = np.where(np.isfinite(losses), np.maximum(losses, 0), np.inf)
    concentration = np.where(np.isfinite(concentration), concentration, 0)
    known = interval_sums(mask.sum(axis=1))
    frame_known = mask.any(axis=1)
    valid_frames = interval_sums(frame_known.astype(int))
    a, b = np.indices((141, 141))
    length = b-a+1
    supported = (length >= 8) & (known >= .8*2*length) & (valid_frames >= 8) & (valid_frames == length)
    edge_w = np.zeros_like(w)
    edge_w[1:] = np.minimum(w[1:], w[:-1])
    omega_x = np.zeros_like(w)
    omega_x[1:] = np.angle(x[:-1].conj()*x[1:])
    omega_y = np.zeros_like(ys.real)
    omega_y[:, 1:] = np.angle(ys[:, :-1].conj()*ys[:, 1:])
    source_j = variance_grid(omega_x.T, edge_w.T)
    target_j = variance_grid(omega_y.transpose(0, 2, 1), edge_w.T)
    raw_zero = interval_sums((w*np.abs(x-ys[24])**2).sum(axis=1))
    raw_zero = np.divide(raw_zero, total_w, out=np.full_like(raw_zero, np.inf), where=total_w>0)
    return dict(loss=losses, concentration=concentration, source_J=source_j, target_J=target_j,
                weight=total_w, support=supported, mask=mask, raw_zero=raw_zero,
                correlation=correlation, bone_weight=wb)


def key(row):
    return row['start'], row['end'], abs(row['lag']), row['lag'], row['part']


def solve(rows, total=141):
    endings = [[] for _ in range(total)]
    for row in rows:
        endings[row['end']].append(row)
    best = [(0., [])]
    for end in range(total):
        candidates = [best[-1]]
        for row in endings[end]:
            score, chosen = best[row['start']]
            candidates.append((score+row['value'], chosen+[row]))
        winner = candidates[0]
        for candidate in candidates[1:]:
            if candidate[0] > winner[0]+1e-12 or (abs(candidate[0]-winner[0]) <= 1e-12 and
                (len(candidate[1]), tuple(map(key,candidate[1]))) < (len(winner[1]), tuple(map(key,winner[1])))):
                winner = candidate
        best.append(winner)
    return {'objective': best[-1][0], 'selected': best[-1][1], 'K':len(best[-1][1])}


def analyze_part(source, target, part):
    blocks = [grid(source,target,part,h) for h in THRESHOLDS]
    losses = np.stack([b['loss'] for b in blocks])
    conservative = losses.max(axis=0)
    order = np.array(sorted(range(49),key=lambda i:(abs(int(LAGS[i])),int(LAGS[i]))))
    best = order[np.argmin(conservative[order], axis=0)]
    aa,bb = np.indices((141,141))
    chosen_loss = losses[:,best,aa,bb]
    rms = np.sqrt(conservative)
    best_rms = rms[best,aa,bb]
    support = np.logical_and.reduce([b['support'] for b in blocks])
    finite_best = np.isfinite(best_rms)
    phase_set = (rms <= best_rms[None]+PAIR) & finite_best[None]
    low = np.min(np.where(phase_set,LAGS[:,None,None],25),axis=0)
    high = np.max(np.where(phase_set,LAGS[:,None,None],-25),axis=0)
    j = np.minimum.reduce([np.minimum(b['source_J'],b['target_J'][best,aa,bb]) for b in blocks])
    rotation_ok = np.logical_and.reduce([(b['concentration'][best,aa,bb] >= .25) &
        (np.abs(b['correlation'][best,:,aa,bb]).min(axis=-1)>1e-12) for b in blocks])
    length = bb-aa+1
    safe_length=np.maximum(length,1)
    cost=1+math.ceil(math.log2(141))+(2*np.floor(np.log2(safe_length))+1)+6+1
    with np.errstate(invalid='ignore'):
        gain=np.min(losses[:,NULL].min(axis=1)-chosen_loss,axis=0)
    weight=np.minimum.reduce([b['weight'] for b in blocks])
    value=weight/2*np.maximum(0,gain-PAIR**2)-EPS**2*cost
    value=np.where(np.isfinite(value),value,-np.inf)
    failures=[~support,~rotation_ok,best_rms>PAIR,2*np.sqrt(j)<=PAIR,
              phase_set[NULL].any(axis=0),(high-low>4)|((low<0)&(high>0)),
              (low==-24)|(high==24),value<=1e-12]
    code=np.zeros((141,141),dtype=np.uint16)
    for bit, failed in enumerate(failures):code |= failed.astype(np.uint16)<<bit
    status=np.full((141,141),len(NAMES),dtype=np.uint8)
    for bit in range(len(NAMES)-1,-1,-1):status[failures[bit]]=bit
    rows=[]
    for a,b in np.argwhere(code==0):
        index=int(best[a,b]); d=int(LAGS[index])
        rows.append({'part':part,'start':int(a),'end':int(b),'lag':d,
                     'value':float(value[a,b]),'cost':float(cost[a,b]),
                     'profile_rms':float(best_rms[a,b]),'J':float(j[a,b]),
                     'null_gain':float(gain[a,b]),'phase_set':LAGS[phase_set[:,a,b]].tolist(),
                     'raw_zero_loss':[float(x['raw_zero'][a,b]) for x in blocks],
                     'rotation_angles':[np.angle(x['correlation'][index,:,a,b]).tolist() for x in blocks],
                     'profile_curves':[x['loss'][:,a,b].tolist() for x in blocks]})
    solved=solve(rows)
    family=(length>=8)
    counts={name:int(((status==i)&family).sum()) for i,name in enumerate(NAMES)}
    counts['QUALIFIED']=int(((code==0)&family).sum())
    counts['all_intervals']=int(family.sum())
    known=np.logical_and.reduce([b['mask'] for b in blocks])
    central=(24,116)
    diagnostics={'common_known_slots':int(known.sum()),'nominal_slots':282,
                 'central_null_profile_rms':np.sqrt(losses[:,24,central[0],central[1]]).tolist(),
                 'central_raw_zero_loss':[float(b['raw_zero'][central]) for b in blocks],
                 'central_J':float(j[central]),'central_status':NAMES[status[central]] if status[central]<len(NAMES) else 'QUALIFIED'}
    evidence={'status':status,'failure_bits':code,'best_lag':LAGS[best],
              'value':value,'best_profile_rms':best_rms,'J':j,'phase_low':low,'phase_high':high,
              'common_mask':known,'profile_loss':losses,'gain':gain}
    return solved|{'counts':counts,'diagnostics':diagnostics},evidence


def analyze(source,target):
    started=time.perf_counter()
    results,evidence={},{}
    for part in PARTS:
        results[part],arrays=analyze_part(source,target,part)
        evidence.update({part+'__'+k:v for k,v in arrays.items()})
    return {'parts':results,'K':sum(r['K'] for r in results.values()),
            'selected':[row for r in results.values() for row in r['selected']],
            'seconds':time.perf_counter()-started},evidence
