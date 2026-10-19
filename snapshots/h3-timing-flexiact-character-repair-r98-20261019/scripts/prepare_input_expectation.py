"""Pre-generation CPU replay of the real Comfy video decoder; no model or CUDA."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['OMP_NUM_THREADS']='2';os.environ['MKL_NUM_THREADS']='2'
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from r98_contract import read,sha,require,definitions

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 runtime=read(ROOT/'configs/runtime.json');sys.path[:0]=[runtime['dependencies'],runtime['core']]
 from compatibility_bootstrap import install,install_video_compat
 install();install_video_compat()
 import torch,comfy.cli_args
 comfy.cli_args.args.cpu=True;comfy.cli_args.args.disable_xformers=True;torch.set_num_threads(2)
 from comfy_api.latest._input_impl import video_types
 import av
 require(not torch.cuda.is_initialized(),'CUDA initialized during CPU replay')
 source=definitions()[0]['source'];path=ROOT/'inputs'/source['video'];require(sha(path)==source['video_sha256'],'source bytes changed')
 tick=time.monotonic();components=video_types.VideoFromFile(str(path)).get_components();frames=components.images
 require(frames.device.type=='cpu' and list(frames.shape)==[158,768,1152,3] and str(components.frame_rate)=='24','decoded source shape/fps differs')
 digest=hashlib.sha256();per=[]
 for f in frames:
  b=f.contiguous().numpy().tobytes();digest.update(b);per.append(hashlib.sha256(b).hexdigest())
 require(all(per[i]==per[i//3*3] for i in range(147)) and all(per[i]==per[146] for i in range(147,158)),'repeat3/last-frame padding differs')
 require(not torch.cuda.is_initialized(),'CUDA initialized during CPU replay')
 v={'schema':'r98-host9-input-decode-expectation-v1','source_sha256':sha(path),'input_video':{'shape':list(frames.shape),'dtype':str(frames.dtype),'sha256':digest.hexdigest()},'frame_sha256':per,'valid_frames':147,'fps':24,'torch_version':torch.__version__,'av_version':av.__version__,'decoder_sha256':sha(video_types.__file__),'compatibility_sha256':sha(ROOT/'scripts/compatibility_bootstrap.py'),'GPU_started':False,'wall_seconds':time.monotonic()-tick,'created_unix':time.time()}
 with a.output.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
 print(json.dumps({k:v[k] for k in ('schema','input_video','torch_version','av_version','GPU_started','wall_seconds')},indent=2))
if __name__=='__main__':main()
