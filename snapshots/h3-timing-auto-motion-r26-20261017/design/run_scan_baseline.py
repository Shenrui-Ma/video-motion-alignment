"""Archive a transparent all-time, part-wise scan using frozen pose diagnostics."""
from pathlib import Path
import datetime
import fcntl
import hashlib
import importlib.util
import json
import time

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT.parent
OUT = ROOT / 'analysis/windowfree_pose_baseline'
NUMERIC = DEV/'h3-timing-architecture-r2-20261016/scripts/timing_metrics.py'
OLD = DEV/'h3-timing-autoresearch-20261016/analysis/pose/old_sam'
R24 = DEV/'h3-timing-fresh-source-r24-20261016'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def cases():
    rows = [
        ('s05_seed1311', OLD/'05_real_megumi_v.pose.json', DEV/'h3-timing-spatial-r3-20261016/analysis/pose/pilot/r3_s05_native_00001_.pose.json'),
        ('s07_seed1311', OLD/'07_real_ary_v.pose.json', DEV/'h3-timing-cross-source-r20-host9-20261016/analysis/pose/pilot/r20_s07_native_00001_.pose.json'),
        ('s05_seed1313', OLD/'05_real_megumi_v.pose.json', DEV/'h3-timing-native-screen-r14-host9-20261016/analysis/pose/pilot/r14_s05_seed1313_native_host9_00001_.pose.json'),
    ]
    for case in ('fresh_a', 'fresh_b'):
        for seed in (2026101610, 2026101611):
            run = f'r24_{case}_seed{seed}_native'
            rows.append((f'{case}_{seed}', R24/f'analysis/source_pose/{case}/{case}.pose.json',
                         R24/f'analysis/postrun/captured/{run}/pose/{run}_00001_.pose.json'))
    return rows

def compact(d):
    return {k:v for k,v in d.items() if k != 'curve'} | {'curve':[
        {k:v for k,v in row.items() if k not in ('source_frames','per_frame_error')}
        for row in d['curve']]}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    lock_path=DEV/'h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock'
    with lock_path.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        started=time.time()
        entries=cases()
        inputs={str(p):digest(p) for _,s,t in entries for p in (s,t)}
        freeze={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'numeric_sha256':digest(NUMERIC),'script_sha256':digest(Path(__file__)),
                'protocol_sha256':digest(ROOT/'design/SCAN_BASELINE_PROTOCOL.txt'),
                'inputs':inputs,'cpu_only':True}
        with (OUT/'FREEZE.json').open('x') as f:json.dump(freeze,f,indent=2)
        spec=importlib.util.spec_from_file_location('frozen_metrics',NUMERIC)
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        results={}
        features=('arm_direction','left_arm_direction','right_arm_direction')
        for name,sp,tp in entries:
            source={c:mod.load_pose(sp,c) for c in (.3,.5)}
            target={c:mod.load_pose(tp,c) for c in (.3,.5)}
            last=int(source[.3]['frames'][-1]);rows=[];identity=[]
            for length in (16,32):
                starts=sorted(set(range(0,last-length+2,4))|{last-length+1})
                for start in starts:
                    w=[start,start+length-1]
                    for feature in features:
                        ds=[mod.local_diagnostic(source[c],target[c],w,24,feature) for c in (.3,.5)]
                        ls=[d['reliable_lag_frames'] for d in ds]
                        status='unknown'
                        if all(x is not None for x in ls) and abs(ls[0]-ls[1])<=2:
                            if min(ls)>2:status='delayed_candidate'
                            elif max(ls)<-2:status='advanced_candidate'
                            elif all(abs(x)<=2 for x in ls):status='aligned'
                        rows.append({'window':w,'feature':feature,'status':status,
                                     'measurements':dict(zip(('0.3','0.5'),map(compact,ds)))})
                        di=mod.local_diagnostic(source[.3],source[.3],w,24,feature)
                        li=di['reliable_lag_frames']
                        if li not in (None,0):raise RuntimeError('Identity self-check nonzero reliable lag')
                        identity.append({'window':w,'feature':feature,'lag':li})
            summary={s:sum(x['status']==s for x in rows) for s in
                     ('delayed_candidate','advanced_candidate','aligned','unknown')}
            covered={s:sorted({i for x in rows if x['status']==s for i in range(x['window'][0],x['window'][1]+1)})
                     for s in ('delayed_candidate','advanced_candidate')}
            results[name]={'source':str(sp),'target':str(tp),'summary':summary,
                           'candidate_covered_frames':covered,'identity_checks':identity,'windows':rows}
            print(name,summary,flush=True)
        for p,h in inputs.items():
            if digest(Path(p))!=h:raise RuntimeError('Input changed')
        payload=mod.clean({'freeze_sha256':digest(OUT/'FREEZE.json'),'cases':results,
                           'elapsed_seconds':time.time()-started,'cpu_only':True})
        with (OUT/'RESULTS.json').open('x') as f:json.dump(payload,f,allow_nan=False)
        summary={k:{'summary':v['summary'],'candidate_covered_frames':v['candidate_covered_frames']} for k,v in results.items()}
        (OUT/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
        print('complete',payload['elapsed_seconds'],flush=True)

if __name__=='__main__':main()
