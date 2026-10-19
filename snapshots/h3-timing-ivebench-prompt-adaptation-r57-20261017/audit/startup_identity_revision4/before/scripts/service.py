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

RUN = Path(__file__).resolve().parents[1]
RUNTIME = json.loads((RUN/'configs/runtime.json').read_text())
CORE = Path(RUNTIME['core'])
PYTHON = RUNTIME['python']
DEPENDENCIES = RUNTIME['dependencies']
MODELS = RUNTIME['models']
GPU = RUNTIME['gpu_uuid']
PORT = RUNTIME['port']


class ResourceUnavailable(ValueError):
    def __init__(self,reason,snapshot):
        super().__init__(reason);self.snapshot=snapshot


def write_json(path, value):
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temporary, path)


def identity(pid):
    proc = Path('/proc') / str(int(pid))
    return {'uid': proc.stat().st_uid,
            'start_ticks': proc.joinpath('stat').read_text().split(') ', 1)[1].split()[19],
            'cmdline': proc.joinpath('cmdline').read_bytes().replace(b'\0', b' ').decode()}


def current_identity(pid):
    try:
        return identity(pid)
    except FileNotFoundError:
        return None


def external_identity(pid):
    """Compare other jobs without persisting their private command arguments."""
    proc = Path('/proc') / str(int(pid))
    try:
        return {'uid': proc.stat().st_uid,
                'start_ticks': proc.joinpath('stat').read_text().split(') ', 1)[1].split()[19],
                'cmdline_sha256': hashlib.sha256(proc.joinpath('cmdline').read_bytes()).hexdigest()}
    except FileNotFoundError:
        return None


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
                            capture_output=True, text=True, check=True, timeout=20).stdout
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
    allowed={int(row['pid']):row['identity'] for row in admission['permitted_compute_processes']}
    owned=[]
    for row in processes:
        uid=proc_uid(row['pid'])
        if uid is None:raise ResourceUnavailable('compute process ownership temporarily unavailable',{'processes':processes})
        if uid!=os.getuid():continue
        owned.append(row)
        actual=external_identity(row['pid'])
        if actual is None:raise ResourceUnavailable('own compute identity disappeared during query',{'pid':row['pid']})
        if row['pid'] not in allowed or actual!=allowed[row['pid']]:
            raise RuntimeError('Unexpected own compute identity '+str(row['pid']))
    if len({row['gpu_uuid'] for row in owned}|{GPU})>2:
        raise ResourceUnavailable('planned service exceeds two owned GPU cards',{'processes':processes})
    if queue['queue_running'] or queue['queue_pending']:
        raise RuntimeError('Existing Comfy service has queued/running work; refusing to start')



