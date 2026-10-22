"""Additional proposal eligibility; existing ranking and temporal policy remain intact."""
import copy,time
import numpy as np
from H3AutomaticWindowRouter.automatic_window_policy import candidate

def costs(a,b,w):
    valid = np.isfinite(a).all(-1)&np.isfinite(b).all(-1)&np.isfinite(w)&(w>0)
    weights = np.where(valid,w,0)
    aa=np.where(valid[...,None],a,0); bb=np.where(valid[...,None],b,0)
    sums=weights.sum(axis=0); total=float(sums.sum())
    if total<=0: return None
    am=(weights[...,None]*aa).sum(axis=0)/np.maximum(sums[:,None],1e-12)
    bm=(weights[...,None]*bb).sum(axis=0)/np.maximum(sums[:,None],1e-12)
    ac=np.where(valid[...,None],a-am,0);bc=np.where(valid[...,None],b-bm,0)
    mse_a=float((weights*np.sum(ac*ac,axis=-1)).sum()/total)
    mse_b=float((weights*np.sum(bc*bc,axis=-1)).sum()/total)
    raw=float((weights*np.linalg.norm(aa-bb,axis=-1)).sum()/total)
    centered=float((weights*np.linalg.norm(ac-bc,axis=-1)).sum()/total)
    offset=float((sums*np.linalg.norm(am-bm,axis=-1)).sum()/total)
    correlation=None if mse_a*mse_b<=1e-20 else float((weights*np.sum(ac*bc,axis=-1)).sum()/total/np.sqrt(mse_a*mse_b))
    return {'weighted_direction_error':raw,'centered_direction_error':centered,'mean_direction_offset':offset,'source_direction_rms_variation':float(np.sqrt(mse_a)),'target_direction_rms_variation':float(np.sqrt(mse_b)),'centered_vector_correlation':correlation,'valid_entries':int(valid.sum()),'valid_fraction':float(valid.mean())}

def at(features, indices, joints):
    x,c=features
    valid=(indices>=0)&(indices<len(x))
    values=np.full((len(indices),len(joints),2),np.nan)
    confidence=np.zeros((len(indices),len(joints)))
    values[valid]=x[indices[valid]][:,joints]
    confidence[valid]=c[indices[valid]][:,joints]
    return values,confidence

def compare(source,target,window,arm,lag,threshold):
    joints={'left':[0,1],'right':[2,3],'both':[0,1,2,3]}[arm]
    indices=np.arange(window[0],window[1]+1)
    s,sc=at(source,indices,joints);p,pc=at(target,indices+lag,joints)
    rows=[]
    for epsilon in range(-2,3):
        n,nc=at(target,indices+epsilon,joints)
        valid=np.isfinite(s).all(-1)&np.isfinite(p).all(-1)&np.isfinite(n).all(-1)
        w=np.where(valid,np.minimum(np.minimum(sc,pc),nc),0)
        w=np.where(w>=threshold,w,0)
        cp=costs(s,p,w);cn=costs(s,n,w)
        row={'null_lag':epsilon,'coverage':float(valid.mean()),'valid_frames':int((w.sum(-1)>0).sum())}
        if cp is None or cn is None or valid.mean()<.8 or (w.sum(-1)>0).sum()<8:
            row['status']='unknown_support'
        else:
            row.update(status='measured',raw_proposal_cost=cp['weighted_direction_error'],raw_null_cost=cn['weighted_direction_error'],centered_proposal_cost=cp['centered_direction_error'],centered_null_cost=cn['centered_direction_error'])
            row['raw_gain']=(row['raw_null_cost']-row['raw_proposal_cost'])/max(row['raw_null_cost'],1e-8)
            row['centered_gain']=(row['centered_null_cost']-row['centered_proposal_cost'])/max(row['centered_null_cost'],1e-8)
        rows.append(row)
    good=all(x['status']=='measured' for x in rows)
    return {'null_comparisons':rows,'status':'measured' if good else 'unknown','min_raw_gain':min(x['raw_gain'] for x in rows) if good else None,'min_centered_gain':min(x['centered_gain'] for x in rows) if good else None}


def apply(observer, loaded):
    """Use existing valid-domain arm features and only demote qualifying rows."""
    started=time.monotonic(); result=copy.deepcopy(observer);details=[]
    for j,row in enumerate(observer['windows']):
        proposal=candidate(row)
        if proposal is None: continue
        arm={'left_arm_direction':'left','right_arm_direction':'right','arm_direction':'both'}[row['feature']]
        comparisons={}
        for c in (.3,.5):
            a,b=loaded['source',c],loaded['target',c]
            comparisons[str(c)]=compare((a['arm_direction'],a['arm_conf']),(b['arm_direction'],b['arm_conf']),row['window'],arm,int(proposal['lags'][str(c)]),c)
        measured=all(v['status']=='measured' for v in comparisons.values())
        if measured:
            raw=min(v['min_raw_gain'] for v in comparisons.values())
            if abs(raw-proposal['min_gain'])>=1e-10:raise ValueError('centered support raw-gain parity differs')
            gain=min(v['min_centered_gain'] for v in comparisons.values())
        else:raw=gain=None
        accepted=measured and gain>.5
        if not accepted:result['windows'][j]['status']='unknown'
        details.append({'row_index':j,'window':row['window'],'feature':row['feature'],'lags':proposal['lags'],'original_status':row['status'],'original_min_gain':proposal['min_gain'],'recomputed_raw_min_gain':raw,'centered_min_gain':gain,'accepted':accepted,'comparisons':comparisons})
    result['centered_eligibility']={'schema':'r142-centered-eligibility-v1','strict_gain_threshold':.5,'accepted':sum(x['accepted'] for x in details),'rejected':sum(not x['accepted'] for x in details),'candidates':details,'seconds':time.monotonic()-started}
    return result


def unfiltered(observer):
    result=copy.deepcopy(observer);proof=result.pop('centered_eligibility')
    for row in proof['candidates']:result['windows'][row['row_index']]['status']=row['original_status']
    return result
