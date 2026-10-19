"""Actual two-seed Native/fixed pair gate. Execution comparability is separate from quality."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import torch
from capture_checks import inspect_capture,inspect_blob,condition_files,signature
from r113_contract import read,sha,require,registry,validate_job,SOURCES,ARMS,RUNS,GEOMETRY,SHAPES,SHARED_ID,VALID,SEEDS,pair_id
from execution_gate import atomic

def walk_blobs(value):
 if isinstance(value,dict):
  if 'tensor_file' in value:yield value
  for v in value.values():yield from walk_blobs(v)
 elif isinstance(value,list):
  for v in value:yield from walk_blobs(v)

def reference_geometry_matches(c,case,plan):
 calls=c['native_vae_calls'];require(len(calls)==1,'expected one video VAE call')
 actual=c['pair_snapshot']['actual'];refs=actual['references']
 shapes_ok=(calls[0]['prepared_frames']['shape']==[107,736,1312,3] and calls[0]['latent']['shape']==list(SHAPES['video']) and c['target_latent_shapes']==[list(SHAPES[k]) for k in ('video','audio')] and [x['kind'] for x in refs]==['video'] and [x['clean_latent']['shape'] for x in refs]==[list(SHAPES['video'])] and actual['target_latent_shapes']==c['target_latent_shapes'])
 segments=c['packed_layout']['segments'];require(len(segments)==4,'expected text/video-reference/audio/target-video segments')
 sizes=[segments[0][1],30176,356,30176];labels=['text','ref_img','audio','video'];offset=0;expected=[]
 for size,label in zip(sizes,labels):expected.append([offset,offset+size,label]);offset+=size
 layout_ok=(segments[0][0]==0 and segments[0][1]>0 and segments==expected and c['packed_layout']['seq_len']==offset and actual['packed_layout']['segments']==segments and actual['packed_layout']['seq_len']==offset and plan['reference_image_segments']==[] and plan['reference_video_segment']==segments[1][:2] and plan['target_video_segment']==segments[3][:2])
 return shapes_ok and layout_ok

def output_file(root,history):
 images=history['outputs']['14']['images'];require(len(images)==1,'expected one final video')
 record=images[0];require(record.get('type')=='output','final file is not in output')
 rel=Path(record.get('subfolder',''))/record['filename'];require(not rel.is_absolute() and '..' not in rel.parts,'unsafe final video path')
 file=root/'output'/rel;require(file.is_file() and not file.is_symlink(),'final video missing')
 return file

def video_properties(path):
 result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames','-of','json',str(path)],capture_output=True,text=True,timeout=120,check=True)
 streams=json.loads(result.stdout)['streams'];require(len(streams)==1,'expected exactly one video stream');s=streams[0]
 require(s['width']==1312 and s['height']==736 and int(s['nb_read_frames'])==107 and s['avg_frame_rate']=='24/1','final geometry/frame count/fps differs')
 return s


def semantic_condition(c):return {k:v for k,v in c.items() if k!='run_id'}

def compare_prefix(left,right):
    checks={}
    for step in range(6):
        for key in ('video','audio'):
            checks[f'step{step}_normalized_{key}']=torch.equal(left[step]['normalized'][key],right[step]['normalized'][key])
    for step in (0,1):
        for key in ('state_video','state_audio','prediction_video','prediction_audio'):
            checks[f'step{step}_raw_{key}']=torch.equal(left[step]['raw'][key],right[step]['raw'][key])
    return checks


def verify_seed(root, seed, owner, source_condition, shared, blob_files):
    jobs, order = registry(root)
    selected = [run for run in order if jobs[run]['seed'] == seed]
    require(len(selected) == 2 and [jobs[r]['arm'] for r in selected] == list(ARMS),
            'fresh pair order differs')
    pair = pair_id(seed)
    noise_file = root/'audit'/(pair+'_noise.pt')
    saved = torch.load(noise_file, map_location='cpu', weights_only=True)
    actual_noise = [{k: signature(t)[k] for k in ('shape', 'dtype', 'sha256')}
                    for t in saved['tensors']]
    checks = {'raw_noise_geometry': len(actual_noise) == 2
              and [v['shape'] for v in actual_noise] == [list(SHAPES[k]) for k in ('video', 'audio')]
              and actual_noise == saved['hashes'] and saved['signature']['seed'] == seed}
    results, prefixes, conditions, manifests, noise_manifests = {}, {}, {}, {}, {}
    for arm, run in zip(ARMS, selected):
        row = validate_job(run, root)
        case = row['case']
        graph = read(root/'configs/graphs'/(run+'.json'))
        grid = torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')],
                            dtype=torch.float32).tolist()
        hist = read(root/'logs'/(run+'_history.json'))
        job = read(root/'logs'/(run+'_job.json'))
        checks[arm+'_history'] = (hist['status']['completed'] is True
            and hist['status']['status_str'] == 'success' and hist['prompt'][2] == graph
            and hist['prompt'][1] == job['prompt_id'] and job['status'] == 'success'
            and job['name'] == run)
        checks[arm+'_generation'] = (job['service_pid'] == owner['pid']
            and job['service_identity'] == owner['identity']
            and job['graph_sha256'] == row['graph_sha256'])
        c = read(root/'audit'/(run+'_conditioning.json'))
        n = read(root/'audit'/(run+'_noise.json'))
        conditions[arm], noise_manifests[arm] = c, n
        checks[arm+'_actual_conditions'] = (c['run_id'] == run
            and c['pair_snapshot']['verified'] is True
            and c['pair_snapshot']['source_run_id'] == SHARED_ID
            and c['pair_snapshot']['source_manifest_sha256'] == sha(shared)
            and c['prompt'] == case['prompt'] and condition_files(c) == condition_files(source_condition))
        checks[arm+'_actual_noise'] = (n['run_id'] == run and n['pair_id'] == pair
            and n['signature'] == saved['signature'] and n['actual_noise_streams'] == actual_noise)
        router = read(root/'audit/router'/(run+'.json'))
        fixed = arm == 'fixed'
        expected = {'run_id': run, 'mode': 'mass_preserve' if fixed else 'native',
            'alpha': 1., 'radius': 0, 'time_offset': 0,
            'block_interval_half_open': [0, 50], 'step_interval_half_open': [6, 15],
            'pixel_interval_inclusive': [0, 97], 'started_calls': 1000,
            'completed_calls': 1000, 'completed_forward_calls': 20,
            'native_override_calls': 1000, 'routed_calls': 450 if fixed else 0,
            'calls_by_forward': [50]*20, 'calls_by_block': [20]*50,
            'routed_by_forward': [0]*6+[50 if fixed else 0]*9+[0]*5,
            'routed_by_block': [9 if fixed else 0]*50,
            'sample_sigmas': grid, 'expected_sampling_steps': 20}
        checks[arm+'_actual_routes'] = all(router.get(k) == v for k, v in expected.items())
        plan, seq = router['validated_layout'], c['packed_layout']['seq_len']
        checks[arm+'_layout'] = (router['first_attention']['qkv_shape'] == [1, 56, seq, 128]
            and plan['frame_rows'] == 943 and plan['latent_interval_half_open'] == [0, 29]
            and plan['position_bin_coverage_inclusive'] == [0, 97]
            and len(plan['reference_image_segments']) == 0)
        checks[arm+'_reference_geometry'] = reference_geometry_matches(c, case, plan)
        checks[arm+'_finite'] = all(x.get('sampled_finite', True) for x in router['forward_summaries'])
        manifest, files, prefix = inspect_capture(root/'audit/x0'/run, run, grid, seed, 'sample_euler')
        prefixes[arm], manifests[arm] = prefix, manifest
        video = output_file(root, hist)
        results[arm] = {'run_id': run, 'seed': seed, 'solver': 'euler',
            'sampler_function': manifest['sampler'],
            'video': {'file': str(video), 'sha256': sha(video), 'properties': video_properties(video)},
            'NFE': 20, 'solver_updates': 20, 'routed_blocks': 450 if fixed else 0,
            'valid_frames': VALID, 'evaluation_indices': list(range(VALID)),
            'job_wall_seconds': job['observed_unix']-job['submitted_unix'],
            'capture_seconds': sum(x['capture_seconds'] for x in manifest['captures']),
            'snapshots': files, 'history_sha256': sha(root/'logs'/(run+'_history.json')),
            'job_sha256': sha(root/'logs'/(run+'_job.json')),
            'conditioning_sha256': sha(root/'audit'/(run+'_conditioning.json')),
            'noise_sha256': sha(root/'audit'/(run+'_noise.json')),
            'router_sha256': sha(root/'audit/router'/(run+'.json')),
            'capture_manifest_sha256': sha(root/'audit/x0'/run/'manifest.json')}
    checks['same_complete_conditions'] = semantic_condition(conditions['native']) == semantic_condition(conditions['fixed'])
    checks['same_raw_noise'] = (noise_manifests['native']['signature'] == noise_manifests['fixed']['signature']
        and noise_manifests['native']['actual_noise_streams'] == noise_manifests['fixed']['actual_noise_streams'])
    checks['same_actual_sigmas'] = manifests['native']['sigmas_video'] == manifests['fixed']['sigmas_video']
    checks.update(compare_prefix(prefixes['native'], prefixes['fixed']))
    return {'schema': 'r113-fresh-seed-pair-runtime-gate-v1', 'passed': all(checks.values()),
        'checks': checks, 'service_owner': owner, 'source_id': SOURCES[0], 'seed': seed,
        'runs': results, 'valid_frames': VALID, 'evaluation_crop_xywh': [16, 8, 1280, 720],
        'frame_rate': 24, 'condition_tensor_files': blob_files,
        'noise_cache': {'file': str(noise_file), 'sha256': sha(noise_file),
                        'tensor_signatures': actual_noise},
        'equal_normalized_prediction_steps': list(range(6)), 'equal_raw_prefix_steps': [0, 1],
        'quality_assessment': 'PENDING_TASK_ACCEPTANCE_AND_SEPARATE_EVENT_VISIBILITY',
        'created_unix': time.time()}


def verify(root=ROOT):
    torch.set_num_threads(1)
    root = Path(root).resolve()
    registry(root)
    runtime, seal = read(root/'configs/runtime.json'), read(root/'deploy_manifest.json')
    owner = read(root/'processes/service.json')
    checks = {'producer_seal': all(sha(root/p) == v['sha256'] for p, v in seal['files'].items()),
              'actual_runtime_device': owner['gpu_uuid'] == runtime['gpu_uuid'] and owner['port'] == runtime['port']}
    shared = root/'audit'/(SHARED_ID+'_conditioning.json')
    source_condition = read(shared)
    require(len(condition_files(source_condition)) == 6, 'six shared condition tensors required')
    blob_files, seen = [], set()
    for record in walk_blobs(source_condition):
        if record['tensor_file'] not in seen:
            seen.add(record['tensor_file'])
            blob_files.append(inspect_blob(root/'audit', record))
    pairs, receipts = {}, []
    for seed in SEEDS:
        value = verify_seed(root, seed, owner, source_condition, shared, blob_files)
        path = root/'analysis/postrun'/f'seed{seed}'/'PAIR_RUNTIME_GATE.json'
        atomic(path, value)
        pairs[str(seed)] = value
        checks[f'seed{seed}_actual_pair'] = value['passed']
        receipts.append({'seed': seed, 'file': str(path), 'sha256': sha(path)})
    left, right = [pairs[str(seed)]['noise_cache']['tensor_signatures'] for seed in SEEDS]
    checks['distinct_seed_noise_video_and_audio'] = all(a['sha256'] != b['sha256'] for a, b in zip(left, right))
    return {'schema': 'r113-two-seed-runtime-gate-v1', 'passed': all(checks.values()),
        'checks': checks, 'service_owner': owner, 'source_id': SOURCES[0],
        'seeds': list(SEEDS), 'jobs': list(RUNS), 'pair_gate_receipts': receipts,
        'runtime_profile': runtime, 'runtime_profile_sha256': sha(root/'configs/runtime.json'),
        'producer_seal_sha256': sha(root/'deploy_manifest.json'),
        'preregistered_events_sha256': sha(root/'design/PREREGISTERED_EVENTS.json'),
        'valid_frames': VALID, 'evaluation_crop_xywh': [16, 8, 1280, 720], 'frame_rate': 24,
        'quality_assessment': 'PENDING_ALL_FOUR_TASK_ACCEPTANCE_AND_EVENT_VISIBILITY',
        'report_all_seeds': True, 'created_unix': time.time()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    destination = args.root/'analysis/postrun/PAIR_RUNTIME_GATE.json'
    try:
        result = verify(args.root)
    except BaseException as error:
        atomic(destination.with_name('PAIR_RUNTIME_GATE_FAILURE.json'),
               {'passed': False, 'error': repr(error), 'unix': time.time()})
        raise
    atomic(destination, result)
    print(json.dumps({'receipt': str(destination), 'sha256': sha(destination),
                      'passed': result['passed'], 'checks': result['checks']}, indent=2))
    if not result['passed']:
        raise SystemExit(2)
