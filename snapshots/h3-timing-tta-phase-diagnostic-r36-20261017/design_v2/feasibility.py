"""R36 v2: old identity proposal + bounded support only; no new view/pose."""
import argparse,fcntl,hashlib,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'vendor'))
import numpy as np
from contract import read,sha,save,require,validate_freeze,video_pose_gate
from math_core import all_windows
from view_output import inverse_pose
from evaluate import feature_arrays
import timing_metrics as metrics


def candidate_gate(low,high):
    d=low.get('reliable_lag_frames');other=high.get('reliable_lag_frames')
    return {'candidate':d,'primary_confidence':.3,'secondary_identity_lag':other,
            'dual_identity_consistent':d is not None and other is not None and abs(d-other)<=2,
            'candidate_changed_using_secondary':False}


def support_bound(s,t,sc,tc,window,candidate,threshold):
    if type(candidate) is not int or not -24<=candidate<=24:raise ValueError('Fixed integer candidate required')
    if s.shape!=t.shape or s.ndim!=3 or s.shape[0]!=141 or s.shape[-1]!=2:raise ValueError('Feature shape')
    if sc.shape!=s.shape[:-1] or tc.shape!=t.shape[:-1] or not np.isfinite(sc).all() or not np.isfinite(tc).all():raise ValueError('Finite confidences')
    frames=np.arange(window[0],window[1]+1);lags=sorted(set([candidate,-2,-1,0,1,2]))
    valid=np.isfinite(s[frames]).all(-1)&(sc[frames]>=threshold);weight=sc[frames].copy()
    for lag in lags:
        idx=frames+lag;inside=(idx>=0)&(idx<141);safe=np.clip(idx,0,140)
        valid &= inside[:,None]&np.isfinite(t[safe]).all(-1)&(tc[safe]>=threshold)
        weight=np.minimum(weight,tc[safe])
    positive=valid&(weight.clip(0,1)>0);coverage=float(valid.mean());n=int(positive.any(-1).sum())
    return {'candidate':candidate,'lags':lags,'coverage_upper_bound':coverage,'valid_frames_upper_bound':n,
            'valid_vectors_upper_bound':int(valid.sum()),'mask':valid.tolist(),
            'possibly_eligible':coverage>=.8 and n>=8 and bool(positive.any()),'new_view_cost_computed':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');args=p.parse_args()
    if not args.execute:print('Prepared v2 existing-identity feasibility only');return
    validate_freeze()
    freeze=read(HERE/'FREEZE.json')
    for name,digest in freeze['files'].items():require(sha(HERE/name)==digest,'v2 frozen file changed')
    require(freeze['authorization']=='root_existing_identity_candidate_and_null_support_only','Scope authority')
    require(not os.environ.get('CUDA_VISIBLE_DEVICES',''),'GPU prohibited')
    lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
    with lock.open('a') as lf:
        try:fcntl.flock(lf,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit(75)
        start=time.monotonic();dest=HERE/'results/identity_candidate_support';require(not dest.exists(),'Existing/partial result retained');dest.mkdir()
        entries=read(ROOT/'INPUTS.json')['items'];protocol=read(HERE/'PROTOCOL.json');features=protocol['windows']['features']
        old={};bound={}
        for e in entries:
            _,path,raw=video_pose_gate(e)
            restored=[inverse_pose(raw,raw,'identity')]
            for c in (.3,.5):
                try:old[e['id'],c]=metrics.load_pose(path,c)
                except ValueError as exc:
                    if str(exc)!='Insufficient reliable torso anchors for scale normalization':raise
                    old[e['id'],c]=None
                for feature in features:
                    try:bound[e['id'],c,feature]=feature_arrays(restored,c,feature)
                    except ValueError as exc:
                        if str(exc)!='Insufficient reliable torso anchors for scale normalization':raise
                        bound[e['id'],c,feature]=None
        rows=[]
        for e in entries[1:]:
            for category,windows in [('fixed',protocol['windows']['fixed']),('scan',all_windows())]:
                for window in windows:
                    for feature in features:
                        diags={}
                        for c in (.3,.5):
                            s=old['source05',c];t=old[e['id'],c]
                            diags[str(c)]=metrics.clean(metrics.local_diagnostic(s,t,list(window),24,feature)) if s is not None and t is not None else {'status':'UNKNOWN_torso_anchor','reliable_lag_frames':None}
                        proposal=candidate_gate(diags['0.3'],diags['0.5']);d=proposal['candidate'];bounds={}
                        for c in (.3,.5):
                            s=bound['source05',c,feature];t=bound[e['id'],c,feature]
                            if d is None or s is None or t is None:out={'possibly_eligible':False,'reason':'no_reliable_identity_candidate_or_torso_anchor','candidate':d}
                            else:out=support_bound(s[0][0],t[0][0],s[1][0],t[1][0],window,d,c)
                            bounds[str(c)]=out
                        rows.append({'endpoint':e['id'],'category':category,'window':list(window),'feature':feature,
                                     'proposal':proposal,'original_identity_diagnostics':diags,'support_upper_bounds':bounds,
                                     'dual_support_possible':all(x['possibly_eligible'] for x in bounds.values()),
                                     'dual_candidate_and_support_possible':proposal['dual_identity_consistent'] and all(x['possibly_eligible'] for x in bounds.values()),
                                     'independent_truth':'UNKNOWN','TTA_benefit_measured':False})
        require(len(rows)==792,'All fixed+scan rows retained')
        counts={}
        for e in entries[1:]:
            own=[r for r in rows if r['endpoint']==e['id']]
            counts[e['id']]={'rows':len(own),'identity_candidate_present':sum(r['proposal']['candidate'] is not None for r in own),'dual_support_possible':sum(r['dual_support_possible'] for r in own),'dual_candidate_and_support_possible':sum(r['dual_candidate_and_support_possible'] for r in own)}
        primary=[{k:r[k] for k in ('endpoint','category','window','feature','proposal','support_upper_bounds','dual_candidate_and_support_possible')} for r in rows if r['category']=='fixed' and r['window']==[50,65]]
        paired=[]
        for case in ('bad','normal'):
            a=[r for r in rows if r['endpoint']==case+'_004'];b=[r for r in rows if r['endpoint']==case+'_005']
            for x,y in zip(a,b):
                require((x['category'],x['window'],x['feature'])==(y['category'],y['window'],y['feature']),'Pair order')
                if x['dual_candidate_and_support_possible'] and y['dual_candidate_and_support_possible']:
                    paired.append({'case':case,'category':x['category'],'window':x['window'],'feature':x['feature'],'identity_candidates':[x['proposal']['candidate'],y['proposal']['candidate']]})
        summary={'status':'complete','scope':'Existing identity feasibility after v1 support failure; no new pose/viewcost/accuracy/control claim',
                 'freeze_sha256':sha(HERE/'FREEZE.json'),'protocol_sha256':sha(HERE/'PROTOCOL.json'),'v1_freeze_sha256':sha(ROOT/'FREEZE.json'),
                 'inputs_sha256':sha(ROOT/'INPUTS.json'),'counts':counts,'primary':primary,'both_endpoint_possible_rows':paired,
                 'elapsed_seconds':time.monotonic()-start,'new_pose_passes':0,'GPU':False,'math_modules_only':True}
        require('torch' not in sys.modules and 'onnxruntime' not in sys.modules,'No model imports')
        save(dest/'RESULTS.json',{'summary':summary,'rows':rows});save(dest/'SUMMARY.json',summary)
        save(dest/'COMPLETE.json',{'status':'complete','freeze_sha256':sha(HERE/'FREEZE.json'),'files':{n:sha(dest/n) for n in ('RESULTS.json','SUMMARY.json')}})
        print(json.dumps({'counts':counts,'elapsed_seconds':summary['elapsed_seconds'],'primary':[{k:r[k] for k in ('endpoint','feature','proposal','dual_candidate_and_support_possible')} for r in primary],'both_endpoint_possible_count':len(paired)},indent=2))

if __name__=='__main__':main()
