import json,hashlib,os
from pathlib import Path
import torch
torch.set_num_threads(1)
rows=[{'case': 'long_0059', 'method': 'native', 'host_key': '9', 'source_file': '/home/research-user/h3_runs/timing_ive_handkerchief_full_context_r126_20261020/audit/tensor_blobs/090756dca6b1ff75fcd0c17fcf78a4f166676f0d26f8f832adde9ec951b68f24.pt', 'source_file_sha256': 'e11885c4d9e91c95f9942dbaae33ba85ff04d960bae691fcbabdd72f93ece7c0', 'source_tensor_sha256': '4f2eb8a7892d4c5a7f827bed3693150bf4f4340ed731b408c398c244d67f8323', 'capture_dir': '/home/research-user/h3_runs/timing_ive_handkerchief_full_context_r126_20261020/audit/x0/r126_long_0059_seed2026101701_native', 'manifest_sha256': 'de8e5d935980e17f8d421f281f328dacf691e4084cc0e0dc6823cdbdfbaea02b', 'shape': [1, 24, 47, 46, 82], 'valid_frames': 144, 'prompt_sha256': '9a80385c1d187e238bcdab38247d32a9cc40b28327c7b52c7b833a8aa183aee6', 'events': [{'id': 'hand_approaches_eye', 'source_interval': [15, 17], 'native_interval': [15, 17], 'global_weak_interval': [15, 17]}, {'id': 'eye_wiping_contact', 'source_interval': [28, 31], 'native_interval': [28, 31], 'global_weak_interval': [28, 31]}, {'id': 'hand_leaves_face', 'source_interval': [95, 98], 'native_interval': [111, 114], 'global_weak_interval': [96, 99]}], 'annotation_sha256': 'be86e75922e8e672952450961717c4003a46502eb4676935ccd6e8b1fda1f134'}]
out=[]
def sig(t):
 return {'shape':list(t.shape),'dtype':str(t.dtype),'finite':bool(torch.isfinite(t).all()),'sha256':hashlib.sha256(t.contiguous().numpy().tobytes()).hexdigest()}
for r in rows:
 d=Path(r['capture_dir']); m=json.loads((d/'manifest.json').read_text()); x=torch.load(d/'x0_step009.pt',map_location='cpu',weights_only=True)
 pair=('r123_short_0358' if r['case']=='short_0358' else 'r126_long_0059')+'_seed2026101701_noise.pt'; npath=d.parents[1]/pair
 row={'case':r['case'],'method':r['method'],'manifest_sha256':hashlib.sha256((d/'manifest.json').read_bytes()).hexdigest(),'manifest_keys':list(m),'callback_count':m.get('callback_count'),'capture_count':len(m.get('captures',[])),'all_20_pt_exist':all((d/f'x0_step{i:03d}.pt').is_file() for i in range(20)),'x0_step009_keys':list(x),'video':sig(x['video']),'audio':sig(x['audio']),'metadata':x.get('metadata',{}),'noise_path':str(npath),'noise_exists':npath.is_file()}
 if npath.is_file():
  n=torch.load(npath,map_location='cpu',weights_only=True); row['noise_keys']=list(n); row['noise_signature']=n.get('signature'); row['noise_streams']=[sig(t) for t in n['tensors']]
 out.append(row)
print(json.dumps({'device':'cpu','cuda_initialized':torch.cuda.is_initialized(),'rows':out},ensure_ascii=False))
