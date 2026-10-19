"""Record successful child exit and actual strict GPU release after supervisor bookkeeping failure."""
import argparse,json,os
from pathlib import Path
import common as c
from gpu_release_gate import wait_after_child

def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);a=p.parse_args()
    d=a.directory.resolve();c.require(d.is_relative_to(c.HERE/'runs') and c.PRODUCER==c.REMOTE,'recovery remote path required');os.environ['CUDA_VISIBLE_DEVICES']=''
    t=c.frozen_runtime();live=c.load_live();ready=c.read(d/'decoder_ready.json');record=c.read(d/'recovery_decoder.process.json');exited=c.read(d/'recovery_decoder.exit.json');decoded=c.read(d/'RECOVERY_DECODE.json');parent=c.read(d/'SUPERVISOR.json')
    entry={k:record[k] for k in ('pid','uid','start_ticks','cmdline_sha256')}
    c.require(entry==ready['identity'] and entry['uid']==os.getuid() and exited['pid']==entry['pid'] and exited['returncode']==0 and exited['identity_absent'] is True,'decoder exit identity differs')
    c.require(decoded['status']=='decoded_archived_Native019' and decoded['original_run_completed'] is False and c.sha(decoded['video_file'])==decoded['video_sha256'] and c.sha(decoded['decode_file'])==decoded['decode_sha256'],'recovered decode evidence differs')
    child={'process':entry,'wall_seconds':exited['wall_seconds'],'returncode':0}
    release=wait_after_child(ready['gpu_uuid'],child,live.assert_idle_gpu,t.identity)
    result={'status':'released','child':child,'release':release,'RECOVERY_DECODE_sha256':c.sha(d/'RECOVERY_DECODE.json'),'original_run_completed':False,'administrative_recovery':{'reason':'Original CPU supervisor failed importing its absent gpu_release_gate after successful decoder exit; this standalone finalizer checks actual recorded exit and current GPU idle.','supervisor_identity':parent['identity'],'child_exit_sha256':c.sha(d/'recovery_decoder.exit.json'),'child_process_sha256':c.sha(d/'recovery_decoder.process.json'),'finalizer_sha256':c.sha(__file__),'release_helper_sha256':c.sha(c.HERE/'gpu_release_gate.py')}}
    c.write_new(d/'DECODER_RELEASED.json',result);print(json.dumps(result))
if __name__=='__main__':main()
