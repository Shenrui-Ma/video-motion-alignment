"""Explicit root execution only: exact peer admission, seven pairs, release, CPU pair gate."""
import argparse, contextlib, fcntl, json, os, signal, subprocess, sys, time, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'audit'))
import service
from r89_contract import read, require, registry, sha, SOURCES
from own_memory_sampler import OwnMemorySampler

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

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true',required=True);parser.add_argument('--attempt',required=True);parser.add_argument('--peer-root',action='append',default=[]);args=parser.parse_args()
    require(ROOT==Path(service.RUNTIME['remote_root']),'root execution requires the actual remote path')
    require(args.attempt.replace('_','').replace('-','').isalnum(),'invalid attempt name')
    audit=ROOT/'audit'/args.attempt;audit.mkdir(exist_ok=False)
    owner=None;entry=None;peers=[];memory_sampler=None
    token=uuid.uuid4().hex
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C',H3_ROOT_ATTEMPT_TOKEN=token)
    def run(argv,timeout=720):
        with (audit/'execution.log').open('ab',buffering=0) as log:
            return subprocess.run(argv,cwd=ROOT,env=env,stdout=log,stderr=log,check=True,timeout=timeout)
    try:
        service.write_json(audit/'ATTEMPT_BINDING.json',{'token':token,'root':str(ROOT),'created_unix':time.time()})
        require(not (ROOT/'processes/service.json').exists(),'existing service record requires separate recovery')
        peers=live_peers(args.peer_root)
        admission={'ready_for_launch':True,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':peer_policy(peers)}
        service.write_json(ROOT/'configs/admission.json',admission)
        service.wait_admission_snapshot(admission,{'queue_running':[],'queue_pending':[]})
        run(['python3','scripts/execution_gate.py','approve-first-pair','--root-admitted','--free-mib','29696'])
        run(['python3','-u','scripts/launch_remote.py','--service-only'])
        owner=read(ROOT/'processes/service.json');ready=read(ROOT/'processes/cuda_gate_ready.json');service.assert_owned(owner)
        require(ready['pid']==owner['pid'] and ready['identity']==service.external_identity(owner['pid']),'preCUDA child identity mismatch')
        require(ready['supervisor']['identity']==service.external_identity(ready['supervisor']['pid']),'preCUDA supervisor identity mismatch')
        memory_sampler=OwnMemorySampler(owner,audit,service);memory_sampler.start()
        peers=live_peers(args.peer_root);entry={'pid':owner['pid'],'identity':ready['identity']}
        admission['permitted_compute_processes']=peer_policy(peers)
        service.write_json(ROOT/'configs/admission.json',admission)
        service.wait_admission_snapshot(admission,{'queue_running':[],'queue_pending':[]})
        for peer in peers:update_peer(peer,entry)
        service.write_json(audit/'ADMITTED.json',{'owner':owner,'ready':ready,'peers':peers,'created_unix':time.time()})
        service.write_json(ROOT/'processes/cuda_gate_go.json',ready)
        def http_ready():
            service.assert_owned(owner)
            try:q=service.queue_at(service.PORT)
            except OSError:return False
            require(not q['queue_running'] and not q['queue_pending'],'unexpected existing queue');return True
        wait_until(http_ready,600,'HTTP service unavailable')
        run(['python3','scripts/start_controller.py','--pid',str(owner['pid']),'--start-ticks',str(owner['identity']['start_ticks'])])
        service.write_json(audit/'STARTED.json',{'owner':owner,'controller':read(ROOT/'processes/controller.json'),'unix':time.time()})
        _,order=registry(ROOT)
        cpuenv=dict(env,CUDA_VISIBLE_DEVICES='',PYTHONPATH=service.RUNTIME['dependencies'])
        def first_completed():
            path=ROOT/'logs/controller_state.json'
            if not path.exists():return False
            state=read(path);require(state.get('status')!='failed','controller failed: '+str(state))
            if state.get('completed')==order[:2]:return True
            service.assert_owned(owner);return False
        wait_until(first_completed,18000,'first pair completion deadline',20)
        source=SOURCES[0]
        with (audit/'first_pair_verify.log').open('xb') as log:
            subprocess.run([service.RUNTIME['python'],'analysis/postrun/verify_pair.py','--source',source],cwd=ROOT,env=cpuenv,stdout=log,stderr=log,check=True,timeout=600)
        gate=ROOT/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json';require(read(gate)['passed'],'actual first pair gate failed')
        try:memory_sampler.snapshot('OWN_GPU_MEMORY_FIRST_PAIR.json')
        except BaseException as error:best_effort_receipt(audit/'MEMORY_RECORDING_ERROR.json',{'error':repr(error),'unix':time.time()})
        service.write_json(audit/'FIRST_PAIR_REVIEW_HOLD.json',{'passed':True,'runs':order[:2],'pair_gate_sha256':sha(gate),'owner':owner,'remaining_submission_requires':'root approve-rest --root-admitted','unix':time.time()})
        def completed():
            path=ROOT/'logs/controller_state.json'
            if not path.exists():return False
            state=read(path)
            require(state.get('status')!='failed','controller failed: '+str(state))
            if state.get('completed')==order:return True
            if state.get('completed')==order[:2] and service.current_identity(owner['pid']) is None:
                return 'first_pair_released_after_review_hold'
            service.assert_owned(owner);return False
        terminal=wait_until(completed,57600,'seven-pair completion deadline',20)
        wait_until(lambda:service.current_identity(owner['pid']) is None,120,'service release deadline')
        rows=service.compute_processes();require(not any(r['pid']==owner['pid'] for r in rows),'service CUDA allocation remains')
        cleanup=read(ROOT/'processes/cleanup.json')
        require(cleanup['pid']==owner['pid'] and cleanup['process_absent'] and cleanup['own_compute_absent'],'exact cleanup receipt missing')
        service.write_json(audit/'ROOT_EXIT_RECEIPT.json',{'passed':True,'owner':owner,'process_absent':True,'CUDA_allocation_absent':True,'cleanup':cleanup,'unix':time.time()})
        cpuenv=dict(env,CUDA_VISIBLE_DEVICES='',PYTHONPATH=service.RUNTIME['dependencies'])
        gates={}
        finished_sources=SOURCES if terminal is True else SOURCES[:1]
        for source in finished_sources:
            with (audit/(source+'_verify.log')).open('xb') as log:
                subprocess.run([service.RUNTIME['python'],'analysis/postrun/verify_pair.py','--source',source],cwd=ROOT,env=cpuenv,stdout=log,stderr=log,check=True,timeout=600)
            path=ROOT/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json';require(read(path)['passed'],'actual pair gate failed')
            gates[source]=sha(path)
        service.write_json(audit/'COMPLETE_REVIEW_HOLD.json',{'passed':True,'jobs':order if terminal is True else order[:2],'GPU_released':True,'remaining_registered_jobs':0 if terminal is True else len(order)-2,'quality_review':'PENDING_ROOT','pair_gate_sha256':gates,'unix':time.time()})
    except BaseException as error:
        owner=failure_cleanup(audit,error,owner,token)
        raise
    finally:
        if memory_sampler is not None:
            try:memory_sampler.finish()
            except BaseException as error:best_effort_receipt(audit/'MEMORY_RECORDING_ERROR.json',{'error':repr(error),'unix':time.time()})
        try:
            if entry is not None and owner is not None and service.current_identity(owner['pid']) is None:
                for peer in peers:
                    try:update_peer(peer,entry,remove=True)
                    except BaseException as error:
                        best_effort_receipt(audit/'PEER_CLEANUP_ERROR.json',{'peer':peer['root'],'error':repr(error),'unix':time.time()})
        except BaseException as error:
            best_effort_receipt(audit/'PEER_CLEANUP_ERROR.json',{'error':repr(error),'unix':time.time()})

if __name__=='__main__':
    with (ROOT/'audit/root_execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        main()
