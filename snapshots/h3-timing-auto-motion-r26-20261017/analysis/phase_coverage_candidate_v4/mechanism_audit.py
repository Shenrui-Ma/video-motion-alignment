"""Bounded postrun reading of frozen arrays; never rescore or generate pose."""
import argparse
from pathlib import Path
import numpy as np
import prepare_once as io
from profile_v4 import NAMES


def runs(mask):
    idx=np.flatnonzero(mask)
    if not len(idx):return []
    groups=np.split(idx,np.flatnonzero(np.diff(idx)>1)+1)
    return [[int(v[0]),int(v[-1])] for v in groups]


def execute(args):
    summary=io.read(io.HERE/'results/SUMMARY.json')
    if summary['cases']!=55:raise ValueError('Incomplete inventory')
    used=[io.record(io.HERE/'mechanism_audit.py'),io.record(io.HERE/'results/SUMMARY.json')]
    details=[]
    for row in summary['rows']:
        case=row['case'];cid=case['id']
        if case.get('mask_task')!='positive' and cid!='local_separate_arms_occluded':continue
        marker=io.HERE/'results'/cid/'COMPLETE.json';complete=io.read(marker)
        for record in complete['files']:io.verify(record)
        used.extend([io.record(marker),*complete['files']])
        result=io.read(row['result']['path']);method=result['methods']['v4'];model=method['result']
        archive=next(Path(r['path']) for r in complete['files'] if r['path'].endswith('.npz'))
        detail={'id':cid,'case':case,'parts':{},'physical_coverage':method['assessment']['physical_coverage'],
                'online_safety':method['assessment']['online_safety']}
        with np.load(archive,allow_pickle=False) as a:
            truth=a['truth__source_phase']
            for part_index,part in enumerate(('left_arm','right_arm')):
                p='v4__'+part+'__';start=a[p+'interval_start'];end=a[p+'interval_end']
                mask=a[p+'witness_mask'];weights=a[p+'witness_raw_weight'];status=a[p+'status']
                members=a[p+'phase_membership'];support=a[p+'witness_support'];rms=a[p+'witness_rms']
                old=a[p+'common_mask'];selected=[]
                for w in model['selected']:
                    if w['part']!=part:continue
                    d=w['diagnostic_best_lag'];idx=w['interval_index'];s=w['start'];e=w['end']
                    phase=truth[s:e+1,part_index];sign=1 if w['direction']=='delay' else -1
                    selected.append({'window':w,'truth_phase_min':float(phase.min()),'truth_phase_max':float(phase.max()),
                        'wrong_direction_frames':(np.flatnonzero(~((np.abs(phase)>2)&(np.sign(phase)==sign)))+s).tolist(),
                        'best_target_interval':[s+d,e+d],
                        'witness_missing_frame_runs_by_h':[runs(~mask[d+24,h,s:e+1].any(axis=1)) for h in range(2)],
                        'witness_slots_by_h':[int(mask[d+24,h,s:e+1].sum()) for h in range(2)],
                        'witness_weight_by_h':[float(weights[d+24,h,s:e+1].sum()) for h in range(2)],
                        'old49_missing_source_runs':[[lo+s,hi+s] for lo,hi in runs(~old[s:e+1].any(axis=1))],
                        'all49_witness_supported':np.all(support[:,:,idx],axis=1).tolist(),
                        'all49_witness_rms':rms[:,idx].tolist(),
                        'all49_D':(np.flatnonzero(members[:,idx])-24).tolist()})
                part_data={'counts':model['parts'][part]['counts'],'selected':selected,
                           'old49_valid_source_runs':runs(old.any(axis=1))}
                if case.get('mask_task')=='positive':
                    lag=next(c['truth']['true_lag'] for c in method['assessment']['physical_coverage'] if c['part']==part)
                    valid=np.all(mask[lag+24].any(axis=-1),axis=0)
                    probes=[]
                    for s,e in runs(valid):
                        if e-s+1<8:continue
                        k=np.flatnonzero((start==s)&(end==e))
                        if len(k)!=1:raise ValueError('Probe absent from frozen full family')
                        k=int(k[0]);st=int(status[k])
                        probes.append({'interval':[s,e],'status':NAMES[st] if st<len(NAMES) else 'QUALIFIED',
                            'D':(np.flatnonzero(members[:,k])-24).tolist(),
                            'true_lag_witness_support':support[lag+24,:,k].tolist(),
                            'true_lag_witness_rms':float(rms[lag+24,k])})
                    part_data.update(true_lag=lag,true_lag_witness_valid_source_runs=runs(valid),
                                     true_lag_witness_available_frames=int(valid.sum()),
                                     longest_available_run_probes=probes)
                detail['parts'][part]=part_data
        details.append(detail)
    out={'scope':'Read existing frozen RESULT/EVIDENCE only; no new lag/threshold/window scoring',
         'indexing':'0-based physical frames, all intervals inclusive, 24 fps',
         'cases':details,'new_real_targets':0}
    io.commit(io.HERE/'MECHANISM_EVIDENCE.json',io.clean(out),used)
    return {'mechanism':io.record(io.HERE/'MECHANISM_EVIDENCE.json'),'cases':len(details)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);args=p.parse_args();args.phase='mechanism_audit'
    raise SystemExit(io.locked(args,execute))
