"""Explicit root execution only: exact peer admission, one historical-parent matched fixed control and exact release."""
import argparse, contextlib, fcntl, json, os, signal, subprocess, sys, time, uuid, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import service
from r112_contract import read, require, registry, sha, SOURCES

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
    require(sha(prior/'deploy_manifest.json')==expected['producer_seal_sha256'],'predecessor seal differs')
    owner=read(prior/'processes/service.json');runtime=read(prior/'configs/runtime.json')
    require(owner['gpu_uuid']==service.GPU and owner['port']==runtime['port'] and runtime['remote_root']==str(prior),'predecessor runtime differs')
    require(owner['identity']['uid']==os.getuid() and str(prior/'scripts/service_entry.py') in owner['identity']['cmdline'],'predecessor is not known owned service')
    audit=prior/'audit'/expected['attempt'];exit=read(audit/'ROOT_EXIT_RECEIPT.json');complete=read(audit/'COMPLETE.json')
    require(complete['passed'] is True and complete['all_sources_reviewed'] is True and complete['GPU_released'] is True,'R103 priority batch not complete')
    require(exit['passed'] is True and exit['owner']==owner and exit['process_absent'] is True and exit['CUDA_allocation_absent'] is True,'predecessor exact exit differs')
    require(service.current_identity(owner['pid']) is None,'predecessor service still exists')
    require(not any(row['pid']==owner['pid'] for row in service.compute_processes()),'predecessor CUDA allocation remains')
    cleanup=read(prior/'processes/cleanup.json');require(cleanup['pid']==owner['pid'] and cleanup.get('process_absent') is True and cleanup.get('own_compute_absent') is True,'predecessor exact cleanup pending')
    return {'owner':owner,'cleanup':cleanup,'complete_sha256':sha(audit/'COMPLETE.json'),'exit_sha256':sha(audit/'ROOT_EXIT_RECEIPT.json'),'followup':'R112 two-arm correspondence trial'}

def prepare_original_noise():
    results=[]
    for source_id,b in read(ROOT/'configs/parent_bindings.json').items():
        source=Path(b['noise']['cache_file']);digest=b['noise']['current_file']['sha256'];target=ROOT/b['new_noise_relative']
        require(sha(source)==digest,'actual parent noise changed: '+source_id)
        if not target.exists():
            tmp=target.with_suffix('.copying')
            with source.open('rb') as before,tmp.open('xb') as after:shutil.copyfileobj(before,after)
            require(sha(tmp)==digest,'original noise copy differs');os.replace(tmp,target)
        require(not target.is_symlink() and sha(target)==digest,'new noise cache differs from actual parent')
        results.append({'source_id':source_id,'source':str(source),'destination':str(target),'sha256':digest,'bytes':target.stat().st_size})
    return results

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true',required=True);parser.add_argument('--attempt',required=True);parser.add_argument('--peer-root',action='append',default=[]);parser.add_argument('--parent-tasks-reviewed',action='store_true',required=True);args=parser.parse_args()
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
        from parent_evidence import verify_parent
        service.write_json(audit/'PARENT_ACTUAL_VERIFIED.json',verify_parent(ROOT,include_snapshots=True))
        service.write_json(audit/'ORIGINAL_AV_NOISE.json',prepare_original_noise())
        peers=live_peers(args.peer_root)
        require(not peers,'R112 host41 cold load uses one H3 service; short metric jobs must finish before launch')
        import cgroup_memory
        service.write_json(audit/'CGROUP_PRE_LAUNCH.json',cgroup_memory.check(ROOT))
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
        service.write_json(audit/'CGROUP_PRE_GO.json',cgroup_memory.check(ROOT))
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
        def verify_run(run):
            path=ROOT/'analysis/postrun'/run/'RUNTIME_GATE.json';gate=read(path)
            require(gate['passed'] is True and all(gate['checks'].values()) and gate['service_owner']==owner,'controller actual gate failed: '+run)
            gates[run]={'file':str(path),'sha256':sha(path)}
        def first_completed():
            path=ROOT/'logs/controller_state.json'
            if path.exists():
                state=read(path);require(state.get('status')!='failed','controller failed: '+str(state))
                if state.get('completed',[])[:1]==order[:1]:return True
            service.assert_owned(owner);return False
        wait_until(first_completed,read(ROOT/'configs/scientific_contract.json')['continuous']['job_timeout_seconds']+600,'first control completion deadline',20)
        verify_run(order[0])
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
        for run_id in order:
            if run_id in finished and run_id not in gates:verify_run(run_id)
        require(finished==order,'two-arm output incomplete')
        pair_path=ROOT/'analysis/postrun/long_0174/PAIR_RUNTIME_GATE.json';pair=read(pair_path)
        require(pair['passed'] is True and all(pair['checks'].values()) and pair['service_owner']==owner,'two-arm aggregate gate failed')
        service.write_json(audit/'COMPLETE.json',{'passed':True,'jobs':finished,'remaining':order[len(finished):],'GPU_released':True,'gates':{'long_0174':{'file':str(pair_path),'sha256':sha(pair_path)}},'run_gates':gates,'pair_gate':{'file':str(pair_path),'sha256':sha(pair_path)},'quality_review':'PENDING_ROOT','unix':time.time()})
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
