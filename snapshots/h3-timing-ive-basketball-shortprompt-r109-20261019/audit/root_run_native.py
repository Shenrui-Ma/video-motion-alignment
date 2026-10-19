"""Explicit root execution only: exact peer admission, one P1 Native, release, CPU prompt-control gate."""
import argparse, contextlib, fcntl, json, os, signal, subprocess, sys, time, uuid, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import service
from r109_contract import read, require, registry, sha, SOURCES

def live_peers(paths):
    peers=[]
    for path in paths:
        root=Path(path).resolve()
        require(root!=ROOT and root.parent==ROOT.parent,'peer must be a distinct root in the same managed run directory')
        file=root/'processes/service.json'
        if not file.exists():continue
        owner=read(file);actual=service.current_identity(owner['pid'])
        if actual is None:continue
        require(actual==owner['identity'],'peer generation changed: '+str(root))
        runtime=read(root/'configs/runtime.json')
        require(Path(runtime['remote_root']).resolve()==root and owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port'],'peer runtime binding differs')
        require(actual['uid']==os.getuid() and str(root/'scripts/service_entry.py') in actual['cmdline'],'peer is not the registered own service')
        peers.append({'root':str(root),'owner':owner,'external_identity':service.external_identity(owner['pid'])})
    require(len({p['owner']['gpu_uuid'] for p in peers}|{service.GPU})<=2,'planned live services exceed two GPUs')
    return peers

def peer_policy(peers):
    return [{'pid':p['owner']['pid'],'identity':p['external_identity']} for p in peers]

def update_peer(peer,entry,remove=False):
    root=Path(peer['root']);owner=peer['owner'];actual=service.current_identity(owner['pid'])
    if actual is None:return
    require(actual==owner['identity'],'peer generation changed during admission update')
    path=root/'configs/admission.json';value=read(path)
    require(value['scope']=='own_user_video_jobs','peer admission scope differs')
    rows=value['permitted_compute_processes']
    if remove:rows[:]=[r for r in rows if r!=entry]
    elif entry not in rows:
        require(not any(r['pid']==entry['pid'] for r in rows),'peer contains reused child PID')
        rows.append(entry)
    service.write_json(path,value)

def wait_until(fn,seconds,message,interval=2):
    deadline=time.monotonic()+seconds
    while True:
        result=fn()
        if result:return result
        if time.monotonic()>deadline:raise TimeoutError(message)
        time.sleep(interval)

def best_effort_receipt(path,value):
    """Receipt I/O must never prevent cleanup or replace the triggering error."""
    try:service.write_json(path,value);return True
    except BaseException as error:
        try:print('Receipt write failed: '+str(path)+': '+repr(error),file=sys.stderr,flush=True)
        except BaseException:pass
        return False

def recover_attempt_owner(token):
    """Stop this attempt's exact supervisor before inspecting its possible child."""
    path=ROOT/'processes/supervisor.json'
    if path.exists():
        supervisor=read(path)
        if supervisor.get('root_attempt_token')==token:
            actual=service.current_identity(supervisor['pid'])
            if actual is not None:
                require(actual==supervisor['identity'] and actual['uid']==os.getuid() and
                        str(ROOT/'scripts/supervise_service.py') in actual['cmdline'],
                        'attempt supervisor generation differs')
                os.kill(supervisor['pid'],signal.SIGTERM)
                if not service.wait_absent(supervisor['pid'],10):
                    require(service.current_identity(supervisor['pid'])==supervisor['identity'],
                            'attempt supervisor changed before kill')
                    os.kill(supervisor['pid'],signal.SIGKILL)
                    require(service.wait_absent(supervisor['pid'],10),'attempt supervisor remains live')
    path=ROOT/'processes/service.json'
    if not path.exists():return None
    owner=read(path)
    if owner.get('root_attempt_token')!=token:return None
    require(owner['gpu_uuid']==service.GPU and owner['port']==service.PORT,
            'attempt service runtime differs')
    actual=service.current_identity(owner['pid'])
    if actual is not None:service.assert_owned(owner)
    return owner

def failure_cleanup(audit,error,owner,token):
    best_effort_receipt(audit/'FAILURE.json',{'error':repr(error),'unix':time.time()})
    try:
        # Launch may fail after creation but before the caller assigns `owner`.
        if owner is None:owner=recover_attempt_owner(token)
        if owner is not None:service.stop(expected_record=owner)
    except BaseException as cleanup:
        best_effort_receipt(audit/'CLEANUP_FAILURE.json',{'primary':repr(error),'cleanup':repr(cleanup)})
    return owner

def verify_predecessor():
    expected=read(ROOT/'configs/predecessor.json');prior=Path(expected['root'])
    require(prior!=ROOT and prior.parent==ROOT.parent,'predecessor root differs')
    owner=read(prior/'processes/service.json')
    require(owner['pid']==expected['service_pid'] and str(owner['identity']['start_ticks'])==expected['service_start_ticks'] and owner['gpu_uuid']==expected['gpu_uuid']==service.GPU,'predecessor generation/device differs')
    history=read(prior/'logs'/(expected['last_run']+'_history.json'))
    require(history['status'].get('completed') is True and history['status'].get('status_str')=='success','predecessor final job incomplete')
    require(service.current_identity(owner['pid']) is None,'predecessor service still exists')
    require(not any(r['pid']==owner['pid'] for r in service.compute_processes()),'predecessor CUDA allocation remains')
    cleanup=read(prior/'processes/cleanup.json')
    require(cleanup['pid']==owner['pid'] and cleanup.get('process_absent') is True and cleanup.get('own_compute_absent') is True,'predecessor exact cleanup receipt pending')
    return {'owner':owner,'cleanup':cleanup,'last_history_sha256':sha(prior/'logs'/(expected['last_run']+'_history.json'))}

def prepare_original_noise():
    bindings=read(ROOT/'configs/parent_bindings.json');prior=Path(bindings['r100_root'])
    source=prior/bindings['noise_cache_relative'];digest=bindings['noise_cache_sha256']
    require(sha(source)==digest,'original R100 AV noise cache changed')
    target=ROOT/'audit/r109_short_0114_seed2026101701_noise.pt'
    if not target.exists():
        tmp=target.with_suffix('.copying')
        with source.open('rb') as before,tmp.open('xb') as after:shutil.copyfileobj(before,after)
        require(sha(tmp)==digest,'R100 noise copy not exact');os.replace(tmp,target)
    require(not target.is_symlink() and sha(target)==digest,'new noise cache differs from actual R100')
    return {'source':str(source),'destination':str(target),'sha256':digest,'bytes':target.stat().st_size}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true',required=True);parser.add_argument('--attempt',required=True);parser.add_argument('--peer-root',action='append',default=[]);args=parser.parse_args()
    require(ROOT==Path(service.RUNTIME['remote_root']),'actual remote root required')
    require(args.attempt.replace('_','').replace('-','').isalnum(),'invalid attempt name')
    audit=ROOT/'audit'/args.attempt;audit.mkdir(exist_ok=False)
    owner=None;entry=None;peers=[];token=uuid.uuid4().hex
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C',H3_ROOT_ATTEMPT_TOKEN=token)
    def run(argv,timeout=720):
        with (audit/'execution.log').open('ab',buffering=0) as log:return subprocess.run(argv,cwd=ROOT,env=env,stdout=log,stderr=log,check=True,timeout=timeout)
    try:
        service.write_json(audit/'ATTEMPT_BINDING.json',{'token':token,'root':str(ROOT),'created_unix':time.time()})
        require(not (ROOT/'processes/service.json').exists(),'existing service record requires separate recovery')
        service.write_json(audit/'PREDECESSOR_RELEASE.json',verify_predecessor())
        service.write_json(audit/'ORIGINAL_AV_NOISE.json',prepare_original_noise())
        peers=live_peers(args.peer_root)
        admission={'ready_for_launch':True,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':peer_policy(peers)}
        service.write_json(ROOT/'configs/admission.json',admission)
        service.wait_admission_snapshot(admission,{'queue_running':[],'queue_pending':[]})
        run(['python3','scripts/execution_gate.py','approve-native','--root-admitted','--free-mib','40960'])
        run(['python3','-u','scripts/launch_remote.py','--service-only'])
        owner=read(ROOT/'processes/service.json');ready=read(ROOT/'processes/cuda_gate_ready.json');service.assert_owned(owner)
        require(ready['pid']==owner['pid'] and ready['identity']==service.external_identity(owner['pid']),'preCUDA child identity mismatch')
        require(ready['supervisor']['identity']==service.external_identity(ready['supervisor']['pid']),'preCUDA supervisor identity mismatch')
        peers=live_peers(args.peer_root);entry={'pid':owner['pid'],'identity':ready['identity']}
        admission['permitted_compute_processes']=peer_policy(peers)
        service.write_json(ROOT/'configs/admission.json',admission)
        service.wait_admission_snapshot(admission,{'queue_running':[],'queue_pending':[]})
        for peer in peers:update_peer(peer,entry)
        service.write_json(audit/'ADMITTED.json',{'owner':owner,'ready':ready,'peers':peers,'unix':time.time()})
        service.write_json(ROOT/'processes/cuda_gate_go.json',ready)
        def http_ready():
            service.assert_owned(owner)
            try:q=service.queue_at(service.PORT)
            except OSError:return False
            require(not q['queue_running'] and not q['queue_pending'],'unexpected existing queue');return True
        wait_until(http_ready,600,'HTTP readiness deadline')
        run(['python3','scripts/start_controller.py','--pid',str(owner['pid']),'--start-ticks',str(owner['identity']['start_ticks'])])
        service.write_json(audit/'STARTED.json',{'owner':owner,'controller':read(ROOT/'processes/controller.json'),'unix':time.time()})
        _,order=registry(ROOT)
        def completed():
            path=ROOT/'logs/controller_state.json'
            if path.exists():
                state=read(path);require(state.get('status')!='failed','controller failed: '+str(state))
                if state.get('completed')==order:return True
            service.assert_owned(owner);return False
        wait_until(completed,18000,'single Native completion deadline',20)
        # Native finalized: ensure exact release before CPU audit or any root visual review.
        wait_until(lambda:service.current_identity(owner['pid']) is None,120,'service release deadline')
        released=service.wait_cuda_release(owner)
        cleanup_path=ROOT/'processes/cleanup.json'
        wait_until(cleanup_path.exists,10,'exact cleanup receipt deadline',.2)
        cleanup=read(cleanup_path);require(cleanup['pid']==owner['pid'] and cleanup['process_absent'] and cleanup['own_compute_absent'],'exact cleanup missing')
        service.write_json(audit/'ROOT_EXIT_RECEIPT.json',{'passed':True,'owner':owner,'process_absent':True,'CUDA_allocation_absent':True,'cleanup':cleanup,'release':released,'unix':time.time()})
        cpuenv=dict(env,CUDA_VISIBLE_DEVICES='',PYTHONPATH=service.RUNTIME['dependencies'])
        with (audit/'verify_native.log').open('xb') as log:
            subprocess.run([service.RUNTIME['python'],'analysis/postrun/verify_native.py'],cwd=ROOT,env=cpuenv,stdout=log,stderr=log,check=True,timeout=900)
        gate=ROOT/'analysis/postrun/NATIVE_RUNTIME_GATE.json';require(read(gate)['passed'],'actual Native gate failed')
        service.write_json(audit/'COMPLETE.json',{'passed':True,'jobs':order,'GPU_released':True,'runtime_gate_sha256':sha(gate),'quality_review':'PENDING_ROOT','unix':time.time()})
    except BaseException as error:
        failure_cleanup(audit,error,owner,token);raise
    finally:
        if entry is not None and owner is not None:
            try:
                if service.current_identity(owner['pid']) is None:
                    for peer in peers:
                        try:update_peer(peer,entry,remove=True)
                        except BaseException as error:best_effort_receipt(audit/'PEER_CLEANUP_ERROR.json',{'peer':peer['root'],'error':repr(error)})
            except BaseException as error:best_effort_receipt(audit/'PEER_CLEANUP_ERROR.json',{'error':repr(error)})

def interrupted(signum,frame):raise InterruptedError('root wrapper received signal '+str(signum))
if __name__=='__main__':
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    with (ROOT/'audit/root_execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);main()
