"""Pose-derived query support only. No model, attention, image or GPU imports."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np

JOINTS=(5,6,7,9,11,12)
ANCHORS=(5,6,11,12)
BONES=((5,7),(7,9))
NAMES=('raw_source','current_target','aligned_desired','endpoint_union','unaligned_swept','aligned_swept')
CENTERS=np.array([(32*(c+.5),32*(r+.5)) for r in range(23) for c in range(41)],dtype=np.float64)


def capsule(d):
    d=np.asarray(d,dtype=np.float64)
    return np.where(d<=32,1,np.where(d>=64,0,.5*(1+np.cos(np.pi*(d-32)/32))))


def distance_segment(points,a,b):
    points=np.asarray(points);a=np.asarray(a);b=np.asarray(b);v=b-a
    den=np.sum(v*v,axis=-1)
    t=np.sum((points-a)*v,axis=-1)/np.where(den>0,den,1)
    t=np.where(den>0,np.clip(t,0,1),0)
    return np.linalg.norm(points-a-t[...,None]*v,axis=-1)


def pose_frame(pose,index):
    f=pose['frames'][index]
    if f['frame']!=index or abs(f['time_s']-index/24)>1e-8:raise ValueError('frame/time mismatch')
    if f['selection_ambiguous']:return None,'ambiguous_person'
    if f['selected_person'] is None:return None,'missing_person'
    person=f['persons'][f['selected_person']]
    pts={}
    for k in JOINTS:
        x,y=person['coco17_xy'][k];c=person['coco17_score'][k]
        if not np.isfinite([x,y,c]).all():return None,'nonfinite_joint_'+str(k)
        if c<.5:return None,'confidence_below_0.5_joint_'+str(k)
        if not (0<=x<1312 and 0<=y<736):return None,'out_of_frame_joint_'+str(k)
        pts[k]=np.array([x+.5,y+.5],dtype=np.float64)
    return pts,None


def align(source,target):
    x=np.array([source[k] for k in ANCHORS]);y=np.array([target[k] for k in ANCHORS])
    xc=x-x.mean(0);yc=y-y.mean(0)
    sx=np.linalg.svd(xc,compute_uv=False);sy=np.linalg.svd(yc,compute_uv=False)
    if sx[0]<=1e-10 or sy[0]<=1e-10 or sx[1]<=sx[0]*1e-10 or sy[1]<=sy[0]*1e-10:
        return None,{'reason':'numerically_degenerate_anchors'}
    u,s,vt=np.linalg.svd(xc.T@yc);d=np.diag([1.,np.linalg.det(vt.T@u.T)])
    rotation=vt.T@d@u.T;scale=float(np.sum(s*np.diag(d))/np.sum(xc*xc))
    if not np.isfinite(scale) or scale<=0:return None,{'reason':'nonpositive_scale'}
    translation=y.mean(0)-scale*rotation@x.mean(0)
    fitted=(scale*(rotation@x.T)).T+translation
    desired={k:target[5]+scale*rotation@(source[k]-source[5]) for k in (5,7,9)}
    if not all(np.isfinite(v).all() and 0<=v[0]<1312 and 0<=v[1]<736 for v in desired.values()):
        return None,{'reason':'desired_limb_outside_frame'}
    return desired,{'scale':scale,'rotation':rotation.tolist(),'translation':translation.tolist(),
        'anchor_rms_px':float(np.sqrt(np.mean(np.sum((fitted-y)**2,axis=-1)))),
        'source_anchor_condition':float(sx[0]/sx[1]),'target_anchor_condition':float(sy[0]/sy[1]),
        'reason':None}


def bone_distance(pose,points=CENTERS):
    return np.minimum.reduce([distance_segment(points,pose[a],pose[b]) for a,b in BONES])


def sweep_distance(current,desired,points=CENTERS,samples=257):
    """Upper/lower bounds on distance to continuous ruled-skeleton union.

    Each bone's sampled distance is >= exact distance. Endpoint max travel L
    bounds its Hausdorff displacement between lambdas; nearest sample <=1/512.
    """
    t=np.linspace(0,1,samples)[:,None]
    uppers=[];lowers=[];errors=[]
    for a,b in BONES:
        aa=(1-t)*current[a]+t*desired[a];bb=(1-t)*current[b]+t*desired[b]
        ds=distance_segment(points[None,:,:],aa[:,None,:],bb[:,None,:]).min(axis=0)
        error=max(np.linalg.norm(desired[a]-current[a]),np.linalg.norm(desired[b]-current[b]))/(2*(samples-1))
        uppers.append(ds);lowers.append(np.maximum(0,ds-error));errors.append(float(error))
    return np.minimum.reduce(uppers),np.minimum.reduce(lowers),max(errors)


def matched(candidate,distance):
    positive=np.sort(candidate[candidate>0])[::-1]
    order=np.lexsort((np.arange(len(distance)),distance))
    out=np.zeros_like(candidate);out[order[:len(positive)]]=positive
    if not np.array_equal(np.sort(out),np.sort(candidate)):raise ValueError('alpha multiset mismatch')
    return out


def stats(alpha):
    return {'K':int(np.count_nonzero(alpha>0)),'sum_alpha':float(np.sum(alpha)),
            'mean_alpha':float(np.mean(alpha))}


def pairwise(masks):
    out={}
    for i,a in enumerate(NAMES):
        for b in NAMES[i+1:]:
            x,y=masks[a],masks[b];u=(x>0)|(y>0)
            out[a+'__'+b]={'binary_iou':float(np.sum((x>0)&(y>0))/np.sum(u)) if np.any(u) else None,
                'soft_iou':float(np.minimum(x,y).sum()/np.maximum(x,y).sum()) if np.maximum(x,y).sum()>0 else None,
                'L1':float(np.abs(x-y).sum()),'exact_equal':bool(np.array_equal(x,y))}
    return out


def spans():
    cursor=0;out={}
    for k in range(42):
        n=(1,4,4,4,4)[k%5]
        if k in range(13,18):out[k]=(cursor,cursor+n-1)
        cursor+=n
    return out


def coverage(alpha,poses):
    points=[]
    for p in poses:
        for a,b in BONES:
            points.extend((1-t)*p[a]+t*p[b] for t in np.linspace(0,1,21))
    if not points:return {'status':'UNKNOWN','point_count':0}
    points=np.array(points);rc=np.floor(points[:,[1,0]]/32).astype(int)
    ok=(rc[:,0]>=0)&(rc[:,0]<23)&(rc[:,1]>=0)&(rc[:,1]<41)
    if not ok.all():raise ValueError('coverage escaped image')
    v=alpha[rc[:,0]*41+rc[:,1]]
    return {'status':'measured','point_count':len(v),'mean_alpha':float(v.mean()),
            'fraction_positive':float((v>0).mean()),'fraction_solid':float((v==1).mean())}


def evaluate(source,target):
    perframe=[];valid={}
    for f in range(44,60):
        s,se=pose_frame(source,f);t,te=pose_frame(target,f)
        row={'frame':f,'source_reason':se,'target_reason':te}
        if se or te:row.update(status='UNKNOWN');perframe.append(row);continue
        d,meta=align(s,t);row['alignment']=meta
        if d is None:row['status']='UNKNOWN';perframe.append(row);continue
        distances={'raw_source':bone_distance(s),'current_target':bone_distance(t),'aligned_desired':bone_distance(d)}
        distances['endpoint_union']=np.minimum(distances['current_target'],distances['aligned_desired'])
        for name,des in [('unaligned_swept',s),('aligned_swept',d)]:
            du,dl,err=sweep_distance(t,des);distances[name]=du
            row[name+'_distance_error_bound_px']=err
            row[name+'_alpha_upper']=capsule(dl)
        row['status']='valid';valid[f]={'source':s,'target':t,'desired':d,'distances':distances,'extra':row}
        perframe.append(row)
    bins=[]
    for k,(a,b) in spans().items():
        frames=list(range(max(44,a),min(59,b)+1));good=[f for f in frames if f in valid]
        rec={'bin':k,'nominal_span':[a,b],'examined_frames':frames,'valid_frames':good,'valid_fraction':len(good)/len(frames)}
        if not good:rec.update(status='UNKNOWN',reason='no_common_valid_geometric_frame');bins.append(rec);continue
        distances={n:np.minimum.reduce([valid[f]['distances'][n] for f in good]) for n in NAMES}
        raw={n:capsule(ds) for n,ds in distances.items()};candidate=raw['aligned_swept']
        if not np.any(candidate>0):rec.update(status='UNKNOWN',reason='empty_swept_query_support');bins.append(rec);continue
        equal={n:matched(candidate,distances[n]) for n in NAMES}
        if not np.array_equal(equal['aligned_swept'],candidate):raise ValueError('candidate rematching changed its own mask')
        rec.update(status='geometry_supported' if len(good)==len(frames) else 'partial_geometry',
            raw_stats={n:stats(x) for n,x in raw.items()},matched_stats={n:stats(x) for n,x in equal.items()},
            raw_pairwise=pairwise(raw),matched_pairwise=pairwise(equal),raw_alpha={n:x.tolist() for n,x in raw.items()},
            matched_alpha={n:x.tolist() for n,x in equal.items()})
        rec['coverage']={mode:{n:{kind:coverage(mask,[valid[f][kind] for f in good]) for kind in ['source','target','desired']}
            for n,mask in masks.items()} for mode,masks in [('raw',raw),('matched',equal)]}
        rec['sweep_numerical_bounds']={}
        for n in ['aligned_swept','unaligned_swept']:
            upper=np.maximum.reduce([valid[f]['extra'][n+'_alpha_upper'] for f in good]);lower=raw[n]
            if np.any(upper+1e-12<lower):raise ValueError('invalid sweep bound')
            rec['sweep_numerical_bounds'][n]={'max_distance_error_bound_px':max(valid[f]['extra'][n+'_distance_error_bound_px'] for f in good),
                'sum_alpha_lower':float(lower.sum()),'sum_alpha_upper':float(upper.sum()),
                'K_lower':int((lower>0).sum()),'K_upper':int((upper>0).sum()),
                'support_ambiguous_rows':np.flatnonzero((lower>0)!=(upper>0)).tolist(),
                'max_alpha_interval_width':float(np.max(upper-lower))}
        bins.append(rec)
    for row in perframe:
        for n in ['aligned_swept_alpha_upper','unaligned_swept_alpha_upper']:row.pop(n,None)
    return {'frames':perframe,'valid_frame_count':len(valid),'total_frames':16,'bins':bins,
            'limits':['geometric support only','common strict0.5 visibility may exclude available source-only regions',
            'pixel proxy not contextual query anatomy','sampled sweep is conservative subset; bounds quantify discretization',
            'equal alpha multiset does not equal m_ref-weighted dose or correction norm']}