def native_memory_profile():
    path=RUN/'configs/native_memory_profile.json';profile=json.loads(path.read_text())
    if profile.get('schema')!='r57-native-memory-admission-v2' or profile.get('margin_mib')!=2048:
        raise ValueError('native memory profile changed')
    relative=Path(profile['evidence_file'])
    if relative.is_absolute() or '..' in relative.parts:raise ValueError('unsafe memory evidence path')
    evidence=RUN/relative
    if hashlib.sha256(evidence.read_bytes()).hexdigest()!=profile['evidence_sha256']:raise ValueError('native memory evidence changed')
    rows=[json.loads(line) for line in evidence.read_text().splitlines() if line.strip()]
    peak=max(float(row['sample'].split(',')[1]) for row in rows)
    if peak!=46353 or profile['sampled_peak_mib']!=peak or profile['required_free_mib']!=peak+2048:
        raise ValueError('native required free memory differs from measured maximum plus margin')
    return dict(profile,profile_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def gpu_readiness(admission,queue,*,clock=time.monotonic,sleep=time.sleep,timeout=600):
    if type(timeout) not in (int,float) or not 0<timeout<=600:raise ValueError('resource wait must be at most600seconds')
    profile=native_memory_profile();deadline=clock()+timeout
    while True:
        if clock()>=deadline:raise TimeoutError('native GPU resource admission deadline expired')
        state={'observed_unix':time.time(),'required_free_mib':profile['required_free_mib'],'memory_profile_sha256':profile['profile_sha256']}
        try:
            processes=compute_processes();state['processes']=processes;check_admission(admission,processes,queue)
            result=subprocess.run(['nvidia-smi','-i',GPU,'--query-gpu=uuid,memory.used,memory.free,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=20)
            rows=[line.strip() for line in result.stdout.splitlines() if line.strip()]
            if len(rows)!=1 or result.stderr.strip():raise RuntimeError('GPU exact-UUID query returned ambiguity or driver error')
            values=[x.strip() for x in rows[0].split(',')]
            if len(values)!=5 or values[0]!=GPU:raise RuntimeError('GPU exact UUID differs from planned device')
            used,free,utilization,temperature=[float(x) for x in values[1:]]
            if not (used>=0 and free>=0 and 0<=utilization<=100 and 0<=temperature<85):raise RuntimeError('GPU health schema/range invalid')
            state.update(csv=rows[0],memory_free_mib=free,memory_used_mib=used,index_fallback=False)
            if free<profile['required_free_mib']:raise ResourceUnavailable('native GPU lacks required free memory',dict(state))
            state['status']='admitted'
        except (ResourceUnavailable,subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
            state.update(status='waiting',error_type=type(error).__name__,error=str(error),snapshot=getattr(error,'snapshot',None))
        except BaseException as error:
            state.update(status='hard_failure',error_type=type(error).__name__,error=str(error))
            with (RUN/'logs/service_resource_admission.jsonl').open('a') as handle:handle.write(json.dumps(state)+'\n')
            raise
        with (RUN/'logs/service_resource_admission.jsonl').open('a') as handle:handle.write(json.dumps(state)+'\n')
        if clock()>=deadline:raise TimeoutError('native GPU resource query completed after deadline')
        if state['status']=='admitted':return state
        sleep(min(2,deadline-clock()))


def command(cache_none=False):
    args = [PYTHON, '-u', str(RUN / 'scripts/service_entry.py'), str(RUN / 'scripts/compatibility_bootstrap.py'), str(CORE / 'main.py'), '--listen', '127.0.0.1', '--port', str(PORT),
            '--base-directory', str(RUN), '--models-directory', MODELS,
            '--disable-auto-launch', '--disable-dynamic-vram', '--disable-cuda-malloc', '--use-pytorch-cross-attention',
            '--enable-triton-backend', '--preview-method', 'none', '--disable-all-custom-nodes',
            '--whitelist-custom-nodes', 'ComfyUI-KJNodes', 'H3EventAudit', 'H3PairAudit', 'H3TemporalRouter', 'H3X0Readout',
            '--input-directory', str(RUN / 'input'), '--output-directory', str(RUN / 'output'),
            '--temp-directory', str(RUN / 'temp'), '--user-directory', str(RUN / 'user'),
            '--database-url', 'sqlite:///' + str(RUN / 'screen.db')]
    if cache_none:
        raise ValueError('R57 Native job requires the existing default model/node cache')
    return args


def start(cache_none=False):
    if str(RUN) != RUNTIME['remote_root']:
        raise RuntimeError('Formal service launch requires exact remote lane root')
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
            raise RuntimeError('R54 root has not completed live hardware/resource admission')
        queue = queue_at(admission.get('existing_comfy_port', 8189))
        hardware = gpu_readiness(admission,queue)
        processes = hardware['processes']
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
        time.sleep(0.2)
        if process.poll() is not None:
            raise RuntimeError('Service exited during startup; inspect logs/comfyui.log')
        record = {'pid': process.pid, 'gpu_uuid': GPU, 'port': PORT, 'started_unix': started,
                  'command': args, 'identity': identity(process.pid), 'cache_none': cache_none,
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
    remaining = compute_processes()
    result = {'pid': pid, 'stopped_unix': time.time(), 'process_absent': current_identity(pid) is None,
              'own_compute_absent': not any(row['pid'] == pid for row in remaining),
              'remaining_gpu_processes': [row for row in remaining if row['gpu_uuid'] == GPU],
              'service_record': record}
    write_json(RUN / f'processes/cleanup_{pid}.json', result)
    write_json(RUN / 'processes/cleanup.json', result)
    print(json.dumps(result))
    if not result['process_absent'] or not result['own_compute_absent']:
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
                             '--query-gpu=uuid,memory.used,memory.free,utilization.gpu,temperature.gpu',
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
    unavailable=None
    try:
        rows=compute_processes();own=[r for r in rows if r['pid']==record['pid']]
    except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
        own=None;unavailable={'error_type':type(error).__name__,'error':str(error)}
    value={'observed_unix':time.time(),'reason':reason,'service':{'pid':record['pid'],'identity':record['identity']},
           'own_compute':own,'compute_snapshot_available':unavailable is None,'unavailable_reason':unavailable,
           'cache_none':record['cache_none'],'explicit_unload_requested':False,
           'model_residency_scope':'PID VRAM and live cached service only; individual model tensor placement not inferred'}
    with (RUN/'logs/residency.jsonl').open('a') as f:f.write(json.dumps(value)+'\n')
    return value
