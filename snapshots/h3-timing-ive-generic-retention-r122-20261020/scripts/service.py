"""Start/stop only the isolated H3 screen service; no dependency installation."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import urllib.request
import process_identity

RUN = Path(__file__).resolve().parents[1]
RUNTIME = json.loads((RUN/'configs/runtime.json').read_text())
CORE = Path(RUNTIME['core'])
PYTHON = RUNTIME['python']
DEPENDENCIES = RUNTIME['dependencies']
MODELS = RUNTIME['models']
GPU = RUNTIME['gpu_uuid']
PORT = RUNTIME['port']


def write_json(path, value):
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temporary, path)


def identity(pid):
    return process_identity.service_record(process_identity.snapshot(pid))


def bind_child(process, command):
    return process_identity.service_record(process_identity.bind_or_reap(process, command))


def current_identity(pid):
    try:
        return identity(pid)
    except (FileNotFoundError, ProcessLookupError):
        return None


def external_identity(pid):
    """Compare other jobs without persisting their private command arguments."""
    return process_identity.hashed_record(process_identity.snapshot(pid))


def proc_uid(pid):
    """Inspect ownership without reading another user's command arguments."""
    try:
        return (Path('/proc') / str(int(pid))).stat().st_uid
    except FileNotFoundError:
        return None


def assert_owned(record):
    actual = current_identity(record['pid'])
    if actual is None:
        raise RuntimeError('Recorded service process is absent')
    if actual != record['identity'] or actual['uid'] != os.getuid():
        raise RuntimeError('Process identity mismatch; refusing operation')
    if record.get('gpu_uuid') != GPU or record.get('port') != PORT:
        raise RuntimeError('Service registry belongs to a different GPU/port')
    if str(CORE / 'main.py') not in actual['cmdline'] or str(RUN) not in actual['cmdline']:
        raise RuntimeError('Service command does not match this isolated task')
    return actual


def refuse_existing_service():
    path = RUN / 'processes/service.json'
    if path.exists():
        previous = json.loads(path.read_text())
        if current_identity(previous['pid']) is not None:
            raise RuntimeError('Recorded PID still exists; inspect or stop owned service first')


def compute_processes():
    output = subprocess.run(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,used_memory',
                             '--format=csv,noheader,nounits'],
                            capture_output=True, text=True, check=True, timeout=10).stdout
    rows = []
    for line in output.splitlines():
        if line.strip():
            gpu, pid, memory = [x.strip() for x in line.split(',')]
            rows.append({'gpu_uuid': gpu, 'pid': int(pid), 'used_memory_mib': memory})
    return rows


def queue_at(port):
    if port is None:
        return {'queue_running': [], 'queue_pending': []}
    with urllib.request.urlopen(f'http://127.0.0.1:{int(port)}/queue', timeout=10) as response:
        return json.load(response)


def check_admission(admission, processes, queue):
    import resource_gate as t
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
    if len({row['gpu_uuid'] for row in owned}|{GPU})>2:
        raise t.ResourceUnavailable('planned single-GPU service exceeds two owned GPU cards',{'processes':processes})
    if queue['queue_running'] or queue['queue_pending']:
        raise RuntimeError('Existing Comfy service has queued/running work; refusing to start')


