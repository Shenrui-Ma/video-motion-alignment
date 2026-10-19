"""Inspect three already-scored intervals of the registered occlusion case."""
import argparse
from pathlib import Path
import numpy as np
import prepare_once as io
from profile_v4 import NAMES


def execute(args):
    root=io.HERE/'results/local_separate_arms_occluded';marker=root/'COMPLETE.json';m=io.read(marker)
    for r in m['files']:io.verify(r)
    archive=next(Path(r['path']) for r in m['files'] if r['path'].endswith('.npz'))
    probes=[]
    with np.load(archive,allow_pickle=False) as a:
        p='v4__right_arm__';start=a[p+'interval_start'];end=a[p+'interval_end'];status=a[p+'status']
        members=a[p+'phase_membership'];values=a[p+'value'];rms=a[p+'witness_rms'];supported=a[p+'witness_support']
        for s,e in [(24,35),(72,88),(96,121)]:
            k=int(np.flatnonzero((start==s)&(end==e))[0]);st=int(status[k])
            probes.append({'interval':[s,e],'status':NAMES[st] if st<len(NAMES) else 'QUALIFIED',
                'D':(np.flatnonzero(members[:,k])-24).tolist(),'value':float(values[k]),
                'true_plus12_rms':float(rms[36,k]),'true_plus12_supported':supported[36,:,k].tolist(),
                'minus16_rms':float(rms[8,k]),'minus16_supported':supported[8,:,k].tolist()})
        # Describe existing qualified candidates covering at least half the known plateau.
        overlap=np.maximum(0,np.minimum(end,88)-np.maximum(start,72)+1)
        eligible=np.flatnonzero((status==len(NAMES))&(overlap>=9))
        best=eligible[np.argsort(-values[eligible])[:5]]
        near=[{'interval':[int(start[k]),int(end[k])],'D':(np.flatnonzero(members[:,k])-24).tolist(),
               'value':float(values[k]),'plateau_overlap_frames':int(overlap[k])} for k in best]
    out={'scope':'Read stored full-family arrays only; no new scoring, no threshold change',
         'probes':probes,'top_existing_qualified_by_value_overlapping_true_plateau':near}
    io.commit(io.HERE/'LOCAL_COUNTEREXAMPLE.json',io.clean(out),[io.record(io.HERE/'local_counterexample_inspection.py'),io.record(marker),*m['files']])
    return {'result':io.record(io.HERE/'LOCAL_COUNTEREXAMPLE.json')}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);args=p.parse_args();args.phase='local_counterexample_inspection'
    raise SystemExit(io.locked(args,execute))
