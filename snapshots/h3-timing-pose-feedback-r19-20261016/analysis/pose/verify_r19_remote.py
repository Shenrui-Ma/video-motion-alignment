"""Independent CPU completion wrapper. Does not import a model or start a GPU."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
RUN='r19_s05_pose_observer'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(root,run):
    root=Path(root);assert run==RUN
    here=root/'analysis/pose';binding=json.loads((here/'expected_service_binding.json').read_text())
    service=json.loads((root/'processes/service.json').read_text())
    assert service['pid']==binding['pid'] and int(service['identity']['uid'])==binding['uid'] and str(service['identity']['start_ticks'])==str(binding['start_ticks'])
    # This inherited service registry stores space-separated cmdline plus exact argv.
    assert service['identity']['cmdline']==' '.join(service['command'])+' '
    command_sha=hashlib.sha256(('\0'.join(service['command'])+'\0').encode()).hexdigest()
    assert command_sha==binding['cmdline_sha256']
    assert service['gpu_uuid']==binding['gpu_uuid'] and service['port']==8479
    assert sha(root/'configs/admission.json') in binding['authorized_admission_sha256']
    started=time.time();manifest=root/'deploy_manifest_v1.json';assert sha(manifest)==binding['manifest_sha256']
    seal=json.loads(manifest.read_text());assert len(seal['files'])==binding['sealed_file_count']
    for rel,row in seal['files'].items():
        p=root/rel;assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],rel
    dest=here/'replication';dest.mkdir(parents=True,exist_ok=True)
    official=dest/(run+'_official_completed_gate.json')
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4')
    done=subprocess.run([sys.executable,str(root/'scripts/verify_completed.py'),'--root',str(root),'--output',str(official)],env=env,text=True,capture_output=True)
    (dest/(run+'_official_completed_gate.log')).write_text(done.stdout+'\n'+done.stderr)
    if done.returncode:raise RuntimeError('Sealed official completion verifier failed; retain log/gate before interpretation')
    gate=json.loads(official.read_text());assert gate['status']=='pass' and gate['cleanup_verified']
    conditions=json.loads((root/'audit'/f'{run}_conditioning.json').read_text());noise=json.loads((root/'audit'/f'{run}_noise.json').read_text())
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(4)
    sys.path.insert(0,str(root/'extensions'))
    from H3X0Readout.core import tensor_signature as sig
    npath=Path(noise['cache_file']);assert npath.resolve().is_relative_to((root/'audit').resolve())
    cache=torch.load(npath,map_location='cpu',weights_only=True);assert cache['signature']==noise['signature'] and len(cache['tensors'])==2
    for v,s in zip(cache['tensors'],noise['actual_noise_streams']):assert torch.isfinite(v).all() and all(sig(v)[k]==x for k,x in s.items())
    refs=[]
    for row in conditions['native_vae_calls']:
        s=row['latent'];p=root/'audit'/s['tensor_file'];v=torch.load(p,map_location='cpu',weights_only=True)
        assert torch.isfinite(v).all() and all(sig(v)[k]==x for k,x in s.items() if k!='tensor_file')
        refs.append({'path':str(p),'file_sha256':sha(p),'actual_tensor':sig(v)})
    audit=json.loads((root/'audit/counterfactual'/f'{run}.json').read_text());c=audit['counterfactual'];branches=c['branches']
    assert [r['nfe_index'] for r in branches]==list(range(gate['NFE']))
    for m in c['measurements']:
        response=json.loads(Path(m['response_file']).read_text())
        assert response['admission_sha256'] in binding['authorized_admission_sha256']
    inventory=[];metadata_keys=('physical_index','branch','nfe_index','sigma','sigma_next','raw_stream_signatures','seed','condition_sha256','reference_sha256')
    for row in branches:
        p=Path(row['file']);assert p.resolve().is_relative_to((root/'audit/counterfactual').resolve()) and sha(p)==row['file_sha256']
        v=torch.load(p,map_location='cpu',weights_only=True)
        assert set(v)=={'video','audio','metadata'} and v['metadata']=={k:row[k] for k in metadata_keys}
        for name,shape in [('video',(1,24,42,46,82)),('audio',(1,32,2,235))]:
            assert v[name].dtype==torch.float32 and tuple(v[name].shape)==shape and torch.isfinite(v[name]).all()
        assert [sig(v[k]) for k in ('video','audio')]==row['normalized_stream_signatures']
        assert [sig(v['video']),sig(v['audio']*4)]==row['raw_stream_signatures']
        inventory.append({'file':str(p),'sha256':row['file_sha256'],'physical_index':row['physical_index'],'branch':row['branch'],'finite':True,'metadata_exact':True})
    # Separate post-run tensor recheck from the live assertions recorded by core.
    historical=[]
    parent=json.loads((root/'configs/parent_r10_audit.json').read_text())['counterfactual']
    for n,b in [(5,'native'),(10,'native')]+([(10,'full')] if 10 in gate['mask'] else []):
        row=next(r for r in branches if (r['physical_index'],r['branch'])==(n,b))
        old=next(r for r in parent['branches'] if (r['physical_index'],r['branch'])==(n,b))
        assert sha(old['file'])==old['file_sha256']
        a=torch.load(row['file'],map_location='cpu',weights_only=True);z=torch.load(old['file'],map_location='cpu',weights_only=True)
        assert all(torch.equal(a[k],z[k]) for k in ('video','audio'))
        historical.append({'physical_index':n,'branch':b,'parent':'R10','AV_tensor_equal':True,'actual_sha256':row['file_sha256'],'parent_sha256':old['file_sha256']})
    assert not torch.cuda.is_initialized()
    out={'passed':True,'run_id':run,'manifest_sha256':binding['manifest_sha256'],'sealed_file_count':binding['sealed_file_count'],
         'official_completed_gate_path':str(official),'official_completed_gate_sha256':sha(official),'official_gate':gate,
         'actual_noise_file_sha256':sha(npath),'actual_reference_inventory':refs,'actual_branch_inventory':inventory,'independent_prefix_recheck':historical,
         'actual_NFE':gate['NFE'],'sampler_updates':20,'callbacks':20,'routed_blocks':50*len(gate['mask']),'active_indices':gate['mask'],
         'same_fixed_mask_as_R18':gate['mask']==list(range(6,12)),
         'measurement_decisions':[dict(physical_index=s['physical_index'],**{k:v for k,v in s['decision'].items() if k!='physical_index'}) for s in c['steps']],
         'observer_wall_seconds':sum(m['wall_seconds'] for m in c['measurements']),
         'cpu_seconds':time.time()-started,'no_GPU_started':True,'scope':'Known development case. Post-run inventory/prefix evidence is distinct from runtime G2/G3 and does not establish final timing or generalization.'}
    (dest/(run+'_integrity.json')).write_text(json.dumps(out,indent=2)+'\n');return out
