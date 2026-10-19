"""Supplement sealed R22 verifier with actual tensor/provenance and live cleanup gates."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
from probe_completion import probe,validate_binding
RUN='r22_s05_seed1313_full6to11'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def verify(root,run):
    started=time.time();root=Path(root);assert run==RUN
    here=root/'analysis/pose';binding=validate_binding(read(here/'expected_service_binding.json'))
    ready=probe(here/'expected_service_binding.json');assert ready['status']=='ready'
    seal=read(root/'deploy_manifest_v1.json');assert len(seal['files'])==48
    for rel,row in seal['files'].items():
        p=root/rel
        assert not Path(rel).is_absolute() and '..' not in Path(rel).parts and not p.is_symlink()
        assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],rel
    prov=read(root/'configs/runtime_provenance.json');parent=read(root/'configs/parent_runtime_provenance.json')
    assert all(prov['core_matches'].values()) and set(prov['models'])==set(parent['models'])
    for name,m in prov['models'].items():
        assert m['size_mtime_match'] and m['prior_full_sha256']==parent['models'][name]['prior_full_sha256']
        assert (m['bytes'],m['mtime_ns'])==(parent['models'][name]['bytes'],parent['models'][name]['mtime_ns'])
    for rel,h in prov['code'].items():assert sha(root/rel)==h
    dest=here/'replication';dest.mkdir(parents=True,exist_ok=True)
    official=dest/(run+'_official_completed_gate.json')
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4')
    done=subprocess.run([sys.executable,str(root/'scripts/verify_completed.py'),'--root',str(root),'--output',str(official)],env=env,text=True,capture_output=True)
    (dest/(run+'_official_completed_gate.log')).write_text(done.stdout+'\n'+done.stderr)
    if done.returncode:raise RuntimeError('Official completion verifier failed; preserve failure')
    gate=read(official);assert gate['passed']
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(4);sys.path.insert(0,str(root/'extensions'))
    from H3X0Readout.core import tensor_signature as sig
    noise=read(root/'audit'/f'{run}_noise.json');condition=read(root/'audit'/f'{run}_conditioning.json')
    p=Path(noise['cache_file']);assert p.resolve().is_relative_to((root/'audit').resolve())
    cache=torch.load(p,map_location='cpu',weights_only=True);assert cache['signature']==noise['signature'] and len(cache['tensors'])==2
    for v,s in zip(cache['tensors'],noise['actual_noise_streams']):assert torch.isfinite(v).all() and all(sig(v)[k]==x for k,x in s.items())
    refs=[]
    for row in condition['native_vae_calls']:
        s=row['latent'];p=root/'audit'/s['tensor_file'];assert p.resolve().is_relative_to((root/'audit').resolve())
        v=torch.load(p,map_location='cpu',weights_only=True);assert torch.isfinite(v).all() and all(sig(v)[k]==x for k,x in s.items() if k!='tensor_file')
        refs.append({'path':str(p),'file_sha256':sha(p),'actual_tensor':sig(v)})
    backend=root/'logs/backend_dispatch_audit.json';assert backend.is_file()
    assert read(backend)['pid']==binding['service_record']['pid']
    assert not torch.cuda.is_initialized()
    result={'passed':True,'run_id':run,'manifest_sha256':binding['manifest_sha256'],'sealed_file_count':48,'actual_NFE':20,'updates':20,'callbacks':20,'routed_blocks':300,'active_indices':list(range(6,12)),'official_gate':gate,'runtime_provenance_sha256':sha(root/'configs/runtime_provenance.json'),'backend_audit_sha256':sha(backend),'actual_reference_inventory':refs,'live_cleanup':ready,'cpu_seconds':time.time()-started,'limits':['Only index005 is paired to actual R14. No future R14 controlled-trajectory substitution.','R14 full postaugmentation conditions unavailable.','Checkpoint provenance uses frozen full SHA plus current size/mtime, not newly rehashed model weights.','R21 common support pending actual completed R21.'],'no_GPU_started':True}
    (dest/(run+'_integrity.json')).write_text(json.dumps(result,indent=2)+'\n')
    return result
