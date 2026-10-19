"""Isolated H3 VAE controls. No DiT/Qwen/audio. No work or CUDA on import."""
import argparse
import gc
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

HERE=Path(__file__).resolve().parent
ARMS=('original','delay4','delay8','constant0')
WINDOWS=((50,65),(69,81),(80,92),(99,111))
HOST41_GPU='GPU-REDACTED'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def tensor_info(x):
    import torch
    if x.device.type!='cpu':raise ValueError('signature requires CPU tensor')
    y=x.contiguous()
    return {'shape':list(y.shape),'dtype':str(y.dtype),'sha256':hashlib.sha256(y.view(torch.uint8).numpy()).hexdigest()}


def atomic_json(path,value):
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)


def exclusive_save(path,value):
    import torch
    fd,tmp=tempfile.mkstemp(prefix='.vae-control-',dir=path.parent);os.close(fd)
    try:
        with open(tmp,'wb') as f:torch.save(value,f);f.flush();os.fsync(f.fileno())
        os.link(tmp,path)
    finally:
        os.unlink(tmp)


def indices_for(arm,frames=141):
    if arm=='original':return list(range(frames))
    if arm=='constant0':return [0]*frames
    if arm not in ('delay4','delay8'):raise ValueError('arm is not in frozen four-arm protocol')
    delay=int(arm[5:]);return [max(0,t-delay) for t in range(frames)]


def control_pixels(rgb,arm):
    import torch
    return rgb.index_select(0,torch.tensor(indices_for(arm,len(rgb)),dtype=torch.long))


def time_geometry():
    spans=[];start=0
    for i in range(42):
        length=(1,4,4,4,4)[i%5];spans.append((start,start+length-1));start+=length
    return spans,[(a+b)/2 for a,b in spans]


def phase_statistics(z):
    """Whole spatial field, no selected ROI/channel or inferred body motion."""
    import torch
    if z.ndim!=5 or z.shape[0]!=1 or z.shape[2]!=42:raise ValueError('expected one 42-bin latent')
    a=z.double();centered=a-a.mean(2,keepdim=True);energy=float(centered.square().sum())
    template=torch.stack([a[:,:,p::5].mean(2) for p in range(5)],2)
    fitted=template.index_select(2,torch.arange(42)%5)
    residual=float((a-fitted).square().sum())
    d=a[:,:,1:]-a[:,:,:-1];dt=torch.tensor([b-a for a,b in zip(time_geometry()[1],time_geometry()[1][1:])],dtype=torch.float64)
    velocity=d/dt[None,None,:,None,None]
    correlations={}
    for lag in range(1,11):
        x=velocity[:,:,:-lag];y=velocity[:,:,lag:];den=float((x.square().sum()*y.square().sum()).sqrt())
        correlations[str(lag)]=float((x*y).sum())/den if den>0 else None
    return {'latent_rms':float(a.square().mean().sqrt()),'adjacent_bin_rms':float(d.square().mean().sqrt()),
            'adjacent_bins_bitwise_equal':torch.equal(z[:,:,1:],z[:,:,:-1]),
            'period5_bitwise_equal':torch.equal(z[:,:,5:],z[:,:,:-5]),
            'period5_difference_rms':float((a[:,:,5:]-a[:,:,:-5]).square().mean().sqrt()),
            'period5_max_abs_difference':float((a[:,:,5:]-a[:,:,:-5]).abs().max()),
            'temporal_variance_energy':energy,'five_phase_explained_fraction':1-residual/energy if energy>0 else None,
            'adjacent_bin_rms_series':d.square().mean((0,1,3,4)).sqrt().tolist(),
            'signed_derivative_autocorrelation_lag_bins1to10':correlations,
            'normalization':'original VAE normalized latent; derivative divided by actual position-center frame spacing',
            'interpretation':'5-bin structure is an encoder/representation diagnostic; never a human-motion score'}


def signed_signal(z):
    centers=time_geometry()[1]
    import numpy as np
    d=z[0,:,1:]-z[0,:,:-1]
    dt=z.new_tensor([b-a for a,b in zip(centers,centers[1:])])
    return np.array([(a+b)/2 for a,b in zip(centers,centers[1:])]),(d/dt[None,:,None,None]).permute(1,0,2,3).reshape(41,-1).numpy()