def wait_admission_snapshot(admission, queue, *, exclude_pid=None, timeout=5,
                            clock=time.monotonic, sleep=time.sleep, query=None):
    """Re-read full compute ownership after transient query/proc races, never admit unknown UID."""
    import resource_gate as t
    if not 0 < timeout <= 10:raise ValueError('invalid short admission retry budget')
    query=compute_processes if query is None else query
    start=clock();attempts=0;last=None
    while True:
        attempts+=1
        try:
            rows=query()
            checked=[r for r in rows if r['pid']!=exclude_pid]
            check_admission(admission,checked,queue)
        except (t.ResourceUnavailable,subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
            last=error
        else:
            if clock()>start+timeout:raise TimeoutError('admission snapshot arrived after short retry budget')
            return {'observed_unix':time.time(),'attempts':attempts,'wait_seconds':clock()-start,
                    'processes':rows,'checked_processes':checked}
        if clock()>=start+timeout:
            raise TimeoutError('no consistent complete ownership snapshot within short retry budget') from last
        sleep(min(.2,max(0,start+timeout-clock())))


def main_memory_profile():
    import resource_gate as t
    from execution_gate import approval
    a=approval(RUN)
    return {'schema':'r122-main-capacity-trial-v1','status':'ROOT_APPROVED_NATIVE_SCREEN_TRIAL',
            'required_free_bytes':a['required_free_bytes'],'profile_sha256':t.sha(RUN/'audit/ROOT_SCREEN_APPROVAL.json')}


def gpu_readiness(admission,queue,*,clock=time.monotonic,sleep=time.sleep):
    import resource_gate as t
    p=main_memory_profile();start=clock();deadline=start+600
    audit=RUN/'logs/service_resource_admission.jsonl'
    while True:
        state={'observed_unix':time.time(),'memory_profile_sha256':p['profile_sha256'],'required_free_bytes':p['required_free_bytes']}
        try:
            processes=compute_processes();state['processes']=processes
            check_admission(admission,processes,queue)
            result=subprocess.run(['nvidia-smi','--id='+GPU,'--query-gpu=index,uuid,memory.used,memory.free,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=10)
            state.update(gpu_raw=result.stdout,gpu_stderr=result.stderr)
            rows=[line.strip().split(',') for line in result.stdout.splitlines() if line.strip()]
            t.require(len(rows)==1 and len(rows[0])==6 and int(rows[0][0])==RUNTIME['expected_gpu_index'] and rows[0][1].strip()==GPU and not result.stderr.strip(),'exact main GPU query invalid')
            used,free,util,temperature=[float(x) for x in rows[0][2:]]
            t.require(used>=0 and free>=0 and 0<=util<=100 and 0<=temperature<85,'main GPU health invalid')
            state.update(memory_free_mib=free,memory_used_mib=used,utilization_percent=util,temperature_c=temperature)
            if free*1024**2<p['required_free_bytes']:raise t.ResourceUnavailable('main GPU lacks certified memory headroom',dict(state))
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


def command(cache_none=False):
    args = [PYTHON, '-u', str(RUN / 'scripts/service_entry.py'), str(RUN / 'scripts/compatibility_bootstrap.py'), str(CORE / 'main.py'), '--listen', '127.0.0.1', '--port', str(PORT),
            '--base-directory', str(RUN), '--models-directory', MODELS,
            '--disable-auto-launch', '--disable-dynamic-vram', '--disable-cuda-malloc', '--use-pytorch-cross-attention', '--reserve-vram', '8',
            '--enable-triton-backend', '--preview-method', 'none', '--disable-all-custom-nodes',
            '--whitelist-custom-nodes', 'ComfyUI-KJNodes', 'H3EventAudit', 'H3PairAudit', 'H3TemporalRouter', 'H3X0Readout',
            '--input-directory', str(RUN / 'input'), '--output-directory', str(RUN / 'output'),
            '--temp-directory', str(RUN / 'temp'), '--user-directory', str(RUN / 'user'),
            '--database-url', 'sqlite:///' + str(RUN / 'screen.db')]
    if RUNTIME['memory_mode'] in ('lowvram','novram'):
        args.append('--'+RUNTIME['memory_mode'])
    if cache_none:
        raise ValueError('R122 Native job requires the existing default model/node cache')
    return args


def start(cache_none=False):
    if str(RUN) != RUNTIME['remote_root']:
        raise RuntimeError('Formal service launch requires exact remote lane root')
    from preflight import check
    check(RUN, live=True)
    for directory in ('input', 'output', 'temp', 'user', 'logs', 'configs', 'processes'):
        (RUN / directory).mkdir(parents=True, exist_ok=True)
    with (RUN / 'processes/service.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        refuse_existing_service()
        for required in (Path(PYTHON), CORE / 'main.py', Path(DEPENDENCIES), Path(MODELS),
                         RUN / 'custom_nodes/ComfyUI-KJNodes'):
            if not required.exists():
                raise RuntimeError('Missing runtime path: ' + str(required))
        if not os.access(PYTHON, os.X_OK):
            raise RuntimeError('Runtime Python is not executable')
        admission = json.loads((RUN / 'configs/admission.json').read_text())
        if admission.get('ready_for_launch') is not True:
            raise RuntimeError('R122 root has not completed live hardware/resource admission')
        hardware = gpu_readiness(admission,queue_at(admission.get('existing_comfy_port',8189)))
        processes = compute_processes()
        queue = queue_at(admission.get('existing_comfy_port', 8189))
        check_admission(admission, processes, queue)
        memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        available_kib = int(memory['MemAvailable'].split()[0])
        if available_kib < 20 * 1024 * 1024:
            raise RuntimeError('Host RAM headroom is below 20 GiB')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', PORT))
        env = os.environ.copy()
        env.update(CUDA_VISIBLE_DEVICES=GPU, PYTHONPATH=DEPENDENCIES + os.pathsep + str(RUN/'scripts'),
                   OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4',
                   TMPDIR=str(RUN/'temp'), TMP=str(RUN/'temp'), TEMP=str(RUN/'temp'), TOKENIZERS_PARALLELISM='false', PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1', LC_ALL='C', LANG='C')
        env['H3_SERVICE_SUPERVISOR_JSON']=json.dumps({'pid':os.getpid(),'identity':external_identity(os.getpid())})
        args = command(cache_none)
        started = time.time()
        with (RUN / 'logs/comfyui.log').open('ab', buffering=0) as log:
            process = subprocess.Popen(args, cwd=str(CORE), env=env, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=log, start_new_session=True,
                                       pass_fds=(lock.fileno(),))
        child_identity = bind_child(process, args)
        record = {'pid': process.pid, 'gpu_uuid': GPU, 'port': PORT, 'started_unix': started,
                  'root_attempt_token': os.environ.get('H3_ROOT_ATTEMPT_TOKEN'),
                  'command': args, 'identity': child_identity, 'cache_none': cache_none,
                  'host_available_kib': available_kib, 'admission': admission, 'gpu_readiness': hardware,
                  'preexisting_compute_processes': processes, 'existing_comfy_queue': queue,
                  'state': 'started_readiness_unverified'}
        write_json(RUN / f'processes/service_{process.pid}.json', record)
        write_json(RUN / 'processes/service.json', record)
    print(json.dumps(record))
    return record


def wait_absent(pid, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if current_identity(pid) is None:
            return True
        time.sleep(0.5)
    return current_identity(pid) is None


def wait_cuda_release(record, seconds=30, *, clock=time.monotonic, sleep=time.sleep,
                      query=None, lookup=None):
    """Allow bounded NVML lag after exact-child exit; never signal a recycled PID."""
    query=compute_processes if query is None else query
    lookup=current_identity if lookup is None else lookup
    start=clock();deadline=start+seconds;polls=0;last={}
    while True:
        actual=lookup(record['pid'])
        if actual is not None and actual!=record['identity']:
            raise RuntimeError('PID generation changed while verifying CUDA release')
        polls+=1
        try:
            rows=query()
            last={'process_absent':actual is None,'own_compute_absent':not any(r['pid']==record['pid'] for r in rows),'rows':rows}
            if last['process_absent'] and last['own_compute_absent']:
                return dict(last,polls=polls,wait_seconds=clock()-start)
        except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
            last={'query_error':repr(error),'process_absent':actual is None}
        if clock()>=deadline:
            raise TimeoutError('CUDA release verification exceeded bounded wait: '+json.dumps({'pid':record['pid'],'polls':polls,'last':last}))
        sleep(min(.5,max(0,deadline-clock())))


def stop(expected_record=None):
    record = json.loads((RUN / 'processes/service.json').read_text())
    if expected_record is not None and (record['pid'] != expected_record['pid'] or record['identity'] != expected_record['identity']):
        raise RuntimeError('Service generation changed; stale controller cannot stop replacement')
    pid = record['pid']
    if current_identity(pid) is not None:
        assert_owned(record)
        os.kill(pid, signal.SIGTERM)
        if not wait_absent(pid, 30):
            assert_owned(record)
            os.kill(pid, signal.SIGKILL)
            wait_absent(pid, 10)
    released = wait_cuda_release(record)
    remaining = released['rows']
    result = {'pid': pid, 'stopped_unix': time.time(), 'process_absent': current_identity(pid) is None,
              'own_compute_absent': not any(row['pid'] == pid for row in remaining),
              'remaining_gpu_processes': [row for row in remaining if row['gpu_uuid'] == GPU],
              'service_record': record}
    result['release_verification']={k:v for k,v in released.items() if k!='rows'}
    result['child_compute_absent']=True  # This profile launches no auxiliary CUDA child.
    write_json(RUN / f'processes/cleanup_{pid}.json', result)
    write_json(RUN / 'processes/cleanup.json', result)
    print(json.dumps(result))
    if not result['process_absent'] or not result['own_compute_absent'] or not result['child_compute_absent']:
        raise RuntimeError('Cleanup not yet verified; inspect process and GPU state')
    return result


def stats():
    result = {'observed_unix': time.time(), 'compute_processes': compute_processes()}
    path = RUN / 'processes/service.json'
    if path.exists():
        record = json.loads(path.read_text())
        result.update(service=record, current_identity=current_identity(record['pid']))
        try:
            assert_owned(record)
            result['queue'] = queue_at(PORT)
        except (OSError, ValueError, RuntimeError) as exc:
            result['service_error'] = str(exc)
    sample = subprocess.run(['nvidia-smi', '-i', GPU,
                             '--query-gpu=index,uuid,memory.used,memory.free,utilization.gpu,temperature.gpu',
                             '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True)
    result['gpu_sample_csv'] = sample.stdout.strip()
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'stop', 'stats'])
    parser.add_argument('--cache-none', action='store_true')
    args = parser.parse_args()
    if args.action == 'start':
        start(args.cache_none)
    elif args.action == 'stop':
        stop()
    else:
        stats()


def residency_snapshot(reason):
    record=json.loads((RUN/'processes/service.json').read_text())
    assert_owned(record)
    optional={}
    try:
        rows=compute_processes();own=[r for r in rows if r['pid']==record['pid']]
        optional['sample_available']=True
    except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
        own=None
        optional.update(sample_available=False,error_type=type(error).__name__,error=str(error))
    value={'observed_unix':time.time(),'reason':reason,'service':{'pid':record['pid'],'identity':record['identity']},
           **optional,'own_compute':own,'cache_none':record['cache_none'],'explicit_unload_requested':False,
           'model_residency_scope':'PID VRAM and live cached service only; individual model tensor placement not inferred'}
    with (RUN/'logs/residency.jsonl').open('a') as f:f.write(json.dumps(value)+'\n')
    return value
