"""Validate each actual R49 archive and each independently prepared source pose."""
from pathlib import Path
import math
from observer_import import t

def check(root, remote=False):
    root = Path(root)
    closure = t.require_parent_closure(root)
    rows = []
    for case in t.read_json(root/'configs/protocol.json')['cases']:
        source, run = case['source_id'], case['parent_run']
        folder = root/'configs/parents'/source
        inv = t.read_json(root/case['parent_file_inventory'])
        gate = t.read_json(folder/'RUN_GATE.json')
        runtime = t.read_json(folder/'RUNTIME_GATE.json')
        history = t.read_json(folder/'history.json')
        router = t.read_json(folder/'router.json')
        condition = t.read_json(root/case['parent_conditioning'])
        capture = t.read_json(root/case['parent_captures'])
        noise = t.read_json(root/case['parent_noise'])
        t.require(gate['passed'] is True and runtime['passed'] is True and
                  all(v is True for v in runtime['checks'].values()), 'parent runtime failed')
        t.require(gate['file_inventory_sha256'] == t.sha(root/case['parent_file_inventory']) and
                  gate['runtime_gate_sha256'] == t.sha(folder/'RUNTIME_GATE.json'), 'parent anchor differs')
        count = runtime['runs'][run]
        t.require(count['NFE'] == count['callback_count'] == count['Euler_updates'] == 20, 'parent counts differ')
        t.require(router['completed_forward_calls'] == 20 and router['completed_calls'] == 1000 and
                  router['routed_calls'] == 0 and router['calls_by_forward'] == [50]*20, 'parent routing differs')
        t.require(history['status']['completed'] is True and history['status']['status_str'] == 'success' and
                  history['prompt'][2] == t.read_json(root/case['parent_graph']), 'actual parent graph/history differs')
        t.require(capture['status'] == 'complete' and capture['run_id'] == run and
                  capture['seed'] == case['seed'] == noise['signature']['seed'] and
                  capture['capture_steps_zero_based'] == list(range(20)) and capture['callback_count'] == 20 and
                  capture['geometry'] == case['geometry'], 'capture identity/geometry differs')
        expected = {str(Path(x['file']).relative_to(case['parent_root'])):
                    {'bytes':x['bytes'], 'sha256':x['sha256']} for x in count['snapshots']}
        t.require(len(expected) == 21 and all(inv[k] == v for k,v in expected.items()), 'actual21 archive differs')
        pose_path = root/case['source_pose_path']
        t.require(t.sha(pose_path) == case['source_pose_sha256'], 'source pose bytes differ')
        pose = t.read_json(pose_path)
        geometry=t.geometry_for(case['run_id']);v=pose['video'];frames=pose['frames']
        t.require((v['fps'],v['width'],v['height'],v['container_frame_count'])==(geometry.fps,geometry.width,geometry.height,geometry.frames),'source full geometry differs')
        t.require(len(frames)==geometry.frames and all(type(f['frame']) is int and f['frame']==i and math.isfinite(f['time_s']) and abs(f['time_s']-i/geometry.fps)<1e-8 for i,f in enumerate(frames)),'source pose timebase differs')
        inputs = t.read_json(root/'configs/input_hashes.json')
        t.require(pose['video']['sha256'] == inputs[case['video']], 'source pose/video differs')
        bound = closure['cases'][source]
        t.require(condition['packed_layout'] == bound['packed_layout'], 'actual layout differs')
        names = set(expected)
        def visit(value):
            if isinstance(value, dict):
                if 'tensor_file' in value:
                    names.add('audit/' + value['tensor_file'])
                for child in value.values(): visit(child)
            elif isinstance(value, list):
                for child in value: visit(child)
        visit(condition)
        names.add('audit/' + noise['pair_id'] + '_noise.pt')
        t.require(len(names) == 30, 'eight conditions, noise and21 endpoints required')
        checked = []
        if remote:
            old = Path(case['parent_root'])
            for rel in sorted(names):
                path, record = old/rel, inv[rel]
                t.require(path.stat().st_size == record['bytes'] and t.sha(path) == record['sha256'],
                          'actual historical entity changed: ' + rel)
                checked.append(rel)
        rows.append({'run':case['run_id'], 'parent_run':run, 'available_indices':list(range(20)),
                     'actual_entities':len(names), 'actual_files_checked':checked})
    return {'passed':True, 'cases':rows, 'scope':'Actual clean inputs/noise/21 endpoints; historical processed condition tree unavailable'}
