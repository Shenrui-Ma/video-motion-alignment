"""Optional root-admitted model-free BF16 operator gate; never auto-launched."""
import argparse,gc,hashlib,json,sys,time,importlib.util
from pathlib import Path
import torch
import torch.nn.functional as F
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'extensions'),str(ROOT/'tests')]
from H3ReverseReferenceRouter import core
from test_reverse import plan,explicit

def attention_pytorch(q,k,v,heads,**kwargs):return F.scaled_dot_product_attention(q,k,v).transpose(1,2).reshape(q.shape[0],q.shape[-2],-1)
def run(actual=False):
 p=plan() if not actual else {'seq_len':87592,'reference_video_segment':[7910,47516],'target_video_segment':[47986,87592],'latent_interval_half_open':[14,20],'frame_rows':943,'key_interval_half_open':[21112,26770],'query_interval_half_open':[61188,66846],'segments':[(0,6960,'text'),(6960,7910,'ref_img'),(7910,47516,'ref_img'),(47516,47986,'audio'),(47986,87592,'video')]}
 g=torch.Generator(device='cuda').manual_seed(2026101717);q,k,v=[torch.randn((1,56,p['seq_len'],128),dtype=torch.bfloat16,device='cuda',generator=g) for _ in range(3)];rng=torch.cuda.get_rng_state().clone();cases=[]
 native=attention_pytorch(q,k,v,56,skip_reshape=True);old=core.flash_attention_lse(q,k,v)[0].transpose(1,2).reshape(1,p['seq_len'],-1)
 assert torch.equal(native,old),'actual official native SDPA differs from archived R3 explicit Flash pathway'
 del native,old
 for mode in ('reverse_block','reverse_same'):
  audit={};start=time.monotonic()
  with torch.inference_mode():out=core.reverse_attention(attention_pytorch,q,k,v,56,p,mode=mode,first_audit=audit,native_kwargs={'skip_reshape':True})
  if not actual:
   oracle,_=explicit(q.float(),k.float(),v.float(),p,mode);err=out.float()-oracle;rel=float(err.square().mean().sqrt()/oracle.square().mean().sqrt());scaled=float(err.abs().max()/oracle.abs().max());assert rel<=.025 and scaled<=.035
   audit['dense_oracle']={'relative_rms':rel,'maxabs_scaled':scaled}
  assert bool(torch.isfinite(out).all()) and all(audit[key] for key in ('input_values_bitwise','nonselected_rows_bitwise','target_video_bitwise','target_audio_bitwise'))
  assert torch.equal(rng,torch.cuda.get_rng_state());torch.cuda.synchronize();cases.append({'mode':mode,'actual_shape':actual,'seconds':time.monotonic()-start,'audit':audit});del out
 del q,k,v;gc.collect();torch.cuda.empty_cache();return cases
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--comfy-root',type=Path,default=Path('/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI'));a=p.parse_args()
 sys.path.insert(0,str(a.comfy_root));sys.argv=['r25_gpu_kernel','--use-pytorch-cross-attention','--disable-dynamic-vram']
 import comfy.options
 comfy.options.enable_args_parsing()
 spec=importlib.util.spec_from_file_location('r25_gpu_existing_compat',ROOT/'scripts/compatibility_bootstrap.py');compat=importlib.util.module_from_spec(spec);spec.loader.exec_module(compat);compat.install();compat.install_video_compat()
 import comfy.ldm.minimax.model as h3
 attention_pytorch=h3.optimized_attention
 assert attention_pytorch.__name__=='attention_pytorch'
 if a.output.exists():raise FileExistsError(a.output)
 if not torch.cuda.is_available() or torch.cuda.device_count()!=1:raise RuntimeError('root must admit exactly one idle GPU via CUDA_VISIBLE_DEVICES')
 torch.set_num_threads(1);cases=run(False)+run(True);j={'passed':True,'NFE':0,'model_weights_loaded':False,'actual_Comfy_native_matches_archived_Flash':True,'core_sha256':hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest(),'cases':cases,'allocated_end':torch.cuda.memory_allocated(),'reserved_end':torch.cuda.memory_reserved()};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j))
