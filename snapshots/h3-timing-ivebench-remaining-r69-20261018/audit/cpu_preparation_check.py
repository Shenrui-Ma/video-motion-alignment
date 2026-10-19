"""Remote CPU verification of frozen package, actual input media and host bindings."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from r69_contract import read,sha,registry
import preflight

def main():
    runtime=read(ROOT/'configs/runtime.json')
    assert ROOT==Path(runtime['remote_root'])
    result={'schema':'r69-cpu-preparation-v1','created_unix':time.time(),'preflight':preflight.check(ROOT),'gpu_inference_started':False}
    result['core']={name:sha(Path(runtime['core'])/name)==expected for name,expected in read(ROOT/'configs/parent_core_hashes.json').items()}
    assert all(result['core'].values())
    prior=read(ROOT/'configs/host41_provenance.json')['models']
    result['models']={}
    for name,item in prior.items():
        p=Path(runtime['models'])/name;st=p.stat()
        match=st.st_size==item['bytes'] and st.st_mtime_ns==item['mtime_ns'] and str(p.resolve())==item['realpath']
        result['models'][name]={'matches_prior_size_mtime_resolved_path':match,'prior_full_sha256':item['prior_full_sha256'],'full_hash_recomputed':False}
        assert match,name
    jobs,order=registry(ROOT)
    result['input_streams']={}
    for run in order[::2]:
        case=jobs[run]['case'];p=ROOT/'inputs'/case['video']
        cmd=['ffprobe','-v','error','-count_frames','-show_entries','stream=codec_type,width,height,nb_read_frames,avg_frame_rate','-of','json',str(p)]
        streams=json.loads(subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=60).stdout)['streams']
        assert len(streams)==1
        st=streams[0]
        assert st['codec_type']=='video' and st['width']==1312 and st['height']==736 and st['avg_frame_rate']=='24/1' and int(st['nb_read_frames'])==90
        assert sha(p)==case['video_sha256']
        result['input_streams'][case['source_id']]={'sha256':sha(p),'properties':st,'valid_frames':case['valid_frame_count'],'reference_audio_connected':False}
    import torch,av
    result['active_python_runtime']={'python':sys.version,'torch':torch.__version__,'av':av.__version__,'av_path':av.__file__,'cuda_initialized':torch.cuda.is_initialized()}
    assert not torch.cuda.is_initialized()
    sock=socket.socket();sock.settimeout(1)
    result['port8538_listening_at_check']=sock.connect_ex(('127.0.0.1',8538))==0;sock.close()
    result['live_root_admission_required']=True
    result['passed']=True
    (ROOT/'audit/CPU_PREPARATION_CHECK.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'sources':len(result['input_streams']),'cuda_initialized':False,'port8538_listening':result['port8538_listening_at_check']}))

if __name__=='__main__':main()
