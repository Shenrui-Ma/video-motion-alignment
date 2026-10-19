"""Read-only CPU evidence audit; no model construction or inference."""
import ast
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import time

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
ROOT = Path('/data3/researcher/h3_runs')
P = ROOT / 'timing_flexiact_expanded_r66_20261018'
C = ROOT / 'flexiact_expanded_evaluation_r66_20261018'
CORE = ROOT / 'silverwolf_486_ref2va4_clean/ComfyUI'
OUT = C / 'audit/temporal_mapping_review'
PAIR = 'human2animal_3__game_man_4'


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    lock = open(ROOT / 'timing_architecture_r2_20261016/analysis/pose/consumer.lock', 'a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 75
    import torch
    import numpy as np
    import av
    torch.set_num_threads(1)
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = P / f'audit/r66_{PAIR}_shared_conditioning.json'
    manifest = json.loads(manifest_path.read_text())
    gate_path = C / 'incoming' / PAIR / 'PAIR_RUNTIME_GATE.json'
    gate = json.loads(gate_path.read_text())
    assert gate['passed']
    result = {'schema': 'r66-temporal-mapping-readonly-v1', 'pair': PAIR,
              'cpu_only': True, 'model_weights_loaded': False,
              'runtime': {'torch':torch.__version__, 'av':av.__version__, 'av_path':av.__file__},
              'manifest_sha256': digest(manifest_path), 'gate_sha256': digest(gate_path)}
    result['code_sha256'] = {s: digest(CORE / s) for s in (
        'comfy/ldm/minimax/vae.py', 'comfy/ldm/minimax/model.py',
        'comfy_extras/nodes_minimax_h3.py', 'comfy/sd.py',
        'comfy/utils.py', 'comfy_api/latest/_input_impl/video_types.py')}

    # Execute original chunk/index methods with a deterministic tagged decoder.
    # This checks bookkeeping only, not learned VAE reconstruction fidelity.
    tree = ast.parse((CORE / 'comfy/ldm/minimax/vae.py').read_text())
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'MiniMaxH3VideoVAE')
    names = {'blend', '_decode_temporal_chunks', '_decode_temporal_frame_plan',
             '_decode_temporal_pad_frames', 'decode_temporal'}
    funcs = [x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name in names]
    env = {'torch': torch, 'math': math}
    exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])), '<actual VAE methods>', 'exec'), env)
    Dummy = type('TaggedDecoderBookkeeping', (), {k: env[k] for k in names})
    obj = Dummy()
    obj.tokens_chunk_size, obj.token_drop = 5, 3
    obj.token_overlap, obj.frame_pre_padding, obj.frame_overlap, obj.vae_ratio_t = 2, 3, 5, 4
    obj._adaptive_decode = lambda z: torch.repeat_interleave(z, 4, dim=2)
    obj._finalize_pixels = lambda z: z
    z = torch.arange(47, dtype=torch.float32).reshape(1, 1, 47, 1, 1)
    decoded = obj.decode_temporal(z, output_buffer=torch.empty(1, 1, 158, 1, 1)).flatten()
    spans = [1 if i % 5 == 0 else 4 for i in range(47)]
    expected = torch.repeat_interleave(torch.arange(47, dtype=torch.float32), torch.tensor(spans))
    result['structural_decode_probe'] = {
        'description': 'Original chunk methods; tagged repeat-interleave decoder; no learned decoder run',
        'latent_count': 47, 'rgb_count': len(decoded),
        'chunk_plan': list(obj._decode_temporal_chunks(47)),
        'nominal_mapping_max_abs_error': float((decoded - expected).abs().max()),
        'nominal_bins_equal_with_float_tolerance': bool(torch.allclose(decoded, expected, atol=1e-5, rtol=0)),
        'monotonic': bool((decoded[1:] >= decoded[:-1] - 1e-5).all())}
    assert result['structural_decode_probe']['nominal_bins_equal_with_float_tolerance']

    # Capture was taken immediately before the native VAE encode call.
    info = manifest['native_vae_calls'][1]['prepared_frames']
    tensor_path = P / 'audit' / info['tensor_file']
    frames = torch.load(tensor_path, map_location='cpu', weights_only=True, mmap=True)
    source = P / 'inputs/source_human2animal_3_video.mp4'
    h_input, h_prepared = hashlib.sha256(), hashlib.sha256()
    records = []
    with av.open(str(source)) as video:
        for i, frame in enumerate(video.decode(video=0)):
            # This source is yuv420p and width 1152 (multiple of 32), matching
            # VideoFromFile's gbrpf32le branch; native Lanczos at equal geometry
            # quantizes to uint8 and divides by 255 even without spatial resize.
            image = np.ascontiguousarray(frame.to_ndarray(format='gbrpf32le'))
            h_input.update(image.data)
            prepared = np.clip(255.0 * image, 0, 255).astype(np.uint8).astype(np.float32) / 255.0
            actual = frames[i].numpy()
            h_prepared.update(actual.data)
            records.append({'index': i, 'pts': frame.pts, 'time_base': str(frame.time_base),
                            'seconds': float(frame.time), 'exact': bool(np.array_equal(prepared, actual)),
                            'max_abs': float(np.max(np.abs(prepared - actual)))})
    result['actual_vae_input_order'] = {
        'source_sha256': digest(source), 'captured_file_sha256': digest(tensor_path),
        'source_decoded_float_sha256': h_input.hexdigest(),
        'matches_input_audit_hash': h_input.hexdigest() == manifest['input_video']['sha256'],
        'captured_tensor_sha256': h_prepared.hexdigest(),
        'matches_captured_audit_hash': h_prepared.hexdigest() == info['sha256'],
        'frame_count': len(records), 'all_frames_exact_in_original_order': all(r['exact'] for r in records),
        'pts_equal_index_over_24': all(abs(r['seconds']-r['index']/24) < 1e-10 for r in records),
        'records': records}
    assert len(records) == 158
    (OUT/'INPUT_ORDER_INTERMEDIATE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    # A separate read-only decode may differ in float/color conversion versions.
    # Preserve exact-vs-approximate observations instead of erasing the evidence.
    assert result['actual_vae_input_order']['matches_captured_audit_hash']
    assert result['actual_vae_input_order']['matches_input_audit_hash']
    assert result['actual_vae_input_order']['all_frames_exact_in_original_order']
    qi = manifest['qwen_presentation'][1]
    q = torch.load(P / 'audit' / qi['actual_sampled_frames']['tensor_file'], map_location='cpu', weights_only=True, mmap=True)
    selected = qi['sampling']['sample_indices']
    result['qwen_order'] = {'indices': selected, 'all_exact': all(torch.equal(q[i], frames[j]) for i,j in enumerate(selected))}
    assert result['qwen_order']['all_exact']
    del frames, q

    pos_info = manifest['packed_layout']['position_ids']
    pos = torch.load(P / 'audit' / pos_info['tensor_file'], map_location='cpu', weights_only=True)
    ref = pos[7306:47914].reshape(47,864,3)
    target = pos[48440:89048].reshape(47,864,3)
    # Run the original native coordinate helpers on CPU.
    mt = ast.parse((CORE / 'comfy/ldm/minimax/model.py').read_text())
    fs = [x for x in mt.body if isinstance(x, ast.FunctionDef) and x.name in {'_video_t_spans','_video_t_grid','patchify_video','unpatchify_video'}]
    menv = {'torch':torch,'FRAME_PER_TOKEN':(1,4,4,4,4),'FRAME_RESCALE':5/3}
    exec(compile(ast.fix_missing_locations(ast.Module(body=fs,type_ignores=[])), '<actual H3 helpers>', 'exec'), menv)
    reft = menv['_video_t_grid'](47,6737)
    tart = menv['_video_t_grid'](47,float(target[0,0,0]))
    tag = torch.arange(47).reshape(1,1,47,1,1).expand(1,1,47,4,6)
    rows = menv['patchify_video'](tag)
    restored = menv['unpatchify_video'](rows,47,2,3,c=1)
    result['actual_position_mapping'] = {
        'reference_origin': float(ref[0,0,0]), 'target_origin': float(target[0,0,0]),
        'constant_absolute_offset': float(target[0,0,0] - ref[0,0,0]),
        'native_reference_grid_exact': bool(torch.equal(ref[:,:,0], reft[:,None].expand(47,864))),
        'native_target_grid_exact': bool(torch.equal(target[:,:,0], tart[:,None].expand(47,864))),
        'relative_coordinate_max_error': float(((target[:,:,0]-target[0,0,0])-(ref[:,:,0]-ref[0,0,0])).abs().max()),
        'spatial_coords_exact': bool(torch.equal(ref[:,:,1:],target[:,:,1:])),
        'tagged_patchify_unpatchify_exact': bool(torch.equal(tag,restored))}
    assert result['actual_position_mapping']['native_reference_grid_exact']
    assert result['actual_position_mapping']['native_target_grid_exact']
    assert result['actual_position_mapping']['tagged_patchify_unpatchify_exact']

    # Check delivered columns at predeclared six times against the actual files.
    indexes = [0,48,72,96,120,144]
    wanted = set(indexes + [146-i for i in indexes])
    raw_paths = [source, C/'incoming'/PAIR/'native.mp4', C/'incoming'/PAIR/'forced.mp4']
    raw = []
    media = []
    for path in raw_paths:
        picked, pts = {}, []
        with av.open(str(path)) as video:
            for i,f in enumerate(video.decode(video=0)):
                pts.append(float(f.time))
                if i in wanted: picked[i] = f.to_ndarray(format='rgb24')
        raw.append(picked)
        media.append({'file':str(path),'sha256':digest(path),'frames':len(pts),
                      'pts_index_over_24':all(abs(v-i/24)<1e-10 for i,v in enumerate(pts))})
    show = C/'showcase'/f'{PAIR}_full_valid.mp4'
    comparison = []
    pts=[]
    with av.open(str(show)) as video:
        for i,f in enumerate(video.decode(video=0)):
            pts.append(float(f.time))
            if i not in indexes: continue
            rgb=f.to_ndarray(format='rgb24')
            for col in range(3):
                crop=rgb[:768,col*1152:(col+1)*1152].astype(np.int16)
                same=float(np.abs(crop-raw[col][i].astype(np.int16)).mean())
                rev=float(np.abs(crop-raw[col][146-i].astype(np.int16)).mean())
                comparison.append({'frame':i,'column':col,'same_time_rgb_mae':same,'reversed_time_rgb_mae':rev})
    result['display_order']={'media':media,'triptych_sha256':digest(show),'triptych_frames':len(pts),
        'triptych_pts_index_over_24':all(abs(v-i/24)<1e-10 for i,v in enumerate(pts)),
        'predeclared_indices':indexes,'comparisons':comparison,
        'same_time_better_than_reversed_where_distinguishable':all(x['same_time_rgb_mae'] <= x['reversed_time_rgb_mae'] for x in comparison)}
    result['wall_seconds']=time.time()-started
    result['passed']=True
    (OUT/'ACTUAL_CPU_PROBE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':True,'wall_seconds':result['wall_seconds'],'output':str(OUT/'ACTUAL_CPU_PROBE.json')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