def interpolate(times,values,queries):
    import numpy as np
    up=np.searchsorted(times,queries,side='right').clip(1,len(times)-1);lo=up-1
    w=((queries-times[lo])/(times[up]-times[lo])).clip(0,1)
    return values[lo]*(1-w[:,None])+values[up]*w[:,None]


def signed_scan(original,changed,window):
    """Same fixed signed-vector cosine scan as prior diagnostic, full-frame only."""
    import numpy as np
    t=np.arange(window[0],window[1]+1,dtype=float);a=interpolate(*original,t);rows=[]
    for lag in range(-24,25):
        b=interpolate(*changed,t+lag);den=np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1);valid=den>1e-10
        value=float(np.mean(1-np.sum(a[valid]*b[valid],axis=1)/den[valid])) if valid.any() else None
        rows.append({'lag_frames':lag,'signed_cosine_error':value,'valid_frames':int(valid.sum())})
    ordered=sorted((r for r in rows if r['signed_cosine_error'] is not None),key=lambda r:r['signed_cosine_error'])
    return {'window_inclusive':list(window),'best':ordered[0] if ordered else None,'curve':rows,
            'note':'fixed linear physical-position interpolation; aliases remain; no success threshold or pose endpoint replacement'}


def analyze_saved(output):
    import torch
    latents={arm:torch.load(output/(arm+'.pt'),map_location='cpu',weights_only=True,mmap=True) for arm in ARMS}
    reports={arm:phase_statistics(z) for arm,z in latents.items()}
    original=signed_signal(latents['original'])
    for arm in ('delay4','delay8'):
        reports[arm]['known_rgb_delay_frames']=int(arm[5:])
        reports[arm]['signed_lag_full_frame']=[signed_scan(original,signed_signal(latents[arm]),w) for w in WINDOWS]
    constant=reports['constant0']
    return {'status':'completed_vae_representation_diagnostic','arms':reports,
            'constant_control_exact_evidence':{'same_RGB_every_frame':True,'latent_time_nonconstant':not constant['adjacent_bins_bitwise_equal'],
                'latent_period5_exact':constant['period5_bitwise_equal']},
            'scope':'No denoising, teacher, edited target, optical flow, pose or new generation-model claim; all four inputs use same VAE.'}


def validate_inputs(condition,audit_root):
    import torch
    c=json.loads(condition.read_text());calls=c['native_vae_calls']
    if len(calls)!=2:raise ValueError('expected identity-image then reference-video VAE calls')
    rgb_meta,z_meta=calls[1]['prepared_frames'],calls[1]['latent']
    if rgb_meta['shape']!=[141,736,1312,3] or z_meta['shape']!=[1,24,42,46,82]:raise ValueError('unregistered geometry')
    root=audit_root.resolve();paths=[]
    for meta in (rgb_meta,z_meta):
        p=(root/meta['tensor_file']).resolve()
        if root not in p.parents:raise ValueError('tensor path outside supplied read-only audit root')
        if not p.is_file():raise FileNotFoundError(p)
        paths.append(p)
    rgb,z=[torch.load(p,map_location='cpu',weights_only=True,mmap=True) for p in paths]
    for x,meta in ((rgb,rgb_meta),(z,z_meta)):
        if tensor_info(x)!={k:meta[k] for k in ('shape','dtype','sha256')}:raise ValueError('actual source tensor SHA/shape/dtype mismatch')
    if rgb.dtype!=torch.float32 or z.dtype!=torch.float32:raise ValueError('expected original FP32 prepared/normalized tensors')
    if not bool(torch.isfinite(rgb).all()) or float(rgb.min())<0 or float(rgb.max())>1:raise ValueError('prepared RGB invalid')
    if not bool(torch.isfinite(z).all()):raise ValueError('nonfinite cached clean reference')
    return rgb,z,{'condition_path':str(condition),'condition_sha256':sha(condition),'run_id':c['run_id'],
                  'prepared_RGB_path':str(paths[0]),'prepared_RGB':rgb_meta,'cached_latent_path':str(paths[1]),'cached_latent':z_meta,
                  'input_video':c['input_video'],'copy_or_modify_audit_input':False}


