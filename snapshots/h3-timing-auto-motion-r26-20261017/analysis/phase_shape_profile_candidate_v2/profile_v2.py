"""Direction-set observer; inherited losses/support/DP are byte-frozen v1."""
import math
import time
import numpy as np
from frozen import V1 as base

NAMES=('UNKNOWN_SUPPORT','UNKNOWN_ROTATION','UNKNOWN_RESIDUAL',
       'NO_SUPPORTED_TIME_DEVIATION','UNKNOWN_DIRECTION_AMBIGUITY',
       'UNKNOWN_MULTIPLE_PHASES','UNKNOWN_SEARCH_BOUNDARY','NONPOSITIVE_VALUE')

def set_geometry(membership):
    """Keep integer topology; a disconnected positive set stays ambiguous."""
    previous=np.concatenate((np.zeros_like(membership[:1]),membership[:-1]),axis=0)
    components=np.sum(membership & ~previous,axis=0)
    low=np.min(np.where(membership,base.LAGS.reshape((-1,)+(1,)*(membership.ndim-1)),25),axis=0)
    high=np.max(np.where(membership,base.LAGS.reshape((-1,)+(1,)*(membership.ndim-1)),-25),axis=0)
    same_side=(components>0)&((low>2)|(high< -2))
    null=membership[base.NULL].any(axis=0)
    boundary=membership[0]|membership[-1]
    return dict(components=components,low=low,high=high,same_side=same_side,null=null,boundary=boundary)

def component_lists(values):
    out=[]
    for value in values:
        if not out or value!=out[-1][-1]+1:out.append([])
        out[-1].append(value)
    return out

def analyze_part(source,target,part):
    blocks=[base.grid(source,target,part,h) for h in base.THRESHOLDS]
    losses=np.stack([b['loss'] for b in blocks]);conservative=losses.max(axis=0)
    order=np.array(sorted(range(49),key=lambda i:(abs(int(base.LAGS[i])),int(base.LAGS[i]))))
    best=order[np.argmin(conservative[order],axis=0)]
    aa,bb=np.indices((141,141));chosen_loss=losses[:,best,aa,bb]
    rms=np.sqrt(conservative);best_rms=rms[best,aa,bb]
    support=np.logical_and.reduce([b['support'] for b in blocks])
    phase_set=(rms<=best_rms[None]+base.PAIR)&np.isfinite(best_rms)[None]
    geometry=set_geometry(phase_set)
    j=np.minimum.reduce([np.minimum(b['source_J'],b['target_J'][best,aa,bb]) for b in blocks])
    rotation_ok=np.logical_and.reduce([(b['concentration'][best,aa,bb]>=.25)&
        (np.abs(b['correlation'][best,:,aa,bb]).min(axis=-1)>1e-12) for b in blocks])
    length=bb-aa+1
    cost=1+math.ceil(math.log2(141))+(2*np.floor(np.log2(np.maximum(length,1)))+1)+6+1
    with np.errstate(invalid='ignore'):gain=np.min(losses[:,base.NULL].min(axis=1)-chosen_loss,axis=0)
    weight=np.minimum.reduce([b['weight'] for b in blocks])
    value=weight/2*np.maximum(0,gain-base.PAIR**2)-base.EPS**2*cost
    value=np.where(np.isfinite(value),value,-np.inf)
    failures=[~support,~rotation_ok,best_rms>base.PAIR,geometry['null'],~geometry['same_side'],
              geometry['components']>1,geometry['boundary'],value<=1e-12]
    code=np.zeros((141,141),dtype=np.uint16)
    for bit,failed in enumerate(failures):code|=failed.astype(np.uint16)<<bit
    status=np.full((141,141),len(NAMES),dtype=np.uint8)
    for bit in range(len(NAMES)-1,-1,-1):status[failures[bit]]=bit
    rows=[]
    for a,b in np.argwhere(code==0):
        index=int(best[a,b]);d=int(base.LAGS[index]);values=base.LAGS[phase_set[:,a,b]].tolist()
        rows.append({'part':part,'start':int(a),'end':int(b),'lag':d,
            'direction':'delay' if geometry['low'][a,b]>2 else 'advance','phase_set':values,
            'phase_components':component_lists(values),'point_estimate_validated':False,
            'value':float(value[a,b]),'cost':float(cost[a,b]),'profile_rms':float(best_rms[a,b]),
            'J':float(j[a,b]),'null_gain':float(gain[a,b]),
            'raw_zero_loss':[float(x['raw_zero'][a,b]) for x in blocks],
            'rotation_angles':[np.angle(x['correlation'][index,:,a,b]).tolist() for x in blocks],
            'profile_curves':[x['loss'][:,a,b].tolist() for x in blocks]})
    solved=base.solve(rows)
    for row in solved['selected']:row['diagnostic_best_lag']=row.pop('lag')
    family=length>=8
    counts={name:int(((status==i)&family).sum()) for i,name in enumerate(NAMES)}
    counts['QUALIFIED']=int(((code==0)&family).sum());counts['all_intervals']=int(family.sum())
    known=np.logical_and.reduce([b['mask'] for b in blocks]);central=(24,116)
    diagnostics={'common_known_slots':int(known.sum()),'nominal_slots':282,
        'central_null_profile_rms':np.sqrt(losses[:,24,24,116]).tolist(),
        'central_raw_zero_loss':[float(b['raw_zero'][central]) for b in blocks],
        'central_J':float(j[central]),'central_status':NAMES[status[central]] if status[central]<len(NAMES) else 'QUALIFIED'}
    evidence={'status':status,'failure_bits':code,'diagnostic_best_lag':base.LAGS[best],
        'value':value,'best_profile_rms':best_rms,'J':j,'phase_low':geometry['low'],
        'phase_high':geometry['high'],'phase_components':geometry['components'],
        'phase_membership':phase_set,'common_mask':known,'profile_loss':losses,'gain':gain}
    for threshold,block in zip(base.THRESHOLDS,blocks):
        for key in ('raw_zero','mask','weight'):evidence[f'h{threshold}__{key}']=block[key]
    return solved|{'counts':counts,'diagnostics':diagnostics},evidence

def analyze(source,target):
    started=time.perf_counter();results={};evidence={}
    for part in base.PARTS:
        results[part],arrays=analyze_part(source,target,part)
        evidence.update({part+'__'+k:v for k,v in arrays.items()})
    return {'parts':results,'K':sum(r['K'] for r in results.values()),
        'selected':[r for part in results.values() for r in part['selected']],
        'decision_target':'direction and engineering phase set; exact lag unvalidated',
        'seconds':time.perf_counter()-started},evidence
