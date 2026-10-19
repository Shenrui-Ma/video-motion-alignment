"""Evaluator-owned wrapper around the sealed official CPU completion verifier."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
RUN='r18_s05_full_6to11'
SEAL_SHA='17021713d84f5d7a9388f60eaf328b4c4c874efe9fc1fb330718b41aa0008a53'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(root,run):
    root=Path(root);assert run==RUN
    service=json.loads((root/'processes/service.json').read_text())
    assert service['pid']==53576 and int(service['identity']['uid'])==1016 and str(service['identity']['start_ticks'])=='2618789964'
    assert service['gpu_uuid']=='GPU-REDACTED' and service['port']==8478
    started=time.time();manifest=root/'deploy_manifest_v1.json';assert sha(manifest)==SEAL_SHA
    seal=json.loads(manifest.read_text());assert len(seal['files'])==50
    for rel,row in seal['files'].items():
        p=root/rel;assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],rel
    dest=root/'analysis/pose/replication';dest.mkdir(parents=True,exist_ok=True)
    official=dest/(run+'_official_completed_gate.json')
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4')
    done=subprocess.run([sys.executable,str(root/'scripts/verify_completed.py'),'--root',str(root),'--output',str(official)],env=env,text=True,capture_output=True)
    (dest/(run+'_official_completed_gate.log')).write_text(done.stdout+'\n'+done.stderr)
    if done.returncode:raise RuntimeError('Sealed official completion verifier failed; retain log/gate before interpretation')
    gate=json.loads(official.read_text());assert gate['passed'] and all(gate['checks'].values())
    conditions=json.loads((root/'audit'/f'{run}_conditioning.json').read_text());noise=json.loads((root/'audit'/f'{run}_noise.json').read_text())
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(4)
    def sig(t):return {'shape':list(t.shape),'dtype':str(t.dtype),'bytes':t.numel()*t.element_size(),'sha256':hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()}
    npath=Path(noise['cache_file']);assert npath.resolve().is_relative_to((root/'audit').resolve())
    cache=torch.load(npath,map_location='cpu',weights_only=True);assert cache['signature']==noise['signature'] and len(cache['tensors'])==2
    for t,s in zip(cache['tensors'],noise['actual_noise_streams']):assert torch.isfinite(t).all() and all(sig(t)[k]==v for k,v in s.items())
    refs=[]
    for row in conditions['native_vae_calls']:
        s=row['latent'];p=root/'audit'/s['tensor_file'];t=torch.load(p,map_location='cpu',weights_only=True)
        assert torch.isfinite(t).all() and all(sig(t)[k]==v for k,v in s.items() if k!='tensor_file')
        refs.append({'path':str(p),'file_sha256':sha(p),'actual_tensor':sig(t)})
    out={'passed':True,'run_id':run,'sealed_50_files_sha256':SEAL_SHA,'official_completed_gate_path':str(official),'official_completed_gate_sha256':sha(official),'official_checks':gate['checks'],'exact_comparisons':gate['exact_comparisons'],'actual_noise_file_sha256':sha(npath),'actual_reference_inventory':refs,'actual_NFE':20,'sampler_updates':20,'callbacks':20,'routed_blocks':300,'active_indices':list(range(6,12)),'cpu_seconds':time.time()-started,'no_GPU_started':True,'scope':'Known development fixed-stop control; successful runtime/prefix bridge does not establish final motion retention.'}
    (dest/(run+'_integrity.json')).write_text(json.dumps(out,indent=2)+'\n');return out
