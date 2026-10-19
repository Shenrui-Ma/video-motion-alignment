"""Explicit same-host recovered final Euler and VAE decode. Root PID-bound GPU admission required."""
import argparse,gc,json,os,shutil,subprocess,sys,time
from pathlib import Path
import supervision as s
import frozen_decode as d
ROOT=Path(__file__).resolve().parent
GPU='GPU-REDACTED'
CORE=Path('/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI')
DEPS=Path('/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps')
VAE=Path('/data5/researcher/ComfyUI/models/vae/minimax_h3_video_vae_fp16.safetensors')
VAE_SHA='7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522'

def signature(t):
    import hashlib
    return {'shape':list(t.shape),'dtype':str(t.dtype),'bytes':t.numel()*t.element_size(),'sha256':hashlib.sha256(t.detach().cpu().contiguous().numpy().tobytes()).hexdigest()}

def pack(payload):
    import torch
    return torch.cat([v.reshape(v.shape[0],1,-1) for v in (payload['video'],payload['audio']*4.0)],dim=-1)

def update(x,denoised,grid,i):
    derivative=(x-denoised)/grid[i].reshape(1,1,1)
    dt=grid[i+1]-grid[i]
    return x+derivative*dt

def load_x19(path):
    import torch
    # The bound CPU proof stores torch.__version__ as this string subclass.
    with torch.serialization.safe_globals([torch.torch_version.TorchVersion]):
        return torch.load(path,map_location='cpu',weights_only=True)['packed']

def admitted(registry,parent):
    s.require(s.alive(parent),'CPU supervisor exited')
    s.require(registry['root_approved'] is True and registry['gpu_uuid']==GPU,'root GPU admission differs')
    idle=d.assert_idle_gpu(GPU)
    text=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True,timeout=10)
    allowed={r['identity']['pid']:r for r in registry['permitted_peers']};cards={GPU}
    for line in text.splitlines():
        if not line.strip():continue
        uuid,pid=line.split(',');pid=int(pid.strip());uuid=uuid.strip();identity=s.identity(pid)
        if identity and identity['uid']==os.getuid():
            s.require(pid in allowed and allowed[pid]['identity']==identity and allowed[pid]['gpu_uuid']==uuid,'unregistered or reused own GPU peer');cards.add(uuid)
    s.require(len(cards)<=2,'more than two owned GPUs');return idle