def admit_gpu(uuid):
    if uuid!=HOST41_GPU:raise ValueError('this staged diagnostic is pinned to .41 GPU1; no other GPU is admitted')
    all_rows=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True)
    for row in all_rows.splitlines():
        if not row.strip():continue
        gpu,pid=[x.strip() for x in row.split(',')]
        try:uid=(Path('/proc')/pid).stat().st_uid
        except FileNotFoundError:continue
        if gpu==uuid or uid==os.getuid():raise RuntimeError('selected GPU or another owned GPU process is active; wait for root cleanup')
    row=subprocess.check_output(['nvidia-smi','--id='+uuid,'--query-gpu=uuid,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip().split(',')
    if len(row)!=3 or row[0].strip()!=uuid or int(row[1])>64 or int(row[2])!=0:raise RuntimeError('selected GPU is not idle')
    if int(dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())['MemAvailable'].split()[0])<20*1024*1024:raise RuntimeError('less than20GiB host RAM available')
    return {'gpu_uuid':uuid,'memory_used_mib':int(row[1]),'utilization_percent':int(row[2]),'owned_compute_processes_before_start':0}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--condition',type=Path,required=True);p.add_argument('--audit-root',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--execute',action='store_true')
    p.add_argument('--core',type=Path);p.add_argument('--runtime-deps',type=Path);p.add_argument('--bootstrap',type=Path)
    p.add_argument('--vae',type=Path);p.add_argument('--gpu-uuid')
    args=p.parse_args()
    # Bind before any torch/Comfy import; CPU validation never sees a GPU.
    os.environ['CUDA_VISIBLE_DEVICES']=args.gpu_uuid if args.execute and args.gpu_uuid else ''
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    import torch
    torch.set_num_threads(1)
    if torch.cuda.is_initialized():raise RuntimeError('CUDA initialized before admission')
    out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=False)
    rgb,cached,input_meta=validate_inputs(args.condition.resolve(),args.audit_root.resolve())
    source_audit=json.loads((HERE/'source_audit.json').read_text())
    record={'schema':'h3-vae-temporal-controls-v1','status':'validated_inputs','script_sha256':sha(__file__),
            'source_audit_sha256':sha(HERE/'source_audit.json'),'pid':os.getpid(),'uid':os.getuid(),
            'started_unix':time.time(),'torch':torch.__version__,'inputs':input_meta,
            'frozen_arms':list(ARMS),'constant_frame_index':0,'delay_padding':'repeat original first frame; truncate tail; no wrap/interpolation',
            'geometry':[141,736,1312,3],'position_bins':time_geometry()[0],'fps':24,'arms':[],
            'scope':'Encoder representation controls only; no DiT/Qwen/audio/model or controller change'}
    atomic_json(out/'execution.json',record)
    if not args.execute:
        print(json.dumps({'status':'CPU inputs verified; no encode/GPU','record':str(out/'execution.json')}));return
    if not all((args.core,args.runtime_deps,args.bootstrap,args.vae,args.gpu_uuid)):p.error('execute requires core, runtime-deps, bootstrap, vae and gpu-uuid')
    for relative,expected in source_audit['core_sha256'].items():
        if sha(args.core/relative)!=expected:raise ValueError('unreviewed actual core differs: '+relative)
    if sha(args.vae)!=source_audit['vae_checkpoint_sha256']:raise ValueError('VAE checkpoint hash mismatch')
    record['core']={'path':str(args.core.resolve()),'sha256':source_audit['core_sha256']}
    record['vae']={'path':str(args.vae.resolve()),'sha256':source_audit['vae_checkpoint_sha256']}
    record['bootstrap']={'path':str(args.bootstrap.resolve()),'sha256':sha(args.bootstrap)}
    record['gpu_admission']=admit_gpu(args.gpu_uuid)
    sys.path[:0]=[str(args.runtime_deps.resolve()),str(args.core.resolve())]
    spec=importlib.util.spec_from_file_location('h3_vae_control_bootstrap',args.bootstrap);compat=importlib.util.module_from_spec(spec);spec.loader.exec_module(compat)
    compat.install()
    import comfy.cli_args
    comfy.cli_args.args.disable_dynamic_vram=True;comfy.cli_args.args.disable_cuda_malloc=True
    comfy.cli_args.args.use_pytorch_cross_attention=True;comfy.cli_args.args.enable_triton_backend=True
    admit_gpu(args.gpu_uuid)
    import comfy.sd
    import comfy.utils
    import comfy.model_management
    record['status']='encoding';atomic_json(out/'execution.json',record)
    vae=state=pixels=z=actual=None
    def terminated(signum,frame):raise KeyboardInterrupt('received signal '+str(signum))
    signal.signal(signal.SIGTERM,terminated)
    try:
        if torch.cuda.device_count()!=1:raise RuntimeError('expected exactly one visible GPU')
        state,metadata=comfy.utils.load_torch_file(str(args.vae),return_metadata=True)
        vae=comfy.sd.VAE(sd=state,metadata=metadata,dtype=torch.float16);vae.throw_exception_if_invalid();state=None
        actual=vae.first_stage_model
        if not isinstance(actual,comfy.ldm.minimax.vae.MiniMaxH3VideoVAE):raise ValueError('not H3 video VAE')
        constants={name:getattr(actual,name) for name in ('clip_length','token_drop','vae_ratio_t','tokens_chunk_size','tile_size','tile_overlap_min','tiling')}
        if constants!={'clip_length':17,'token_drop':3,'vae_ratio_t':4,'tokens_chunk_size':5,'tile_size':256,'tile_overlap_min':64,'tiling':True}:raise ValueError('actual VAE chunking differs')
        record['actual_VAE_constants']=constants;record['vae_dtype']=str(vae.vae_dtype)
        if vae.vae_dtype!=torch.float16:raise ValueError('expected original FP16 VAE compute')
        # Native H3 handles spatial tiling internally. Reject wrapper OOM fallback so four arms keep identical path.
        def refuse_fallback(*a,**k):raise RuntimeError('wrapper OOM fallback refused; preserve existing frozen tiling path')
        vae._encode_tiled_owned=refuse_fallback
        for arm in ARMS:
            pixels=control_pixels(rgb,arm);before=tensor_info(pixels);torch.cuda.reset_peak_memory_stats();started=time.time()
            with torch.inference_mode():z=vae.encode(pixels).detach().cpu()
            torch.cuda.synchronize()
            if list(z.shape)!=[1,24,42,46,82] or z.dtype!=torch.float32 or not bool(torch.isfinite(z).all()):raise ValueError('invalid native encode output')
            item={'arm':arm,'pixel_indices':indices_for(arm),'input_tensor':before,'latent':tensor_info(z),
                  'encode_seconds':time.time()-started,'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),
                  'peak_cuda_reserved_bytes':torch.cuda.max_memory_reserved()}
            if tensor_info(pixels)!=before:raise ValueError('VAE modified prepared control pixels')
            if arm=='original':
                delta=z-cached;item['cache_comparison']={'bitwise_equal':torch.equal(z,cached),
                    'actual_hash_equal':item['latent']['sha256']==input_meta['cached_latent']['sha256'],
                    'max_abs_error':float(delta.abs().max()),'rms_error':float(delta.square().mean().sqrt())}
                if not item['cache_comparison']['bitwise_equal'] or not item['cache_comparison']['actual_hash_equal']:
                    record['arms'].append(item);raise RuntimeError('original does not reproduce supplied same-host cached reference; no shifted controls encoded')
            exclusive_save(out/(arm+'.pt'),z);item['file_sha256']=sha(out/(arm+'.pt'));record['arms'].append(item)
            atomic_json(out/'execution.json',record);pixels=z=None;gc.collect()
        expected={k:input_meta['prepared_RGB'][k] for k in ('shape','dtype','sha256')}
        if tensor_info(rgb)!=expected:raise ValueError('source prepared RGB changed')
        record['status']='encodes_complete'
    except BaseException as error:
        record['status']='failed';record['error']=f'{type(error).__name__}: {error}';raise
    finally:
        pixels=z=state=vae=actual=None
        comfy.model_management.unload_all_models();gc.collect();comfy.model_management.soft_empty_cache()
        record['finished_encode_unix']=time.time();record['cuda_reserved_bytes_after_cleanup']=torch.cuda.memory_reserved()
        atomic_json(out/'execution.json',record)
    rgb=cached=None;gc.collect()
    try:
        result=analyze_saved(out);atomic_json(out/'RESULTS.json',result)
    except BaseException as error:
        record['status']='analysis_failed';record['error']=f'{type(error).__name__}: {error}'
        atomic_json(out/'execution.json',record);raise
    record['status']='complete';record['finished_unix']=time.time();atomic_json(out/'execution.json',record)
    print(json.dumps({'status':'complete','output':str(out),'result_sha256':sha(out/'RESULTS.json')}))


if __name__=='__main__':main()
