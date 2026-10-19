"""Bounded lock-respecting correctness/manifest preparation, synthetic only."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='4'
import argparse,fcntl,hashlib,json,signal,subprocess,sys,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
def read(path):return json.loads(Path(path).read_text())
def record(path):
    p=Path(path);data=p.read_bytes();return {'path':str(p),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
def verify(item):
    if record(item['path'])!=item:raise ValueError('Bound file changed: '+item['path'])
def write(path,obj):
    path=Path(path);path.parent.mkdir(exist_ok=True,parents=True)
    with path.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def commit(path,value,used):
    path=Path(path)
    for item in used:verify(item)
    tmp=path.with_suffix('.tmp');write(tmp,value)
    with tmp.open('rb') as f:os.fsync(f.fileno())
    for item in used:verify(item)
    os.link(tmp,path);tmp.unlink()
def array_record(a):return {'shape':list(a.shape),'dtype':str(a.dtype),'sha256':hashlib.sha256(a.tobytes(order='C')).hexdigest()}
def clean(x):
    import numpy as np
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,np.bool_):return bool(x)
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [clean(v) for v in x]
    return x
def execute(args):
    used=[record(p) for p in sorted(HERE.glob('*.py'))]
    if args.phase=='tests':
        proc=subprocess.run([sys.executable,'-m','unittest','-v','test_candidate'],cwd=HERE,capture_output=True,text=True,timeout=110)
        log=HERE/'audit'/f'{args.attempt}.log'
        with log.open('x') as f:f.write(proc.stdout+proc.stderr)
        if proc.returncode:raise RuntimeError('Correctness failed: '+str(log))
        out={'log':record(log)}
    else:
        import synthetic_v4 as synthetic
        old=read(HERE.parent/'phase_shape_profile_candidate_v2/CASE_MANIFEST.json')
        rows=[]
        for i,case in enumerate(synthetic.cases()):
            x,y,truth,plateaus=synthetic.build(case)
            hashes={name:{k:array_record(a) for k,a in values.items()} for name,values in [('source',x),('target',y),('truth',truth)]}
            row={'case':case,'inputs':hashes,'plateaus':plateaus}
            if i<43:
                for key in row:
                    if row[key]!=old['cases'][i][key]:raise ValueError('Original43 changed: '+case['id'])
            rows.append(row)
        dest=HERE/'CASE_MANIFEST.json'
        commit(dest,{'seed':2026101707,'cases':rows,'original43_exact':True,'new_mask_cases':12},used)
        out={'manifest':record(dest),'cases':len(rows)}
    for item in used:verify(item)
    return {'files_used':used,**out}
def locked(args,fn):
    audit=HERE/'audit';audit.mkdir(exist_ok=True)
    if not args.attempt.replace('_','').isalnum():raise ValueError('Invalid attempt')
    receipt={'phase':args.phase,'attempt':args.attempt,'started_unix':time.time(),'threads_max':4}
    write(audit/(args.attempt+'.claim'),receipt);start=time.perf_counter()
    with LOCK.open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            write(audit/(args.attempt+'.json'),receipt|{'status':'busy','exit_code':75});print('BUSY');return 75
        def timeout(*_):raise TimeoutError('Bounded phase exceeded120s')
        signal.signal(signal.SIGALRM,timeout);signal.alarm(120)
        try:receipt.update(result=fn(args),status='pass',exit_code=0)
        except Exception as error:receipt.update(status='failed',exit_code=1,error=str(error),traceback=traceback.format_exc())
        finally:
            signal.alarm(0);receipt['seconds']=time.perf_counter()-start;write(audit/(args.attempt+'.json'),receipt)
    print(json.dumps({k:receipt[k] for k in ['phase','attempt','status','exit_code','seconds']}));return receipt['exit_code']
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('tests','manifest'));parser.add_argument('--attempt',required=True)
    raise SystemExit(locked(parser.parse_args(),execute))
