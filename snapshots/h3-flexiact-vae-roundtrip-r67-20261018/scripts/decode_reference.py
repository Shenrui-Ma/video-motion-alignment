"""Decode an actual H3 reference VAE.encode result. CUDA only with --execute."""
import argparse,gc,json,os,shutil,subprocess,sys,time
from pathlib import Path
from common import *

def admission(uuid,minimum_mib):
    raw=subprocess.check_output(['nvidia-smi','--id='+uuid,'--query-gpu=index,uuid,memory.free,memory.used,temperature.gpu,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=20)
    rows=[x.split(',') for x in raw.strip().splitlines()];require(len(rows)==1 and rows[0][1].strip()==uuid,'GPU UUID exact binding')
    idx,found,free,used,temp,util=[x.strip() for x in rows[0]]
    require(int(free)>=minimum_mib,'insufficient actual free VRAM');require(int(temp)<85,'GPU thermal admission')
    apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_gpu_memory','--format=csv,noheader,nounits'],text=True,timeout=20)
    owned=set();processes=[]
    for line in apps.splitlines():
        fields=[x.strip() for x in line.split(',')]
        if len(fields)!=3:continue
        gpu,pid,mem=fields
        try:uid=Path('/proc',pid).stat().st_uid
        except FileNotFoundError:continue
        except PermissionError:uid=None
        if uid==os.getuid():owned.add(gpu)
        processes.append({'gpu_uuid':gpu,'pid':pid,'uid':uid,'used_mib':mem})
    require(len(owned|{uuid})<=2,'own-user maximum 2 GPUs')
    return {'gpu_index':int(idx),'uuid':uuid,'free_mib':int(free),'used_mib':int(used),'temperature':int(temp),'utilization':int(util),'own_gpu_uuids_before':sorted(owned),'compute_processes':processes,'scope':'foreign users allowed; required actual free capacity and own-device cap','unix':time.time()}

def install_fallback_guard(cls):
    rec={'calls':0,'installed':[]}
    def forbidden(*args,**kwargs):
        rec['calls']+=1
        raise RuntimeError('R67 refuses wrapper OOM tiled fallback; retain native H3 internal tiling')
    for name in ('decode_tiled','decode_tiled_','decode_tiled_1d','decode_tiled_3d','_decode_tiled_owned'):
        if hasattr(cls,name):setattr(cls,name,forbidden);rec['installed'].append(name)
    require('decode_tiled_3d' in rec['installed'],'3D fallback guard install')
    return rec

def validate_inputs(root,inputs):
    c=json.loads((root/'configs/contract.json').read_text());p=json.loads((inputs/'PREPARED.json').read_text())
    require(p['status']=='complete' and p['case']==c['case'],'prepared source completed')
    require(p['contract_sha256']==sha(root/'configs/contract.json'),'source contract binding')
    require(p['conditioning_sha256']==c['conditioning_sha256'],'source conditioning binding')
    require(p['latent']['signature']==c['video_vae_call']['latent'],'latent manifest identity')
    path=inputs/p['latent']['file'];require(sha(path)==p['latent']['sha256'],'latent file SHA')
    z=load_bound_tensor(path,c['video_vae_call']['latent'])
    require(tuple(z.shape)==(1,24,47,48,72),'actual reference latent geometry')
    for k,v in p['products'].items():require(sha(inputs/v['file'])==v['sha256'] and v['lossless_pixel_verified'],'source RGB product '+k)
    for f,digest in c['core_sha256'].items():require(sha(Path(c['core'])/f)==digest,'actual core source '+f)
    require(sha(c['vae'])==c['vae_sha256'],'actual VAE checkpoint SHA')
    require(shutil.which('ffmpeg') is not None,'ffmpeg available')
    return c,p,z

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--output',type=Path);ap.add_argument('--gpu-uuid');ap.add_argument('--execute',action='store_true');ap.add_argument('--validate-only',action='store_true');a=ap.parse_args()
    require(a.execute!=a.validate_only,'choose exactly one of --validate-only / --execute')
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(2);require(not torch.cuda.is_initialized(),'no preinitialized CUDA')
    root=Path(__file__).resolve().parents[1]
    c,p,z=validate_inputs(root,a.inputs.resolve())
    if a.validate_only:
        import av,numpy,einops,safetensors
        print(json.dumps({'status':'CPU_VALIDATED','cuda_initialized':torch.cuda.is_initialized(),'torch':torch.__version__,'pyav':av.__version__,'latent_signature':tensor_signature(z),'contract_sha256':sha(root/'configs/contract.json')}));return
    require(a.gpu_uuid==c['gpu_uuid'],'explicit approved GPU UUID');require(a.output is not None and not a.output.exists(),'new output directory')
    first=admission(a.gpu_uuid,c['required_free_mib'])
    os.environ['CUDA_VISIBLE_DEVICES']=a.gpu_uuid
    sys.path.insert(0,c['dependencies']);sys.path.insert(0,c['core'])
    from compatibility_bootstrap import install,install_video_compat
    install();install_video_compat()
    import comfy.cli_args
    comfy.cli_args.args.disable_dynamic_vram=True
    comfy.cli_args.args.disable_cuda_malloc=True
    comfy.cli_args.args.use_pytorch_cross_attention=True
    second=admission(a.gpu_uuid,c['required_free_mib'])
    import comfy.sd,comfy.utils,comfy.model_management
    guard=install_fallback_guard(comfy.sd.VAE)
    a.output.mkdir(parents=True,exist_ok=False)
    record={'schema':'r67-clean-reference-decode-v1','status':'running','pid':os.getpid(),'uid':os.getuid(),'started_unix':time.time(),'contract_sha256':sha(root/'configs/contract.json'),'prepared_sha256':sha(a.inputs/'PREPARED.json'),'reference_latent':p['latent'],'gpu_admission':[first,second],'fallback_guard':guard,'normalization':'saved native VAE.encode result passed unchanged to comfy.sd.VAE.decode; internal MiniMaxH3VideoVAE.decode z*latents_std+latents_mean exactly once','vae_sha256':c['vae_sha256'],'vae_dtype':'torch.float16','torch':torch.__version__,'encode_runtime':c['source_encode_runtime'],'decode_runtime':c['decode_runtime'],'valid_frames':147,'original49_indices':list(range(0,147,3))}
    write(a.output/'RESULT.json',record);state=vae=images=None
    try:
        require(torch.cuda.device_count()==1,'exactly one visible GPU');torch.cuda.reset_peak_memory_stats()
        state,metadata=comfy.utils.load_torch_file(c['vae'],return_metadata=True)
        vae=comfy.sd.VAE(sd=state,metadata=metadata,dtype=torch.float16);vae.throw_exception_if_invalid()
        require(vae.latent_channels==24 and vae.latent_dim==3 and isinstance(vae.first_stage_model,comfy.ldm.minimax.vae.MiniMaxH3VideoVAE),'H3 VAE class')
        state=None
        start=time.monotonic()
        with torch.inference_mode():images=vae.decode(z)
        torch.cuda.synchronize();record['native_decode_seconds']=time.monotonic()-start
        if images.ndim==5 and images.shape[0]==1:images=images.flatten(0,1)
        require(tuple(images.shape)==(158,768,1152,3),'decoded geometry')
        images=images.detach().cpu();record['decoded_signature']=tensor_signature(images.contiguous())
        record['products']={}
        for name,idx,fps in [('reconstruction_158',range(158),24),('reconstruction_valid147',range(147),24),('reconstruction_original49',range(0,147,3),8)]:
            record['products'][name]=write_frames(images,idx,fps,a.output/(name+'.mp4'))
        require(guard['calls']==0,'no wrapper fallback');record['status']='complete'
    except BaseException as e:
        record['status']='failed';record['error']=f'{type(e).__name__}: {e}';raise
    finally:
        record['max_memory_allocated_bytes']=torch.cuda.max_memory_allocated();record['max_memory_reserved_bytes']=torch.cuda.max_memory_reserved()
        state=vae=images=None
        try:comfy.model_management.unload_all_models();gc.collect();comfy.model_management.soft_empty_cache()
        except BaseException as cleanup_error:
            record['cleanup_error']=f'{type(cleanup_error).__name__}: {cleanup_error}'
            if record['status']=='complete':record['status']='failed_cleanup'
        finally:
            record['reserved_after_cleanup_bytes']=torch.cuda.memory_reserved();record['finished_unix']=time.time();record['wall_seconds']=record['finished_unix']-record['started_unix'];write(a.output/'RESULT.json',record)
    require(record['status']=='complete','decode/cleanup did not complete; retained RESULT.json')
    print(json.dumps({'status':record['status'],'record':str(a.output/'RESULT.json')}))
if __name__=='__main__':main()
