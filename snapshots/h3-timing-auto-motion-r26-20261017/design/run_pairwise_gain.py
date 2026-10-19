from pathlib import Path
from collections import Counter
import json,datetime,time,fcntl,importlib.util
from pairwise_gain import compare
import run_physical_tolerance as base

ROOT=base.ROOT;OUT=ROOT/'analysis/pairwise_gain_v1'

def main():
    OUT.mkdir(exist_ok=True)
    cases={}
    for p in base.INPUTS:cases.update(json.loads(p.read_text())['cases'])
    files=set(base.INPUTS+[base.NUMERIC,Path(__file__),ROOT/'design/pairwise_gain.py',
              ROOT/'design/physical_tolerance.py',ROOT/'design/PAIRWISE_GAIN_PROTOCOL.txt',
              ROOT/'design/test_pairwise_gain.py',ROOT/'design/test_physical_tolerance.py'])
    for case in cases.values():files.update([Path(case['source']),Path(case['target'])])
    hashes={str(p):base.sha(p) for p in sorted(files)}
    with (OUT/'FREEZE.json').open('x') as f:json.dump({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'files':hashes,'thresholds':[0,.25,.5],'development_only':True,'model_NFE':0},f,indent=2)
    spec=importlib.util.spec_from_file_location('metrics',base.NUMERIC)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    lock=ROOT.parent/'h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock'
    with lock.open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX);start=time.time();results={}
        for name,case in cases.items():
            src={c:m.load_pose(case['source'],c) for c in (.3,.5)}
            tar={c:m.load_pose(case['target'],c) for c in (.3,.5)}
            rows=[]
            for row in case['windows']:
                out={'window':row['window'],'feature':row['feature'],'baseline':row['status']}
                if row['status'] in ('delayed_candidate','advanced_candidate'):
                    ds={str(c):compare(src[c],tar[c],row['window'],row['measurements'][str(c)]['reliable_lag_frames'],row['feature']) for c in (.3,.5)}
                    out['comparison']=ds
                    if any(d['status']=='unknown' for d in ds.values()):out['status']='unknown'
                    else:out.update(status='measured',min_gain=min(d['min_gain'] for d in ds.values()))
                else:out['status']='baseline_'+row['status']
                rows.append(out)
            summary={str(threshold):dict(Counter(
                ('retained_'+r['baseline'] if r['min_gain']>threshold else 'below_gain') if r['status']=='measured' else r['status']
                for r in rows)) for threshold in (0,.25,.5)}
            results[name]={'summary':summary,'windows':rows};print(name,summary,flush=True)
        for p,h in hashes.items():assert base.sha(Path(p))==h,p
        with (OUT/'RESULTS.json').open('x') as f:json.dump(m.clean({'cases':results,'elapsed_seconds':time.time()-start,
             'freeze_sha256':base.sha(OUT/'FREEZE.json')}),f,allow_nan=False)
        (OUT/'SUMMARY.json').write_text(json.dumps({k:v['summary'] for k,v in results.items()},indent=2)+'\n')

if __name__=='__main__':main()
