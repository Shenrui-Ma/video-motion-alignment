"""Root-only one-leg fresh-service retry; preserve original partial evidence and Native."""
import argparse,fcntl,json,os,shutil,signal,subprocess,sys,time,urllib.error,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import service,job
from r84_contract import read,sha,require,registry
import root_helpers as h
RUN_ID='r84_one_leg__movie_man_9_seed2026101701_forced'
SOURCE='one_leg__movie_man_9'


def same(a,b):return a['pid']==b['pid'] and a['identity']==b['identity']


def inspect_retry(root,old_pid,old_start,*,lookup=None,query=None,probe=None):
    root=Path(root);lookup=lookup or service.current_identity;query=query or service.compute_processes
    owner=read(root/'processes/service.json')
    require(owner['pid']==old_pid and str(owner['identity']['start_ticks'])==str(old_start),'old service identity differs')
    records=[]
    for path in sorted((root/'processes').rglob('*.json')):
        value=read(path)
        if isinstance(value,dict) and 'pid' in value and 'identity' in value:
            require(lookup(value['pid']) is None,'registered old PID is live: '+str(value['pid']))
            records.append({'file':str(path.relative_to(root)),'pid':value['pid'],'identity':value['identity']})
    compute=query();pids={r['pid'] for r in records}
    require(not any(r['pid'] in pids for r in compute),'old registered PID remains in CUDA inventory')
    jobs,order=registry(root);case=jobs[RUN_ID]['case']
    for other in order[1:]:require(not(root/'logs'/(other+'_job.json')).exists(),'another case has actual state; bounded retry requires separate review')
    current=read(root/'logs'/(RUN_ID+'_job.json'))
    require(current['name']==RUN_ID and current['service_pid']==owner['pid'] and current['service_identity']==owner['identity'],'old job service binding differs')
    require(current.get('status')!='success','completed job exists; inspect without resampling')
    history=root/'logs'/(RUN_ID+'_history.json')
    if history.exists():
        history_value=read(history)
        require(history_value['prompt'][1]==current.get('prompt_id'),'saved history differs from original prompt')
        require(not(history_value['status'].get('completed') is True and history_value['status'].get('status_str')=='success'),'successful history exists; inspect before retry')
    manifest_path=root/'audit/x0'/RUN_ID/'manifest.json';manifest=read(manifest_path)
    indices=[c['step_zero_based'] for c in manifest['captures']]
    require(indices==list(range(len(indices))) and len(indices)<20,'capture state is complete/nonprefix; inspect before retry')
    require(manifest.get('status')!='complete' and not manifest.get('final_sampler_result'),'final sampler result exists; inspect before retry')
    outputs=[]
    for path in sorted((root/'output').rglob(RUN_ID+'*')):
        require(path.is_file() and not path.is_symlink(),'unexpected output path')
        info={'file':str(path.relative_to(root)),'sha256':sha(path),'bytes':path.stat().st_size}
        if path.suffix.lower()=='.mp4':
            try:
                if probe is None:
                    raw=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=nb_read_frames','-of','json',str(path)],timeout=60)
                    count=int(json.loads(raw)['streams'][0]['nb_read_frames'])
                else:count=probe(path)
                info['decoded_frame_count']=count
            except (subprocess.CalledProcessError,subprocess.TimeoutExpired,ValueError,KeyError,IndexError) as error:
                info['decode_error']=repr(error);count=None
            require(count is None or count<158,'full-sized output exists; inspect before retry')
        outputs.append(info)
    gate=root/'analysis/postrun'/SOURCE/'PAIR_RUNTIME_GATE.json'
    require(not(gate.exists() and read(gate).get('passed') is True),'successful pair gate exists')
    return {'passed_for_retry':True,'old_owner':owner,'old_job':current,'captured_indices':indices,'outputs':outputs,'processes':records,'CUDA_inventory':compute,'case':case,'unix':time.time()}


