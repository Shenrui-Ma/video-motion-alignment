"""Explicit root execution only: exact peer admission, Native-first decisions, release, complete outcome ledger."""
import argparse, contextlib, fcntl, json, os, signal, subprocess, sys, time, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import service
import urllib.request
from r132_contract import read, require, registry, sha, SOURCES

atomic=service.write_json

def start_capacity_monitor(owner,d):
 command=['python3','-u',str(ROOT/'scripts/capacity_trial.py'),'--root',str(ROOT),
          '--output',str(d/'CAPACITY_TRIAL.jsonl'),'--ready',str(d/'CAPACITY_MONITOR_READY.json')]
 with (d/'capacity_monitor.log').open('ab',buffering=0) as log:
  child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 ident=service.bind_child(child,command)
 atomic(ROOT/'processes/capacity_monitor.json',{'pid':child.pid,'identity':ident,'service':owner})
 return child,ident

def capacity_ready(child,ident,owner,d):
 import capacity_trial
 deadline=time.monotonic()+30
 while time.monotonic()<deadline:
  service.assert_owned(owner)
  require(child.poll() is None and service.current_identity(child.pid)==ident,'capacity monitor exited before readiness')
  path=d/'CAPACITY_MONITOR_READY.json'
  if path.exists():
   ready=read(path)
   require(ready['passed'] is True and capacity_trial.same_identity(ready['owner'],capacity_trial.bind_service(ROOT)),
           'capacity readiness service identity differs')
   require(capacity_trial.same_identity(ready['monitor_identity'],capacity_trial.identity(child.pid)),
           'capacity readiness monitor identity differs')
   return ready
  time.sleep(.05)
 raise TimeoutError('capacity monitor readiness timeout')

def finish_capacity_monitor(child,ident):
 if child is None:return None
 try:code=child.wait(timeout=10)
 except subprocess.TimeoutExpired:
  import capacity_trial
  current=capacity_trial.identity(child.pid)
  require(service.current_identity(child.pid)==ident and current is not None,'capacity monitor generation changed')
  capacity_trial.signal_exact(current)
  code=child.wait(timeout=10)
 return {'pid':child.pid,'identity':ident,'exit_code':code,'exact_generation_absent':service.current_identity(child.pid)!=ident}

def live_peers(paths):
    peers=[]
    for path in paths:
        root=Path(path).resolve()
        managed={p.resolve() for p in [ROOT.parent,Path('/data3/researcher/h3_runs'),Path('/data4/researcher/h3_runs')]}
        explicit_peers={Path(p) for p in ['/home/researcher/h3_runs/reference_feedback_r151_20261021/cases/short_0252', '/home/researcher/h3_runs/reference_feedback_r151_20261021/cases/short_0358', '/home/researcher/h3_runs/reference_feedback_r151_20261021/cases/05_real_megumi_v']}
        require(root!=ROOT and (root.parent in managed or root in explicit_peers),'peer root is outside explicit authorization')
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

