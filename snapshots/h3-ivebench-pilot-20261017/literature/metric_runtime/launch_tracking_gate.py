"""Record a stable pre-CUDA PID; root supplies the identical ready record as go."""
import argparse,hashlib,json,os,runpy,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def identity():
    p=Path('/proc')/str(os.getpid())
    return {'uid':p.stat().st_uid,'start_ticks':p.joinpath('stat').read_text().rsplit(')',1)[1].split()[19],'cmdline_sha256':sha(p/'cmdline')}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('runner_arguments',nargs=argparse.REMAINDER);a=p.parse_args()
    arguments=a.runner_arguments[1:] if a.runner_arguments[:1]==['--'] else a.runner_arguments
    bindings=[ROOT/'run_tracks.py',ROOT/'ive_mf_adapter.py']
    for flag in ['--input-manifest','--selection']:
        if flag not in arguments:raise ValueError('required runner argument: '+flag)
        bindings.append(Path(arguments[arguments.index(flag)+1]))
    control=Path(a.control);control.mkdir(parents=True,exist_ok=False)
    record={'pid':os.getpid(),'identity':identity(),'CUDA_started':False,'gpu_uuid':os.environ.get('CUDA_VISIBLE_DEVICES'),
        'arguments':arguments,'bindings':[{'file':str(f.resolve()),'sha256':sha(f)} for f in bindings]}
    tmp=control/'ready.tmp';tmp.write_text(json.dumps(record,indent=2)+'\n');tmp.replace(control/'ready.json')
    start=time.monotonic();go=control/'go.json'
    while not go.exists():
        if time.monotonic()-start>600:raise TimeoutError('root admission not completed within600 seconds')
        time.sleep(.1)
    if json.loads(go.read_text())!=record or identity()!=record['identity']:raise ValueError('root gate/process identity differs')
    if any(sha(f['file'])!=f['sha256'] for f in record['bindings']):raise ValueError('admitted code/input changed')
    sys.argv=[str(ROOT/'run_tracks.py')]+arguments
    runpy.run_path(str(ROOT/'run_tracks.py'),run_name='__main__')
