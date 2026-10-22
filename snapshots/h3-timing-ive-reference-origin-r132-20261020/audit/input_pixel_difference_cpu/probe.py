import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import json,hashlib,sys
from pathlib import Path
import av,numpy as np,torch,PIL
from PIL import Image
torch.set_num_threads(1)
root=Path(sys.argv[1]); name=sys.argv[2]
audit=root/'audit'; d=json.loads((audit/name).read_text())
p=root/'inputs/long_0039_video.mp4'
prep=d['native_vae_calls'][0]['prepared_frames']; q=d['qwen_presentation'][0]['actual_sampled_frames']
x=torch.load(audit/prep['tensor_file'],map_location='cpu',weights_only=True,mmap=True)
qv=torch.load(audit/q['tensor_file'],map_location='cpu',weights_only=True,mmap=True)
frame_sz=int(np.prod(x.shape[1:])); idx=np.linspace(0,frame_sz-1,8192,dtype=np.int64)
chosen=[0,12,24,36,48,60,72,84,96,105,106]
raw=[]; saved=[]; resized=[]; pts=[]; fmt=[]
h=hashlib.sha256(); emax=0.;esum=0.;en=0;bad=0
c=av.open(str(p)); st=c.streams.video[0]; st.thread_type='AUTO'
for i,f in enumerate(c.decode(st)):
 a=f.to_ndarray(format='gbrpf32le'); a=np.ascontiguousarray(a)
 h.update(a.tobytes());pts.append([f.pts,str(f.time_base)]);fmt.append(f.format.name)
 b=np.array(Image.fromarray(np.clip(255.*a,0,255).astype(np.uint8)).resize((x.shape[2],x.shape[1]),resample=Image.Resampling.LANCZOS)).astype(np.float32)/255.
 z=x[i].numpy();diff=b.astype(np.float64)-z
 emax=max(emax,float(np.max(np.abs(diff))));esum+=float(np.sum(diff*diff));en+=diff.size;bad+=int(np.count_nonzero(diff))
 if i in chosen:
  raw.append(a.reshape(-1)[idx].tolist());saved.append(z.reshape(-1)[idx].tolist());resized.append(b.reshape(-1)[idx].tolist())
result={'source_file_sha':hashlib.sha256(p.read_bytes()).hexdigest(),'environment':{'av':av.__version__,'av_libraries':av.library_versions,'torch':torch.__version__,'numpy':np.__version__,'PIL':PIL.__version__},'frames':i+1,'shape':list(x.shape),'pts':pts,'formats':sorted(set(fmt)),'decoded_sha':h.hexdigest(),'actual_input_sha':d['input_video']['sha256'],'decode_matches_recorded_input':h.hexdigest()==d['input_video']['sha256'],'actual_prepared_sha':prep['sha256'],'recreated_preparation_vs_actual':{'max':emax,'rms':(esum/en)**.5,'nonzero_ratio':bad/en},'sample_frames':chosen,'sample_flat_indices':idx.tolist(),'raw_samples':raw,'actual_prepared_samples':saved,'recreated_prepared_samples':resized,'actual_qwen_samples':[qv[j].reshape(-1)[idx].numpy().tolist() for j in range(qv.shape[0])],'qwen_source_indices':list(range(0,107,12)),'value_range_sample':[float(np.min(raw)),float(np.max(raw))],'core_hashes':{}}
for rel in ['comfy_api/latest/_input_impl/video_types.py','comfy_extras/nodes_minimax_h3.py','comfy/utils.py']:
 core=Path(json.loads((root/'configs/runtime.json').read_text())['core']);result['core_hashes'][rel]=hashlib.sha256((core/rel).read_bytes()).hexdigest()
print(json.dumps(result))
