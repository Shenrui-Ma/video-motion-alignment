def check_admission(admission, processes, queue):
    from observer_import import t
    t.admission_document(approved=True)
    allowed={int(row['pid']):row['identity'] for row in admission['permitted_compute_processes']}
    owned=[]
    for row in processes:
        uid=proc_uid(row['pid'])
        if uid is None:raise t.ResourceUnavailable('compute process ownership unavailable',{'processes':processes})
        if uid!=os.getuid():continue
        owned.append(row)
        actual=external_identity(row['pid'])
        if row['pid'] not in allowed or actual!=allowed[row['pid']]:
            raise RuntimeError('Unexpected own compute identity '+str(row['pid']))
    if len({row['gpu_uuid'] for row in owned}|{GPU,t.DECODER_UUID})>2:
        raise t.ResourceUnavailable('planned service exceeds two owned GPU cards',{'processes':processes})
    if queue['queue_running'] or queue['queue_pending']:
        raise RuntimeError('Existing Comfy service has queued/running work; refusing to start')


def main_memory_profile():
    from observer_import import t
    path=RUN/'configs/main_memory_profile.json';p=t.read_json(path)
    t.require(p.get('schema')=='h3-main-memory-profile-v4' and p.get('status')=='MEASURED_BOUND','main memory profile pending')
    evidence=t.inside(str((RUN/p['evidence_file']).absolute()),RUN/'configs/main_memory_evidence')
    t.require(t.sha(evidence)==p['evidence_sha256'],'main memory evidence changed')
    r=t.read_json(evidence)
    t.require(r.get('root_approved') is True and r['main_gpu_uuid']==GPU,'main capacity certificate device/approval differs')
    required=r['main_native_peak_sampled_bytes']+r['routing_increment_bound_bytes']+r['main_margin_bytes']
    t.require(r['main_margin_bytes']>=1024**3 and p['required_free_bytes']==r['main_estimated_peak_bytes']>=required,'main capacity bound differs')
    return dict(p,profile_sha256=t.sha(path))


def gpu_readiness(admission,queue,*,clock=time.monotonic,sleep=time.sleep):
    from observer_import import t
    p=main_memory_profile();start=clock();deadline=start+600
    audit=RUN/'logs/service_resource_admission.jsonl'
    while True:
        state={'observed_unix':time.time(),'memory_profile_sha256':p['profile_sha256'],'required_free_bytes':p['required_free_bytes']}
        try:
            processes=compute_processes();state['processes']=processes
            check_admission(admission,processes,queue)
            result=subprocess.run(['nvidia-smi','--id='+GPU,'--query-gpu=uuid,memory.used,memory.free,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=10)
            state.update(gpu_raw=result.stdout,gpu_stderr=result.stderr)
            rows=[line.strip().split(',') for line in result.stdout.splitlines() if line.strip()]
            t.require(len(rows)==1 and len(rows[0])==5 and rows[0][0].strip()==GPU and not result.stderr.strip(),'exact main GPU query invalid')
            used,free,util,temperature=[float(x) for x in rows[0][1:]]
            t.require(used>=0 and free>=0 and 0<=util<=100 and 0<=temperature<85,'main GPU health invalid')
            state.update(memory_free_mib=free,memory_used_mib=used,utilization_percent=util,temperature_c=temperature)
            if free*1024**2<p['required_free_bytes']:raise t.ResourceUnavailable('main GPU lacks certified memory headroom',state)
            state['status']='admitted'
        except (t.ResourceUnavailable,subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
            state.update(status='waiting',reason=str(error),snapshot=getattr(error,'snapshot',None))
        except BaseException as error:
            state.update(status='hard_failure',reason=type(error).__name__+': '+str(error))
            with audit.open('a') as handle:handle.write(json.dumps(state,sort_keys=True)+'\n')
            raise
        with audit.open('a') as handle:handle.write(json.dumps(state,sort_keys=True)+'\n')
        if clock()>deadline:raise TimeoutError('main resource admission exceeded600seconds')
        if state['status']=='admitted':return state
        sleep(min(1,deadline-clock()))


