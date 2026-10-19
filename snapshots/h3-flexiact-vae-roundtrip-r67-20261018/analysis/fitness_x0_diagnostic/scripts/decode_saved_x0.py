"""Read saved predicted-clean x0 by actual run/index; no diffusion forward."""
import argparse,gc,hashlib,importlib.util,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R67=ROOT.parents[1]
sys.path.insert(0,str(R67/'scripts'))
from common import sha,write,require,tensor_signature,write_frames
import decode_reference as native_decoder
import frozen_x0_reader as reader
import frozen_capture_core as capture

def load_endpoint(run_id,index):
    gate=json.loads((ROOT/'configs/PAIR_RUNTIME_GATE.json').read_text());contract=json.loads((ROOT/'configs/contract.json').read_text())
    require(sha(ROOT/'configs/PAIR_RUNTIME_GATE.json')==contract['gate_sha256'],'actual pair gate SHA')
    require(gate['passed'] and all(v is True for v in gate['checks'].values()),'actual completed pair gate')
    require(gate['checks']['Native_prefix_0_5_equal'],'same-state prefix evidence')
    require([run_id,index] in contract['planned_run_indices'],'registered diagnostic run/index')
    matches=[(arm,rec) for arm,rec in gate['runs'].items() if rec['run_id']==run_id];require(len(matches)==1,'unique actual run binding')
    arm,run=matches[0];path=ROOT/'inputs'/arm/f'x0_step{index:03d}.pt';entry=next(s for s in run['snapshots'] if Path(s['file']).name==path.name)
    require(sha(path)==entry['sha256'] and path.stat().st_size==entry['bytes'],'snapshot actual output hash/size')
    require(sha(path.parent/'manifest.json')==contract['manifests'][arm],'completed x0 manifest hash')
    payload=reader.load_snapshot(path,capture);m=payload['metadata']
    require(m['run_id']==run_id and m['step_zero_based']==index and m['model_call_one_based']==index+1,'metadata run/index')
    require(m['normalization_stage']=='after_process_latent_out' and m['video_latent_scale_factor']==1 and m['audio_scale']==4,'actual normalization contract')
    require(m['seed']==2026101701 and m['geometry']=={'width':1152,'height':768,'frames':158,'fps':24},'seed/geometry')
    return payload,{'arm':arm,'run_id':run_id,'index':index,'file':str(path),'file_sha256':sha(path),'manifest_sha256':sha(path.parent/'manifest.json'),'metadata':m,'role':'same-state Native/forced predicted endpoint pair' if index==6 else 'Native trajectory evolution before first intervention; not a paired counterfactual'}

def verify_code():
    c=json.loads((ROOT/'configs/contract.json').read_text())
    for p,digest in c['dependency_sha256'].items():
        f=(R67/p[4:]) if p.startswith('R67/') else ROOT/p
        require(sha(f)==digest,'frozen CPU reader / parent decoder dependency '+p)
    return c

