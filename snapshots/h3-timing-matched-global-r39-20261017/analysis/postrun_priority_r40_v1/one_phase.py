"""Explicit single call; original unique/Mac/remote locks and download."""
import argparse,hashlib,json,os,shlex,subprocess,sys,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
ORIGINAL=HERE.parent/'postrun'
PIN='01ddbe4ebc26f0f9743c15bbccdf770deb9d581c4b3c26aa913e53593cdc5fb1'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if not args.execute:print('Prepared only.');return
    if (HERE/'FAILURE.json').exists():raise ValueError('prior failure requires review')
    frozen=json.loads((HERE/'FREEZE.json').read_text())
    for rel,h in frozen['files'].items():
        if sha(HERE/rel)!=h:raise ValueError('supplement changed '+rel)
    if sha(ORIGINAL/'FREEZE.json')!=PIN:raise ValueError('original seal changed')
    sys.path.insert(0,str(ORIGINAL))
    import one_phase as original
    base=original.base
    remote=base.P['root_remote']+'/analysis/'+HERE.name
    subprocess.run(base.SSH+[base.HOST,'mkdir -p '+shlex.quote(remote)],check=True,timeout=30)
    paths=[str(HERE/r) for r in frozen['files']]+[str(HERE/'FREEZE.json')]
    subprocess.run(['rsync','-a','-e',shlex.join(base.SSH),*paths,base.HOST+':'+remote+'/'],check=True,timeout=60)
    def supplemented(args,timeout=900):
        if args not in (['status'],['finalize']):raise ValueError('unexpected phase '+repr(args))
        cmd=shlex.join(['env','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1',base.PYTHON,remote+'/remote_entry.py',*args])
        return subprocess.run(base.SSH+[base.HOST,cmd],capture_output=True,text=True,timeout=timeout)
    base.remote=supplemented
    result=original.execute_one()
    result.update(wrapper_sha256=sha(HERE/'FREEZE.json'),original_seal_sha256=PIN,R40_priority_before_and_after_remote_lock=True)
    (HERE/'LAST_ONE_PHASE.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
if __name__=='__main__':
    try:main()
    except Exception:
        (HERE/'FAILURE.json').write_text(json.dumps({'unix':time.time(),'traceback':traceback.format_exc(),'automatic_retry':False},indent=2)+'\n');raise