def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--parent-json',required=True);p.add_argument('--admission',type=Path,required=True);a=p.parse_args();out=a.directory.resolve();s.require(out.is_relative_to(ROOT/'runs'),'output outside recovery slice');parent=json.loads(a.parent_json);s.install_lifetime_guard(parent)
    manifest=s.read_json(ROOT/'MANIFEST.json')
    for rel,row in manifest['files'].items():s.require(s.sha(ROOT/rel)==row['sha256'],'slice input/source SHA differs: '+rel)
    registry=s.read_json(a.admission);admission_sha=s.sha(a.admission);identity=s.identity(os.getpid())
    s.write_new(out/'ready.json',{'identity':identity,'gpu_uuid':GPU,'admission_sha256':admission_sha,'manifest_sha256':s.sha(ROOT/'MANIFEST.json'),'CUDA_initialized':False})
    deadline=time.monotonic()+600
    while not (out/'go.json').exists():
        s.require(s.alive(parent),'supervisor exited while waiting');s.require(time.monotonic()<deadline,'root go timeout');time.sleep(.2)
    go=s.read_json(out/'go.json');s.require(go=={'root_approved':True,'identity':identity,'gpu_uuid':GPU,'admission_sha256':admission_sha,'manifest_sha256':s.sha(ROOT/'MANIFEST.json')},'root go identity/binding differs')
    admitted(registry,parent)
    for rel,digest in s.read_json(ROOT/'inputs/core_expected.json').items():s.require(s.sha(CORE/rel)==digest,'host9 frozen core differs: '+rel)
    s.require(s.sha(VAE)==VAE_SHA,'FP16 VAE checkpoint differs')
    os.environ['CUDA_VISIBLE_DEVICES']=GPU
    import torch
    s.require(not torch.cuda.is_initialized(),'CUDA initialized before gate')
    context=s.read_json(ROOT/'inputs/CONTEXT.json');decision=s.read_json(ROOT/'inputs/DECISION19.json');proof=s.read_json(ROOT/'inputs/CPU_X14_REPLAY.json');native9=s.read_json(ROOT/'inputs/native_host9.json')
    s.require(decision['decision19']['chosen_full'] is False and decision['context_sha256']==s.sha(ROOT/'inputs/CONTEXT.json'),'final OFF decision not bound')
    x14=torch.load(ROOT/'inputs/step014_input_raw.pt',map_location='cpu',weights_only=True)['packed'];full14=torch.load(ROOT/'inputs/step014_full.pt',map_location='cpu',weights_only=True)
    x19=load_x19(ROOT/'inputs/x19_reconstructed_cpu.pt');native19=torch.load(ROOT/'inputs/step019_native.pt',map_location='cpu',weights_only=True)
    s.require(signature(x19)==context['Native019_branch']['same_input'],'x19 packed signature differs')
    s.require([signature(native19[k]) for k in ('video','audio')]==context['original_request']['normalized_stream_signatures'],'Native019 normalization differs')
    grid=torch.tensor(context['original_request']['full_grid'],dtype=torch.float32);s.require(float(grid[20])==0.0,'not final Euler step')
    admitted(registry,parent)
    with torch.inference_mode():
        x15=update(x14.cuda(),pack(full14).cuda(),grid.cuda(),14).cpu()
        check={'index':14,'actual':signature(x15),'expected':proof['rows'][0]['expected']};check['exact']=check['actual']==check['expected'];s.write_new(out/'EULER14_CHECK.json',check);s.require(check['exact'],'host9 GPU arithmetic differs from actual live x15')
        final_cpu=update(x19,pack(native19),grid,19)
        final_gpu=update(x19.cuda(),pack(native19).cuda(),grid.cuda(),19).cpu()
    arithmetic={'schema':'r53-recovered-final-euler-v1','original_run_completed':False,'cross_host':False,'torch':torch.__version__,'gpu_name':torch.cuda.get_device_name(),'step14_exact':True,'final_CPU_signature':signature(final_cpu),'final_GPU_signature':signature(final_gpu),'final_CPU_GPU_exact':torch.equal(final_cpu,final_gpu),'max_abs_CPU_GPU_difference':float((final_cpu-final_gpu).abs().max()),'decision19_sha256':s.sha(ROOT/'inputs/DECISION19.json'),'x19_sha256':s.sha(ROOT/'inputs/x19_reconstructed_cpu.pt'),'Native019_sha256':s.sha(ROOT/'inputs/step019_native.pt')}
    s.write_new(out/'FINAL_EULER.json',arithmetic);s.require(arithmetic['final_CPU_GPU_exact'],'final GPU Euler differs from CPU arithmetic')
    count=native19['video'].numel();video=final_gpu[:,:,:count].reshape(native19['video'].shape);audio=final_gpu[:,:,count:].reshape(native19['audio'].shape)/4.0
    torch.save({'video':video,'audio':audio,'metadata':{'recovery':True,'original_run_completed':False,'cross_host':False,'final_euler_sha256':s.sha(out/'FINAL_EULER.json'),'geometry':{'frames':141,'height':736,'width':1312,'fps':24}}},out/'recovered_final.pt')
    sys.path.insert(0,str(DEPS));sys.path.insert(0,str(CORE));sys.argv=[sys.argv[0]]
    from compatibility_bootstrap import install,install_video_compat
    install();install_video_compat()
    import comfy.cli_args
    comfy.cli_args.args.disable_dynamic_vram=True;comfy.cli_args.args.disable_cuda_malloc=True;comfy.cli_args.args.use_pytorch_cross_attention=True
    import comfy.sd,comfy.utils,comfy.model_management
    d.install_fallback_guard(comfy.sd.VAE);state,metadata=comfy.utils.load_torch_file(str(VAE),return_metadata=True);vae=comfy.sd.VAE(sd=state,metadata=metadata,dtype=torch.float16);vae.throw_exception_if_invalid();del state
    s.require(vae.latent_channels==24 and vae.latent_dim==3 and isinstance(vae.first_stage_model,comfy.ldm.minimax.vae.MiniMaxH3VideoVAE),'H3 video VAE differs')
    records={};start=time.monotonic()
    try:
        for name,latent in [('native019_host9',native19['video']),('recovered_final',video)]:
            with torch.inference_mode():images=vae.decode(latent)
            if images.ndim==5 and images.shape[0]==1:images=images.flatten(0,1)
            s.require(tuple(images.shape)==(141,736,1312,3) and bool(torch.isfinite(images).all()),'decoded geometry/finite check failed');images=images.detach().cpu()
            result=d.write_video(images,out/(name+'.mp4'),shutil.which('ffmpeg'));del images
            result.update(status='complete',file=str(out/(name+'.mp4')),file_sha256=s.sha(out/(name+'.mp4')),original_run_completed=False,cross_host=False,vae_sha256=VAE_SHA,fallback_guard=d.FALLBACK)
            s.write_new(out/(name+'.json'),result);records[name]=result
    finally:
        vae=None;comfy.model_management.unload_all_models();gc.collect();comfy.model_management.soft_empty_cache()
    comparison={'native_RGB_exact_to_host9':records['native019_host9']['preencode_rgb24_sha256']==native9['preencode_rgb24_sha256'],'native_decoded_tensor_exact_to_host9':records['native019_host9']['decoded_tensor_sha256']==native9['decoded_tensor_sha256'],'native_matching_RGB_frames':sum(a==b for a,b in zip(records['native019_host9']['preencode_rgb24_frame_sha256'],native9['preencode_rgb24_frame_sha256'])),'total_frames':141}
    s.write_new(out/'RECOVERY_FINAL.json',{'status':'same_host_recovered_final_video','original_run_completed':False,'final_euler_sha256':s.sha(out/'FINAL_EULER.json'),'recovered_final_pt_sha256':s.sha(out/'recovered_final.pt'),'outputs':records,'same_host_comparison':comparison,'decode_seconds':time.monotonic()-start,'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'process_gpu_reserved_after_cleanup':torch.cuda.memory_reserved(),'interpretation':'Recovered continuation on the original host and software runtime. Native decode equality is reported explicitly; original failed-run records are preserved.'})
    print(json.dumps(comparison),flush=True)
if __name__=='__main__':main()
