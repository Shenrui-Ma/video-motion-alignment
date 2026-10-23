"""CPU-only reconstruction from historical full AV Euler x0, never a model replay."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import math
import torch

SCHEMA = 'h3-signed-phase-reconstructed-state-v1'

def tensor_info(x):
    x=x.detach().to('cpu').contiguous()
    return dict(shape=list(x.shape),dtype=str(x.dtype),sha256=hashlib.sha256(x.view(torch.uint8).numpy().tobytes()).hexdigest(),finite=bool(torch.isfinite(x).all()))

def file_sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def validate_leaf(x,shape=None):
    if not isinstance(x,torch.Tensor) or x.dtype != torch.float32 or x.device.type != 'cpu':
        raise ValueError('only CPU float32 full streams are supported')
    if shape is not None and list(x.shape)!=list(shape): raise ValueError('stream shape mismatch')
    if not bool(torch.isfinite(x).all()): raise ValueError('nonfinite stream')

def pack(streams):
    if len(streams)!=2: raise ValueError('video+audio required')
    for x in streams: validate_leaf(x)
    if any(x.shape[0]!=1 for x in streams): raise ValueError('batch1 required')
    return torch.cat([x.reshape(1,1,-1) for x in streams],dim=-1)

def unpack(packed,shapes):
    if packed.ndim!=3 or packed.shape[:2]!=(1,1): raise ValueError('bad packed shape')
    if packed.numel()!=sum(math.prod(s) for s in shapes): raise ValueError('bad packed length')
    return [v.reshape(s) for v,s in zip(packed.split([math.prod(s) for s in shapes],dim=-1),shapes)]

def raw_x0(saved,audio_scale):
    if audio_scale != 4.0: raise ValueError('audited original audio_scale must be 4')
    video,audio=saved['video'],saved['audio']
    validate_leaf(video);validate_leaf(audio)
    # Recorder applies a binary-exact factor 1/4; reverse it before shared-sigma Euler.
    return pack([video,audio*audio_scale])

def sigma_grid(values):
    s=torch.tensor(values,dtype=torch.float32)
    if s.ndim!=1 or s.numel()!=21 or not bool(torch.isfinite(s).all()): raise ValueError('Euler20 grid required')
    if s[0].item()!=1 or s[-1].item()!=0 or not bool((s[:-1]>s[1:]).all()): raise ValueError('full strict 1-to-0 grid required')
    if s.double().tolist()!=list(values): raise ValueError('manifest must contain exact historical FP32 sigma values')
    return s

def initialize(noise, *, noise_scale, initial_sigma):
    if noise_scale != 1.0 or float(initial_sigma)!=1.0:
        raise ValueError('only verified original noise_scale1 sigma0=1 supported')
    # Original CONST.noise_scaling: sigma*(noise_scale*noise)+(1-sigma)*latent.
    # At sigma0=1 any finite initial latent cancels. Denoise masks are separately rejected.
    return initial_sigma*(noise_scale*noise)+(1.0-initial_sigma)*torch.zeros_like(noise)

def euler_update(x,denoised,sigma,sigma_next):
    # Exact operation order of actual Comfy sample_euler/to_d; audio ALSO uses video sigma.
    d=(x-denoised)/sigma.view(1,1,1)
    dt=sigma_next-sigma
    return x+d*dt

def _compare(a,b):
    d=(a.double()-b.double())
    return dict(exact_equal=torch.equal(a,b),max_abs=float(d.abs().max()),mean_abs=float(d.abs().mean()),rms=float(d.square().mean().sqrt()))

def reconstruct_row(row,outdir,*,save_states=True):
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=False)
    cap=Path(row['capture_dir']);mp=cap/'manifest.json'
    if file_sha(mp)!=row['manifest_sha256']: raise ValueError('capture manifest identity mismatch')
    m=json.loads(mp.read_text())
    if m['schema']!='h3-x0-readout-v1' or m['status']!='complete' or m['sampler']!='sample_euler' or m['callback_count']!=20:
        raise ValueError('incomplete or unsupported historical capture')
    if m['normalization_stage']!='after_process_latent_out' or m['video_latent_scale_factor']!=1 or m['audio_scale']!=4:
        raise ValueError('unverified AV normalization')
    if [c['step_zero_based'] for c in m['captures']]!=list(range(20)): raise ValueError('capture sequence mismatch')
    s=sigma_grid(m['sigmas_video']);shapes=m['target_latent_shapes']
    n=torch.load(row['noise_path'],map_location='cpu',weights_only=True)
    if n['signature'].get('seed')!=m['seed'] or not n['signature'].get('nested'): raise ValueError('noise signature mismatch')
    ns=n['tensors']
    for x,shape,expected in zip(ns,shapes,row['noise_streams']):
        validate_leaf(x,shape)
        if tensor_info(x)['sha256']!=expected['sha256']: raise ValueError('noise content mismatch')
    pnoise=pack(ns)
    if tensor_info(pnoise)['sha256']!=m['noise']['sha256']: raise ValueError('noise differs from original packed sampler input')
    x=initialize(pnoise,noise_scale=1.0,initial_sigma=s[0])
    trace=[];states=[]
    for i,c in enumerate(m['captures']):
        xp=cap/c['file'];saved=torch.load(xp,map_location='cpu',weights_only=True)
        metadata=saved['metadata']
        for key in ('schema','run_id','total_steps','audio_scale','video_latent_scale_factor','geometry','seed','normalization_stage'):
            if metadata[key]!=c[key]:raise ValueError('x0 metadata identity mismatch: '+key)
        if metadata['step_zero_based']!=i or metadata['sigma_video']!=float(s[i]) or metadata['sigma_next_video']!=float(s[i+1]): raise ValueError('x0 step/sigma mismatch')
        for name,shape in zip(('video','audio'),shapes):
            validate_leaf(saved[name],shape)
            if tensor_info(saved[name])['sha256']!=c[name]['sha256']: raise ValueError('x0 tensor identity mismatch')
        denoised=raw_x0(saved,4.0)
        rec=dict(step=i,sigma_video=float(s[i]),sigma_next_video=float(s[i+1]),state=tensor_info(x),x0_file_sha256=file_sha(xp),x0_raw=tensor_info(denoised))
        if save_states and i in row['selected_steps']:
            target=outdir/f'state_step{i:03d}.pt'
            payload=dict(schema=SCHEMA,packed_x=x.clone(),shapes=shapes,step_zero_based=i,sigma_video=float(s[i]),sigmas_video=m['sigmas_video'],audio_scale=4.0,normalization='raw sampler carry; video unscaled/audio carried on VIDEO sigma',historical_x0_file=str(xp),historical_x0_file_sha256=rec['x0_file_sha256'],manifest_sha256=row['manifest_sha256'],noise_sha256=tensor_info(pnoise)['sha256'])
            torch.save(payload,target)
            states.append(dict(step=i,file=str(target),sha256=file_sha(target),packed_x=rec['state']))
        x=euler_update(x,denoised,s[i],s[i+1])
        if not bool(torch.isfinite(x).all()): raise ValueError('nonfinite reconstructed state')
        trace.append(rec)
    # CONST.inverse_noise_scaling at terminal sigma=0 is identity, but retain the division.
    final=x/(1.0-s[-1]);v,a=unpack(final,shapes);normalized=[v,a*(1/4.0)]
    fp=cap/'sampler_final.pt';historical_final=torch.load(fp,map_location='cpu',weights_only=True)
    for name,shape in zip(('video','audio'),shapes):
        validate_leaf(historical_final[name],shape)
        if tensor_info(historical_final[name])['sha256']!=m['final_sampler_result'][name]['sha256']:raise ValueError('final sampler tensor identity mismatch')
    for key in ('snapshot_kind','sigma_video','sigma_audio','audio_scale','geometry','seed','normalization_stage'):
        if historical_final['metadata'][key]!=m['final_sampler_result'][key]:raise ValueError('final sampler metadata mismatch')
    endpoint={k:_compare(t,historical_final[k]) for k,t in zip(('video','audio'),normalized)}
    result=dict(schema=SCHEMA,case=row['case'],method=row['method'],cuda_initialized=torch.cuda.is_initialized(),source_manifest_sha256=row['manifest_sha256'],noise_file_sha256=file_sha(row['noise_path']),state_files=states,trace=trace,endpoint_comparison=endpoint,original_final_file_sha256=file_sha(fp),reconstruction_arithmetic='actual FP32 Euler operation order; packed complete AV; audio x0 multiplied by4',status='cpu_reconstructed_pending_same_state_forward',historical_intermediate_noisy_state_available=False,passive_capture_released=False)
    if not all(v['exact_equal'] for v in endpoint.values()): result['status']='cpu_reconstructed_endpoint_difference_requires_review'
    (outdir/'RECONSTRUCTION.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--host-key',required=True);p.add_argument('--output',required=True);p.add_argument('--audit-only',action='store_true');args=p.parse_args()
    torch.set_num_threads(1)
    if torch.cuda.is_initialized(): raise RuntimeError('CPU-only command')
    rows=[r for r in json.loads(Path(args.inputs).read_text())['rows'] if r['host_key']==args.host_key]
    results=[reconstruct_row(r,Path(args.output)/(r['case']+'_'+r['method']),save_states=not args.audit_only) for r in rows]
    print(json.dumps(dict(cuda_initialized=torch.cuda.is_initialized(),rows=results),allow_nan=False))
if __name__=='__main__':main()
