"""Authorized local mask/cardinality pruning; never loads model or computes lag."""
import argparse,fcntl,os,sys,time
from pathlib import Path
from contract import ROOT,read,sha,save,require,authorize,video_pose_gate


def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');args=p.parse_args()
    if not args.execute:
        print('Prepared identity support bound only; root allocation required');return
    authorize('identity-support-upper-bound')
    require(str(ROOT).startswith('/Users/researcher/DevProjects/'),'This bounded pass uses local archived identity data')
    require(not os.environ.get('CUDA_VISIBLE_DEVICES',''),'GPU prohibited')
    lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
    with lock.open('a') as lf:
        try:fcntl.flock(lf,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit(75)
        import numpy as np
        from view_output import inverse_pose
        from evaluate import feature_arrays
        from math_core import all_windows
        from support_bound import identity_bound
        start=time.monotonic();dest=ROOT/'results/identity_support_upper_bound'
        require(not dest.exists(),'Existing/partial support pass retained');dest.mkdir(parents=True)
        protocol=read(ROOT/'PROTOCOL.json');entries=read(ROOT/'INPUTS.json')['items']
        views={}
        for entry in entries:
            _,_,raw=video_pose_gate(entry,remote=False)
            views[entry['id']]=[inverse_pose(raw,raw,'identity')]
        features=protocol['evaluation']['features'];arrays={}
        for entry in entries:
            for threshold in (.3,.5):
                for feature in features:
                    try:arrays[(entry['id'],threshold,feature)]=feature_arrays(views[entry['id']],threshold,feature)
                    except ValueError as exc:
                        if str(exc)!='Insufficient reliable torso anchors for scale normalization':raise
                        arrays[(entry['id'],threshold,feature)]=None
        rows=[];endpoint_counts={}
        for entry in entries[1:]:
            for category,windows in [('fixed',protocol['evaluation']['fixed_windows']),('scan',all_windows())]:
                for window in windows:
                    for feature in features:
                        row={'endpoint':entry['id'],'category':category,'window':list(window),'feature':feature,'thresholds':{}}
                        for threshold in (.3,.5):
                            source=arrays[('source05',threshold,feature)];target=arrays[(entry['id'],threshold,feature)]
                            if source is None or target is None:
                                value={'status':'IMPOSSIBLE_torso_anchor','possibly_eligible':False,'phase_or_cost_computed':False}
                            else:
                                s,sc=source;t,tc=target
                                value=identity_bound(s[0],t[0],sc[0],tc[0],tuple(window),threshold)
                            row['thresholds'][str(threshold)]=value
                        row['dual_possibly_eligible']=all(v['possibly_eligible'] for v in row['thresholds'].values())
                        rows.append(row)
            own=[r for r in rows if r['endpoint']==entry['id']]
            endpoint_counts[entry['id']]={'rows':len(own),'dual_possible':sum(r['dual_possibly_eligible'] for r in own),
                'by_threshold':{str(c):sum(r['thresholds'][str(c)]['possibly_eligible'] for r in own) for c in (.3,.5)}}
        require(len(rows)==4*(12+186),'All frozen rows retained')
        possible=[{k:r[k] for k in ('endpoint','category','window','feature')} for r in rows if r['dual_possibly_eligible']]
        summary={'status':'complete','freeze_sha256':sha(ROOT/'FREEZE.json'),'protocol_sha256':sha(ROOT/'PROTOCOL.json'),
                 'inputs_sha256':sha(ROOT/'INPUTS.json'),'endpoint_counts':endpoint_counts,'rows':len(rows),
                 'possible_rows':possible,'any_potentially_eligible':bool(possible),
                 'next_action':'Root may allocate unchanged10newposepasses' if possible else 'STOP strict diagnostic; do not run10newposepasses',
                 'scope':'Necessary identity support bound only. No phase costs/lags/gains computed; no labels inferred; no general TTA failure claim.',
                 'new_pose_passes':0,'model_imports':False,'GPU':False,'elapsed_seconds':time.monotonic()-start}
        require('torch' not in sys.modules and 'onnxruntime' not in sys.modules,'Model imports prohibited')
        save(dest/'RESULTS.json',{'summary':summary,'rows':rows})
        save(dest/'SUMMARY.json',summary)
        save(dest/'COMPLETE.json',{'status':'complete','freeze_sha256':sha(ROOT/'FREEZE.json'),
             'files':{n:sha(dest/n) for n in ('RESULTS.json','SUMMARY.json')}})
        print(__import__('json').dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
