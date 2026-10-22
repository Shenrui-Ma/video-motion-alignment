"""Collect one actually verified R69 pair, retaining its real provenance."""
import argparse
import math
import re
import shutil
from common import *

def is_sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None

def validate_gate(gate, source):
    expected = entry(source)
    count, total = (expected['input_protocol'][key] for key in ('effective_frame_count', 'h3_frame_count'))
    require(gate.get('schema') == 'r69-paired-runtime-gate-v1' and gate.get('passed') is True and gate.get('source_id') == source and gate.get('prompt_version') == 'P0', 'actual R69 gate differs')
    checks = gate.get('checks', {})
    require(checks and all(value is True for value in checks.values()), 'actual pair gate contains unsuccessful checks')
    for key in ('producer_seal', 'actual_runtime_device', 'actual_clean_conditions_equal', 'actual_initial_AV_noise_equal', 'Native_prefix_0_5_equal'):
        require(checks.get(key) is True, 'pair gate check missing: ' + key)
    for method in METHODS:
        for suffix in ('history','service','shared_conditions','actual_execution_counts','actual_layout','sampled_finite','actual_noise_cache'):
            require(checks.get(method+'_'+suffix) is True, 'actual method evidence missing: '+method+'_'+suffix)
    require(is_sha(gate.get('runtime_profile_sha256')), 'runtime profile binding missing')
    require(gate.get('prefix_tensor_comparison') == [{'step_zero_based':i,'video':True,'audio':True} for i in range(6)], 'six actual AV prefix comparisons required')
    blobs=gate.get('condition_tensor_files',[])
    require(len(blobs)==6 and len({x['file'] for x in blobs})==6 and all(is_sha(x.get('sha256')) and is_sha(x.get('tensor_signature',{}).get('sha256')) for x in blobs), 'six verified actual condition blobs required')
    require(set(gate['runs']) == set(METHODS), 'both methods required')
    for method, run in gate['runs'].items():
        require(run['run_id'] == f'r69_{source}_seed2026101701_{method}' and run['valid_frames'] == count and run['NFE'] == run['Euler_updates'] == 20 and run['routed_blocks'] == (0 if method == 'native' else 450), 'actual run/validtime/route differs')
        prop = run['video']['properties']
        require(prop['width'] == 1312 and prop['height'] == 736 and int(prop['nb_read_frames']) == total and prop['avg_frame_rate'] == '24/1' and run['evaluation_crop_xywh'] == [16, 8, 1280, 720], 'actual geometry differs')
        names=[f'x0_step{i:03d}.pt' for i in range(20)]+['sampler_final.pt']
        snapshots=run.get('snapshots',[])
        require([Path(x['file']).name for x in snapshots]==names and all(x['bytes']>0 and is_sha(x['sha256']) for x in snapshots), 'all 20 x0 plus final actual captures required')
        require(is_sha(run['video'].get('sha256')) and all(is_sha(run.get(key)) for key in ('router_file_sha256','history_sha256','job_sha256')), 'actual media/evidence hashes required')
        require(math.isfinite(run.get('job_wall_seconds',float('nan'))) and run['job_wall_seconds']>0,'actual efficiency record required')
    return gate

def validate_router(router, method):
    forced=method=='forced'
    expected={'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,
              'native_override_calls':1000,'routed_calls':450 if forced else 0,
              'calls_by_forward':[50]*20,'calls_by_block':[20]*50,
              'routed_by_forward':[50 if forced and 6<=i<15 else 0 for i in range(20)],
              'routed_by_block':[9 if forced else 0]*50,
              'expected_sampling_steps':20,'pixel_interval_inclusive':[0,89],
              'block_interval_half_open':[0,50],'step_interval_half_open':[6,15] if forced else [0,20],
              'alpha':1.,'radius':0,'time_offset':0,'mode':'mass_preserve' if forced else 'native'}
    require(all(router.get(k)==v for k,v in expected.items()),'actual router counters or fixed schedule differ')
    layout=router['validated_layout']
    require(layout['latent_interval_half_open']==[0,27] and layout['frame_rows']==943 and layout['query_interval_half_open']==layout['target_video_segment'] and layout['key_interval_half_open']==layout['reference_video_segment'],'actual full27-bin routing differs')

def collect(producer, source):
    producer = Path(producer).resolve()
    receipt = producer / 'analysis/postrun' / source / 'PAIR_RUNTIME_GATE.json'
    gate = validate_gate(read(receipt), source)
    require(gate['runtime_profile_sha256']==sha(producer/'configs/runtime.json'),'producer runtime changed after gate')
    seal=read(producer/'deploy_manifest.json')
    require(all(sha(producer/name)==x['sha256'] for name,x in seal['files'].items()),'producer frozen files changed after gate')
    out = ROOT / 'incoming' / source
    require(not out.exists(), 'existing intake must be preserved')
    out.mkdir(parents=True)
    shutil.copy2(receipt, out / 'PAIR_RUNTIME_GATE.json')
    for method in METHODS:
        run = gate['runs'][method]
        video = Path(run['video']['file'])
        require(video.resolve().is_relative_to(producer / 'output') and sha(video) == run['video']['sha256'], 'actual video changed/outside producer')
        shutil.copy2(video, out / (method + '.mp4'))
        for kind, folder, digest_key in [('history', 'logs', 'history_sha256'), ('job', 'logs', 'job_sha256'), ('router', 'audit/router', 'router_file_sha256')]:
            name = run['run_id'] + ('.json' if kind == 'router' else '_' + kind + '.json')
            path = producer / folder / name
            require(sha(path) == run[digest_key], 'actual evidence changed: ' + kind)
            if kind=='router':validate_router(read(path),method)
            shutil.copy2(path, out / (method + '_' + kind + '.json'))
        shutil.copy2(producer / 'configs/graphs' / (run['run_id'] + '.json'), out / (method + '_graph.json'))
    save(out / 'COLLECTION.json', {'schema': 'r69-portable-actual-pair-v1', 'source': source, 'fixed_denominator': 5, 'producer': str(producer), 'receipt': bound(receipt), 'files': {path.name: sha(path) for path in out.iterdir() if path.is_file()}})
    return out

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--source', choices=PAIRS, required=True); p.add_argument('--producer-root', type=Path, required=True)
    a = p.parse_args(); verify_runtime(); print(collect(a.producer_root, a.source))
