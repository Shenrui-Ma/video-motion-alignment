"""Freeze and rescore every existing all-time candidate; CPU only."""
from pathlib import Path
import datetime, fcntl, hashlib, importlib.util, json, time
from collections import Counter
from physical_tolerance import rescore

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/physical_tolerance_v1'
NUMERIC=ROOT.parent/'h3-timing-architecture-r2-20261016/scripts/timing_metrics.py'
INPUTS=[ROOT/f'analysis/{name}/RESULTS.json' for name in
        ('windowfree_pose_baseline','windowfree_pose_early005')]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=True)
    records={}
    for p in INPUTS:records.update(json.loads(p.read_text())['cases'])
    files=set(INPUTS+[NUMERIC,Path(__file__),ROOT/'design/physical_tolerance.py',
                      ROOT/'design/PHYSICAL_TOLERANCE_PROTOCOL.txt',ROOT/'design/test_physical_tolerance.py'])
    for r in records.values():files.update([Path(r['source']),Path(r['target'])])
    hashes={str(p):sha(p) for p in sorted(files)}
    freeze={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':hashes,
            'proposal_policy':'All archived windows; only original reliable outside-tolerance proposals rescored',
            'development_only':True,'model_NFE':0,'tolerance_RGB_frames':2}
    with (OUT/'FREEZE.json').open('x') as f:json.dump(freeze,f,indent=2)
    spec=importlib.util.spec_from_file_location('metrics',NUMERIC)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    lockpath=ROOT.parent/'h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock'
    with lockpath.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        start=time.time(); results={}
        for name,case in records.items():
            sources={c:m.load_pose(case['source'],c) for c in (.3,.5)}
            targets={c:m.load_pose(case['target'],c) for c in (.3,.5)}
            rows=[]
            for row in case['windows']:
                status=row['status']; out={'window':row['window'],'feature':row['feature'],'baseline':status}
                if status not in ('delayed_candidate','advanced_candidate'):
                    out['status']='baseline_'+status
                else:
                    ds={str(c):rescore(sources[c],targets[c],row['window'],
                        row['measurements'][str(c)]['reliable_lag_frames'],row['feature']) for c in (.3,.5)}
                    out['rescore']=ds
                    if all(d['status']=='above_source_tolerance' for d in ds.values()):
                        out['status']='retained_'+status
                    elif any(d['status'].startswith('unknown') for d in ds.values()):
                        out['status']='unknown_common_rescore'
                    else:out['status']='below_source_tolerance'
                rows.append(out)
            counts=dict(Counter(r['status'] for r in rows))
            results[name]={'summary':counts,'windows':rows}
            print(name,counts,flush=True)
        for p,h in hashes.items():
            assert sha(Path(p))==h, p
        payload=m.clean({'freeze_sha256':sha(OUT/'FREEZE.json'),'cases':results,
                         'elapsed_seconds':time.time()-start,'model_NFE':0})
        with (OUT/'RESULTS.json').open('x') as f:json.dump(payload,f,allow_nan=False)
        (OUT/'SUMMARY.json').write_text(json.dumps({k:v['summary'] for k,v in results.items()},indent=2)+'\n')

if __name__=='__main__':main()
