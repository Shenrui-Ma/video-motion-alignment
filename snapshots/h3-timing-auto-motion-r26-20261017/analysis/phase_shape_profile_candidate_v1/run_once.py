"""One bounded, shared-lock synthetic phase; no real target option exists."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name]='4'
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
def verify(r):
    actual=record(r['path'])
    assert all(actual[k]==r[k] for k in actual),str(r['path'])
def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(data,f,indent=2,allow_nan=False);f.write('\n')
def commit(path,data):
    temporary=path.with_suffix('.tmp')
    write(temporary,data)
    os.link(temporary,path)
    temporary.unlink()
def array_record(a):
    return {'shape':list(a.shape),'dtype':str(a.dtype),'sha256':hashlib.sha256(a.tobytes(order='C')).hexdigest()}
def timeout(signum,frame):raise TimeoutError('Bounded phase >120 seconds')


def execute(args):
    import numpy as np
    import profile as model
    import synthetic
    sealed=read(HERE/'CODE_FREEZE.json')
    protocol=read(HERE/'PROTOCOL_FREEZE.json')
    for r in [*sealed['files'],*protocol['files']]:verify(r)
    used=[record(HERE/'CODE_FREEZE.json'),record(HERE/'PROTOCOL_FREEZE.json'),*sealed['files'],*protocol['files']]
    if args.phase=='tests':
        result=subprocess.run([sys.executable,'-m','unittest','-v','test_profile'],cwd=HERE,capture_output=True,text=True,timeout=110)
        log=HERE/'audit'/f'{args.attempt}.log'
        with log.open('x') as f:f.write(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('Correctness tests failed: '+str(log))
        output={'unit_log':record(log)}
    elif args.phase=='case':
        case=next(r for r in synthetic.cases() if r['id']==args.case_id)
        manifest=read(HERE/'CASE_MANIFEST.json')
        bound=next(r for r in manifest['cases'] if r['case']['id']==args.case_id)
        source,target=synthetic.build(case)
        actual={name:{k:array_record(a) for k,a in v.items()} for name,v in [('source',source),('target',target)]}
        assert actual==bound['inputs'],'Input manifest mismatch'
        root=HERE/'results'/args.case_id
        if (root/'COMPLETE.json').exists():raise FileExistsError(str(root/'COMPLETE.json'))
        destination=root/args.attempt;destination.mkdir(parents=True,exist_ok=False)
        result,evidence=model.analyze(source,target)
        result.update(case=case,verdict=synthetic.verdict(case,result,evidence),protocol_sha256=record(HERE/'PROTOCOL.json')['sha256'],input_hashes=actual)
        # Mathematical UNKNOWN arrays stay in NPZ; JSON selected rows are finite.
        def clean(value):
            if isinstance(value,float) and not np.isfinite(value):return None
            if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
            if isinstance(value,list):return [clean(v) for v in value]
            return value
        path=destination/'RESULT.json';write(path,clean(result))
        archive=destination/'EVIDENCE.npz'
        with archive.open('xb') as f:np.savez_compressed(f,**evidence)
        output={'case_id':args.case_id,'status':'complete','files':[record(path),record(archive)],'result':record(path)}
        for r in used:verify(r)
        commit(root/'COMPLETE.json',output)
    else:
        rows=[];records=[]
        for case in synthetic.cases():
            cp=HERE/'results'/case['id']/'COMPLETE.json';complete=read(cp)
            for r in complete['files']:verify(r)
            records += [record(cp),*complete['files']]
            result=read(complete['result']['path'])
            rows.append({'id':case['id'],'group':case['group'],'truth':case['truth'],'K':result['K'],
                         'verdict':result['verdict'],'seconds':result['seconds'],
                         'selected':[{k:r[k] for k in ('part','start','end','lag')} for r in result['selected']],
                         'counts':{p:r['counts'] for p,r in result['parts'].items()},'result':complete['result']})
        required=[r for r in rows if r['verdict']['required']]
        output={'status':'complete','rows':rows,'required_cases':len(required),
                'required_pass':sum(r['verdict']['pass'] for r in required),
                'scientific_pass':all(r['verdict']['pass'] for r in required),
                'real_targets_scored':0,'online_actuator_enabled':False,'files':records}
        for r in used:verify(r)
        commit(HERE/'results/SUMMARY.json',output)
    for r in used:verify(r)
    return output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=('tests','case','finalize'))
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--case-id')
    args=parser.parse_args()
    if not args.attempt.replace('_','').isalnum():parser.error('Invalid attempt')
    audit=HERE/'audit';audit.mkdir(exist_ok=True)
    receipt={'phase':args.phase,'attempt':args.attempt,'case_id':args.case_id,'started_unix':time.time(),'threads_max':4}
    write(audit/(args.attempt+'.claim'),receipt)
    started=time.perf_counter()
    with LOCK.open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            write(audit/(args.attempt+'.json'),receipt|{'status':'busy','exit_code':75});print('BUSY');return 75
        signal.signal(signal.SIGALRM,timeout);signal.alarm(120)
        try:receipt.update(result=execute(args),status='pass',exit_code=0)
        except Exception as exc:receipt.update(status='failed',exit_code=1,error=str(exc),traceback=traceback.format_exc())
        finally:
            signal.alarm(0);receipt['seconds']=time.perf_counter()-started
            write(audit/(args.attempt+'.json'),receipt)
    print(json.dumps({k:receipt[k] for k in ('phase','status','exit_code','seconds')}))
    return receipt['exit_code']


if __name__=='__main__':raise SystemExit(main())
