"""CPU-only materialization of actual recorded reference VAE input/output."""
import argparse,json,os,shutil,time
from pathlib import Path
from common import *

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--producer',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(2);require(not torch.cuda.is_initialized(),'CUDA must be uninitialized')
    root=Path(__file__).resolve().parents[1]; c=json.loads((root/'configs/contract.json').read_text());a.output.mkdir(parents=True,exist_ok=False)
    p=a.producer/'audit'/c['conditioning_name'];require(sha(p)==c['conditioning_sha256'],'actual conditioning file')
    data=json.loads(p.read_text());calls=[x for x in data['native_vae_calls'] if x['prepared_frames']['shape']==[158,768,1152,3]];require(len(calls)==1,'unique full video VAE call');call=calls[0]
    require(call==c['video_vae_call'],'VAE call identity')
    latent_path=a.producer/'audit'/call['latent']['tensor_file'];rgb_path=a.producer/'audit'/call['prepared_frames']['tensor_file']
    latent=load_bound_tensor(latent_path,call['latent']);frames=load_bound_tensor(rgb_path,call['prepared_frames'])
    require(frames.min()>=0 and frames.max()<=1,'prepared RGB range')
    shutil.copyfile(latent_path,a.output/'reference_latent.pt')
    products={}
    for name,idx,fps in [('prepared_158',range(158),24),('prepared_valid147',range(147),24),('prepared_original49',range(0,147,3),8)]:
        products[name]=write_frames(frames,idx,fps,a.output/(name+'.mp4'))
    record={'status':'complete','case':'fitness','contract_sha256':sha(root/'configs/contract.json'),'conditioning_file':str(p),'conditioning_sha256':sha(p),'actual_rgb_tensor_file':str(rgb_path),'actual_rgb_pt_sha256':sha(rgb_path),'actual_rgb_signature':call['prepared_frames'],'latent_origin':'native VAE.encode return, before model.process_latent_in; VAE.decode owns channel inverse normalization','latent':{'file':'reference_latent.pt','sha256':sha(a.output/'reference_latent.pt'),'signature':call['latent']},'products':products,'cuda_initialized':torch.cuda.is_initialized(),'completed_unix':time.time()}
    write(a.output/'PREPARED.json',record);print(json.dumps({'status':'complete','record':str(a.output/'PREPARED.json')}))
if __name__=='__main__':main()
