"""Root-invoked CPU supervisor for one explicitly admitted recovery decode."""
import argparse,json,os,shutil,sys
from pathlib import Path
import common as c

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-name',required=True);p.add_argument('--admission',type=Path,required=True);p.add_argument('--root-admitted',action='store_true');a=p.parse_args()
    c.require(a.root_admitted and c.PRODUCER==c.REMOTE,'root-admitted exact remote recovery required')
    c.require(a.run_name and all(x.isalnum() or x in '_-' for x in a.run_name),'invalid recovery run name')
    c.original_request();t=c.frozen_runtime();root_admission=c.read(a.admission)
    c.require(root_admission['root_approved'] is True,'root recovery admission missing')
    directory=c.HERE/'runs'/a.run_name;directory.mkdir(parents=True,exist_ok=False)
    shutil.copy2(c.ARCHIVE/c.REQUEST_REL,directory/'request.json')
    parent=t.identity(os.getpid());c.require(parent is not None,'CPU supervisor identity unavailable')
    c.write_new(directory/'SUPERVISOR.json',{'schema':'r53-recovery-supervisor-v1','identity':parent,'root_admission':root_admission,'root_admission_sha256':c.sha(a.admission),'original_request_sha256':c.REQUEST_SHA})
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',TMPDIR=str(c.HERE/'temp'),TMP=str(c.HERE/'temp'),TEMP=str(c.HERE/'temp'));(c.HERE/'temp').mkdir(exist_ok=True)
    command=[sys.executable,str(c.HERE/'decode_recovery.py'),'--directory',str(directory),'--parent-json',json.dumps(parent),'--admission',str(a.admission.resolve())]
    child=t.run_child(command,env,directory,'recovery_decoder',1200,parent)
    c.require(not t.alive(child['process']),'recovery decoder remains alive')
    from gpu_release_gate import wait_after_child
    import decode_live_child as live
    release=wait_after_child(root_admission['gpu_uuid'],child,live.assert_idle_gpu,t.identity)
    c.write_new(directory/'DECODER_RELEASED.json',{'status':'released','child':child,'release':release,'RECOVERY_DECODE_sha256':c.sha(directory/'RECOVERY_DECODE.json'),'original_run_completed':False})
    print(json.dumps({'directory':str(directory),'status':'recovered_native019_decoded_and_GPU_released','next':'CPU pose and frozen signed controller replay'}))
if __name__=='__main__':main()