def archive_attempt(root,audit,evidence):
    root=Path(root).resolve();audit=Path(audit).resolve();case=evidence['case'];sealed=set(read(root/'deploy_manifest.json')['files'])
    paths=[root/'processes',root/'logs',root/'audit/x0'/RUN_ID,root/'audit/router'/(RUN_ID+'.json'),root/'audit/tensor_blobs',root/'analysis/postrun'/SOURCE,root/'audit/ROOT_JOB_APPROVALS'/(RUN_ID+'.json'),root/'audit'/(case['baseline_noise_pair_id']+'_noise.pt')]
    paths.extend((root/'audit').glob(RUN_ID+'_*'));paths.extend((root/'audit').glob(case['reference_cache_id']+'_*'))
    paths.extend(root/row['file'] for row in evidence['outputs'])
    paths=sorted(set(p for p in paths if p.exists()),key=lambda p:str(p))
    all_files=[]
    for path in paths:
        require(path.resolve().is_relative_to(root) and not path.is_symlink(),'archive target leaves current run')
        for file in ([path] if path.is_file() else path.rglob('*')):
            if file.is_file():
                rel=str(file.relative_to(root));require(rel not in sealed,'attempt archive would move frozen file: '+rel)
                require(not file.is_symlink(),'archive symlink rejected');all_files.append({'file':rel,'bytes':file.stat().st_size,'sha256':sha(file)})
    # Both local noise copies are known inputs; only the first case's copy is reset.
    source=Path(case['baseline_root'])/'audit'/(case['baseline_noise_pair_id']+'_noise.pt')
    binding=read(root/'configs/HISTORICAL_BINDINGS.json')[SOURCE]['files'][str(source.relative_to(case['baseline_root']))]
    require(sha(source)==binding['sha256'] and source.stat().st_size==binding['bytes'],'historical Native noise changed')
    service.write_json(audit/'ARCHIVE_PLAN.json',{'evidence':evidence,'files':all_files,'source_noise':str(source),'source_noise_sha256':sha(source)})
    archive=audit/'previous_attempt';archive.mkdir(exist_ok=False)
    for path in paths:
        target=archive/path.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);path.rename(target)
    for name in ['processes','logs','audit/tensor_blobs']:(root/name).mkdir(parents=True,exist_ok=True)
    copied=root/'audit'/source.name;shutil.copyfile(source,copied)
    require(sha(copied)==binding['sha256'],'restored paired noise bytes differ')
    service.write_json(audit/'ARCHIVED.json',{'passed':True,'files':all_files,'restored_noise':{'file':str(copied),'sha256':sha(copied)},'historical_Native_modified':False,'unix':time.time()})


