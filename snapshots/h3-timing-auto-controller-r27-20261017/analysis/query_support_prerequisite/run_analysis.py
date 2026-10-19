import os
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from pathlib import Path
import json,hashlib,fcntl,time
import support

HERE=Path(__file__).resolve().parent

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,msg):
    if not v:raise ValueError(msg)

def main():
    freeze=read(HERE/'FREEZE.json')
    for rel,h in freeze['files'].items():require(sha(HERE/rel)==h,'frozen file changed '+rel)
    protocol=read(HERE/'PROTOCOL.json');binding=read(HERE/'BINDING.json');archive=Path(binding['archive'])
    out=HERE/'results';require(not out.exists(),'immutable results already exist')
    with open(protocol['cpu_lock'],'a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);start=time.monotonic()
        for rel,entry in binding['inputs'].items():require(sha(archive/rel)==entry['sha256'],'input hash '+rel)
        gate=read(archive/'RUN_GATE.json');require(gate['passed'] is True and gate['run_id']==binding['run_id'],'run gate')
        source=read(archive/binding['source'])
        frames=source['frames'];require(len(frames)==141,'source frames')
        cases=[]
        for entry in binding['targets']:
            target=read(archive/entry['pose'])
            for pose in [source,target]:
                v=pose['video'];require((v['width'],v['height'],v['container_frame_count'],v['fps'])==(1312,736,141,24),'geometry')
                require(pose['joint_order']==source['joint_order'] and len(pose['frames'])==141,'pose schema')
            for key in ['detector_sha256','pose_sha256','detector_code_sha256','pose_code_sha256']:
                require(target['provenance'][key]==source['provenance'][key],'pose implementation changed '+key)
            cases.append({'index':entry['index'],'pose_sha256':entry['pose_sha256'],'endpoint_sha256':entry['endpoint_sha256'],**support.evaluate(source,target)})
        for rel,entry in binding['inputs'].items():require(sha(archive/rel)==entry['sha256'],'input changed during analysis '+rel)
        result={'schema':'r27-query-support-prerequisite-result-v1','protocol_sha256':sha(HERE/'PROTOCOL.json'),
                'binding_sha256':sha(HERE/'BINDING.json'),'freeze_sha256':sha(HERE/'FREEZE.json'),'cases':cases,
                'cpu_wall_seconds':time.monotonic()-start,'completed_unix':time.time(),'no_gpu_or_model':True,'no_masked_attention_implementation':True}
        out.mkdir();(out/'RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        (out/'COMPLETE.json').write_text(json.dumps({'status':'complete','results_sha256':sha(out/'RESULTS.json')},indent=2)+'\n')
        print(json.dumps({'status':'complete','wall':result['cpu_wall_seconds'],'cases':[{'index':x['index'],'valid_frames':x['valid_frame_count'],'bins':[{'bin':b['bin'],'status':b['status'],'valid_frames':b['valid_frames']} for b in x['bins']]} for x in cases]}))
if __name__=='__main__':main()
