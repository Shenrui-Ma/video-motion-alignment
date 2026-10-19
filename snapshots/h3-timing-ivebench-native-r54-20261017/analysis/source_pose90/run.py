"""Extract source poses on .41 using the previously verified CPU implementation."""
from pathlib import Path
import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
AUX=Path('/data3/researcher/ComfyUI-H3/custom_nodes/comfyui_controlnet_aux')
LOCK=Path('/data3/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    return json.loads(Path(p).read_text())
def write(p,data):
    temp=p.with_name(p.name+'.tmp');temp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n');os.replace(temp,p)

def main(pair):
    protocol=read(HERE/'PROTOCOL.json')
    cases=[r for r in protocol['cases'] if pair=='all' or r['pair_id']==pair]
    assert cases
    assert sha(HERE/'pose_probe.py')==protocol['pose_script_sha256']
    for rel,digest in protocol['aux_files'].items():assert sha(AUX/rel)==digest,rel
    output=HERE/'outputs';output.mkdir(exist_ok=True)
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    with LOCK.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        start=time.monotonic()
        command=[sys.executable,str(HERE/'pose_probe.py'),'--aux-root',str(AUX),'--threads','4','--stride','1','--output-dir',str(output)]
        for row in cases:
            video=ROOT/'inputs'/row['video']
            assert sha(video)==row['video_sha256']
            assert sha(ROOT/'inputs'/row['provenance'])==row['provenance_sha256']
            command += ['--video',str(video)]
        env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1')
        with (HERE/'pose.log').open('a') as log:
            done=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900)
        if done.returncode:raise RuntimeError('CPU pose extraction failed; inspect pose.log')
        result=[]
        for row in cases:
            path=output/(Path(row['video']).stem+'.pose.json');data=read(path)
            assert data['video']['sha256']==row['video_sha256']
            assert [data['video'][k] for k in ['width','height','container_frame_count','fps']]==[1312,736,90,24]
            assert len(data['frames'])==90 and all(x['frame']==i and x['time_s']==i/24 for i,x in enumerate(data['frames']))
            assert data['provenance']['device']=='cpu' and data['provenance']['providers']==['CPUExecutionProvider']
            assert data['provenance']['script_sha256']==protocol['pose_script_sha256']
            result.append(dict(pair_id=row['pair_id'],pose_file=str(path),pose_sha256=sha(path),video_sha256=row['video_sha256'],valid_indices=list(range(row['effective_frames'])),padding_indices=list(range(row['effective_frames'],90)),statistics=data['statistics']))
        name='COMPLETE.json' if pair=='all' else 'COMPLETE_'+pair+'.json'
        write(HERE/name,dict(status='complete',protocol_sha256=sha(HERE/'PROTOCOL.json'),runtime_script_sha256=sha(Path(__file__)),invocation_seconds=time.monotonic()-start,cases=result))
        print(json.dumps(dict(status='complete',cases=len(result),seconds=time.monotonic()-start)),flush=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--pair',default='all',choices=['all','short_0210','short_0230','short_0263','short_0352','short_0370']);args=parser.parse_args();main(args.pair)
