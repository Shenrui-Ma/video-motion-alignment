"""Declared gain baseline with common support within each null comparison."""
import numpy as np
from physical_tolerance import align,CONF

def compare(source,edited,window,lag,feature,tolerance=2):
    selected=(source['frames']>=window[0]) & (source['frames']<=window[1])
    times=source['times'][selected];fps=source['raw']['video']['fps']
    s=source[feature][selected];sc=source[CONF[feature]][selected]
    p,pc=align(edited,times+lag/fps,feature)
    rows=[]
    for e in range(-tolerance,tolerance+1):
        n,nc=align(edited,times+e/fps,feature)
        valid=np.isfinite(s).all(-1)&np.isfinite(p).all(-1)&np.isfinite(n).all(-1)
        weights=np.where(valid,np.minimum(np.minimum(sc,pc),nc).clip(0,1),0)
        coverage=float(valid.mean());frames=int((weights.sum(-1)>0).sum())
        row={'null_lag':e,'coverage':coverage,'valid_frames':frames,
             'valid_vectors':int(valid.sum()),'weight_sum':float(weights.sum())}
        if coverage<.8 or frames<8 or weights.sum()<=0:
            row['status']='unknown_support'
        else:
            cp=float((np.nan_to_num(np.linalg.norm(s-p,axis=-1))*weights).sum()/weights.sum())
            cn=float((np.nan_to_num(np.linalg.norm(s-n,axis=-1))*weights).sum()/weights.sum())
            row.update(proposal_cost=cp,null_cost=cn,gain=(cn-cp)/max(cn,1e-8),
                       status='valid' if cp<=.5 else 'unknown_residual_shape')
        rows.append(row)
    result={'proposal_lag':lag,'null_comparisons':rows}
    if any(r['status']!='valid' for r in rows):return result|{'status':'unknown','min_gain':None}
    return result|{'status':'measured','min_gain':min(r['gain'] for r in rows)}
