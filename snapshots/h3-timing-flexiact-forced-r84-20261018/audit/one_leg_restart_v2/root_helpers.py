"""Explicit root execution only: exact peer admission, two runs, release, CPU gate."""
import argparse, contextlib, fcntl, json, os, signal, subprocess, sys, time, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import service
from r84_contract import read, require, registry, sha, SOURCES

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

def has_attempt_token(record, token):
    """Only inspect this own exact process's inherited root-attempt marker."""
    actual=service.current_identity(record['pid'])
    if actual is None:return False
    require(actual==record['identity'] and actual['uid']==os.getuid(),'attempt process identity changed')
    raw=(Path('/proc')/str(record['pid'])/'environ').read_bytes()
    marker=b'H3_ROOT_ATTEMPT_TOKEN='+token.encode()
    require(service.current_identity(record['pid'])==actual,'attempt identity changed during environment binding')
    return marker in raw.split(b'\0')


def recover_attempt_owner(token):
    """Original R84 registries lack tokens; bind the inherited environment before signalling."""
    owner=None;path=ROOT/'processes/service.json'
    if path.exists():
        candidate=read(path)
        if has_attempt_token(candidate,token):
            service.assert_owned(candidate);owner=candidate
    path=ROOT/'processes/supervisor.json'
    if path.exists():
        supervisor=read(path)
        if has_attempt_token(supervisor,token):
            actual=service.current_identity(supervisor['pid'])
            require(str(ROOT/'scripts/supervise_service.py') in actual['cmdline'],'wrong attempt supervisor command')
            os.kill(supervisor['pid'],signal.SIGTERM)
            if not service.wait_absent(supervisor['pid'],10):
                require(service.current_identity(supervisor['pid'])==supervisor['identity'],'attempt supervisor changed before kill')
                os.kill(supervisor['pid'],signal.SIGKILL)
                require(service.wait_absent(supervisor['pid'],10),'attempt supervisor remains live')
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

