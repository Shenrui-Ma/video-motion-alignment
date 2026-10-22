"""Five gates at a frozen identity proposal; no new lag search."""
import numpy as np
EPS=1e-12
NULLS=(-2,-1,0,1,2)


def candidate_family(proposal):
    d=proposal.get('candidate');h=proposal.get('secondary_identity_lag')
    if not proposal.get('dual_identity_consistent') or type(d) is not int or type(h) is not int or abs(d-h)>2:
        return 'UNKNOWN_identity_candidate'
    if d>=4 and h>=4:return 'DELAY'
    if abs(d)<=2 and abs(h)<=2:return 'ALIGNED'
    if d<=-3 and h<=-3:return 'ADVANCED'
    return 'UNKNOWN_mixed_identity_family_or_lag3'


def common_costs(source,target,source_conf,target_conf,window,threshold,candidate):
    s,t=np.asarray(source),np.asarray(target);sc,tc=np.asarray(source_conf),np.asarray(target_conf)
    if s.shape!=t.shape or s.ndim!=4 or s.shape[:2]!=(3,141) or s.shape[-1]!=2:raise ValueError('Three-view feature shape')
    if sc.shape!=s.shape[:-1] or tc.shape!=t.shape[:-1] or not np.isfinite(sc).all() or not np.isfinite(tc).all():raise ValueError('Finite confidence shape')
    if type(candidate) is not int or not -24<candidate<24:raise ValueError('Reliable nonboundary candidate required')
    a,b=window
    if not (type(a) is int and type(b) is int and 0<=a<=b<141):raise ValueError('Window')
    frames=np.arange(a,b+1);lags=sorted(set([candidate,*NULLS]))
    valid=np.isfinite(s[:,frames]).all(axis=(0,3))&(sc[:,frames]>=threshold).all(0);weight=sc[:,frames].min(0)
    for d in lags:
        idx=frames+d;inside=(idx>=0)&(idx<141);safe=np.clip(idx,0,140)
        valid &= inside[:,None]&np.isfinite(t[:,safe]).all(axis=(0,3))&(tc[:,safe]>=threshold).all(0)
        weight=np.minimum(weight,tc[:,safe].min(0))
    weight=np.where(valid,weight.clip(0,1),0);denom=float(weight.sum())
    out={'window':list(window),'candidate_lag':candidate,'lags':lags,'common_mask':valid.tolist(),'common_weights':weight.tolist(),
         'coverage':float(valid.mean()),'valid_frames':int((weight.sum(-1)>0).sum()),'weight_sum':denom}
    if out['coverage']<.8 or out['valid_frames']<8 or denom<=0:return out|{'status':'UNKNOWN_common_support','costs':None}
    costs=np.empty((3,3,len(lags)))
    for vi in range(3):
        for vj in range(3):
            for k,d in enumerate(lags):
                safe=np.clip(frames+d,0,140);distance=np.linalg.norm(s[vi,frames]-t[vj,safe],axis=-1)
                costs[vi,vj,k]=(np.where(valid,np.nan_to_num(distance),0)*weight).sum()/denom
    if not np.isfinite(costs).all():raise ValueError('Nonfinite cost')
    return out|{'status':'measured','costs':costs.tolist()}


def decisions(record,proposal):
    unknown=lambda reason:{x:{'status':'UNKNOWN','reason':reason} for x in 'ABCDE'}
    d=proposal.get('candidate');family=candidate_family(proposal)
    out={'candidate_lag':d,'candidate_from':'frozen .3 identity; .5 consistency only','identity_family':family}
    if family.startswith('UNKNOWN'):return out|{'shared_gate':family,'arms':unknown(family)}
    if record['status']!='measured':return out|{'shared_gate':record['status'],'arms':unknown(record['status'])}
    if record['candidate_lag']!=d:raise ValueError('Candidate changed')
    lags=record['lags'];c=np.asarray(record['costs']);expected=sorted(set([d,*NULLS]))
    if lags!=expected or c.shape!=(3,3,len(lags)) or not np.isfinite(c).all() or (c<0).any():raise ValueError('Frozen lag/cost contract')
    k=lags.index(d);ni=[lags.index(x) for x in NULLS];mean=c.mean((0,1))
    if c[:,:,k].max()>.5:return out|{'shared_gate':'UNKNOWN_view_residual','arms':unknown('large_residual_in_at_least_one_view')}
    if family in ('ALIGNED','ADVANCED'):return out|{'shared_gate':family,'arms':{x:{'status':family} for x in 'ABCDE'}}
    identity_adv=c[0,0,ni]-c[0,0,k];mean_adv=mean[ni]-mean[k];all_adv=c[:,:,ni]-c[:,:,k,None]
    values={'A':float(np.min(identity_adv/np.maximum(c[0,0,ni],1e-8))),
            'B':float(np.min(mean_adv/np.maximum(mean[ni],1e-8))),
            'C':float(identity_adv.min()),'D':float(mean_adv.min()),'E':float(all_adv.min())}
    arms={}
    for name,v in values.items():
        limit=.5 if name in 'AB' else 0
        arms[name]={'status':'ON' if v>limit+EPS else ('UNKNOWN' if name=='E' else 'NO_ON'),
                    'advantage_or_gain':v,'decision_limit':limit,'candidate_lag':d}
    arms['E']['upper_envelope']=float(all_adv.min(-1).max())
    return out|{'shared_gate':'DELAY_ELIGIBLE','arms':arms}
