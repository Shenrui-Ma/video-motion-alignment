"""CPU-only replay of actual Comfy input decode; does not modify producer or gate."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['OMP_NUM_THREADS']='2';os.environ['MKL_NUM_THREADS']='2'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def sig(a):return hashlib.sha256(a.tobytes(order='C')).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--runtime-root',required=True);p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
r=Path(a.runtime_root);runtime=json.loads((r/'configs/runtime.json').read_text());sys.path[:0]=[str(r/'scripts'),runtime['dependencies'],runtime['core']]
from compatibility_bootstrap import install,install_video_compat
install();install_video_compat()
import torch,comfy.cli_args
comfy.cli_args.args.cpu=True;comfy.cli_args.args.disable_xformers=True;torch.set_num_threads(2)
from comfy_api.latest._input_impl import video_types
import av,numpy as np
assert not torch.cuda.is_initialized()
tick=time.monotonic();video=video_types.VideoFromFile(str(Path(a.input))).get_components();frames=video.images
assert frames.device.type=='cpu' and not torch.cuda.is_initialized()
record={'input_file':str(Path(a.input)),'input_file_sha256':sha(a.input),'input_video':{'shape':list(frames.shape),'dtype':str(frames.dtype)},'frame_rate':str(video.frame_rate),'av_version':av.__version__,'library_versions':av.library_versions,'torch_version':torch.__version__,'core_video_types':{'path':video_types.__file__,'sha256':sha(video_types.__file__)},'compatibility_sha256':sha(r/'scripts/compatibility_bootstrap.py'),'frames':[],'CUDA_initialized':torch.cuda.is_initialized()}
whole=hashlib.sha256();decoded=[]
with av.open(str(a.input)) as container:
 stream=container.streams.video[0]
 for f in container.decode(stream):
  # Lossless YUV420 samples are compared with original preparation records.
  yuv=f.to_ndarray(format='yuv420p');rgb=f.to_ndarray(format='rgb24')
  decoded.append({'pts':f.pts,'time_base':str(f.time_base),'pts_s':float(f.pts*f.time_base),'format':f.format.name,'yuv420p_md5':hashlib.md5(yuv.tobytes()).hexdigest(),'rgb24_sha256':sig(rgb),'colorspace':f.colorspace,'color_range':f.color_range})
for i,t in enumerate(frames):
 array=t.contiguous().numpy();whole.update(array.tobytes());u8=np.rint(np.clip(array,0,1)*255).astype('uint8');u16=np.rint(np.clip(array,0,1)*65535).astype('uint16')
 # Fixed grid covers all frames/channels; exact sampled differences are kept separately from full-frame hash equality.
 sample=array[::16,::16,:]
 record['frames'].append({'index':i,'float_sha256':sig(array),'rounded_rgb8_sha256':sig(u8),'rounded_rgb16_sha256':sig(u16),'min':float(array.min()),'max':float(array.max()),'sample_shape':list(sample.shape),'sample_values':sample.reshape(-1).tolist(),**decoded[i]})
record['input_video']['sha256']=whole.hexdigest();record['wall_seconds']=time.monotonic()-tick
out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
with out.open('x') as f:json.dump(record,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in record.items() if k!='frames'},indent=2))
