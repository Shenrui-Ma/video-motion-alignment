"""Authorized offline metrics only; no synthesized image and no controller replay."""
import argparse,copy,os,sys,time,fcntl
from pathlib import Path
from contract import *
sys.path.insert(0,str(ROOT/'vendor'))

def get_views(entry,remote):
    import numpy as np
    import timing_metrics as metrics
    from view_output import inverse_pose
    _,_,identity=video_pose_gate(entry,remote)
    out=[inverse_pose(identity,identity,'identity')]
    for view in ('flip','pad16'):
        dest=ROOT/'results/views'/entry['id']/view;c=read(dest/'COMPLETE.json')
        require(c['status']=='complete' and c['freeze_sha256']==sha(ROOT/'FREEZE.json') and c['input_video_sha256']==entry['video_sha256'] and c['identity_pose_sha256']==entry['identity_pose_sha256'],'View completion binding')
        actual={str(q.relative_to(dest)) for q in dest.rglob('*') if q.is_file()}-{'COMPLETE.json'}
        require(actual==set(c['files']),'View exact inventory')
        for name,digest in c['files'].items():require(sha(dest/name)==digest,'View artifact changed')
        raw=read(dest/'inverse.pose.json');validate_pose(raw)
        require(raw['r36_view']==view and sha(dest/'inverse.pose.json')==c['inverse_pose_sha256'],'Inverse artifact binding')
        out.append(raw)
    return out,identity

def feature_arrays(views,threshold,feature):
    import numpy as np
    import timing_metrics as metrics
    confkey={'arm_direction':'arm_conf','left_arm_direction':'left_arm_conf','right_arm_direction':'right_arm_conf'}[feature]
    fs=[];cs=[]
    for raw in views:
        xy=np.full((141,17,2),np.nan);conf=np.zeros((141,17))
        for i,row in enumerate(raw['frames']):
            if row['selected_person'] is not None:
                person=row['persons'][row['selected_person']];xy[i]=person['coco17_xy'];conf[i]=person['coco17_score']
        # Frozen full-pose feature builder may reject torso anchors even for arms.
        # Preserve this same UNKNOWN; do not silently fall back to another feature definition.
        f=metrics.pose_features(xy,conf,np.arange(141)/24,np.arange(141),raw,threshold)
        fs.append(f[feature]);cs.append(f[confkey])
    return np.stack(fs),np.stack(cs)

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:print('Prepared offline evaluation; root allocation required');return
    authorize('evaluate');require_pruning_allows_pose();require(str(ROOT)==REMOTE_ROOT,'Remote CPU evaluation root')
    require(not os.environ.get('CUDA_VISIBLE_DEVICES',''),'GPU prohibited')
    lock=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
    with lock.open('a') as lf:
        try:fcntl.flock(lf,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit(75)
        if online_pending():raise SystemExit(75)
        import numpy as np
        import timing_metrics as metrics
        import pairwise_gain
        from math_core import all_windows,common_costs,decisions,combine_thresholds
        started=time.monotonic();dest=ROOT/'results/evaluation';require(not dest.exists(),'Existing/partial evaluation retained');dest.mkdir()
        protocol=read(ROOT/'PROTOCOL.json');entries=read(ROOT/'INPUTS.json')['items'];source,_=get_views(entries[0],True)
        features=protocol['evaluation']['features'];fixed=[tuple(x) for x in protocol['evaluation']['fixed_windows']]
        outputs={};errors={}
        for entry in entries[1:]:
            target,_=get_views(entry,True);arrays={}
            for c in (.3,.5):
                for feature in features:
                    try:arrays[(c,feature)]=(*feature_arrays(source,c,feature),*feature_arrays(target,c,feature))
                    except ValueError as exc:
                        if str(exc)!='Insufficient reliable torso anchors for scale normalization':raise
                        arrays[(c,feature)]=None
            rows=[]
            for category,windows in [('fixed',fixed),('scan',all_windows())]:
                for window in windows:
                    for feature in features:
                        result={'category':category,'window':list(window),'feature':feature,'thresholds':{},'independent_truth':'UNKNOWN_pending_current_endpoint_blind_review'}
                        for c in (.3,.5):
                            data=arrays[(c,feature)]
                            if data is None:
                                cost={'status':'UNKNOWN_torso_anchor','costs':None}
                            else:
                                s,sc,t,tc=data;cost=common_costs(s,t,sc,tc,window,c)
                            result['thresholds'][str(c)]={'common_cost':cost,'decision':decisions(cost)}
                        result['dual']=combine_thresholds(result['thresholds']['0.3']['decision'],result['thresholds']['0.5']['decision']);rows.append(result)
            # Original source/candidate/support stays a separately named descriptor.
            originals=[]
            for c in (.3,.5):
                try:
                    s=metrics.load_pose(entries[0]['remote_identity_pose'],c);t=metrics.load_pose(entry['remote_identity_pose'],c)
                except ValueError as exc:
                    if str(exc)!='Insufficient reliable torso anchors for scale normalization':raise
                    originals.append({'confidence':c,'status':'UNKNOWN_torso_anchor'});continue
                for window in fixed+all_windows():
                    for feature in features:
                        diag=metrics.local_diagnostic(s,t,window,24,feature);d=diag['reliable_lag_frames']
                        gain=pairwise_gain.compare(s,t,window,d,feature) if d is not None and d>=4 else None
                        originals.append({'confidence':c,'window':list(window),'feature':feature,'diagnostic':metrics.clean(diag),'pairwise_gain':metrics.clean(gain)})
            payload={'schema':'r36-offline-v1','input':entry['id'],'input_video_sha256':entry['video_sha256'],'index':entry['sampling_index_zero_based'],'known_history':entry['known_history'],'rows':rows,'original_production_descriptors':originals,'independent_labels_applied':False,'claims':'Correlated development endpoints; no new policy trajectory or accuracy without independent labels'}
            save(dest/(entry['id']+'.json'),metrics.clean(payload));outputs[entry['id']]=payload
        persistence=[]
        for case in ('bad','normal'):
            a,b=outputs[case+'_004'],outputs[case+'_005']
            for x,y in zip(a['rows'],b['rows']):
                require((x['category'],x['window'],x['feature'])==(y['category'],y['window'],y['feature']),'Ordered window binding')
                persistence.append({'case':case,'category':x['category'],'window':x['window'],'feature':x['feature'],'both_recorded_endpoints_ON':{arm:x['dual'][arm]['status']=='ON' and y['dual'][arm]['status']=='ON' for arm in 'ABCDE'},'scope':'two archived states only; no new online path'})
        save(dest/'TWO_ENDPOINT_PERSISTENCE.json',persistence)
        save(dest/'COMPLETE.json',{'status':'complete','freeze_sha256':sha(ROOT/'FREEZE.json'),'files':{q.name:sha(q) for q in dest.iterdir() if q.is_file()},'elapsed_seconds':time.monotonic()-started,'new_GPU':False,'new_pose_in_evaluate':False,'truth_labels':'all UNKNOWN until independent root labels','source07_and_new_source_validation':'pending'})
        print('Offline diagnostic complete; no accuracy or control-effect claim')

if __name__=='__main__':main()