def readonly_peer_policy(root=ROOT):
    """Allow this exact user service without modifying or signalling it."""
    spec=read(Path(root)/'configs/readonly_peer.json')
    if spec.get('boot_id')!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():return []
    actual=service.external_identity(spec['pid'])
    if actual is None:return []
    require(actual==spec['identity'] and actual['uid']==os.getuid(),'existing user service identity changed')
    for row in service.compute_processes():
        if row['pid']==spec['pid']:require(row['gpu_uuid']==spec['gpu_uuid'],'existing user service GPU changed')
    require(spec['gpu_uuid']!=service.GPU,'existing user service occupies requested GPU')
    return [{'pid':spec['pid'],'identity':actual}]


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
    owner=None;entry=None;peers=[];monitor=None;monitor_identity=None;capacity_result=None
    token=uuid.uuid4().hex
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C',H3_ROOT_ATTEMPT_TOKEN=token)
    def run(argv,timeout=720):
        with (audit/'execution.log').open('ab',buffering=0) as log:
            return subprocess.run(argv,cwd=ROOT,env=env,stdout=log,stderr=log,check=True,timeout=timeout)
    try:
        service.write_json(audit/'ATTEMPT_BINDING.json',{'token':token,'root':str(ROOT),'created_unix':time.time()})
        require(not (ROOT/'processes/service.json').exists(),'existing service record requires separate recovery')
        peers=live_peers(args.peer_root)
        admission={'ready_for_launch':True,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':peer_policy(peers)+readonly_peer_policy()}
        service.write_json(ROOT/'configs/admission.json',admission)
        service.wait_admission_snapshot(admission,{'queue_running':[],'queue_pending':[]})
        run(['python3','scripts/execution_gate.py','approve-screen','--root-admitted','--free-mib',str(read(ROOT/'configs/runtime.json')['minimum_free_mib'])])
        run(['python3','-u','scripts/launch_remote.py','--service-only'])
        owner=read(ROOT/'processes/service.json');ready=read(ROOT/'processes/cuda_gate_ready.json');service.assert_owned(owner)
        require(ready['pid']==owner['pid'] and ready['identity']==service.external_identity(owner['pid']),'preCUDA child identity mismatch')
        require(ready['supervisor']['identity']==service.external_identity(ready['supervisor']['pid']),'preCUDA supervisor identity mismatch')
        peers=live_peers(args.peer_root);entry={'pid':owner['pid'],'identity':ready['identity']}
        admission['permitted_compute_processes']=peer_policy(peers)+readonly_peer_policy()
        service.write_json(ROOT/'configs/admission.json',admission)
        service.wait_admission_snapshot(admission,{'queue_running':[],'queue_pending':[]})
        for peer in peers:update_peer(peer,entry)
        service.write_json(audit/'ADMITTED.json',{'owner':owner,'ready':ready,'peers':peers,'created_unix':time.time()})
        monitor,monitor_identity=start_capacity_monitor(owner,audit)
        capacity_ready(monitor,monitor_identity,owner,audit)
        command=['python3','-u',str(ROOT/'scripts/capacity_watchdog.py'),'--owner',str(ROOT/'processes/service.json')]
        with (audit/'capacity_watchdog.log').open('ab',buffering=0) as log:
            child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        service.write_json(ROOT/'processes/capacity_watchdog.json',{'pid':child.pid,'identity':service.bind_child(child,command)})
        service.write_json(ROOT/'processes/cuda_gate_go.json',ready)
        def http_ready():
            service.assert_owned(owner)
            try:q=service.queue_at(service.PORT)
            except OSError:return False
            require(not q['queue_running'] and not q['queue_pending'],'unexpected existing queue')
            with urllib.request.urlopen(f'http://127.0.0.1:{service.PORT}/object_info',timeout=30) as response:info=json.load(response)
            required={node['class_type'] for name in registry(ROOT)[1] for node in read(ROOT/'configs/graphs'/(name+'.json')).values()}
            require(required<=set(info),'actual HTTP node types missing: '+repr(sorted(required-set(info))))
            service.write_json(audit/'HTTP_NODE_SCHEMA.json',{'passed':True,'required':sorted(required),'available':sorted(info)})
            return True
        wait_until(http_ready,600,'HTTP service unavailable')
        run(['python3','scripts/start_controller.py','--pid',str(owner['pid']),'--start-ticks',str(owner['identity']['start_ticks'])])
        service.write_json(audit/'STARTED.json',{'owner':owner,'controller':read(ROOT/'processes/controller.json'),'unix':time.time()})
        _,order=registry(ROOT)
        policy=read(ROOT/'configs/scientific_contract.json')['continuous']
        def terminal():
            actual=service.current_identity(owner['pid'])
            state_path=ROOT/'logs/controller_state.json'
            if state_path.exists():require(read(state_path).get('status')!='failed','controller failed: '+repr(read(state_path)))
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
        capacity_result=finish_capacity_monitor(monitor,monitor_identity);monitor=None
        require(capacity_result['exit_code']==0,'capacity monitor failed')
        service.write_json(audit/'CAPACITY_MONITOR_EXIT.json',capacity_result)
        service.write_json(audit/'ROOT_EXIT_RECEIPT.json',{'passed':True,'owner':owner,'process_absent':True,'CUDA_allocation_absent':True,'cleanup':cleanup,'unix':time.time()})
        gate_path=ROOT/'analysis/postrun/sam07/SCHEDULE_RUNTIME_GATE.json'
        gate=read(gate_path)
        require(gate['passed'] is True and gate['service_owner']==owner,'reference-origin gate incomplete or owner changed')
        require(read(ROOT/'logs/controller_state.json')['status']=='all_sources_finished','controller incomplete')
        service.write_json(audit/'COMPLETE.json',{'schema':'r149-schedule-completion-v1','passed':True,'jobs':order,'remaining':[],'GPU_released':True,'runtime_gate_sha256':sha(gate_path),'service_owner':gate['service_owner'],'unix':time.time()})
    except BaseException as error:
        owner=failure_cleanup(audit,error,owner,token)
        raise
    finally:
        if monitor is not None:
            best_effort_receipt(audit/'CAPACITY_MONITOR_EXIT.json',finish_capacity_monitor(monitor,monitor_identity))
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
