"""Pairwise shared-support phase evidence; conditional on visible pose."""
import math
import time
import numpy as np
from bindings import BASE,solve

LAGS=BASE.LAGS;NULL=BASE.NULL;PARTS=BASE.PARTS;HS=BASE.THRESHOLDS
TAU=BASE.PAIR;EPS=BASE.EPS
PAIRS=np.array([(i,j) for i in range(49) for j in range(i+1,49)],dtype=np.int16)
NAMES=('UNKNOWN_SUPPORT','UNKNOWN_COMPARISON_CYCLE','UNKNOWN_COMPARISON_GRAPH',
       'NO_SUPPORTED_TIME_DEVIATION','UNKNOWN_DIRECTION','UNKNOWN_MULTIPLE_PHASES',
       'UNKNOWN_SEARCH_BOUNDARY','UNKNOWN_WITNESS_SUPPORT','UNKNOWN_ROTATION',
       'UNKNOWN_RESIDUAL','NONPOSITIVE_VALUE')

def family():
    a,b=np.indices((141,141));valid=b-a+1>=8
    return a[valid],b[valid]

def sums(a,start,end):
    prefix=np.concatenate((np.zeros((1,)+a.shape[1:],dtype=a.dtype),np.cumsum(a,axis=0)),axis=0)
    return prefix[end+1]-prefix[start]

def context(source,target,part,h):
    x0,cx0=BASE.validate(source);y0,cy0=BASE.validate(target)
    bones=PARTS[part];x=x0[:,bones];cx=cx0[:,bones]
    ys=np.zeros((49,141,2),complex);cs=np.zeros((49,141,2));vy=np.zeros_like(cs,bool)
    vx=np.isfinite(x)&np.isfinite(cx)&(cx>=h)&(np.abs(np.abs(x)-1)<1e-6)
    for i,d in enumerate(LAGS):
        u=np.arange(141)+d;valid=(u>=0)&(u<141)
        y=y0[u[valid]][:,bones];c=cy0[u[valid]][:,bones]
        good=np.isfinite(y)&np.isfinite(c)&(c>=h)&(np.abs(np.abs(y)-1)<1e-6)
        ys[i,valid]=np.where(good,y,0);cs[i,valid]=np.where(good,c,0);vy[i,valid]=good
    return dict(x=np.where(vx,x,0),cx=np.where(vx,cx,0),vx=vx,ys=ys,cs=cs,vy=vy)

def shared(ctx,indices):
    mask=ctx['vx']&np.all(ctx['vy'][indices],axis=0)
    weight=np.where(mask,np.minimum(ctx['cx'],np.min(ctx['cs'][indices],axis=0)),0.)
    return mask,weight

def stats(ctx,indices,start,end,require_no_holes=False):
    mask,w=shared(ctx,indices)
    wb=sums(w,start,end);total=wb.sum(axis=1)
    slots=sums(mask.astype(np.int16),start,end).sum(axis=1)
    frames=sums(mask.any(axis=1).astype(np.int16),start,end)
    length=end-start+1
    support=(slots>=.8*2*length)&(frames>=8)&np.all(wb>0,axis=1)
    if require_no_holes:support&=frames==length
    losses=[];correlations=[];concentrations=[]
    for index in indices:
        c=sums(w*ctx['x']*ctx['ys'][index].conj(),start,end)
        with np.errstate(divide='ignore',invalid='ignore'):
            loss=2*(total-np.abs(c).sum(axis=1))/total
            concentration=np.min(np.abs(c)/wb,axis=1)
        if np.any(np.isfinite(loss)&(loss< -1e-12)):raise ArithmeticError('Profile loss below roundoff tolerance')
        loss=np.where(total>0,np.maximum(loss,0),np.inf)
        support&=np.isfinite(loss)
        losses.append(loss);correlations.append(c);concentrations.append(np.where(np.isfinite(concentration),concentration,0))
    return dict(loss=np.stack(losses),correlation=np.stack(correlations),
                concentration=np.stack(concentrations),weight=total,bone_weight=wb,
                slots=slots,frames=frames,support=support,mask=mask,raw_weight=w)

def edge_from_rms(r_d,r_e,supported):
    """Worst-h aggregation deliberately permits cross-threshold preferences."""
    a=np.max(r_d,axis=0);b=np.max(r_e,axis=0)
    return supported&(a>b+TAU+1e-12),supported&(b>a+TAU+1e-12)

