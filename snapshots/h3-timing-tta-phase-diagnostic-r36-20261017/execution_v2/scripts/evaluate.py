"""Authorized offline metrics only; no synthesized image and no controller replay."""
import argparse,copy,os,sys,time,fcntl
from pathlib import Path
from contract import *
sys.path.insert(0,str(ROOT/'vendor'))

def get_views(entry,remote):
    from view_output import inverse_pose
    from phase_artifacts import completed_or_recover,validate_record
    _,_,identity=video_pose_gate(entry,remote)
    out=[inverse_pose(identity,identity,'identity')]
    for view in ('flip','pad16'):
        dest=ROOT/'results/views'/entry['id']/view
        c=completed_or_recover(dest,entry,view);require(c is not None,'Required view not complete')
        attempt=validate_record(dest,c,entry,view)
        raw=read(attempt/'inverse.pose.json');validate_pose(raw)
        require(raw['r36_view']==view,'Inverse view binding');out.append(raw)
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

def evaluation_dependencies(entries,remote):
    """Full upstream bindings are rechecked even when an evaluation is reused."""
    from phase_artifacts import completed_or_recover,validate_record
    result={'model_files':verify_model_files(entries)} if remote else {}
    for entry in entries:
        video_pose_gate(entry,remote)
        result[entry['id']]={'video_sha256':entry['video_sha256'],'identity_pose_sha256':entry['identity_pose_sha256'],'views':{}}
        for view in ('flip','pad16'):
            dest=ROOT/'results/views'/entry['id']/view
            complete=completed_or_recover(dest,entry,view)
            require(complete is not None,'Required view not complete')
            validate_record(dest,complete,entry,view)
            result[entry['id']]['views'][view]={'completion_sha256':sha(dest/'COMPLETE.json'),'inverse_pose_sha256':complete['inverse_pose_sha256']}
    return result


def verify_evaluation_complete(dest,dependencies):
    p=dest/'COMPLETE.json'
    if not p.exists():return False
    c=read(p);require(c['status']=='complete' and c['freeze_sha256']==sha(ROOT/'FREEZE.json'),'Evaluation completion binding')
    require(c['input_dependencies']==dependencies,'Evaluation upstream bindings changed')
    relative=Path(c['attempt']);require(not relative.is_absolute() and relative.parts[:1]==('attempts',) and len(relative.parts)==2 and '..' not in relative.parts,'Evaluation attempt path')
    attempt=dest/relative;require(attempt.resolve().is_relative_to(dest.resolve()) and not attempt.is_symlink(),'Evaluation attempt path')
    actual={str(q.relative_to(attempt)) for q in attempt.rglob('*') if q.is_file()}-{'VALIDATED.json'}
    require(actual==set(c['files']),'Evaluation exact inventory')
    for name,digest in c['files'].items():
        artifact=attempt/name;require(not artifact.is_symlink() and artifact.resolve().is_relative_to(attempt.resolve()) and sha(artifact)==digest,'Evaluation artifact changed')
    require(sha(attempt/'VALIDATED.json')==c['attempt_manifest_sha256'],'Evaluation validated record')
    require(read(attempt/'VALIDATED.json')=={k:v for k,v in c.items() if k!='attempt_manifest_sha256'},'Evaluation manifest equality')
    return True


