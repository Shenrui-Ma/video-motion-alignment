"""One locked bounded synthetic phase. No real-data scoring entry point."""
import os
for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[variable]='4'
import argparse
import fcntl
import hashlib
import json
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE=Path(__file__).resolve().parent
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
def read(path):return json.loads(Path(path).read_text())
def record(path):
    path=Path(path);data=path.read_bytes()
    return {'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
def verify(item):
    actual=record(item['path'])
    if any(actual[k]!=item[k] for k in actual):raise ValueError('Sealed record changed: '+str(item['path']))
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def commit(path,value,used):
    for item in used:verify(item)
    temporary=path.with_suffix('.tmp');write(temporary,value)
    with temporary.open('rb') as f:os.fsync(f.fileno())
    for item in used:verify(item)
    os.link(temporary,path);temporary.unlink()
def array_record(a):return {'shape':list(a.shape),'dtype':str(a.dtype),'sha256':hashlib.sha256(a.tobytes(order='C')).hexdigest()}
def clean(value):
    import numpy as np
    if isinstance(value,(float,np.floating)):return float(value) if np.isfinite(value) else None
    if isinstance(value,np.integer):return int(value)
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    return value

def execute(args):
    import numpy as np
    from bindings import V2
    import profile_v3
    import synthetic_v2 as synthetic
    import evaluation
    protocol=read(HERE/'PROTOCOL_FREEZE.json');code=read(HERE/'CODE_FREEZE.json')
    used=[record(HERE/'PROTOCOL_FREEZE.json'),record(HERE/'CODE_FREEZE.json'),
          *protocol['files'],*protocol['external_inputs'],*code['files']]
    for item in used:verify(item)
    if args.phase=='tests':
        process=subprocess.run([sys.executable,'-m','unittest','-v','test_candidate'],cwd=HERE,capture_output=True,text=True,timeout=110)
        log=HERE/'audit'/f'{args.attempt}.log'
        with log.open('x') as f:f.write(process.stdout+process.stderr)
        if process.returncode:raise RuntimeError('Correctness failed: '+str(log))
        output={'log':record(log)}
    elif args.phase=='case':
        case=next(c for c in synthetic.cases() if c['id']==args.case_id)
        manifest=next(c for c in read(HERE/'CASE_MANIFEST.json')['cases'] if c['case']['id']==args.case_id)
        if manifest['case']!=case:raise ValueError('Case definition changed')
        source,target,truth,plateaus=synthetic.build(case)
        hashes={name:{k:array_record(a) for k,a in value.items()} for name,value in [('source',source),('target',target),('truth',truth)]}
        if hashes!=manifest['inputs'] or plateaus!=manifest['plateaus']:raise ValueError('Input/truth manifest changed')
        root=HERE/'results'/case['id']
        if (root/'COMPLETE.json').exists():raise FileExistsError(str(root/'COMPLETE.json'))
        destination=root/args.attempt;destination.mkdir(parents=True,exist_ok=False)
        methods={};arrays={}
        for name,model in [('v2',V2),('v3',profile_v3)]:
            result,evidence=model.analyze(source,target)
            if case.get('suite')=='local12':assess=evaluation.local_verdict(case,result,evidence,truth,plateaus)
            else:assess={'original_point_task':evaluation.original_point_verdict(case,result,evidence),
                         'direction_task':evaluation.original_direction_verdict(case,result,evidence)}
            methods[name]={'result':result,'assessment':assess}
            arrays.update({name+'__'+key:val for key,val in evidence.items()})
        for key in [k for k in arrays if k.startswith('v2__')]:
            other='v3__'+key[4:]
            if not np.array_equal(arrays[key],arrays[other],equal_nan=True):raise ValueError('Candidate evidence changed: '+key)
        if any(methods['v2']['result']['parts'][p]['counts']!=methods['v3']['result']['parts'][p]['counts'] for p in methods['v2']['result']['parts']):raise ValueError('Candidate counts changed')
        arrays.update({'truth__'+key:val for key,val in truth.items()})
        result_path=destination/'RESULT.json'
        write(result_path,clean({'case':case,'methods':methods,'plateaus':plateaus,'input_hashes':hashes,'protocol_sha256':record(HERE/'PROTOCOL.json')['sha256']}))
        archive=destination/'EVIDENCE.npz'
        with archive.open('xb') as f:np.savez_compressed(f,**arrays)
        output={'status':'complete','case_id':case['id'],'result':record(result_path),'files':[record(result_path),record(archive)]}
        commit(root/'COMPLETE.json',output,[*used,*output['files']])
    else:
        rows=[];records=[]
        for case in synthetic.cases():
            marker=HERE/'results'/case['id']/'COMPLETE.json';complete=read(marker)
            if complete.get('status')!='complete' or complete.get('case_id')!=case['id']:raise ValueError('Case marker identity mismatch')
            if complete['result'] not in complete['files']:raise ValueError('Uncommitted RESULT')
            for item in complete['files']:verify(item)
            result=read(complete['result']['path'])
            if result['case']!=case or result['protocol_sha256']!=record(HERE/'PROTOCOL.json')['sha256']:raise ValueError('Result case/protocol mismatch')
            methods={name:{'K':v['result']['K'],'selected':v['result']['selected'],
                          'counts':{p:r['counts'] for p,r in v['result']['parts'].items()},
                          'seconds':v['result']['seconds'],'assessment':v['assessment']} for name,v in result['methods'].items()}
            rows.append({'case':case,'methods':methods,'result':complete['result']})
            records.extend([record(marker),*complete['files']])
        required=[r['methods']['v3']['assessment']['direction_task'] for r in rows if r['methods']['v3']['assessment']['direction_task']['required']]
        output={'status':'complete','rows':rows,'required_direction_cases':len(required),
                'required_direction_pass':sum(r['pass'] for r in required),'scientific_pass':all(r['pass'] for r in required),
                'real_targets_scored':0,'online_actuator_enabled':False,'files':records}
        commit(HERE/'results/SUMMARY.json',output,[*used,*records])
    for item in used:verify(item)
    return output

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('tests','case','finalize'))
    parser.add_argument('--attempt',required=True);parser.add_argument('--case-id');args=parser.parse_args()
    if not args.attempt.replace('_','').isalnum():parser.error('Invalid attempt')
    receipt={'phase':args.phase,'attempt':args.attempt,'case_id':args.case_id,'started_unix':time.time(),'threads_max':4}
    audit=HERE/'audit';audit.mkdir(exist_ok=True);write(audit/(args.attempt+'.claim'),receipt)
    start=time.perf_counter()
    with LOCK.open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            write(audit/(args.attempt+'.json'),receipt|{'status':'busy','exit_code':75});print('BUSY');return 75
        def timeout(*args):raise TimeoutError('Bounded phase >120 seconds')
        signal.signal(signal.SIGALRM,timeout);signal.alarm(120)
        try:receipt.update(result=execute(args),status='pass',exit_code=0)
        except Exception as exc:receipt.update(status='failed',exit_code=1,error=str(exc),traceback=traceback.format_exc())
        finally:
            signal.alarm(0);receipt['seconds']=time.perf_counter()-start;write(audit/(args.attempt+'.json'),receipt)
    print(json.dumps({key:receipt[key] for key in ('phase','status','exit_code','seconds')}))
    return receipt['exit_code']
if __name__=='__main__':raise SystemExit(main())