def graph_geometry(edges):
    """edges[node,interval] stores uint64 outgoing neighbors."""
    edges=np.asarray(edges,dtype=np.uint64);count,n=edges.shape
    incoming=np.zeros((count,n),bool)
    for node in range(count):incoming[node]=np.any((edges&np.uint64(1<<node))!=0,axis=0)
    reach=edges.copy()
    for k in range(count):
        for i in range(count):
            route=(reach[i]&np.uint64(1<<k))!=0
            reach[i]|=np.where(route,reach[k],np.uint64(0))
    cycle=np.zeros(n,bool)
    for i in range(count):cycle|=(reach[i]&np.uint64(1<<i))!=0
    return ~incoming,cycle

def build_graph(contexts,start,end,keep_pair_curves=False):
    n=len(start);edges=np.zeros((49,n),np.uint64);known=np.zeros_like(edges)
    pair_curves=[];pair_support=[];pair_slots=[]
    for i,j in PAIRS:
        blocks=[stats(ctx,[i,j],start,end) for ctx in contexts]
        rms=np.sqrt(np.stack([q['loss'] for q in blocks]))
        good=np.logical_and.reduce([q['support'] for q in blocks])
        j_wins,i_wins=edge_from_rms(rms[:,0],rms[:,1],good)
        edges[j]|=np.where(j_wins,np.uint64(1<<int(i)),np.uint64(0))
        edges[i]|=np.where(i_wins,np.uint64(1<<int(j)),np.uint64(0))
        known[i]|=np.where(good,np.uint64(1<<int(j)),np.uint64(0))
        known[j]|=np.where(good,np.uint64(1<<int(i)),np.uint64(0))
        if keep_pair_curves:
            pair_curves.append(rms);pair_support.append(good);pair_slots.append(np.stack([q['slots'] for q in blocks]))
    membership,cycle=graph_geometry(edges)
    out={'edges':edges,'comparable':known,'D':membership,'cycle':cycle}
    if keep_pair_curves:out.update(pair_rms=np.stack(pair_curves),pair_support=np.stack(pair_support),pair_slots=np.stack(pair_slots))
    return out

def witnesses(contexts,start,end):
    all_blocks=[]
    for d in range(49):
        # Duplicate null entries are harmless and preserve a fixed anchor+5-null axis.
        blocks=[stats(ctx,[d,*NULL],start,end,True) for ctx in contexts]
        all_blocks.append(blocks)
    def stack(key):return np.stack([np.stack([q[key] for q in blocks]) for blocks in all_blocks])
    return {key:stack(key) for key in ('loss','correlation','concentration','weight','bone_weight','slots','frames','support','mask','raw_weight')}

def diagnostic_j(contexts,d,start,end):
    values=[]
    for ctx in contexts:
        _,w=shared(ctx,[d,*NULL]);w=w[start:end+1]
        edge=np.minimum(w[1:],w[:-1]);den=edge.sum()
        for series in (ctx['x'],ctx['ys'][d]):
            seq=series[start:end+1];omega=np.angle(seq[:-1].conj()*seq[1:]);mass=edge.sum(axis=0)
            mean=np.divide((edge*omega).sum(axis=0),mass,out=np.zeros(2),where=mass>0)
            values.append(float((edge*(omega-mean)**2).sum()/den) if den else 0.)
    return min(values)

