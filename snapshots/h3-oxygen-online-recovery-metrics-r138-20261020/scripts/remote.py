"""Reuse SSH reads; additionally permit exact inherited observations and compact."""
from common import *
import subprocess
_pin=read(ROOT/'configs/SHARED_HELPERS.json')['remote.py'];require(sha(_pin['file'])==_pin['sha256'],'shared transport changed')
exec(compile(Path(_pin['file']).read_text(),_pin['file'],'exec'),globals())

def fetch(path,destination,timeout=240):
    p=Path(path);c=config()
    if p!=Path(c['compact_remote_root'])/'ACTUAL_AUDIT_COMPACT.json':safe_path(p)
    require('..' not in p.parts,'path traversal')
    try:subprocess.run(['rsync','-az','-e','ssh -o BatchMode=yes -o ConnectTimeout=15',c['host']+':'+str(p),str(destination)],check=True,timeout=timeout)
    except subprocess.TimeoutExpired as e:raise TimeoutError('bounded transfer timed out') from e
    except subprocess.CalledProcessError as e:
        if e.returncode in (12,30,35,255):raise ConnectionError('transfer unavailable: '+str(e.returncode)) from e
        raise
