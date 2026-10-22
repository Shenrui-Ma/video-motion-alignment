def record_resources(current):
    sample={'unix':time.time(),'job':current}
    try:
        stats=subprocess.run(['nvidia-smi','-i',service.GPU,'--query-gpu=uuid,memory.used,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=20,check=True)
    except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
        sample.update(sample=None,sample_available=False,error_type=type(error).__name__,error=str(error))
    else:
        sample.update(sample=stats.stdout.strip() or None,sample_available=bool(stats.stdout.strip()))
    with (service.RUN/'logs/resources.jsonl').open('a') as handle:handle.write(json.dumps(sample)+'\n')


def wait_controller_registration(expected_pid, expected_start_ticks, *, timeout=10,
                                 clock=time.monotonic, sleep=time.sleep):
    """No Comfy submission until the launcher publishes this exact controller."""
    own_pid = os.getpid()
    own_identity = service.identity(own_pid)
    deadline = clock() + timeout
    path = service.RUN / 'processes/controller.json'
    while clock() < deadline:
        if service.current_identity(own_pid) != own_identity:
            raise RuntimeError('controller generation changed before registration')
        if path.exists():
            record = read(path)
            if (record.get('pid') != own_pid or record.get('identity') != own_identity or
                record.get('role') != 'controller' or record.get('service_pid') != expected_pid or
                str(record.get('service_identity', {}).get('start_ticks')) != str(expected_start_ticks)):
                raise RuntimeError('controller registration does not identify this launch')
            owner = read(service.RUN / 'processes/service.json')
            if owner['pid'] != expected_pid or owner['identity'] != record['service_identity']:
                raise RuntimeError('registered controller service generation differs')
            service.assert_owned(owner)
            return record
        sleep(min(.02, max(0, deadline-clock())))
    raise TimeoutError('controller registration missing; no job submitted')