def analyze_part(source,target,part,start=None,end=None):
    if start is None:start,end=family()
    start=np.asarray(start);end=np.asarray(end);n=len(start);columns=np.arange(n)
    contexts=[context(source,target,part,h) for h in HS]
    graph=build_graph(contexts,start,end);member=graph['D']
    previous=np.concatenate((np.zeros_like(member[:1]),member[:-1]),axis=0)
    components=(member&~previous).sum(axis=0)
    low=np.min(np.where(member,LAGS[:,None],25),axis=0)
    high=np.max(np.where(member,LAGS[:,None],-25),axis=0)
    witness=witnesses(contexts,start,end)
    eligible=np.all(witness['support'],axis=1)&member
    wrms=np.sqrt(witness['loss'][:,:,0]).max(axis=1)
    score=np.where(eligible,wrms,np.inf)
    order=np.array(sorted(range(49),key=lambda i:(abs(int(LAGS[i])),int(LAGS[i]))))
    best=order[np.argmin(score[order],axis=0)]
    picked=score[best,columns]
    concentration=witness['concentration'][best,:,0,columns]
    correlation=witness['correlation'][best,:,0,columns]
    rot=(concentration>=.25).all(axis=1)&(np.abs(correlation).min(axis=(1,2))>1e-12)
    loss=witness['loss'][best,:,:,columns]
    gain=(loss[:,:,1:].min(axis=2)-loss[:,:,0]).min(axis=1)
    weight=witness['weight'][best,:,columns].min(axis=1)
    length=end-start+1
    cost=1+math.ceil(math.log2(141))+(2*np.floor(np.log2(length))+1)+6+1
    value=weight/2*np.maximum(0,gain-TAU**2)-EPS**2*cost
    value=np.where(np.isfinite(value),value,-np.inf)
    failures=[~np.any(graph['comparable']!=0,axis=0),graph['cycle'],components==0,
              member[NULL].any(axis=0),(low< -2)&(high>2),components>1,
              member[0]|member[-1],~eligible.any(axis=0),~rot,picked>TAU,value<=1e-12]
    bits=np.zeros(n,np.uint16);status=np.full(n,len(NAMES),np.uint8)
    for i,bad in enumerate(failures):bits|=bad.astype(np.uint16)<<i
    for i in reversed(range(len(NAMES))):status[failures[i]]=i
    rows=[]
    for k in np.flatnonzero(bits==0):
        d=int(best[k]);a=int(start[k]);b=int(end[k]);phase=LAGS[member[:,k]].tolist()
        rows.append(dict(part=part,start=a,end=b,lag=int(LAGS[d]),diagnostic_best_lag=int(LAGS[d]),
            direction='delay' if phase[0]>0 else 'advance',phase_set=phase,value=float(value[k]),
            cost=float(cost[k]),profile_rms=float(picked[k]),null_gain=float(gain[k]),
            rotation_angles=np.angle(correlation[k]).tolist(),J=diagnostic_j(contexts,d,a,b),
            conditional_evidence=True,witness_no_empty_frame=True,interval_index=int(k)))
    result=solve(rows)
    counts={name:int((status==i).sum()) for i,name in enumerate(NAMES)}
    counts.update(QUALIFIED=int((bits==0).sum()),all_intervals=n)
    oldmask=np.logical_and.reduce([BASE.contexts(source,target,part,h)[2] for h in HS])
    central=[stats(ctx,[24],np.array([24]),np.array([116]))['loss'][0,0] for ctx in contexts]
    result.update(counts=counts,diagnostics={'common_known_slots':int(oldmask.sum()),'nominal_slots':282,
        'central_null_profile_rms':np.sqrt(central).tolist(),'central_null_support_definition':'source+target0 only',
        'source_visible_slots':[int(ctx['vx'].sum()) for ctx in contexts]})
    arrays={'interval_start':start,'interval_end':end,'status':status,'failure_bits':bits,
            'edges':graph['edges'],'pair_comparable':graph['comparable'],'phase_membership':member,
            'cycle':graph['cycle'],'common_mask':oldmask,'best_lag':LAGS[best],'value':value,
            'witness_eligible':eligible,'witness_rms':wrms,'witness_gain_anchor':gain}
    for key in ('loss','weight','bone_weight','slots','frames','support','mask','raw_weight'):
        arrays['witness_'+key]=witness[key]
    selected=result['selected']
    if selected:
        sa=np.array([r['start'] for r in selected]);sb=np.array([r['end'] for r in selected])
        selected_pairs=build_graph(contexts,sa,sb,True)
        for key in ('pair_rms','pair_support','pair_slots'):arrays['selected_'+key]=selected_pairs[key]
    return result,arrays

def analyze(source,target):
    started=time.perf_counter();parts={};arrays={}
    for part in PARTS:
        result,evidence=analyze_part(source,target,part);parts[part]=result
        arrays.update({part+'__'+key:val for key,val in evidence.items()})
    return {'parts':parts,'K':sum(r['K'] for r in parts.values()),
            'selected':[r for p in parts.values() for r in p['selected']],
            'seconds':time.perf_counter()-started,'scope':'conditional visible-support directional evidence'},arrays
