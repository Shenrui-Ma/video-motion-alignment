"""CPU-only remote inspection/drain. Never sends signals or starts processes."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import urllib.request


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def digest(document):
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def identity(record, required_text, proc_root=Path('/proc'), uid=None):
    if not record:
        return {'state': 'missing_record'}
    proc = proc_root / str(record['pid'])
    try:
        # comm may contain spaces; field 22 follows the final ')' plus 19 fields.
        stat = (proc / 'stat').read_text()
        ticks = stat.rsplit(')', 1)[1].split()[19]
        actual_uid = proc.stat().st_uid
        command = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
        matched = actual_uid == (os.getuid() if uid is None else uid) and ticks == str(record['start_ticks']) and required_text in command
        return {'state': 'owned_alive' if matched else 'identity_mismatch', 'pid': record['pid'], 'uid': actual_uid, 'start_ticks': ticks}
    except FileNotFoundError:
        return {'state': 'exited', 'pid': record['pid']}


def locked(path):
    if not path.exists():
        return False
    with path.open('r+') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(stream, fcntl.LOCK_UN)
        return False


def partition(manifest, states):
    jobs = manifest['jobs']
    ids = [job['id'] for job in jobs]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate job IDs')
    # Retain every state entry, including pending/submitting/unknown/failed.
    # A pending record may already be waiting for service readiness inside run_job.
    kept = [job for job in jobs if job['id'] in states]
    parked = [job for job in jobs if job['id'] not in states]
    return {**manifest, 'jobs': kept}, {**manifest, 'jobs': parked}


def deployment_ready(worker, service, locks, listening, status, states):
    return (worker['state'] == 'exited' and status.get('event') == 'finished'
            and status.get('cleanup_code') == 0 and status.get('queue_exit_code') in (0, 1)
            and service['state'] in ('exited', 'missing_record')
            and not any(locks.values()) and not listening
            and all(s.get('status') in ('completed', 'failed', 'invalid') for s in states.values()))


def snapshot(root):
    manifest = read(root / 'jobs.json')
    if manifest is None:
        raise ValueError('Missing manifest')
    states = read(root / 'queue_state/state.json', {'jobs': {}})['jobs']
    worker = identity(read(root / 'worker_pid.json'), str(root / 'scripts/host_worker.py'))
    service_rec = read(root / 'service.json')
    service = identity(service_rec, str(root))
    locks = {name: locked(root / name) for name in ('worker.lock', 'queue_state/runner.lock')}
    queue = None
    api_error = None
    port = service_rec.get('port') if service_rec else None
    port = port or (8673 if root.name.endswith('host9a') else 8674)
    listening = False
    with socket.socket() as sock:
        sock.settimeout(2)
        listening = sock.connect_ex(('127.0.0.1', port)) == 0
    if listening:
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(f'http://127.0.0.1:{port}/queue', timeout=8) as response:
                q = json.load(response)
            queue = [{'prompt_id': row[1], 'job_id': (row[3] or {}).get('durable_job_id')} for row in q.get('queue_running', []) + q.get('queue_pending', [])]
        except Exception as error:
            api_error = str(error)
    status = read(root / 'worker_status.json', {})
    ready = deployment_ready(worker, service, locks, listening, status, states)
    return {'root': str(root), 'checked_unix': time.time(), 'manifest': manifest,
            'manifest_sha256': digest(manifest), 'states': states, 'worker': worker,
            'service': service, 'locks': locks, 'api_queue': queue, 'api_error': api_error,
            'port_listening': listening, 'worker_status': status, 'ready_for_deployment': ready}


def main_gate(root):
    doc = read(root / 'jobs.json')
    states = read(root / 'queue_state/state.json', {'jobs': {}})['jobs']
    ids = [job['id'] for job in doc['jobs'] if job['id'].startswith('new_')]
    missing = [job for job in ids if states.get(job, {}).get('status') != 'completed']
    return {'required': 24, 'total': len(ids), 'completed': len(ids) - len(missing), 'pending': missing,
            'passed': len(ids) == 24 and len(set(ids)) == 24 and not missing}


def validate_drain(snap, original=None):
    if snap['worker']['state'] not in ('owned_alive', 'exited'):
        raise ValueError('Worker identity cannot be verified')
    if snap['service']['state'] == 'identity_mismatch':
        raise ValueError('Service identity mismatch')
    if snap['worker']['state'] == 'owned_alive' and not snap['locks']['worker.lock']:
        raise ValueError('Owned worker lacks worker lock')
    if snap['service']['state'] == 'owned_alive' and snap['api_error']:
        raise ValueError('Live service API unavailable; inspect before drain')
    # Every active API entry must map to our recorded manifest and durable state.
    ids = {job['id'] for job in (original or snap['manifest'])['jobs']}
    for row in snap['api_queue'] or []:
        if row['job_id'] not in ids or row['job_id'] not in snap['states']:
            raise ValueError('Active API job not reconciled to manifest/state')


def drain(root, expected_hash):
    directory = root / 'innovation_handoff'
    directory.mkdir(exist_ok=True)
    with (directory / 'drain.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        snap = snapshot(root)
        if snap['manifest_sha256'] != expected_hash:
            raise ValueError('Manifest changed since local preflight; retry inspection')
        original_path = directory / 'original_manifest.json'
        original = read(original_path)
        validate_drain(snap, original)
        if original is None:
            original = snap['manifest']
            atomic(original_path, original)
        original_map = {j['id']: j for j in original['jobs']}
        for job in snap['manifest']['jobs']:
            if original_map.get(job['id']) != job:
                raise ValueError('Manifest contains new/modified job after prior drain')
        kept, parked = partition(original, snap['states'])
        atomic(directory / 'parked_manifest.json', parked)
        atomic(root / 'jobs.json', kept)
        # Runner may have selected one job from its old manifest immediately before
        # replacement. Never signal it; absorb any persisted intent on reinspection.
        post = snapshot(root)
        kept, parked = partition(original, post['states'])
        atomic(directory / 'parked_manifest.json', parked)
        atomic(root / 'jobs.json', kept)
        return {'action': 'drained', 'kept': kept, 'parked': parked, 'snapshot': snapshot(root)}


def dispatch(request):
    root = Path(request['root'])
    if request['action'] == 'main_gate':
        return main_gate(root)
    if request['action'] == 'inspect':
        return snapshot(root)
    if request['action'] == 'drain':
        return drain(root, request['expected_hash'])
    raise ValueError('Unknown action')




import subprocess

def merge_manifest(base,pilots):
    ids=[j['id'] for j in base['jobs']+pilots['jobs']]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate existing/pilot IDs')
    return {**base,'jobs':base['jobs']+pilots['jobs']}

def verify_assets(records):
    for row in records:
        path=Path(row['path'])
        if path.is_symlink() or not path.is_file():raise ValueError('Missing/unexpected asset '+str(path))
        h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1048576),b''):h.update(block)
        if h.hexdigest()!=row['sha256']:raise ValueError('Asset SHA mismatch '+str(path))

def launch_owned_worker(root,record_path,receipt):
    # Child waits for the durable identity record before executing host_worker.
    # Until then worker_status remains finished, so the existing supervisor stays idle.
    rfd,wfd=os.pipe()
    wrapper="import os,sys;f=int(sys.argv[1]);b=os.read(f,1);os.close(f);sys.exit(75) if b!=b'1' else None;os.execvp('python3',['python3','-u',sys.argv[2]])"
    try:
        with (root/'logs/worker.log').open('ab') as log:
            child=subprocess.Popen(['python3','-u','-c',wrapper,str(rfd),str(root/'scripts/host_worker.py')],cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,pass_fds=(rfd,))
        os.close(rfd);rfd=None
        proc=Path('/proc')/str(child.pid)
        ticks=(proc/'stat').read_text().rsplit(')',1)[1].split()[19]
        if proc.stat().st_uid!=os.getuid():raise RuntimeError('New worker UID mismatch')
        rec={'pid':child.pid,'start_ticks':ticks}
        atomic(root/'worker_pid.json',rec)
        receipt.update(phase='armed',worker=rec,armed_unix=time.time())
        atomic(record_path,receipt)
        os.write(wfd,b'1');os.close(wfd);wfd=None
        receipt.update(phase='activated',activated_unix=time.time())
        atomic(record_path,receipt)
        return receipt
    finally:
        if rfd is not None:os.close(rfd)
        if wfd is not None:os.close(wfd)

def activate_request(req):
    root=Path(req['root']);directory=root/'innovation_handoff';directory.mkdir(exist_ok=True)
    with (directory/'activation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        target=merge_manifest(req['base'],req['pilots']);target_hash=digest(target)
        receipt_path=directory/'partial_activation.json';receipt=read(receipt_path,{})
        snap=snapshot(root)
        if receipt and receipt.get('target_hash')!=target_hash:raise ValueError('Activation target changed')
        if snap['manifest_sha256'] not in (digest(req['base']),target_hash):raise ValueError('Manifest changed outside activation')
        if receipt.get('phase') in ('armed','activated'):
            owned=identity(receipt.get('worker'),str(root/'scripts/host_worker.py'))
            pilot_states={j['id']:snap['states'].get(j['id']) for j in req['pilots']['jobs']}
            if owned['state']=='owned_alive' or any(pilot_states.values()):
                return {'status':'already_activated','manifest':target,'receipt':receipt,'worker':owned}
            if owned['state']=='identity_mismatch':raise ValueError('Activation worker identity mismatch')
            # Child failed before any pilot submission: normal stopped-state gates
            # below decide whether a retry can safely launch another worker.
        if not snap['ready_for_deployment']:
            return {'status':'not_ready','worker':snap['worker'],'service':snap['service'],'worker_status':snap['worker_status'],'locks':snap['locks'],'port_listening':snap['port_listening']}
        if any(snap['states'].get(j['id'],{}).get('status')!='completed' for j in req['base']['jobs']):
            raise ValueError('Every retained old job must be completed')
        verify_assets(req['assets'])
        if req['action']=='prepare':
            if snap['manifest_sha256']!=target_hash:atomic(root/'jobs.json',target)
            receipt.update(phase='prepared',target_hash=target_hash,base_hash=digest(req['base']),prepared_unix=time.time(),verified_assets=len(req['assets']))
            atomic(receipt_path,receipt)
            return {'status':'prepared','manifest':target,'receipt':receipt}
        if req['action']!='activate' or snap['manifest_sha256']!=target_hash:raise ValueError('Activation requires prepared target manifest')
        # Recheck after file verification, since it can take several seconds.
        fresh=snapshot(root)
        if not fresh['ready_for_deployment'] or fresh['manifest_sha256']!=target_hash:return {'status':'not_ready'}
        result=launch_owned_worker(root,receipt_path,receipt)
        return {'status':'activated','manifest':target,'receipt':result}

"""Host-local handoff logic. The generated launcher supplies existing safe helpers."""
import math

def preceding_status(states, ids):
    failed=[j for j in ids if states.get(j,{}).get('status') in ('failed','failed_exhausted','blocked','invalid')]
    if failed:raise RuntimeError('direction jobs failed: '+','.join(failed))
    return all(states.get(j,{}).get('status')=='completed' for j in ids)

def verify_partial_audit(audit):
    assert audit['status']=='complete'
    assert audit['completed_forwards']==20 and audit['completed_blocks']==1000 and audit['compensated_calls']==1000
    assert audit['delta_resolved'] and audit['delta_mode']=='reference_origin'
    rotation=audit['rotation'];assert rotation['frequency_mask']==[0]*8+[1]*8 and rotation['selected_pair_indices']==list(range(8,16))
    assert math.isfinite(rotation['delta_physical_frames']) and rotation['delta_physical_frames']!=0
    layers=[layer for forward in audit['forward_summaries'] for layer in forward.get('layers',[])]
    assert len(layers)==1000 and all(x['finite'] and math.isfinite(x['correction_rms']) for x in layers)
    assert any(x['correction_rms']>0 for x in layers)
    return {'status':'passed','completed_blocks':audit['completed_blocks'],'compensated_calls':audit['compensated_calls'],
            'delta_derivation':audit['delta_derivation'],'rotation':rotation,'correction_rms_mean':sum(x['correction_rms'] for x in layers)/len(layers)}

def guard(req):
    root=Path(req['root']);directory=root/'innovation_handoff';directory.mkdir(exist_ok=True)
    status_path=directory/'partial_guard_status.json'
    with (directory/'partial_guard.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        atomic(directory/'partial_guard_pid.json',{'pid':os.getpid(),'start_ticks':Path('/proc',str(os.getpid()),'stat').read_text().rsplit(')',1)[1].split()[19],'uid':os.getuid()})
        expires=time.time()+24*3600
        ids=[j['id'] for j in req['base']['jobs'] if j['id'].startswith('promptfmt_')];assert len(ids)==5
        activated=False
        while time.time()<expires:
            states=read(root/'queue_state/state.json',{'jobs':{}})['jobs']
            if not activated:
                if not preceding_status(states,ids):
                    atomic(status_path,{'status':'waiting_prompt_five','unix':time.time(),'completed':sum(states.get(j,{}).get('status')=='completed' for j in ids),'total':5});time.sleep(60);continue
                prepared=activate_request({**req,'action':'prepare'})
                if prepared['status']=='not_ready':
                    atomic(status_path,{'status':'waiting_natural_exit','unix':time.time(),'snapshot':prepared});time.sleep(30);continue
                result=prepared if prepared['status']=='already_activated' else activate_request({**req,'action':'activate'})
                if result['status']=='not_ready':time.sleep(30);continue
                atomic(directory/'partial_pilots_active_manifest.json',result['manifest'])
                atomic(directory/'partial_pilots_activation.json',{k:v for k,v in result.items() if k!='manifest'})
                activated=True
            ids2=[j['id'] for j in req['pilots']['jobs']]
            failures=[j for j in ids2 if states.get(j,{}).get('status') in ('failed','failed_exhausted','blocked','invalid')]
            if failures:raise RuntimeError('partial pilots failed: '+','.join(failures))
            if all(states.get(j,{}).get('status')=='completed' for j in ids2):
                rows=[]
                for jid in ids2:
                    attempt=states[jid]['attempt_id'];audit=read(root/'audit/partial_temporal_rope'/f'{attempt}.json');row=verify_partial_audit(audit)
                    result=read(root/'queue_state/results'/f'{jid}.json');assert result['files']
                    for f in result['files']:
                        p=Path(f['path']);assert p.stat().st_size>0 and hashlib.sha256(p.read_bytes()).hexdigest()==f['sha256']
                    timing=read(root/'audit/timing'/f'{attempt}.json');assert len(timing['steps'])==20
                    rows.append({'id':jid,'audit':row,'sampler_wall_seconds':timing.get('sampler_wall_seconds'),'mean_sampling_step_seconds':timing.get('mean_sampling_step_seconds')})
                atomic(directory/'partial_pilots_verified.json',{'status':'passed','rows':rows,'unix':time.time()})
                atomic(status_path,{'status':'partial_pilots_complete_waiting_review','unix':time.time()});return
            atomic(status_path,{'status':'partial_pilots_running','unix':time.time(),'states':{j:states.get(j,{}).get('status','not_started') for j in ids2}});time.sleep(60)
        raise TimeoutError('bounded 24 hour partial handoff guard expired')


REQ=json.loads(Path(sys.argv[1]).read_text())
if __name__=="__main__":
 try:guard(REQ)
 except Exception as error:
  atomic(Path(REQ["root"])/"innovation_handoff/partial_guard_status.json",{"status":"failed","error":repr(error),"unix":time.time()})
  raise
