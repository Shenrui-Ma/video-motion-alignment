"""Read-only CPU probe: stdout JSON only; no GPU, no files written remotely."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,importlib.metadata,json,sys
from pathlib import Path
import numpy as np
import torch
import av
import PIL
p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--run',required=True);p.add_argument('--core',required=True);p.add_argument('--full-input-hash',action='store_true');a=p.parse_args()
torch.set_num_threads(1)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def sig(x):return hashlib.sha256(x.contiguous().view(torch.uint8).numpy()).hexdigest()
r=Path(a.root);cpath=r/'audit'/f'{a.run}_conditioning.json';c=json.loads(cpath.read_text());pm=c['native_vae_calls'][1]['prepared_frames'];blob=r/'audit'/pm['tensor_file'];x=torch.load(blob,map_location='cpu',weights_only=True,mmap=True)
frames=[0,55,83,140];ys=torch.linspace(0,735,16).round().long();xs=torch.linspace(0,1311,16).round().long()
result={'run':a.run,'python':sys.version,'versions':{'torch':torch.__version__,'numpy':np.__version__,'pillow':PIL.__version__,'av':av.__version__,'av_libraries':av.library_versions,'module_files':{'av':av.__file__,'PIL':PIL.__file__,'torch':torch.__file__,'numpy':np.__file__},'PYTHONPATH':os.environ.get('PYTHONPATH')},'condition_json_sha256':sha(cpath),'actual_input_video_audit':c['input_video'],'actual_prepared_meta':pm,'sample_frames':frames,'sample_y':ys.tolist(),'sample_x':xs.tolist(),'prepared_samples':{},'decoded_samples':{},'source_files':{},'core_hashes':{}}
for folder in ['input','inputs']:
 f=r/folder/'05_real_megumi_v.mp4';result['source_files'][folder]={'exists':f.exists(),'bytes':f.stat().st_size if f.exists() else None,'sha256':sha(f) if f.exists() else None}
for relative in ['comfy_api/latest/_input_impl/video_types.py','comfy/utils.py','comfy/sd.py','comfy_extras/nodes_minimax_h3.py']:
 f=Path(a.core)/relative;result['core_hashes'][relative]=sha(f) if f.exists() else None
for i in frames:
 frame=x[i];result['prepared_samples'][str(i)]={'frame_sha256':sig(frame),'values':frame[ys[:,None],xs[None,:]].tolist()}
source=r/'input/05_real_megumi_v.mp4';fullhash=hashlib.sha256();index=0
with av.open(str(source)) as container:
 stream=container.streams.video[0];stream.thread_type='AUTO';result['stream']={'width':stream.width,'height':stream.height,'codec':stream.codec_context.name,'format':stream.codec_context.format.name,'time_base':str(stream.time_base),'average_rate':str(stream.average_rate),'frames':stream.frames}
 for frame in container.decode(stream):
  fmt='rgb24' if frame.format.name in ('yuvj420p','yuvj422p','yuvj444p','rgb24','rgba','pal8') else 'gbrpf32le'
  if index in frames or a.full_input_hash:
   array=frame.to_ndarray(format=fmt);t=torch.from_numpy(array)
   if fmt=='rgb24':t=t.float()/255.
   if a.full_input_hash:fullhash.update(t.contiguous().view(torch.uint8).numpy())
   if index in frames:result['decoded_samples'][str(index)]={'pts':frame.pts,'time':frame.time,'decoded_format':frame.format.name,'conversion_format':fmt,'frame_sha256':sig(t),'values':t[ys[:,None],xs[None,:]].tolist(),'colorspace':getattr(frame,'colorspace',None),'color_range':getattr(frame,'color_range',None)}
  index+=1
result['decoded_frame_count']=index
if a.full_input_hash:
 result['direct_decode_raw_sha256']=fullhash.hexdigest();result['direct_decode_reproduces_actual_input']=fullhash.hexdigest()==c['input_video']['sha256']
result['CUDA_initialized']=torch.cuda.is_initialized()
if result['CUDA_initialized']:raise RuntimeError('CPU-only invariant failed')
print(json.dumps(result,allow_nan=False))
