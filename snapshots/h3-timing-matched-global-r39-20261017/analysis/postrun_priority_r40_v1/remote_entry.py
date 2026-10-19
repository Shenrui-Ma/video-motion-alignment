"""Only status/finalize through the original sealed R39 consumer."""
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ORIGINAL=HERE.parent/'postrun'
PIN='01ddbe4ebc26f0f9743c15bbccdf770deb9d581c4b3c26aa913e53593cdc5fb1'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    if sys.argv[1:] not in (['status'],['finalize']):
        raise ValueError('supplement authorizes only status/finalize')
    for rel,h in json.loads((HERE/'FREEZE.json').read_text())['files'].items():
        if sha(HERE/rel)!=h:raise ValueError('supplement changed '+rel)
    if sha(ORIGINAL/'FREEZE.json')!=PIN:raise ValueError('original seal changed')
    sys.path.insert(0,str(ORIGINAL))
    import remote_consume
    from priority import install
    install(remote_consume)
    # Original locked() invokes this global before and after flock.
    # Original main/seal/data validation, metrics and delivery remain intact.
    remote_consume.main()
if __name__=='__main__':
    try:main()
    except BlockingIOError:
        print('CPU_LOCK_BUSY_OR_ONLINE_PRIORITY');raise SystemExit(75)
