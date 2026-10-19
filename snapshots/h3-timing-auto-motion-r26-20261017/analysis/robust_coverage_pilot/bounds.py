"""Conditional direction-distance completion bounds; standard-library only.

No pose imputation, candidate selection, or controller action is performed here.
Observed values are assumed exact. All missing weight caps are fixed to one.
"""
import math

GAIN = .5
RESIDUAL = .5
EPS = 1e-8
MARGIN = 1e-12


def validate_slot(slot):
    if type(slot['frame']) is not int:
        raise ValueError('integer physical frame required')
    for key in ('proposal', 'null'):
        x = slot[key]
        if x is not None and (not math.isfinite(x) or not 0 <= x <= 2):
            raise ValueError('direction distance must be None or within [0,2]')
    complete = slot['proposal'] is not None and slot['null'] is not None
    w = slot['weight']
    if complete:
        if w is None or not math.isfinite(w) or not 0 <= w <= 1:
            raise ValueError('complete triplet needs confidence weight in [0,1]')
    elif w is not None:
        raise ValueError('incomplete triplet weight is unknown, not zero')


def ratio_extreme(known_sum, known_weight, values, maximum):
    """Exact extremum of (S+sum w_i*v_i)/(W+sum w_i), 0<=w_i<=1.

    Sorting v produces a prefix optimizer; including the empty prefix preserves
    the option that all missing weights vanish. W must be positive.
    """
    if known_weight <= 0:
        return 2. if maximum else 0.
    candidates = [known_sum/known_weight]
    for count, value in enumerate(sorted(values, reverse=maximum), 1):
        known_sum += value
        candidates.append(known_sum/(known_weight+count))
    return (max if maximum else min)(candidates)


def interval(slots, method, tight):
    if method not in ('uniform', 'confidence_completion'):
        raise ValueError('unknown method')
    if not slots:
        return {'certified':False, 'reasons':['empty_domain']}
    for slot in slots:
        validate_slot(slot)
    complete = [s for s in slots if s['proposal'] is not None and s['null'] is not None]
    partial = [s for s in slots if s['proposal'] is None or s['null'] is None]
    # frame IDs are shared across bones; do not count bones as independent frames.
    valid_frames = len({s['frame'] for s in complete if s['weight'] > 0})
    observed_weight = sum(s['weight'] for s in complete)
    if method == 'uniform':
        weights = [1.]*len(complete)
    else:
        weights = [s['weight'] for s in complete]
    W = sum(weights)
    Sp = sum(w*s['proposal'] for s,w in zip(complete,weights))
    Sn = sum(w*s['null'] for s,w in zip(complete,weights))
    partial_p_upper = [s['proposal'] if tight and s['proposal'] is not None else 2. for s in partial]
    partial_n_lower = [s['null'] if tight and s['null'] is not None else 0. for s in partial]
    partial_h_lower = [(1-GAIN)*n-p for p,n in zip(partial_p_upper,partial_n_lower)]
    J = (1-GAIN)*Sn-Sp
    if method == 'uniform':
        J += sum(partial_h_lower)
        denominator = len(slots)
        Cp_upper = (Sp+sum(partial_p_upper))/denominator
        Cn_lower = (Sn+sum(partial_n_lower))/denominator
        H_lower = J/denominator
    else:
        J += sum(min(0.,h) for h in partial_h_lower)
        Cp_upper = ratio_extreme(Sp,W,partial_p_upper,True)
        Cn_lower = ratio_extreme(Sn,W,partial_n_lower,False)
        # Conservative normalized lower bound: use W if numerator negative,
        # W+M if positive. Certification uses unnormalized J directly.
        H_lower = J/(W+len(partial) if J>=0 else W) if W>0 else None
    reasons=[]
    if valid_frames<8:reasons.append('fewer_than_8_common_frames')
    if observed_weight<=0:reasons.append('no_positive_observed_confidence_weight')
    if not J>MARGIN:reasons.append('gain_not_certified')
    if Cp_upper>RESIDUAL:reasons.append('residual_not_certified')
    if not Cn_lower>EPS:reasons.append('null_denominator_not_certified')
    return {'method':method,'tight':tight,'certified':not reasons,'reasons':reasons,
            'expected_slots':len(slots),'common_slots':len(complete),
            'common_coverage':len(complete)/len(slots),'common_frames':valid_frames,
            'observed_confidence_weight':observed_weight,'method_observed_weight':W,
            'missing_weight_cap_sum':len(partial),'proposal_observed_sum':Sp,
            'null_observed_sum':Sn,'advantage_unnormalized_lower':J,
            'advantage_normalized_lower':H_lower,'proposal_cost_upper':Cp_upper,
            'null_cost_lower':Cn_lower,
            'partial_proposal_known':sum(s['proposal'] is not None for s in partial),
            'partial_null_known':sum(s['null'] is not None for s in partial)}


def joint_decision(entries):
    """Two confidence entries, each already tested against every null."""
    if set(entries)!={'0.3','0.5'}:raise ValueError('both fixed confidences required')
    reasons=[];lags=[]
    for c,e in entries.items():
        if e.get('candidate_flags'):reasons.append(c+':candidate_rejected')
        lag=e.get('candidate_lag');lags.append(lag)
        comparisons=e.get('comparisons',[])
        if [r.get('null_lag') for r in comparisons]!=[-2,-1,0,1,2]:
            reasons.append(c+':missing_null_comparisons')
        if any(not r['bound']['certified'] for r in comparisons):reasons.append(c+':bound_unknown')
    if any(x is None for x in lags):reasons.append('no_candidate')
    else:
        if abs(lags[0]-lags[1])>2:reasons.append('confidence_lag_disagreement')
        if not (min(lags)>2 or max(lags)<-2):reasons.append('not_same_signed_outside_tolerance')
    status='UNKNOWN' if reasons else ('CERTIFIED_DELAYED_EVIDENCE' if min(lags)>2 else 'CERTIFIED_ADVANCED_EVIDENCE')
    return {'status':status,'reasons':reasons,'candidate_lags':lags,
            'scope':'conditional gain/residual evidence, not unique physical lag or policy action'}


def select_candidate(curve):
    if len(curve)!=49 or [r['lag_frames'] for r in curve]!=list(range(-24,25)):
        raise ValueError('complete ordered49 curve required')
    finite=[r for r in curve if r['error'] is not None and math.isfinite(r['error']) and r['valid_frame_count']>=8]
    if not finite:return {'candidate_lag':None,'candidate_flags':['no_finite_8frame_proposal']}
    best=min(finite,key=lambda r:r['error'])
    remote=[r for r in finite if abs(r['lag_frames']-best['lag_frames'])>=4]
    runner=min(remote,key=lambda r:r['error']) if remote else None
    gap=(runner['error']-best['error'])/max(best['error'],1e-8) if runner else None
    flags=[]
    if abs(best['lag_frames'])==24:flags.append('search_boundary')
    if gap is not None and gap<.05:flags.append('observed_flat_or_multiple_phases')
    if best['error']>.5:flags.append('observed_residual_shape')
    return {'candidate_lag':best['lag_frames'],'candidate_flags':flags,'best':best,
            'remote_runner':runner,'observed_remote_relative_gap':gap}
