"""CPU-only actual execution, tensor inventory and parent-prefix verification.

R14 normal seed1313 contributes an actual index005 AV anchor only.
After fixed routing starts at6, future old-native endpoints are not paired.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ['CUDA_VISIBLE_DEVICES'] = ''
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'extensions'))
from H3X0Readout.core import tensor_signature
from preflight import check, RUN_ID


def load_json(path): return json.loads(path.read_text())
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_snapshot(path, record):
    value = torch.load(path, map_location='cpu', weights_only=True)
    if set(value) != {'video', 'audio', 'metadata'}:
        raise ValueError('unexpected snapshot schema: '+str(path))
    metadata = {k:v for k,v in record.items() if k not in ('file','capture_seconds')}
    if value['metadata'] != metadata:
        raise ValueError('snapshot metadata does not equal manifest: '+str(path))
    for key, shape in [('video', (1,24,42,46,82)), ('audio', (1,32,2,235))]:
        tensor = value[key]
        if tensor.dtype != torch.float32 or tuple(tensor.shape) != shape or not bool(torch.isfinite(tensor).all()):
            raise ValueError('invalid actual tensor: '+str(path)+'/'+key)
        signature = tensor_signature(tensor)
        if signature != record[key] or signature != value['metadata'][key]:
            raise ValueError('actual tensor/manifest/metadata disagree: '+str(path)+'/'+key)
    return value


def verify(root, r14_x0, output):
    torch.set_num_threads(1)
    result = {'static_preflight': check(root), 'checks': {}, 'exact_comparisons': []}
    checks = result['checks']
    read = lambda name: load_json(root/'configs'/name)
    graph = read(RUN_ID+'.json')
    cond = load_json(root/'audit'/(RUN_ID+'_conditioning.json'))
    noise = load_json(root/'audit'/(RUN_ID+'_noise.json'))
    pc, pn = read('parent_full_conditioning.json'), read('parent_full_noise.json')
    for key in ('prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion',
                'conditioning_embedding','token_tags','target_latent_shapes','packed_layout'):
        checks['condition_'+key] = cond[key] == pc[key]
    for key in ('signature','actual_noise_streams'):
        checks['noise_'+key] = noise[key] == pn[key]
    history = load_json(root/'logs'/(RUN_ID+'_history.json'))
    checks['history_success'] = history['status']['status_str']=='success' and history['status']['completed']
    checks['executed_graph_exact'] = history['prompt'][2] == graph
    router = load_json(root/'audit/router'/(RUN_ID+'.json'))
    for key, expected in {'completed_forward_calls':20,'completed_calls':1000,'started_calls':1000,
                          'native_override_calls':1000,'routed_calls':300,
                          'calls_by_forward':[50]*20,'calls_by_block':[20]*50,
                          'routed_by_forward':[0]*6+[50]*6+[0]*8,'routed_by_block':[6]*50,
                          'step_interval_half_open':[6,12],'block_interval_half_open':[0,50],
                          'pixel_interval_inclusive':[50,65],'mode':'mass_preserve',
                          'alpha':1.0,'radius':0,'time_offset':0}.items():
        checks['router_'+key] = router.get(key) == expected
    checks['actual_attention_geometry'] = router['first_attention']['qkv_shape']==[1,56,87592,128]
    folder = root/'audit/x0'/RUN_ID
    manifest = load_json(folder/'manifest.json')
    parent = read('parent_full_x0_manifest.json')
    indices = [5,6,7,8,9,10,11,12,15,19]
    checks['capture_complete'] = manifest['status']=='complete' and manifest['callback_count']==20
    checks['capture_indices'] = [x['step_zero_based'] for x in manifest['captures']]==indices
    checks['declared_capture_indices'] = manifest['capture_steps_zero_based']==indices
    checks['declared_callback_count'] = manifest['expected_callback_count']==20
    checks['actual_sigmas'] = manifest['sigmas_video']==parent['sigmas_video']==router['sample_sigmas']
    for key in ('geometry','target_latent_shapes','seed','audio_scale'):
        checks['capture_'+key] = manifest.get(key)==parent.get(key) and key in manifest
    records = manifest['captures']+[manifest['final_sampler_result']]
    filenames = [x['file'] for x in records]
    checks['capture_inventory'] = (filenames==[f'x0_step{i:03d}.pt' for i in indices]+['sampler_final.pt'] and
                                  sorted(x.name for x in folder.glob('*.pt'))==sorted(filenames))
    values = {}
    for record in records:
        path = folder/record['file']
        if Path(record['file']).name != record['file'] or path.is_symlink():
            raise ValueError('unsafe capture file')
        values[record['file']] = checked_snapshot(path, record)
    # The actual unmodified prefix before the first routed forward.
    r14_manifest = load_json(r14_x0/'manifest.json')
    checks['actual_parent_manifest_pin'] = digest(r14_x0/'manifest.json')==digest(root/'configs/parent_full_x0_manifest.json')
    name='x0_step005.pt'
    matches=[x for x in r14_manifest['captures'] if x['file']==name]
    if len(matches)!=1:raise ValueError('missing/duplicate R14 index005')
    a=checked_snapshot(r14_x0/name,matches[0]);b=values[name]
    equal={key:torch.equal(a[key],b[key]) for key in ('video','audio')}
    raw_equal={'video':torch.equal(a['video'],b['video']),'audio':torch.equal(a['audio']*4,b['audio']*4)}
    result['exact_comparisons'].append({'index':5,'reference':'actual R14 seed1313 unmodified prefix','video_audio_equal':equal,'raw_video_audio_equal':raw_equal})
    checks['before_intervention_prefix005_exact'] = all(equal.values()) and all(raw_equal.values())
    cleanup=load_json(root/'processes/cleanup.json')
    registry=load_json(root/'processes/service.json')
    checks['exact_service_cleanup']=(cleanup['service_record']==registry and cleanup['process_absent'] and cleanup['own_compute_absent'])
    result.update(passed=all(checks.values()),
                  capture_manifest_sha256=digest(folder/'manifest.json'),
                  limitations=['R14 did not archive post-augmentation tensors; clean conditions, actual noise, pinned seed/helper and prefix005 are the available evidence.',
                               'No expectation of old-native endpoint equality after routing begins at6.',
                               'Known normal development case; final timing and quality must be assessed, fixed guidance may work as well.',
                               'Cleanup is archived evidence; root must inspect live resource state.'],
                  timing={'capture_elapsed_seconds':manifest['finished_unix']-manifest['created_unix'],
                          'capture_copy_seconds':sum(x['capture_seconds'] for x in manifest['captures'])})
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--r14-x0',type=Path,default=Path('/data5/researcher/h3_runs/timing_native_screen_r14_host9_20261016/audit/x0/r14_s05_seed1313_native_host9'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=verify(args.root,args.r14_x0,args.output)
    print(json.dumps({'passed':result['passed'],'checks':result['checks'],'output':str(args.output)}))
    raise SystemExit(0 if result['passed'] else 1)
