import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
import argparse,json,hashlib
import av
import numpy as np
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args()
r={'av_version':av.__version__,'av_module':av.__file__,'libraries':av.library_versions,'source_sha256':hashlib.sha256(Path(a.source).read_bytes()).hexdigest(),'samples':{}}
all_yuv=hashlib.sha256();all_float=hashlib.sha256()
with av.open(a.source) as c:
 s=c.streams.video[0];s.thread_type='AUTO'
 for i,f in enumerate(c.decode(s)):
  y=f.to_ndarray(format='yuv420p');rgb=f.to_ndarray(format='gbrpf32le');all_yuv.update(np.ascontiguousarray(y));all_float.update(np.ascontiguousarray(rgb))
  if i in [0,55,83,140]:
   color=f.to_ndarray(format='rgb24')
   r['samples'][str(i)]={'yuv420p_shape':list(y.shape),'native_yuv_sha256':hashlib.sha256(np.ascontiguousarray(y)).hexdigest(),'rgb24_sha256':hashlib.sha256(np.ascontiguousarray(color)).hexdigest(),'gbrpf32le_sha256':hashlib.sha256(np.ascontiguousarray(rgb)).hexdigest(),'color_range':getattr(f,'color_range',None),'colorspace':getattr(f,'colorspace',None)}
r['full_native_yuv_sha256']=all_yuv.hexdigest();r['full_gbrpf32le_sha256']=all_float.hexdigest();r['frame_count']=i+1
print(json.dumps(r,indent=2))
