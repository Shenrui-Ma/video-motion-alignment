"""Race-safe signalling through an unreaped direct child on pre-pidfd Linux."""
import json,os,signal,time
from pathlib import Path
KEYS=('pid','uid','start_ticks','cmdline_sha256')
PROTOCOL='r149-direct-child-stop-v1'

def same(a,b):return a is not None and all(str(a.get(k))==str(b.get(k)) for k in KEYS)

def direct_child_signal(expected,sig,*,lookup,waitid=os.waitid,kill=os.kill):
    """No wait/reap occurs between kernel child check and signal; PID stays reserved."""
    if expected['uid']!=os.getuid() or not same(lookup(expected['pid']),expected):return False
    try:
        state=waitid(os.P_PID,expected['pid'],os.WEXITED|os.WNOHANG|os.WNOWAIT)
    except ChildProcessError:return False
    if state is not None:return False  # Exited child remains unreaped for its owner.
    if not same(lookup(expected['pid']),expected):return False
    try:kill(expected['pid'],sig)
    except ProcessLookupError:return False
    return True

def channel(root,expected,*,lookup):
    root=Path(root);service=json.loads((root/'processes/service.json').read_text())
    if service['pid']!=expected['pid'] or not same(lookup(expected['pid']),expected):raise ValueError('service generation unavailable')
    # The persistent original parent record binds a kernel parent, not a PID/name search.
    parent=json.loads((root/'processes/supervisor.json').read_text())
    if parent.get('stop_protocol')!=PROTOCOL or parent.get('service_record')!=service:raise ValueError('direct-child stop protocol unavailable')
    current=lookup(parent['pid']);old=parent['identity']
    if current is None or any(str(current[k])!=str(old[k]) for k in ('uid','start_ticks','cmdline')):raise ValueError('service parent generation changed')
    stat=Path('/proc',str(expected['pid']),'stat').read_text().rsplit(') ',1)[1].split()
    if int(stat[1])!=parent['pid'] or current['uid']!=expected['uid']:raise ValueError('registered parent is not service parent')
    return parent

def request_stop(root,expected,sig,*,lookup):
    channel(root,expected,lookup=lookup)
    if sig not in (signal.SIGTERM,signal.SIGKILL):raise ValueError('unsupported termination signal')
    p=Path(root)/'processes'/('parent_stop_'+str(expected['pid'])+'_'+str(expected['start_ticks'])+'.json')
    tmp=p.with_name(p.name+'.'+str(os.getpid())+'.tmp')
    tmp.write_text(json.dumps({'schema':PROTOCOL,'target':expected,'signal':int(sig),'requested_unix':time.time()})+'\n')
    os.replace(tmp,p)
    return True

def consume(root,expected,*,lookup):
    p=Path(root)/'processes'/('parent_stop_'+str(expected['pid'])+'_'+str(expected['start_ticks'])+'.json')
    if not p.exists():return False
    request=json.loads(p.read_text())
    if request.get('schema')!=PROTOCOL or not same(request.get('target'),expected):raise ValueError('stop request targets a different generation')
    sig=request['signal']
    if sig not in (signal.SIGTERM,signal.SIGKILL):raise ValueError('unsupported termination signal')
    return direct_child_signal(expected,sig,lookup=lookup)