def install_watchdog(owner,audit):
    previous=read(ROOT/'processes/watchdog.json');actual=service.current_identity(previous['pid'])
    require(actual==previous['identity'] and actual['uid']==os.getuid() and str(ROOT/'scripts/lease_watchdog.py') in actual['cmdline'],'new original watchdog identity differs')
    service.write_json(audit/'ORIGINAL_WATCHDOG.json',previous)
    os.kill(previous['pid'],signal.SIGTERM)
    require(service.wait_absent(previous['pid'],10),'original watchdog remains live')
    service.assert_owned(owner)
    command=['python3','-u',str(HERE/'watchdog_entry.py'),'--receipt-dir',str(audit/'watchdog'),'--expected-pid',str(owner['pid']),'--expected-start-ticks',str(owner['identity']['start_ticks'])]
    with (audit/'watchdog.log').open('ab',buffering=0) as log:
        child=subprocess.Popen(command,cwd=ROOT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    identity=service.bind_child(child,command)
    replacement={'pid':child.pid,'identity':identity,'role':'watchdog_v2','service_pid':owner['pid'],'service_identity':owner['identity']}
    service.write_json(ROOT/'processes/watchdog.json',replacement)
    def ready():
        require(child.poll() is None,'v2 watchdog exited')
        path=audit/'watchdog/STARTED.json'
        if not path.exists():return False
        value=read(path);require(value['watchdog_pid']==child.pid and value['watchdog_identity']==identity and same(value['owner'],owner),'v2 startup identity differs');return True
    h.wait_until(ready,20,'v2 watchdog readiness timeout',.2)
    service.write_json(audit/'WATCHDOG_REPLACED.json',{'original':previous,'replacement':replacement,'before_CUDA_GO':True,'policy_sha256':sha(ROOT/'audit/watchdog_recovery_v2/watchdog_v2.py')})
    return child,replacement


def poll_completed(owner,audit):
    service.assert_owned(owner)
    try:answer=job.status(RUN_ID)
    except (TimeoutError,ConnectionError,urllib.error.URLError) as error:
        if isinstance(error,urllib.error.HTTPError):raise
        service.write_json(audit/'PROGRESS.json',{'observation':'UNKNOWN','error':repr(error),'deadline_reset':False,'unix':time.time()});return False
    status=answer.get('status');service.write_json(audit/'PROGRESS.json',{'answer':answer,'unix':time.time(),'deadline_reset':False})
    if isinstance(status,dict):
        require(status.get('status_str')!='error','actual Comfy history error')
        return status.get('completed') is True and status.get('status_str')=='success'
    require(status not in ('error','submission_uncertain'),'actual job failure');return False


def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true',required=True);p.add_argument('--native-reviewed',action='store_true',required=True);p.add_argument('--attempt',required=True);p.add_argument('--old-pid',type=int,default=857566);p.add_argument('--old-start-ticks',default='8690132');a=p.parse_args()
    require(ROOT==Path(service.RUNTIME['remote_root']),'exact remote run required');require(a.attempt.replace('_','').replace('-','').isalnum(),'invalid attempt')
    audit=ROOT/'audit'/a.attempt;audit.mkdir(exist_ok=False);owner=None;token=uuid.uuid4().hex
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',H3_ROOT_ATTEMPT_TOKEN=token,LC_ALL='C',LANG='C')
    def run(args,cpu=False,timeout=720,name='execution.log'):
        with (audit/name).open('ab',buffering=0) as log:return subprocess.run(args,cwd=ROOT,env=dict(env,CUDA_VISIBLE_DEVICES='',PYTHONPATH=service.RUNTIME['dependencies']) if cpu else env,stdout=log,stderr=log,check=True,timeout=timeout)
    try:
        service.write_json(audit/'ATTEMPT_BINDING.json',{'root':str(ROOT),'token':token,'script_sha256':sha(Path(__file__)),'unix':time.time()})
        seal=read(ROOT/'deploy_manifest.json');require(all(sha(ROOT/k)==v['sha256'] for k,v in seal['files'].items()),'frozen producer changed')
        evidence=inspect_retry(ROOT,a.old_pid,a.old_start_ticks);service.write_json(audit/'ACTUAL_RETRY_INSPECTION.json',evidence)
        archive_attempt(ROOT,audit,evidence)
        admission={'ready_for_launch':True,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]}
        service.write_json(ROOT/'configs/admission.json',admission)
        service.wait_admission_snapshot(admission,{'queue_running':[],'queue_pending':[]})
        run(['python3','scripts/execution_gate.py','approve-service','--root-admitted','--free-mib','30720'])
        run(['python3','-u','scripts/launch_remote.py','--service-only'])
        candidate=read(ROOT/'processes/service.json');require(h.has_attempt_token(candidate,token),'wrong launch attempt');service.assert_owned(candidate);owner=candidate
        ready=read(ROOT/'processes/cuda_gate_ready.json')
        require(ready['pid']==owner['pid'] and ready['identity']==service.external_identity(owner['pid']),'preCUDA child identity differs')
        require(ready['supervisor']['identity']==service.external_identity(ready['supervisor']['pid']),'preCUDA supervisor differs')
        watchdog,_=install_watchdog(owner,audit)
        service.wait_admission_snapshot(admission,{'queue_running':[],'queue_pending':[]})
        service.write_json(audit/'ADMITTED.json',{'owner':owner,'ready':ready,'same_host_own_peers':[],'watchdog_v2_ready':True,'unix':time.time()})
        service.write_json(ROOT/'processes/cuda_gate_go.json',ready)
        def http_ready():
            service.assert_owned(owner)
            try:q=service.queue_at(service.PORT)
            except OSError:return False
            require(not q['queue_running'] and not q['queue_pending'],'unexpected existing queue');return True
        h.wait_until(http_ready,600,'HTTP service unavailable')
        run(['python3','scripts/execution_gate.py','approve-run',RUN_ID,'--root-admitted','--native-reviewed'])
        job.submit(RUN_ID,expected_owner=owner)
        service.write_json(audit/'STARTED.json',{'owner':owner,'run_id':RUN_ID,'single_service_trial':True,'unix':time.time()})
        seconds=read(ROOT/'configs/scientific_contract.json')['continuous']['job_timeout_seconds']
        h.wait_until(lambda:poll_completed(owner,audit),seconds,'one_leg job deadline',20)
        cleanup=service.stop(expected_record=owner)
        require(cleanup['process_absent'] and cleanup['own_compute_absent'],'exact release failed')
        service.write_json(audit/'ROOT_EXIT_RECEIPT.json',{'passed':True,'owner':owner,'process_absent':True,'CUDA_allocation_absent':True,'cleanup':cleanup,'unix':time.time()})
        run([service.PYTHON,'analysis/postrun/verify_pair.py','--source',SOURCE],cpu=True,timeout=1200,name='pair_verify.log')
        gate=ROOT/'analysis/postrun'/SOURCE/'PAIR_RUNTIME_GATE.json';require(read(gate)['passed'],'actual pair gate failed')
        service.write_json(audit/'COMPLETE_REVIEW_HOLD.json',{'passed':True,'pair_gate_sha256':sha(gate),'run_id':RUN_ID,'GPU_released':True,'fitness_submitted':False,'next':'root review one_leg; fitness separately','unix':time.time()})
    except BaseException as error:
        h.failure_cleanup(audit,error,owner,token);raise

if __name__=='__main__':
    def interrupted(signum,frame):raise KeyboardInterrupt('root retry signal '+str(signum))
    signal.signal(signal.SIGTERM,interrupted)
    with (ROOT/'audit/root_execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);main()