def main():
    a=argparse.ArgumentParser();a.add_argument('--run-id',required=True);a.add_argument('--index',type=int,required=True);a.add_argument('--validate-only',action='store_true');a.add_argument('--execute',action='store_true');a.add_argument('--output',type=Path);a.add_argument('--gpu-uuid');args=a.parse_args()
    require(args.validate_only!=args.execute,'choose validate-only/execute')
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(2);require(not torch.cuda.is_initialized(),'CUDA starts only after admission')
    contract=verify_code();payload,info=load_endpoint(args.run_id,args.index)
    if args.validate_only:
        print(json.dumps({'status':'CPU_VALIDATED','cuda_initialized':torch.cuda.is_initialized(),'input':info}));return
    c=json.loads((R67/'configs/contract.json').read_text());require(args.gpu_uuid==c['gpu_uuid'],'approved explicit GPU UUID');require(args.output is not None and not args.output.exists(),'new output dir')
    for rel,digest in c['core_sha256'].items():require(sha(Path(c['core'])/rel)==digest,'actual core bytes')
    require(sha(c['vae'])==c['vae_sha256'],'actual VAE checkpoint')
    boot=Path(contract['bootstrap']);require(sha(boot)==contract['bootstrap_sha256'],'actual compatibility bootstrap')
    first=native_decoder.admission(args.gpu_uuid,c['required_free_mib']);os.environ['CUDA_VISIBLE_DEVICES']=args.gpu_uuid
    sys.path.insert(0,c['dependencies']);sys.path.insert(0,c['core'])
    spec=importlib.util.spec_from_file_location('compatibility_bootstrap',boot);compat=importlib.util.module_from_spec(spec);sys.modules['compatibility_bootstrap']=compat;spec.loader.exec_module(compat);compat.install();compat.install_video_compat()
    import comfy.cli_args
    comfy.cli_args.args.disable_dynamic_vram=True;comfy.cli_args.args.disable_cuda_malloc=True;comfy.cli_args.args.use_pytorch_cross_attention=True
    second=native_decoder.admission(args.gpu_uuid,c['required_free_mib'])
    import comfy.sd,comfy.utils,comfy.model_management
    guard=native_decoder.install_fallback_guard(comfy.sd.VAE);args.output.mkdir(parents=True)
    rec={'schema':'r67-saved-x0-decode-v1','status':'running','pid':os.getpid(),'uid':os.getuid(),'input':info,'started_unix':time.time(),'gpu_admission':[first,second],'normalization':'payload.video was saved after process_latent_out and is already VAE-ready; native VAE.decode applies channel mean/std; no further scaling','model_forward_calls':0,'vae_sha256':c['vae_sha256'],'fallback_guard':guard,'torch':torch.__version__,'code_contract_sha256':sha(ROOT/'configs/contract.json')}
    write(args.output/'RESULT.json',rec);state=vae=images=None
    try:
        require(torch.cuda.device_count()==1,'one visible GPU');torch.cuda.reset_peak_memory_stats()
        state,metadata=comfy.utils.load_torch_file(c['vae'],return_metadata=True)
        vae=comfy.sd.VAE(sd=state,metadata=metadata,dtype=torch.float16);vae.throw_exception_if_invalid();require(vae.latent_channels==24 and vae.latent_dim==3 and isinstance(vae.first_stage_model,comfy.ldm.minimax.vae.MiniMaxH3VideoVAE),'native H3 VAE')
        state=None;started=time.monotonic()
        with torch.inference_mode():images=vae.decode(payload['video'])
        torch.cuda.synchronize();rec['decode_seconds']=time.monotonic()-started
        if images.ndim==5 and images.shape[0]==1:images=images.flatten(0,1)
        require(tuple(images.shape)==(158,768,1152,3),'full158 geometry');images=images.detach().cpu();rec['decoded_signature']=tensor_signature(images.contiguous());rec['products']={}
        for name,idx,fps in [('x0_158',range(158),24),('x0_valid147',range(147),24),('x0_original49',range(0,147,3),8)]:rec['products'][name]=write_frames(images,idx,fps,args.output/(name+'.mp4'))
        require(guard['calls']==0,'native fallback count');rec['status']='complete'
    except BaseException as e:rec['status']='failed';rec['error']=f'{type(e).__name__}: {e}';raise
    finally:
        rec['max_memory_allocated_bytes']=torch.cuda.max_memory_allocated();rec['max_memory_reserved_bytes']=torch.cuda.max_memory_reserved();state=vae=images=None
        try:comfy.model_management.unload_all_models();gc.collect();comfy.model_management.soft_empty_cache()
        except BaseException as e:
            rec['cleanup_error']=f'{type(e).__name__}: {e}'
            if rec['status']=='complete':rec['status']='failed_cleanup'
        finally:rec['reserved_after_cleanup_bytes']=torch.cuda.memory_reserved();rec['finished_unix']=time.time();write(args.output/'RESULT.json',rec)
    require(rec['status']=='complete','decode/cleanup error retained');print(json.dumps({'status':'complete','result':str(args.output/'RESULT.json')}))
if __name__=='__main__':main()
