"""Independent completed R17 provenance, sampler and tensor integrity; CPU only."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

SEAL = 'c1495d4f68e2af821134db34793250fa44f10b482c1ef0d73b097f038d554cab'
RUNS = {'r17_s05_plus4_a05_6to14': 4., 'r17_s05_minus4_a05_6to14': -4.}
PARENT = Path('/data5/researcher/h3_runs/timing_spatial_r3_20261016')
CORE = Path('/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def require(value, label):
    if not value:raise ValueError(label)


def tensor_signature(t):
    import torch
    require(t.device.type=='cpu','signature must inspect CPU tensor')
    value=t.contiguous()
    # Bound temporary host arrays; preparedRGB can exceed1GiB.
    raw=value.view(torch.uint8).reshape(-1);h=hashlib.sha256()
    for part in raw.split(16*1024*1024):h.update(part.numpy())
    return {'shape':list(t.shape),'dtype':str(t.dtype),'bytes':t.numel()*t.element_size(),'sha256':h.hexdigest()}


def verify(root,run):
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(4)
    start=time.monotonic();root=Path(root);delta=RUNS[run]
    read=lambda p:json.loads((root/p).read_text())
    seal=root/'deploy_manifest_v1.json'
    require(sha(seal)==SEAL,'producer seal identity')
    bundle=json.loads(seal.read_text());require(len(bundle['files'])==50,'sealed file count')
    for relative,row in bundle['files'].items():
        p=(root/relative).resolve()
        require(p.is_relative_to(root.resolve()) and p.is_file(),'safe sealed path '+relative)
        require(p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],'sealed file '+relative)
    protocol=read('configs/protocol.json');g=read('configs/'+run+'.json');h=read('logs/'+run+'_history.json')
    require(h['status']['status_str']=='success' and h['status']['completed'] and h['prompt'][2]==g,'actual successful exact graph')
    a=read('audit/phase_rope/'+run+'.json')
    require(a['status']=='complete' and a['run_id']==run and a['alpha']==.5,'completed phase identity')
    require(a['rotation']['delta_physical_frames']==delta and a['rotation']['delta_rope_units']==delta*5/3,'signed phase units')
    require(a['rotation']['rotated_channel_pairs']==[[0,16],[48,64]],'temporal channels')
    require(a['step_interval_half_open']==[6,15] and a['block_interval_half_open']==[0,50] and a['pixel_interval_inclusive']==[50,65],'frozen schedule/window')
    require(a['completed_forward_calls']==20 and a['completed_calls']==a['started_calls']==1000,'actual20NFE1000blocks')
    require(a['calls_by_forward']==[50]*20 and a['calls_by_block']==[20]*50,'complete forward/block lattice')
    require(a['phase_calls']==450 and a['direct_native_calls']==550 and a['native_override_calls']==1000,'actual phase/native call counts')
    require(a['phase_by_forward']==[50 if 6<=i<15 else 0 for i in range(20)] and a['phase_by_block']==[9]*50,'active schedule counts')
    summaries=a['forward_summaries']
    require([s['forward_index'] for s in summaries]==list(range(20)),'ordered forward summaries')
    require(all(s.get('sampled_finite',True) for s in summaries),'sampled finite audit')
    require(a['backend']=='aten._scaled_dot_product_flash_attention.default','explicit backend')
    c=a['model_contract'];require((c['heads'],c['head_dim'],c['attention_inner'],c['hidden_size'],c['num_blocks'])==(56,128,7168,5376,50),'actual architecture')
    require(len(c['layers'])==50 and all(row['projection_sizes']==[5376,21504,7168,5376] for row in c['layers']),'actual all50 projections')
    native=read('configs/parent_native_attention.json')
    require(all(a['first_attention'][key]==native['first_attention'][key] for key in ('qkv_shape','dtype','heads','returned_shape')),'actual attention shape/dtype parent')
    require(a['validated_layout']==native['validated_layout'],'packed layout parent')
    require(g['7']['class_type']=='BasicGuider' and g['8']['inputs']['sampler_name']=='euler','actual sampling graph')
    require(g['50']['inputs']['delta_frames']==delta,'actual graph sign')
    condition=read('audit/'+run+'_conditioning.json');parent=read('configs/parent_full_conditioning.json')
    checks={k:condition[k]==parent[k] for k in ('prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion','conditioning_embedding','token_tags','target_latent_shapes','packed_layout')}
    require(all(checks.values()),'actual conditioning differs: '+repr(checks))
    require(condition['pair_snapshot']['verified'],'actual pair snapshot')
    require(condition['native_vae_calls'][1]['prepared_frames']['sha256']==protocol['expected_reference_prepared_rgb_sha256'],'preparedRGB pin')
    require(condition['native_vae_calls'][1]['latent']['sha256']==protocol['expected_reference_clean_sha256'],'reference latent pin')
    require(a['source_provenance']['actual_reference_clean_sha256']==protocol['expected_reference_clean_sha256'],'phase reference pin')
    reference_inventory=[]
    for row in condition['native_vae_calls']:
        entry={}
        for key in ('prepared_frames','latent'):
            s=row[key];p=(root/'audit'/s['tensor_file']).resolve()
            require(p.is_relative_to((root/'audit').resolve()),'safe reference tensor path')
            t=torch.load(p,map_location='cpu',weights_only=True,mmap=True)
            sig=tensor_signature(t)
            require(all(sig[k]==v for k,v in s.items() if k!='tensor_file'),'actual reference/prepared bytes '+key)
            require(all(bool(torch.isfinite(part).all()) for part in t.reshape(-1).split(4*1024*1024)),'finite reference/prepared')
            entry[key]={'path':str(p),'file_sha256':sha(p),'tensor':sig};del t
        reference_inventory.append(entry)
    noise=read('audit/'+run+'_noise.json');pn=read('configs/parent_full_noise.json')
    require(noise['signature']==pn['signature'] and noise['actual_noise_streams']==pn['actual_noise_streams'],'actual parent noise')
    require(noise['signature']['seed']==2026101311,'actual seed')
    np=Path(noise['cache_file']).resolve();require(np.is_relative_to((root/'audit').resolve()),'noise location')
    nd=torch.load(np,map_location='cpu',weights_only=True,mmap=True)
    require(nd['signature']==noise['signature'] and len(nd['tensors'])==2,'cached noise signature')
    for t,s in zip(nd['tensors'],noise['actual_noise_streams']):
        require(bool(torch.isfinite(t).all()) and all(tensor_signature(t)[k]==v for k,v in s.items()),'actual noise tensor')
    packed=tensor_signature(torch.cat([t.reshape(1,1,-1) for t in nd['tensors']],-1))
    folder=root/'audit/x0'/run;m=json.loads((folder/'manifest.json').read_text());indices=[5,6,7,8,9,10,15,19]
    require(m['status']=='complete' and m['run_id']==run and m['seed']==2026101311,'capture complete identity')
    require(m['callback_count']==m['expected_callback_count']==20 and m['sampler']=='sample_euler','actual20Euler callbacks')
    require(m['capture_steps_zero_based']==indices and [r['step_zero_based'] for r in m['captures']]==indices,'capture indices')
    parentm=read('configs/parent_full_x0_manifest.json')
    require(m['sigmas_video']==a['sample_sigmas']==parentm['sigmas_video'] and m['noise']==packed,'actual same sigma/noise grid')
    require(m['audio_scale']==parentm['audio_scale'] and m['video_latent_scale_factor']==1.,'same output normalization')
    rows=m['captures']+[m['final_sampler_result']]
    names=[f'x0_step{i:03d}.pt' for i in indices]+['sampler_final.pt']
    require([r['file'] for r in rows]==names and {p.name for p in folder.glob('*.pt')}==set(names),'exact nine snapshot set')
    inventory=[]
    for row in rows:
        p=folder/row['file'];d=torch.load(p,map_location='cpu',weights_only=True,mmap=True)
        require(set(d)=={'video','audio','metadata'} and all(row[k]==v for k,v in d['metadata'].items()),'snapshot metadata '+p.name)
        require(d['metadata']['normalization_stage']=='after_process_latent_out' and d['metadata']['geometry']=={'width':1312,'height':736,'frames':141,'fps':24},'snapshot geometry/normalization')
        for name,shape in [('video',[1,24,42,46,82]),('audio',[1,32,2,235])]:
            t=d[name]
            require(list(t.shape)==shape and t.dtype==torch.float32 and bool(torch.isfinite(t).all()) and tensor_signature(t)==row[name],'snapshot tensor '+p.name+'/'+name)
        inventory.append({'path':str(p),'file_sha256':sha(p),'video':row['video'],'audio':row['audio'],'finite':True})
    old=torch.load(PARENT/'audit/x0/r3_s05_full_6to14/x0_step005.pt',map_location='cpu',weights_only=True,mmap=True)
    new=torch.load(folder/'x0_step005.pt',map_location='cpu',weights_only=True,mmap=True)
    prefix={name:torch.equal(old[name],new[name]) for name in ('video','audio')}
    require(all(prefix.values()),'actual pre-intervention prefix005 mismatch '+repr(prefix))
    pins=read('configs/parent_core_hashes.json');require({p:sha(CORE/p) for p in pins}==pins,'actual installed core source')
    require(a['source_provenance']['h3_source_sha256']==pins['comfy/ldm/minimax/model.py'],'phase source pin')
    runtime=read('configs/runtime_provenance.json');pm=read('configs/parent_runtime_provenance.json')['models']
    require(all(runtime['core_matches'].values()),'runtime startup core match')
    for name,row in runtime['models'].items():
        old=pm[name];p=Path(row['path']);st=p.stat()
        require((st.st_size,st.st_mtime_ns)==(old['bytes'],old['mtime_ns']) and row['prior_full_sha256']==old['prior_full_sha256'],'model size/mtime/hash provenance '+name)
    dispatch=read('logs/backend_dispatch_audit.json');pd=json.loads((PARENT/'logs/backend_dispatch_audit.json').read_text())
    successful=lambda d:{k for k,v in d['operations'].items() if v.get('successful_calls',0)>0}
    require(successful(dispatch)==successful(pd)=={'triton.int8_linear'},'actual INT8 backend differs')
    require(all(v.get('failed_calls',0)==0 for v in dispatch['operations'].values()),'backend errors')
    service=read('processes/service.json')
    require(service['pid']==5985 and service['gpu_uuid']=='GPU-REDACTED' and dispatch['pid']==service['pid'],'authorized actual service/GPU')
    messages=h['status'].get('messages',[])
    stamps={kind:data.get('timestamp') for kind,data in messages if isinstance(data,dict)}
    first=stamps.get('execution_start');last=stamps.get('execution_success')
    efficiency={'history_wall_seconds':None if first is None or last is None else (last-first)/1000,
                'snapshot_capture_seconds':sum(x.get('capture_seconds',0) for x in m['captures']),
                'scope':'actual execution/capture records only; no speed diagnosis'}
    require(not torch.cuda.is_initialized(),'CPU verifier initialized CUDA')
    result={'passed':True,'run_id':run,'delta_frames':delta,'actual_NFE':20,'Euler_updates':20,'callbacks':20,
            'completed_blocks':1000,'phase_calls':450,'direct_native_calls':550,'condition_checks':checks,
            'parent_noise_equal':True,'packed_noise':packed,'prefix005_equal_R3':prefix,
            'actual_reference_inventory':reference_inventory,'capture_inventory':inventory,'capture_indices':indices,
            'sealed_files':50,'seal_sha256':sha(seal),'protocol_sha256':sha(root/'configs/protocol.json'),
            'actual_backend_operations':sorted(successful(dispatch)),'backend_counter_scope':'process-wide cumulative, not disjoint per-run NFE',
            'core_pins':pins,'model_full_hash_recomputed':False,'model_provenance':'parent full SHA plus current size/mtime; no redundant full checkpoint hash',
            'GPU':'GPU3 vs R3 GPU2, same host; prefix equality is measured above','service_pid':5985,
            'efficiency':efficiency,'CPU_seconds':time.monotonic()-start,'no_GPU_started':True,
            'scope':'Independent integrity only. Keep both signs and unknown metrics; no predicted sign or efficacy claim.'}
    dest=root/'analysis/pose/replication'/(run+'_integrity.json');dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('run');args=parser.parse_args()
    with Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=verify(args.root,args.run)
    print(json.dumps({'passed':result['passed'],'run':args.run,'actual_NFE':result['actual_NFE']}))
