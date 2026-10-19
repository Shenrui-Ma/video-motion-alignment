"""CPU-only R20 actual evidence, all endpoint inventory, prefix and cleanup gate.

This checks paired execution, not motion quality. Run after both jobs and cleanup.
No claim that the new .41 baseline equals the historical .9 baseline.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extensions'))
from H3X0Readout.core import tensor_signature
from preflight import ARMS, CAPTURES, check, digest, read

SHAPES = {'video':(1,24,42,46,82), 'audio':(1,32,2,235)}

def signature(tensor):
    if not isinstance(tensor,torch.Tensor) or tensor.device.type != 'cpu' or not bool(torch.isfinite(tensor).all()):
        raise ValueError('invalid/nonfinite CPU tensor')
    return tensor_signature(tensor)

def safe_file(root, name):
    path=Path(name)
    if path.is_absolute() or '..' in path.parts or (root/path).is_symlink() or not (root/path).resolve().is_relative_to(root.resolve()):
        raise ValueError('unsafe archive file: '+name)
    return root/path

def checked_snapshot(folder, record, run_id):
    path=safe_file(folder,record['file'])
    if Path(record['file']).name != record['file']:
        raise ValueError('snapshot filename must be one component')
    value=torch.load(path,map_location='cpu',weights_only=True)
    if set(value) != {'video','audio','metadata'}:
        raise ValueError('unexpected snapshot schema')
    metadata={k:v for k,v in record.items() if k not in ('file','capture_seconds')}
    if value['metadata'] != metadata or metadata['run_id'] != run_id:
        raise ValueError('snapshot metadata/manifest/run mismatch')
    for key,shape in SHAPES.items():
        if tuple(value[key].shape) != shape or value[key].dtype != torch.float32 or signature(value[key]) != record[key]:
            raise ValueError('snapshot actual tensor signature mismatch: '+key)
    return value, {'file':str(path), 'bytes':path.stat().st_size,'sha256':digest(path)}

def expected_routing(full):
    return [0]*6+[50 if full else 0]*9+[0]*5

def inspect_capture(folder, run_id, grid):
    m=read(folder/'manifest.json')
    if (m['status']!='complete' or m['callback_count']!=20 or m['expected_callback_count']!=20 or
            m['run_id']!=run_id or m['capture_steps_zero_based']!=list(CAPTURES) or
            [r['step_zero_based'] for r in m['captures']]!=list(CAPTURES) or
            m['sigmas_video']!=grid or m['seed']!=2026101311 or m['sampler']!='sample_euler' or
            m['audio_scale']!=4 or m['video_latent_scale_factor']!=1 or
            m['normalization_stage']!='after_process_latent_out' or
            m['geometry']!={'width':1312,'height':736,'frames':141,'fps':24} or
            m['target_latent_shapes'] != [list(SHAPES[k]) for k in ('video','audio')]):
        raise ValueError('capture run/geometry/count/sigma/normalization gate failed: '+run_id)
    if any(r['snapshot_kind']!='x0_estimate' for r in m['captures']):
        raise ValueError('wrong intermediate snapshot kind')
    final=m['final_sampler_result']
    if final['snapshot_kind']!='sampler_final' or final['sigma_video']!=0.0 or final['sigma_audio']!=0.0 or final['step_zero_based']!=19:
        raise ValueError('wrong final snapshot semantics')
    records=m['captures']+[final]
    names=[r['file'] for r in records]
    expected=[f'x0_step{i:03d}.pt' for i in CAPTURES]+['sampler_final.pt']
    if names!=expected or sorted(p.name for p in folder.glob('*.pt'))!=sorted(expected):
        raise ValueError('missing/extra/duplicated actual endpoint inventory')
    files=[];prefix=None
    for r in records:
        value,inventory=checked_snapshot(folder,r,run_id);files.append(inventory)
        if r['file']=='x0_step005.pt':prefix=value
        if r['snapshot_kind']=='x0_estimate':
            i=r['step_zero_based']; sv=grid[i]
            if (r['sigma_video']!=sv or r['sigma_next_video']!=grid[i+1] or
                    r['model_call_one_based']!=i+1 or r['sigma_audio']!=sv/(4-3*sv)):
                raise ValueError('snapshot sigma/index mismatch')
    return m,files,prefix

def inspect_blob(root,record):
    path=safe_file(root,record['tensor_file'])
    value=torch.load(path,map_location='cpu',weights_only=True)
    expected={k:record[k] for k in ('shape','dtype','sha256')}
    # EventAudit signatures have exactly these three fields; x0 adds no assumption.
    got=signature(value)
    if {k:got[k] for k in expected} != expected:
        raise ValueError('actual condition tensor blob mismatch: '+str(path))
    return {'file':str(path),'sha256':digest(path),'tensor_signature':expected}

def verify(root, output):
    torch.set_num_threads(1);root=Path(root).resolve()
    result={'static_preflight':check(root),'checks':{},'runs':{},'condition_tensor_files':[]}
    checks=result['checks']; protocol=read(root/'configs/protocol.json')
    grid=torch.tensor([float(x) for x in read(root/'configs'/f'{ARMS[0]}.json')['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist()
    conds=[]; noises=[]; prefixes=[]; all_files=[]
    registry=read(root/'processes/service.json')
    for run_id in ARMS:
        full=run_id==ARMS[1]; graph=read(root/'configs'/f'{run_id}.json')
        history=read(root/'logs'/f'{run_id}_history.json'); job=read(root/'logs'/f'{run_id}_job.json')
        checks[run_id+'_history_graph']=(history['status']['status_str']=='success' and history['status']['completed'] is True and history['prompt'][2]==graph)
        checks[run_id+'_same_service']=(job['status']=='success' and job['graph_sha256']==digest(root/'configs'/f'{run_id}.json') and
            job['service_pid']==registry['pid'] and job['service_identity']==registry['identity'] and history['prompt'][1]==job['prompt_id'])
        c=read(root/'audit'/f'{run_id}_conditioning.json');n=read(root/'audit'/f'{run_id}_noise.json')
        conds.append(c);noises.append(n)
        checks[run_id+'_actual_pair_snapshot']=(c['run_id']==run_id and c['pair_snapshot']['verified'] is True and c['pair_snapshot']['source_run_id']=='07_sam_1312x736_shared_r20')
        router=read(root/'audit/router'/f'{run_id}.json')
        expect={'run_id':run_id,'mode':'mass_preserve' if full else 'native','alpha':1.,'radius':0,'time_offset':0,
            'block_interval_half_open':[0,50],'step_interval_half_open':[6,15],'pixel_interval_inclusive':[54,69],
            'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,
            'routed_calls':450 if full else 0,'calls_by_forward':[50]*20,'calls_by_block':[20]*50,
            'routed_by_forward':expected_routing(full),'routed_by_block':[9 if full else 0]*50,
            'sample_sigmas':grid,'expected_sampling_steps':20}
        checks[run_id+'_actual_counts_and_schedule']=all(router.get(k)==v for k,v in expect.items())
        plan=router['validated_layout']
        checks[run_id+'_source07_actual_layout']=(router['first_attention']['qkv_shape']==[1,56,87592,128] and
            router['first_attention']['heads']==56 and plan['latent_interval_half_open']==[16,22] and
            plan['pixel_interval_inclusive']==[54,69] and plan['position_bin_coverage_inclusive']==[52,72] and
            plan['reference_video_segment']==[7910,47516] and plan['target_video_segment']==[47986,87592] and
            plan['key_interval_half_open']==[22998,28656] and plan['query_interval_half_open']==[63074,68732] and plan['frame_rows']==943)
        checks[run_id+'_finite_router_diagnostics']=all(x.get('sampled_finite',True) for x in router['forward_summaries'])
        m,files,prefix=inspect_capture(root/'audit/x0'/run_id,run_id,grid)
        all_files+=files; prefixes.append(prefix)
        result['runs'][run_id]={'manifest_sha256':digest(root/'audit/x0'/run_id/'manifest.json'),'files':files,
            'timing':{'job_wall_seconds':job['observed_unix']-job['submitted_unix'],
                      'capture_wrapper_seconds':m['finished_unix']-m['created_unix'],
                      'snapshot_copy_seconds':sum(x['capture_seconds'] for x in m['captures'])},
            'NFE':20,'Euler_updates':20,'callback_count':20,'routed_calls':router['routed_calls'],
            'history_sha256':digest(root/'logs'/f'{run_id}_history.json')}
    keys=('prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion',
          'conditioning_embedding','token_tags','target_latent_shapes','packed_layout')
    checks['pair_actual_conditions']=all(conds[0][k]==conds[1][k] for k in keys)
    historical=read(root/'configs/source07_host9_conditioning.json')
    checks['host9_actual_condition_reuse']=all(conds[0][k]==historical[k] for k in keys)
    old_noise=read(root/'configs/source07_host9_noise.json')
    checks['host9_actual_noise_reuse']=all(noises[0][k]==old_noise[k] for k in ('signature','actual_noise_streams'))
    checks['pair_snapshot_actual_tensors']=conds[0]['pair_snapshot']['actual']==conds[1]['pair_snapshot']['actual']
    common=root/'audit/07_sam_1312x736_shared_r20_conditioning.json'
    checks['shared_manifest_bound']=all(c['pair_snapshot']['source_manifest_sha256']==digest(common) for c in conds)
    checks['pair_actual_noise']=all(noises[0][k]==noises[1][k] for k in ('signature','actual_noise_streams','pair_id'))
    checks['pair_noise_and_seed']=all(n['run_id']==r and n['pair_id']=='07_sam_1312x736_2026101311_r20' and n['signature']['seed']==2026101311 for n,r in zip(noises,ARMS))
    cache=root/'audit/07_sam_1312x736_2026101311_r20_noise.pt'
    saved=torch.load(cache,map_location='cpu',weights_only=True)
    actual=[{k:signature(t)[k] for k in ('shape','dtype','sha256')} for t in saved['tensors']]
    checks['actual_cached_noise_tensors']=(len(actual)==2 and saved['signature']==noises[0]['signature'] and saved['hashes']==actual==noises[0]['actual_noise_streams'])
    checks['actual_prefix005_bitwise']=all(torch.equal(prefixes[0][k],prefixes[1][k]) for k in ('video','audio'))
    checks['all10_endpoint_files_unique']=len(all_files)==10 and len({x['file'] for x in all_files})==10
    seen=set()
    def visit(value):
        if isinstance(value,dict):
            if 'tensor_file' in value and {'shape','dtype','sha256'}<=set(value) and value['tensor_file'] not in seen:
                seen.add(value['tensor_file']);result['condition_tensor_files'].append(inspect_blob(root/'audit',value))
            for v in value.values():visit(v)
        elif isinstance(value,list):
            for v in value:visit(v)
    visit(read(common))
    cleanup=read(root/'processes/cleanup.json');controller=read(root/'logs/controller_state.json')
    checks['queue_complete']=(controller['status']=='all_queued_jobs_complete' and controller['completed']==list(ARMS))
    checks['exact_owned_cleanup']=(cleanup['service_record']==registry and cleanup['process_absent'] is True and cleanup['own_compute_absent'] is True)
    result.update(passed=all(checks.values()),noise_cache_sha256=digest(cache),
        limitations=['Quality/pose/decoded141frame playback gates are separate, not implied by execution success.',
                     'Only captured prefix005 is compared exactly; no claim of separately archived indices0..4.',
                     'Cleanup is recorded evidence, root must confirm live PID/GPU absence.',
                     'Historical source07 output is not a replacement for the current paired Native; conditions/noise reuse is checked separately.'])
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();r=verify(a.root,a.output);print(json.dumps({'passed':r['passed'],'checks':r['checks'],'output':str(a.output)}));raise SystemExit(0 if r['passed'] else 1)
