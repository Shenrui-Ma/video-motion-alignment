"""Prepare/check/tests now; authorized target phases later. One phase per call."""
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
import adapter

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
LEGACY=BASE/'phase_consistent_segmentation_execution/run_once.py'
INPUTS=BASE/'phase_consistent_segmentation_design/INPUTS.json'
INPUT_SHA='2386219d3264c320365dd8ce076310103d6085a37ff56b8a266cccb3b0e6f3fc'
CANDIDATE=BASE/'phase_shape_profile_candidate_v1'
CODE_SHA='388850951becc46fbee2f06d536cc58dd2bfa5e771d43c4913436c2359028aa4'
PROTOCOL_SHA='280f82dcd9a1db7cfe56d3640a6908ffc6d7287a7106af470b86d1b8ffe5e4d1'


def read(path):return json.loads(Path(path).read_text())
def record(path):
    path=Path(path);data=path.read_bytes()
    return {'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
def verify(item):
    actual=record(item['path'])
    if any(actual[k]!=item[k] for k in actual):raise ValueError('Input/code record mismatch: '+str(item['path']))
    return actual
def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def bindings():
    expected=read(HERE/'BINDING.json')
    for item in expected['files']:verify(item)
    if record(INPUTS)['sha256']!=INPUT_SHA:raise ValueError('Inputs manifest changed')
    for name,sha in [('CODE_FREEZE.json',CODE_SHA),('PROTOCOL_FREEZE.json',PROTOCOL_SHA)]:
        if record(CANDIDATE/name)['sha256']!=sha:raise ValueError('Candidate freeze changed')
        for item in read(CANDIDATE/name)['files']:verify(item)
    return expected
def verify_execution():
    for item in read(HERE/'FREEZE.json')['files']:verify(item)
    return record(HERE/'FREEZE.json')['sha256']
def authorize(target_id):
    freeze=verify_execution()
    auth=read(HERE/'ROOT_TARGET_AUTHORIZATION.json')
    expected={'authorized':True,'phase':'target','execution_freeze_sha256':freeze,
              'candidate_code_freeze_sha256':CODE_SHA,'candidate_protocol_freeze_sha256':PROTOCOL_SHA,
              'inputs_sha256':INPUT_SHA}
    for key,value in expected.items():
        if (key=='authorized' and auth.get(key) is not True) or auth.get(key)!=value:
            raise ValueError('Authorization mismatch: '+key)
    if target_id not in auth.get('allowed_target_ids',[]):raise ValueError('Target not authorized')
    return record(HERE/'ROOT_TARGET_AUTHORIZATION.json')
def clean(value):
    import numpy as np
    if isinstance(value,(float,np.floating)):return float(value) if np.isfinite(value) else None
    if isinstance(value,np.integer):return int(value)
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    return value


def run_target(inputs,target_id,attempt,used,legacy):
    import numpy as np
    auth=authorize(target_id)
    target=next(r for r in inputs['targets'] if r['id']==target_id)
    source=next(r for r in inputs['sources'] if r['source_id']==target['source_id'])
    identity=source['identity_pose']
    for item in (identity,target['pose']):verify(item);legacy.validate_grid(read(item['path']))
    root=HERE/'results/targets'/target_id.replace(':','__')
    legacy.ensure_no_complete(root/'COMPLETE.json')
    destination=root/attempt;destination.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter()
    a,af=adapter.load(identity['path']);b,bf=adapter.load(target['pose']['path'])
    conversion=time.perf_counter()-start
    result,evidence=adapter.analyze(a,b)
    result.update(target=target,source_id=source['source_id'],feature_failures={'source':af,'target':bf},
                  conversion_seconds=conversion,formula='frozen_phase_shape_profile_candidate_v1',
                  semantic_labels='UNKNOWN',input_binding_sha256=record(HERE/'BINDING.json')['sha256'],
                  scope='Historical controlled trajectory/current native endpoint or final-only; offline descriptive rescore')
    result_path=destination/'RESULT.json';write(result_path,clean(result))
    evidence_path=destination/'EVIDENCE.npz'
    with evidence_path.open('xb') as f:np.savez_compressed(f,**evidence)
    complete={'status':'complete','target_id':target_id,'result':record(result_path),
              'files':[record(result_path),record(evidence_path)]}
    legacy.commit_new(root/'COMPLETE.json',complete,[*used,auth,identity,target['pose'],*complete['files']])
    return complete


def validate_completed_identity(complete,result,target,binding_sha):
    if complete.get('status')!='complete' or complete.get('target_id')!=target['id']:
        raise ValueError('COMPLETE target identity/status mismatch: '+target['id'])
    if complete.get('result') not in complete.get('files',[]):
        raise ValueError('RESULT record missing from committed files: '+target['id'])
    if result.get('target')!=target or result.get('source_id')!=target['source_id']:
        raise ValueError('RESULT target/input/source identity mismatch: '+target['id'])
    if result.get('input_binding_sha256')!=binding_sha:
        raise ValueError('RESULT input binding mismatch: '+target['id'])


def finalize(inputs,used,legacy):
    rows=[];records=[]
    for target in inputs['targets']:
        authorize(target['id'])
        complete_path=HERE/'results/targets'/target['id'].replace(':','__')/'COMPLETE.json'
        complete=read(complete_path)
        for item in complete['files']:verify(item)
        result=read(complete['result']['path'])
        validate_completed_identity(complete,result,target,record(HERE/'BINDING.json')['sha256'])
        rows.append({'id':target['id'],'source_id':target['source_id'],'run_id':target['run_id'],
                     'endpoint_index':target['endpoint_index'],'stage':target['stage'],
                     'K':result['K'],'parts':{p:{k:v[k] for k in ('K','counts','diagnostics')} for p,v in result['parts'].items()},
                     'selected':[{k:r[k] for k in ('part','start','end','lag','value','J','profile_rms','raw_zero_loss','phase_set')} for r in result['selected']],
                     'conversion_seconds':result['conversion_seconds'],'analysis_seconds':result['seconds'],
                     'feature_failures':result['feature_failures'],'result':complete['result']})
        records.extend([record(complete_path),*complete['files']])
    if len(rows)!=63:raise ValueError('Expected all63 registered rows')
    output={'status':'complete','rows':rows,'files':records,'semantic_accuracy':None,
            'false_positive_rate':None,'online_control':False,'full_trajectories':3,'final_only':3,
            'note':'All63 are posthoc development diagnostics; correlated endpoints are not independent trials.'}
    legacy.commit_new(HERE/'results/SUMMARY.json',output,[*used,record(HERE/'ROOT_TARGET_AUTHORIZATION.json'),*records])
    return record(HERE/'results/SUMMARY.json')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=('check','tests','target','finalize'))
    parser.add_argument('--attempt',required=True);parser.add_argument('--target-id')
    args=parser.parse_args()
    if not args.attempt.replace('_','').isalnum():parser.error('Invalid attempt')
    receipt={'phase':args.phase,'attempt':args.attempt,'target_id':args.target_id,'started_unix':time.time(),'threads_max':4}
    audit=HERE/'audit';audit.mkdir(exist_ok=True);write(audit/(args.attempt+'.claim'),receipt)
    start=time.perf_counter()
    with LOCK.open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            write(audit/(args.attempt+'.json'),receipt|{'status':'busy','exit_code':75});print('BUSY');return 75
        def timeout(signum,frame):raise TimeoutError('Bounded phase exceeded120seconds')
        signal.signal(signal.SIGALRM,timeout);signal.alarm(120)
        try:
            bind=bindings();inputs=read(INPUTS);legacy=adapter.module_at(LEGACY,'frozen_execution_utilities')
            codes=[record(HERE/p) for p in ('run_once.py','adapter.py','test_adapter.py')]
            used=[record(HERE/'BINDING.json'),*bind['files'],*codes]
            receipt['code_files']=codes
            if args.phase=='check':result=legacy.check_metadata(inputs)
            elif args.phase=='tests':
                process=subprocess.run([sys.executable,'-m','unittest','-v','test_adapter'],cwd=HERE,capture_output=True,text=True,timeout=110)
                log=audit/(args.attempt+'.log')
                with log.open('x') as f:f.write(process.stdout+process.stderr)
                if process.returncode:raise RuntimeError('Adapter correctness failed: '+str(log))
                result={'log':record(log)}
            elif args.phase=='target':result=run_target(inputs,args.target_id,args.attempt,used,legacy)
            else:result=finalize(inputs,used,legacy)
            for item in used:verify(item)
            receipt.update(status='pass',exit_code=0,result=result)
        except Exception as exc:receipt.update(status='failed',exit_code=1,error=str(exc),traceback=traceback.format_exc())
        finally:
            signal.alarm(0);receipt['seconds']=time.perf_counter()-start;write(audit/(args.attempt+'.json'),receipt)
    print(json.dumps({k:receipt[k] for k in ('phase','status','exit_code','seconds')}))
    return receipt['exit_code']


if __name__=='__main__':raise SystemExit(main())