def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:print('Prepared fixed-candidate evaluation; root allocation required');return
    authorize('evaluate');require(str(ROOT)==REMOTE_ROOT,'Remote CPU evaluation root')
    require(not os.environ.get('CUDA_VISIBLE_DEVICES',''),'GPU prohibited')
    lock=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
    with lock.open('a') as lf:
        try:fcntl.flock(lf,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit(75)
        if online_pending():raise SystemExit(75)
        from fixed_candidate import common_costs,decisions
        from math_core import combine_thresholds
        from phase_artifacts import create_attempt
        import timing_metrics as metrics
        started=time.monotonic();dest=ROOT/'results/evaluation'
        entries=read(ROOT/'INPUTS.json')['items'];dependencies=evaluation_dependencies(entries,True)
        if verify_evaluation_complete(dest,dependencies):print('Reused verified complete evaluation');return
        # A crash between validation and final commit can be recovered without recomputation.
        for previous in sorted((dest/'attempts').glob('attempt*')):
            if (previous/'VALIDATED.json').exists():
                old=read(previous/'VALIDATED.json');save(dest/'COMPLETE.json',old|{'attempt_manifest_sha256':sha(previous/'VALIDATED.json')})
                verify_evaluation_complete(dest,dependencies);print('Recovered complete evaluation');return
        ledger=read(ROOT/'evidence/identity_candidate_ledger.json')
        require(ledger['summary']['inputs_sha256']==sha(ROOT/'INPUTS.json') and len(ledger['rows'])==792,'Frozen candidate ledger binding')
        source,_=get_views(entries[0],True);targets={e['id']:get_views(e,True)[0] for e in entries[1:]}
        attempt=create_attempt(dest)
        try:
            outputs={}
            for entry in entries[1:]:
                target=targets[entry['id']];arrays={}
                for c in (.3,.5):
                    for feature in ('arm_direction','left_arm_direction','right_arm_direction'):
                        try:arrays[c,feature]=(*feature_arrays(source,c,feature),*feature_arrays(target,c,feature))
                        except ValueError as exc:
                            if str(exc)!='Insufficient reliable torso anchors for scale normalization':raise
                            arrays[c,feature]=None
                original=[r for r in ledger['rows'] if r['endpoint']==entry['id']];require(len(original)==198,'All fixed+scan rows')
                rows=[]
                for old in original:
                    proposal=old['proposal'];d=proposal['candidate'];feature=old['feature'];window=tuple(old['window'])
                    row={k:old[k] for k in ('category','window','feature')};row.update(proposal=proposal,thresholds={},independent_truth='UNKNOWN_pending_independent_current_endpoint_labels')
                    for c in (.3,.5):
                        data=arrays[c,feature]
                        if d is None:cost={'status':'UNKNOWN_identity_candidate','costs':None}
                        elif data is None:cost={'status':'UNKNOWN_torso_anchor','costs':None}
                        else:
                            s,sc,t,tc=data;cost=common_costs(s,t,sc,tc,window,c,d)
                        row['thresholds'][str(c)]={'common_cost':cost,'decision':decisions(cost,proposal)}
                    row['dual']=combine_thresholds(row['thresholds']['0.3']['decision'],row['thresholds']['0.5']['decision']);rows.append(row)
                payload={'schema':'r36-v2-fixed-candidate-result','input':entry['id'],'input_video_sha256':entry['video_sha256'],'index':entry['sampling_index_zero_based'],'known_history':entry['known_history'],
                         'candidate_ledger_sha256':sha(ROOT/'evidence/identity_candidate_ledger.json'),'rows':rows,'original_production_descriptors':original,
                         'independent_labels_applied':False,'scope':'Development fixed-candidate start-side gate diagnostic; original primary stop-side UNKNOWN retained; no online policy or lag-selection benefit'}
                save(attempt/(entry['id']+'.json'),metrics.clean(payload));outputs[entry['id']]=payload
            persistence=[]
            for case in ('bad','normal'):
                for x,y in zip(outputs[case+'_004']['rows'],outputs[case+'_005']['rows']):
                    require((x['category'],x['window'],x['feature'])==(y['category'],y['window'],y['feature']),'Ordered window binding')
                    persistence.append({'case':case,'category':x['category'],'window':x['window'],'feature':x['feature'],'both_recorded_endpoints_ON':{arm:x['dual'][arm]['status']=='ON' and y['dual'][arm]['status']=='ON' for arm in 'ABCDE'},'scope':'Existing two states; no new policy trajectory'})
            save(attempt/'TWO_ENDPOINT_PERSISTENCE.json',persistence)
            summary={'status':'complete','scope':'Fixed-identity candidate gate development diagnostic only','counts':{name:{arm:{status:sum(r['dual'][arm]['status']==status for r in out['rows']) for status in ('ON','ALIGNED','ADVANCED','NO_ON','UNKNOWN')} for arm in 'ABCDE'} for name,out in outputs.items()},'new_pose_in_evaluate':False,'GPU':False,'labels':'UNKNOWN','elapsed_seconds':time.monotonic()-started}
            save(attempt/'SUMMARY.json',summary)
            require(evaluation_dependencies(entries,True)==dependencies,'Evaluation inputs changed during computation')
            complete={'status':'complete','input_dependencies':dependencies,'attempt':str(attempt.relative_to(dest)),'freeze_sha256':sha(ROOT/'FREEZE.json'),'files':{str(q.relative_to(attempt)):sha(q) for q in attempt.rglob('*') if q.is_file()},'elapsed_seconds':time.monotonic()-started}
            save(attempt/'VALIDATED.json',complete);save(dest/'COMPLETE.json',complete|{'attempt_manifest_sha256':sha(attempt/'VALIDATED.json')});verify_evaluation_complete(dest,dependencies)
            print('Fixed-candidate evaluation complete; no accuracy or online-control claim')
        except BaseException as exc:
            import traceback
            if not (attempt/'FAILURE.json').exists():save(attempt/'FAILURE.json',{'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc(),'elapsed_seconds':time.monotonic()-started,'scientific_UNKNOWN':False})
            raise

if __name__=='__main__':main()
