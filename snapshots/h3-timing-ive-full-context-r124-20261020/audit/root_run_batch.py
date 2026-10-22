"""Explicit root execution only: exact peer admission, Native-first decisions, release, complete outcome ledger."""
import argparse, contextlib, fcntl, json, os, signal, subprocess, sys, time, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import service
from r124_contract import read, require, registry, sha, SOURCES

def live_peers(paths):
    peers=[]
    for path in paths:
        root=Path(path).resolve()
        managed={p.resolve() for p in [ROOT.parent,Path('/data5/researcher/h3_runs'),Path('/home/researcher/h3_runs')]}
        require(root!=ROOT and root.parent in managed,'peer must be a distinct root in an authorized managed run directory')
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
    owner=None;entry=None;peers=[]
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
        run(['python3','scripts/execution_gate.py','approve-screen','--root-admitted','--free-mib','40960'])
        run(['python3','-u','scripts/launch_remote.py','--service-only'])
        owner=read(ROOT/'processes/service.json');ready=read(ROOT/'processes/cuda_gate_ready.json');service.assert_owned(owner)
        require(ready['pid']==owner['pid'] and ready['identity']==service.external_identity(owner['pid']),'preCUDA child identity mismatch')
        require(ready['supervisor']['identity']==service.external_identity(ready['supervisor']['pid']),'preCUDA supervisor identity mismatch')
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
        policy=read(ROOT/'configs/scientific_contract.json')['continuous']
        def terminal():
            actual=service.current_identity(owner['pid'])
            if actual is None:return True
            service.assert_owned(owner)
            path=ROOT/'logs/controller_state.json'
            if path.exists():
                value=read(path);require(value.get('status')!='failed','controller failed: '+str(value))
            return False
        wait_until(terminal,policy['max_service_seconds']+120,'bounded screening service did not release',20)
        service.wait_cuda_release(owner)
        wait_until((ROOT/'processes/cleanup.json').exists,10,'cleanup receipt deadline',.2)
        cleanup=read(ROOT/'processes/cleanup.json')
        require(cleanup['pid']==owner['pid'] and cleanup['process_absent'] and cleanup['own_compute_absent'],'exact cleanup receipt missing')
        service.write_json(audit/'ROOT_EXIT_RECEIPT.json',{'passed':True,'owner':owner,'process_absent':True,'CUDA_allocation_absent':True,'cleanup':cleanup,'unix':time.time()})
        from execution_gate import ledger,decision,first_guided,first_guided_reviewed
        value=ledger(ROOT);state=read(ROOT/'logs/controller_state.json')
        require(state.get('status') in ('all_sources_finished','review_timeout','awaiting_native_review','awaiting_first_guided_review'),'unexpected terminal controller state')
        # A watchdog may expire while the controller is observing the same idle hold.
        rows=value['rows'];successful=[];native_only=[];paired=[]
        for row in rows:
            successful.append(row['native_run'])
            if row['status']=='paired':successful.append(row['forced_run']);paired.append(row['source_id'])
            else:native_only.append(row['source_id'])
        all_done=len(rows)==len(SOURCES) and (first_guided(ROOT) is None or first_guided_reviewed(ROOT))
        result={'schema':'r124-screen-completion-v1','passed':True,'all_sources_reviewed':all_done,'terminal_sources':rows,'successful_runs':successful,'native_only_sources':native_only,'guided_sources':paired,'remaining_sources':list(SOURCES[len(rows):]),'controller_state':state,'GPU_released':True,'first_guided_capacity_verified':first_guided(ROOT) is not None,'first_guided_quality_reviewed':first_guided(ROOT) is not None and first_guided_reviewed(ROOT),'unreviewed_native_results':[s for s in SOURCES if (ROOT/'analysis/postrun'/s/'NATIVE_RUNTIME_GATE.json').exists() and s not in [x['source_id'] for x in rows]],'unix':time.time()}
        service.write_json(audit/('COMPLETE.json' if all_done else 'RELEASED_PENDING_REVIEW.json'),result)
    except BaseException as error:
        owner=failure_cleanup(audit,error,owner,token)
        raise
    finally:
        try:
            if entry is not None and owner is not None and service.current_identity(owner['pid']) is None:
                for peer in peers:
                    try:update_peer(peer,entry,remove=True)
                    except BaseException as error:
                        best_effort_receipt(audit/'PEER_CLEANUP_ERROR.json',{'peer':peer['root'],'error':repr(error),'unix':time.time()})
        except BaseException as error:
            best_effort_receipt(audit/'PEER_CLEANUP_ERROR.json',{'error':repr(error),'unix':time.time()})

def interrupted(signum,frame):raise InterruptedError('root wrapper signal '+str(signum))

if __name__=='__main__':
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    with (ROOT/'audit/root_execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        main()
