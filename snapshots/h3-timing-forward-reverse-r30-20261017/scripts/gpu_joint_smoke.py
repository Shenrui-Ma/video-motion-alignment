"""Root-admitted model-free four-mode gate. Never called by launch or CPU checks."""
import argparse,gc,hashlib,importlib.util,json,sys,time
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'extensions'),str(ROOT/'tests')]
from H3ForwardReverseRouter import core
from H3ForwardReverseRouter.base_router import route_attention
from H3ForwardReverseRouter.reverse_frozen import reverse_attention
from test_reverse_parent import plan,explicit

def run(native,actual):
 p=plan() if not actual else {'seq_len':87592,'reference_video_segment':[7910,47516],'target_video_segment':[47986,87592],'latent_interval_half_open':[14,20],'frame_rows':943,'key_interval_half_open':[21112,26770],'query_interval_half_open':[61188,66846],'segments':[(0,6960,'text'),(6960,7910,'ref_img'),(7910,47516,'ref_img'),(47516,47986,'audio'),(47986,87592,'video')]}
 g=torch.Generator(device='cuda').manual_seed(2026101717);q,k,v=[torch.randn((1,56,p['seq_len'],128),dtype=torch.bfloat16,device='cuda',generator=g) for _ in range(3)]
 rng=torch.cuda.get_rng_state().clone();ra,rb=p['key_interval_half_open'];ta,tb=p['query_interval_half_open'];cases=[]
 # Sequential cases keep no four full-size outputs. Selected historical rows alone
 # remain live for exact F/B component tests; this overhead is included in peaks.
 native_out=native(q,k,v,56,skip_reshape=True)
 with torch.inference_mode():out=core.joint_attention(native,q,k,v,56,p,mode='native',native_kwargs={'skip_reshape':True})
 assert torch.equal(out,native_out);del out,native_out
 historical_F=route_attention(q,k,v,56,p,mode='mass_preserve',alpha=1.,radius=0,time_offset=0);f_rows=historical_F[:,ta:tb].clone();del historical_F
 historical_B=reverse_attention(native,q,k,v,56,p,mode='reverse_block',alpha=1.,native_kwargs={'skip_reshape':True});b_rows=historical_B[:,ra:rb].clone();del historical_B
 for mode in ('native','forward','reverse_block','joint'):
  gc.collect();torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();start=time.monotonic();base_alloc=torch.cuda.memory_allocated();audit={}
  with torch.inference_mode():out=core.joint_attention(native,q,k,v,56,p,mode=mode,first_audit=audit if mode!='native' else None,native_kwargs={'skip_reshape':True})
  if mode in ('forward','joint'):assert torch.equal(out[:,ta:tb],f_rows)
  if mode in ('reverse_block','joint'):assert torch.equal(out[:,ra:rb],b_rows)
  if mode!='native':assert all(audit[k] is True for k in ('nonselected_rows_bitwise','input_values_bitwise','forward_component_rows_bitwise','reverse_component_rows_bitwise','target_audio_bitwise','finite'))
  if mode in ('forward','joint'):assert audit['native_vs_prewrite_full_Flash_bitwise'] is True
  oracle_report=None
  if not actual:
   n=torch.nn.functional.scaled_dot_product_attention(q.float(),k.float(),v.float()).transpose(1,2).reshape_as(out)
   oracle=n.clone()
   if mode in ('forward','joint'):
    z=q.float()@k.float().transpose(-1,-2)/(128**.5);prob=z.softmax(-1);a,b=p['reference_video_segment'];mass=prob[:,:,ta:tb,a:b].sum(-1,keepdim=True);o_ref=(prob[:,:,ta:tb,a:b]@v[:,:,a:b].float())/mass
    rows=p['frame_rows'];lo,hi=p['latent_interval_half_open'];aligned=[]
    for t in range(lo,hi):
     qa=q[:,:,ta+(t-lo)*rows:ta+(t-lo+1)*rows].float();ka=k[:,:,a+t*rows:a+(t+1)*rows].float();va=v[:,:,a+t*rows:a+(t+1)*rows].float();aligned.append((qa@ka.transpose(-1,-2)/(128**.5)).softmax(-1)@va)
    corr=(torch.cat(aligned,dim=2)-o_ref)*mass;oracle[:,ta:tb]+=corr.transpose(1,2).reshape_as(oracle[:,ta:tb])
   if mode in ('reverse_block','joint'):oracle[:,ra:rb]=explicit(q.float(),k.float(),v.float(),p,'reverse_block')[0][:,ra:rb]
   err=out.float()-oracle;rel=float(err.square().mean().sqrt()/oracle.square().mean().sqrt());scaled=float(err.abs().max()/oracle.abs().max());assert rel<=.025 and scaled<=.035;oracle_report={'relative_rms':rel,'scaled_maxabs':scaled,'limits':[.025,.035]}
  assert bool(torch.isfinite(out).all()) and torch.equal(rng,torch.cuda.get_rng_state());torch.cuda.synchronize();cases.append({'mode':mode,'actual_shape':actual,'shape':list(q.shape),'seconds':time.monotonic()-start,'base_allocated_bytes':base_alloc,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'first_audit':audit,'oracle':oracle_report,'historical_component_rows_exact':True});del out
 del q,k,v,f_rows,b_rows;gc.collect();torch.cuda.empty_cache();return cases

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--comfy-root',type=Path,default=Path('/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI'));a=p.parse_args()
 if a.output.exists():raise FileExistsError(a.output)
 sys.path.insert(0,str(a.comfy_root));sys.argv=['r30-gpu-kernel','--use-pytorch-cross-attention','--disable-dynamic-vram'];import comfy.options;comfy.options.enable_args_parsing()
 sp=importlib.util.spec_from_file_location('r30_gpu_compat',ROOT/'scripts/compatibility_bootstrap.py');compat=importlib.util.module_from_spec(sp);sp.loader.exec_module(compat);compat.install();compat.install_video_compat()
 import comfy.ldm.minimax.model as h3
 assert h3.optimized_attention.__name__=='attention_pytorch'
 if not torch.cuda.is_available() or torch.cuda.device_count()!=1:raise RuntimeError('root must admit one idle GPU via exact CUDA_VISIBLE_DEVICES')
 torch.set_num_threads(1);cases=run(h3.optimized_attention,False)+run(h3.optimized_attention,True)
 result={'passed':True,'NFE':0,'model_weights_loaded':False,'core_sha256':hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest(),'cases':cases,'allocated_end':torch.cuda.memory_allocated(),'reserved_end':torch.cuda.memory_reserved(),'scope':'independent four-mode kernel gate; includes retained historical selected-row outputs and audit copies; does not prove complete DiT resident peak'}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
