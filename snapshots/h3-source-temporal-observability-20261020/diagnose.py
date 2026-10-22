"""Offline identifiability diagnostic; no producer, threshold or controller changes."""
from pathlib import Path
import json, hashlib, sys
import numpy as np
ROOT = Path(__file__).resolve().parent


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def directions(path, threshold):
    data = json.loads(Path(path).read_text())
    frames = data['frames'][:98]
    xy = np.full((len(frames), 17, 2), np.nan)
    confidence = np.zeros((len(frames), 17))
    for t, row in enumerate(frames):
        selected = row['selected_person']
        if selected is not None:
            person = row['persons'][selected]
            xy[t] = person['coco17_xy']
            confidence[t] = person['coco17_score']
    delta = np.stack([xy[:, b]-xy[:, a] for a,b in [(5,7),(7,9),(6,8),(8,10)]], axis=1)
    conf = np.stack([np.minimum(confidence[:, a],confidence[:, b]) for a,b in [(5,7),(7,9),(6,8),(8,10)]], axis=1)
    lengths = np.linalg.norm(delta,axis=-1)
    vectors = delta/np.maximum(lengths[...,None],1e-12)
    vectors[(conf<threshold)|(lengths<=1e-8)] = np.nan
    return vectors, conf


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


def curve(source, target, window, arm, threshold):
    a,ca=source;b,cb=target
    joints={'left':[0,1],'right':[2,3],'both':[0,1,2,3]}[arm]
    output=[]
    for lag in range(-24,25):
        t=np.arange(window[0],window[1]+1)
        t=t[(t+lag>=0)&(t+lag<len(b))]
        if len(t)<.8*(window[1]-window[0]+1):continue
        u=t+lag
        aa=a[t][:,joints];bb=b[u][:,joints]
        w=np.minimum(ca[t][:,joints],cb[u][:,joints])
        w=np.where(w>=threshold,w,0)
        entry=costs(aa,bb,w)
        if entry is not None:output.append({'lag':lag,'retained_source_frames':t.tolist(),**entry})
    return output


def sanity():
    t=np.arange(32,dtype=float)
    a=np.stack([np.cos(t*.3),np.sin(t*.3)],axis=-1)[:,None,:]
    w=np.ones((32,1))
    assert costs(a,a,w)['weighted_direction_error']==0
    offset=np.array([.5,-.4])[None,None,:]
    r=costs(a,a+offset,w)
    assert r['weighted_direction_error']>.6 and r['centered_direction_error']<1e-14
    flat=np.zeros_like(a)
    assert costs(flat,flat,w)['centered_vector_correlation'] is None
    conf=np.ones((len(a),1));curve_rows=curve((np.repeat(a,4,axis=1),np.repeat(conf,4,axis=1)),(np.repeat(np.roll(a,3,axis=0),4,axis=1),np.repeat(conf,4,axis=1)),[5,20],'left',.5)
    assert min(curve_rows,key=lambda r:r['weighted_direction_error'])['lag']==3


def main():
    sanity()
    source=ROOT/'inputs/source.pose.json';target=ROOT/'inputs/index10.pose.json'
    cases=[('early_selected',[4,19],'left'),('action_selected',[44,59],'left'),('action_right',[40,55],'right')]
    result={'scope':'Post-hoc diagnostic on frozen source and index10 ordinary prediction. Source self-comparison and centered cost are diagnostics only. No controller output or inference changed.','input_sha256':{str(source):digest(source),str(target):digest(target)},'script_sha256':digest(__file__),'rows':[],'sanity_checks_passed':4}
    for c in [.3,.5]:
        s=directions(source,c);p=directions(target,c)
        for label,window,arm in cases:
            result['rows'].append({'name':label,'window':window,'arm':arm,'confidence':c,'source_to_prediction':curve(s,p,window,arm,c),'source_self':curve(s,s,window,arm,c)})
    (ROOT/'RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    for row in result['rows']:
        values={x['lag']:x for x in row['source_to_prediction']}
        v=values[0];best=min(values.values(),key=lambda x:x['weighted_direction_error'])
        print(json.dumps({'name':row['name'],'confidence':row['confidence'],'source_rms':v['source_direction_rms_variation'],'zero_error':v['weighted_direction_error'],'zero_centered':v['centered_direction_error'],'raw_best_lag':best['lag'],'best_error':best['weighted_direction_error'],'best_centered':best['centered_direction_error'],'centered_best_lag':min(values.values(),key=lambda x:x['centered_direction_error'])['lag']}))

if __name__=='__main__':
    if '--sanity' in sys.argv:
        sanity();print('4 diagnostic sanity checks passed')
    else:main()
