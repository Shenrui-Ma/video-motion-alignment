"""Explicit root execution only: exact peer admission, one historical-Native fixed control and exact release."""
import argparse, contextlib, fcntl, json, os, signal, subprocess, sys, time, uuid, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import service
from r118_contract import read, require, registry, sha, SOURCES

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
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true',required=True);parser.add_argument('--attempt',required=True);parser.add_argument('--peer-root',action='append',default=[]);parser.add_argument('--parent-tasks-reviewed',action='store_true',required=True);parser.add_argument('--predecessor-attempt',action='append',default=[]);args=parser.parse_args()
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
        review=read(ROOT/'audit/GPU_DEPLOYMENT_REVIEW.json')
        require(review.get('approved') is True and review.get('producer_seal_sha256')==sha(ROOT/'deploy_manifest.json'),'root GPU review does not bind this producer')
        from predecessor import check as check_predecessors
        service.write_json(audit/'PREDECESSORS_RELEASED.json',check_predecessors(ROOT,args.predecessor_attempt))
        from r118_contract import verify_historical_native
        service.write_json(audit/'PARENT_ACTUAL_VERIFIED.json',verify_historical_native(ROOT))
        peers=live_peers(args.peer_root)
        admission={'ready_for_launch':True,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':peer_policy(peers)}
        service.write_json(ROOT/'configs/admission.json',admission)
        service.wait_admission_snapshot(admission,{'queue_running':[],'queue_pending':[]})
        run(['python3','scripts/execution_gate.py','approve-run','--root-admitted','--parent-tasks-reviewed','--free-mib','40960'])
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
        cpuenv=dict(env,CUDA_VISIBLE_DEVICES='',PYTHONPATH=service.RUNTIME['dependencies'])
        gates={}
        def verify_source(source):
            path=ROOT/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json';gate=read(path)
            require(gate['passed'] is True and all(gate['checks'].values()) and gate['service_owner']==owner,'controller actual paired gate failed: '+source)
            gates[source]={'file':str(path),'sha256':sha(path)}
        def first_completed():
            path=ROOT/'logs/controller_state.json'
            if path.exists():
                state=read(path);require(state.get('status')!='failed','controller failed: '+str(state))
                if state.get('completed',[])[:1]==order[:1]:return True
            service.assert_owned(owner);return False
        wait_until(first_completed,read(ROOT/'configs/scientific_contract.json')['continuous']['job_timeout_seconds']+600,'first control completion deadline',20)
        verify_source(SOURCES[0])
        end=time.monotonic()+read(ROOT/'configs/scientific_contract.json')['continuous']['max_service_seconds']
        finished=[]
        while time.monotonic()<end:
            state=read(ROOT/'logs/controller_state.json');require(state.get('status')!='failed','controller failed: '+str(state))
            finished=state.get('completed',[]);require(order[:len(finished)]==finished,'completed order changed')
            if finished==order or service.current_identity(owner['pid']) is None:break
            service.assert_owned(owner);time.sleep(20)
        else:raise TimeoutError('bounded remaining controls deadline')
        wait_until(lambda:service.current_identity(owner['pid']) is None,120,'service release deadline')
        released=service.wait_cuda_release(owner)
        cleanup_path=ROOT/'processes/cleanup.json';wait_until(cleanup_path.exists,10,'exact cleanup receipt deadline',.2)
        cleanup=read(cleanup_path);require(cleanup['pid']==owner['pid'] and cleanup['process_absent'] and cleanup['own_compute_absent'],'exact cleanup missing')
        service.write_json(audit/'ROOT_EXIT_RECEIPT.json',{'passed':True,'owner':owner,'process_absent':True,'CUDA_allocation_absent':True,'cleanup':cleanup,'release':released,'unix':time.time()})
        for source,run_id in zip(SOURCES,order):
            if run_id in finished and source not in gates:verify_source(source)
        require(finished==order,'single output incomplete')
        service.write_json(audit/'COMPLETE.json',{'passed':True,'jobs':finished,'remaining':order[len(finished):],'GPU_released':True,'gates':gates,'quality_review':'PENDING_ROOT','unix':time.time()})
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
