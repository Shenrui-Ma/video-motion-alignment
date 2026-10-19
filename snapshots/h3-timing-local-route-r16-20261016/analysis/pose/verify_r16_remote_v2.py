"""Independent completed R16 execution/input/capture audit; CPU only."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def verify(root,run):
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(4)
    def sig(t):return {'shape':list(t.shape),'dtype':str(t.dtype),'bytes':t.numel()*t.element_size(),'sha256':hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()}
    started=time.time();root=Path(root)
    variant={'r16_s05_roi_6to14':'roi','r16_s05_uniform_6to14':'uniform'}[run]
    read=lambda p:json.loads((root/p).read_text())
    protocol=read('configs/protocol.json');g=read('configs/'+run+'.json');h=read('logs/'+run+'_history.json')
    assert h['status']['status_str']=='success' and h['status']['completed'] and h['prompt'][2]==g
    audit=read('audit/router/'+run+'.json');local=audit['local_query_gain']
    # Frozen router retains "sampling" after its last block. Completion is
    # established by successful exact history, all 20x50 calls, and the recorder.
    assert audit['status']=='sampling' and audit['run_id']==run and audit['mode']=='mass_preserve'
    assert audit['alpha']==1 and audit['radius']==audit['time_offset']==0
    assert audit['step_interval_half_open']==[6,15] and audit['block_interval_half_open']==[0,50]
    assert audit['pixel_interval_inclusive']==[50,65]
    assert audit['completed_forward_calls']==20 and audit['completed_calls']==audit['started_calls']==1000
    assert audit['calls_by_forward']==[50]*20 and audit['routed_calls']==450
    assert audit['routed_by_forward']==[50 if 6<=n<15 else 0 for n in range(20)]
    assert audit['routed_by_block']==[9]*50
    assert local['variant']==variant and local['no_new_model_prediction'] and local['zero_rows_written'] is False
    assert local['expected_model_calls']==local['expected_euler_updates']==20
    assert local['mask_file_sha256']==protocol['source_query_mask_file_sha256']==sha(root/'configs/source_query_mask.json')
    assert local['actual_clean_reference_sha256']==protocol['reference_clean_tensor_sha256']
    assert g['50']['inputs']['mask_variant']==variant and g['50']['inputs']['mask_sha256']==local['mask_file_sha256']
    assert g['8']['inputs']['sampler_name']=='euler' and g['7']['class_type']=='BasicGuider'
    condition=read('audit/'+run+'_conditioning.json');parent=read('configs/parent_full_conditioning.json')
    condition_checks={k:condition[k]==parent[k] for k in ('prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion','conditioning_embedding','token_tags','target_latent_shapes','packed_layout')}
    assert all(condition_checks.values()),condition_checks
    noise=read('audit/'+run+'_noise.json');pn=read('configs/parent_full_noise.json')
    assert noise['signature']==pn['signature'] and noise['actual_noise_streams']==pn['actual_noise_streams']
    assert noise['signature']['seed']==2026101311
    path=Path(noise['cache_file']);assert path.resolve().is_relative_to((root/'audit').resolve())
    nd=torch.load(path,map_location='cpu',weights_only=True);assert nd['signature']==noise['signature'] and len(nd['tensors'])==2
    for t,s in zip(nd['tensors'],noise['actual_noise_streams']):assert torch.isfinite(t).all() and all(sig(t)[k]==v for k,v in s.items())
    packed_noise=sig(torch.cat([t.reshape(1,1,-1) for t in nd['tensors']],-1))
    ref_inventory=[]
    for row in condition['native_vae_calls']:
        s=row['latent'];p=root/'audit'/s['tensor_file'];t=torch.load(p,map_location='cpu',weights_only=True)
        assert torch.isfinite(t).all() and all(sig(t)[k]==v for k,v in s.items() if k!='tensor_file')
        ref_inventory.append({'path':str(p),'sha256':sha(p),'tensor':sig(t)})
    folder=root/'audit/x0'/run;m=json.loads((folder/'manifest.json').read_text());indices=[5,6,7,8,9,10,15,19]
    assert m['status']=='complete' and m['run_id']==run and m['seed']==2026101311
    assert m['expected_callback_count']==m['callback_count']==20
    assert m['capture_steps_zero_based']==indices and [r['step_zero_based'] for r in m['captures']]==indices
    assert m['sigmas_video']==audit['sample_sigmas'] and m['noise']==packed_noise
    entries=m['captures']+[m['final_sampler_result']]
    assert [r['file'] for r in entries]==[f'x0_step{n:03d}.pt' for n in indices]+['sampler_final.pt']
    assert {p.name for p in folder.glob('*.pt')}=={r['file'] for r in entries} and len(entries)==9
    inventory=[]
    for row in entries:
        p=folder/row['file'];d=torch.load(p,map_location='cpu',weights_only=True)
        assert set(d)=={'video','audio','metadata'} and all(row[k]==v for k,v in d['metadata'].items())
        assert d['metadata']['normalization_stage']=='after_process_latent_out' and d['metadata']['geometry']=={'width':1312,'height':736,'frames':141,'fps':24}
        for name,shape in [('video',[1,24,42,46,82]),('audio',[1,32,2,235])]:
            t=d[name];assert list(t.shape)==shape and t.dtype==torch.float32 and torch.isfinite(t).all() and sig(t)==row[name]
        inventory.append({'path':str(p),'sha256':sha(p),'video':row['video'],'audio':row['audio'],'finite':True})
    parent_root=Path('/data5/researcher/h3_runs/timing_spatial_r3_20261016')
    previous=torch.load(parent_root/'audit/x0/r3_s05_full_6to14/x0_step005.pt',map_location='cpu',weights_only=True)
    current=torch.load(folder/'x0_step005.pt',map_location='cpu',weights_only=True)
    prefix={name:torch.equal(previous[name],current[name]) for name in ('video','audio')}
    assert all(prefix.values()),prefix
    comfy=Path('/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI')
    core=read('configs/parent_core_hashes.json');assert {p:sha(comfy/p) for p in core}==core
    bundle_path=root/'deploy_manifest_v1.json';bundle=json.loads(bundle_path.read_text())
    expected_hashes={p:row['sha256'] for p,row in bundle['files'].items()}
    assert len(expected_hashes)==63
    actual_bundle={p:sha(root/p) for p in bundle['files']}
    admission_change=read('audit/r17_parallel_admission_update.json')
    assert admission_change['field_changed']=='permitted_compute_processes'
    assert admission_change['old_sha256']==expected_hashes['configs/admission.json']=='fe7295a1015556a9f939538648dce8b9493f6a326f1c439b4ffd50230b6ac15e'
    assert admission_change['new_sha256']==actual_bundle['configs/admission.json']=='bc780c5042e1a1bb42164e0a2f649af85cbf6833a4f9e3cd5e3bc1193570197a'
    current_admission=read('configs/admission.json')
    assert current_admission==admission_change['new']
    assert admission_change['old']=={'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]}
    expected_admission=dict(admission_change['old'],permitted_compute_processes=[{'pid':5985,'identity':{'uid':1016,'start_ticks':'2618526185','cmdline_sha256':'5df03b3b3467a1bc9134c70f78fc49a5e69d8379a071ebfcbd9c12493035ccb9'}}])
    assert current_admission==expected_admission
    expected_bundle=dict(expected_hashes,**{'configs/admission.json':admission_change['new_sha256']})
    assert actual_bundle==expected_bundle
    out={'passed':True,'run_id':run,'variant':variant,'actual_NFE':20,'sampler_updates':20,'callbacks':20,
         'completed_blocks':1000,'routed_blocks':450,'active_indices':list(range(6,15)),
         'actual_condition_checks':condition_checks,'actual_noise_equal_R3':True,'actual_noise_file_sha256':sha(path),
         'packed_noise':packed_noise,'actual_reference_inventory':ref_inventory,'prefix005_equal_R3_full':prefix,
         'capture_indices':indices,'capture_inventory':inventory,'mask_audit':local,
         'protocol_sha256':sha(root/'configs/protocol.json'),'bundle_sha256':sha(bundle_path),'core_sha256':core,
         'administrative_admission_change':admission_change,'all_other_bundle_files_unchanged':True,
         'router_status_semantics':'Frozen router ends with sampling; complete success is independently bound to executed history, 20x50 calls, and complete 20-callback recorder.',
         'cpu_seconds':time.time()-started,'no_GPU_started':True,
         'dose_limit':'Equal sum of source mask alpha per bin is not equal attention-mass-weighted correction dose.',
         'scope':'One known development source/seed; finite/runtime integrity is not visual efficacy.'}
    dest=root/'analysis/pose/replication'/(run+'_integrity.json');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(out,indent=2)+'\n')
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('run');a=p.parse_args()
    with Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=verify(a.root,a.run)
    print(json.dumps({'passed':result['passed'],'run':a.run,'actual_NFE':20,'routed_blocks':450}))
