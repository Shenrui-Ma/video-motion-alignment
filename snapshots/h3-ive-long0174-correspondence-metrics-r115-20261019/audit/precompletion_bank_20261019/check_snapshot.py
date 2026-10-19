"""Check the first run's captured bank on CPU while its video is still sampling."""
import hashlib, importlib.util, json, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'match_geometry_review/diagnostic.py'
spec = importlib.util.spec_from_file_location('frozen_geometry', SOURCE)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def tensor_digest(a, dtype):
    return hashlib.sha256(canonical({'shape': list(a.shape), 'dtype': dtype}) + a.tobytes()).hexdigest()

def main():
    out = ROOT / 'geometry_result'
    d.require(not out.exists(), 'preserve previous snapshot analysis')
    snapshot = d.read(ROOT / 'ROUTER_SNAPSHOT.json')['snapshot']
    d.require(snapshot['run_id'] == 'r115_long_0174_seed2026101701_fixed_one_bin', 'wrong actual run')
    tracks, visibility, binding = d.verify_source()
    regions_file = ROOT.parent / 'match_geometry_review/SOURCE_PERSON_TRACK_SUBSET.json'
    regions = d.read(regions_file)
    d.validate_regions(regions, binding)
    frames = d.representative_frames()
    blocks, rows, acceptance = {}, [], []
    for block in range(50):
        folder = ROOT / 'banks' / f'block_{block:02d}'
        meta = d.read(folder / 'bank.json')
        d.require(meta['storage'] == {'file': 'indices.npz', 'sha256': d.sha(folder / 'indices.npz')}, 'bank bytes differ')
        m = meta['metadata']
        d.require(m['block'] == block and m['source_step'] == 5 and m['spatial_grid'] == [23, 41], 'bank provenance differs')
        d.require(m['geometry'] == {'batch':1,'heads':56,'total_bins':47,'valid_bins':43,'frame_rows':943,'head_dim':128}, 'geometry differs')
        with np.load(folder / 'indices.npz', allow_pickle=False) as z:
            d.require(set(z.files) == {'forward', 'backward'}, 'unexpected bank fields')
            d.require(all(np.issubdtype(z[k].dtype, np.integer) for k in z.files), 'integer indices required')
            arrays = np.stack([z['forward'], z['backward']]).astype('<i8')
        d.require(arrays.shape == (2, 42, 943) and np.all((arrays >= -1) & (arrays < 943)), 'indices outside support')
        for forward, backward in zip(*arrays):
            p = np.arange(943); f = forward >= 0; b = backward >= 0
            d.require(np.array_equal(backward[forward[f]], p[f]) and np.array_equal(forward[backward[b]], p[b]), 'nonreciprocal indices')
        d.require(tensor_digest(arrays, 'torch.int64') == meta['indices_sha256'], 'indices digest differs')
        d.require(tensor_digest(arrays >= 0, 'torch.bool') == meta['masks_sha256'], 'mask digest differs')
        body = {k:v for k,v in meta.items() if k not in ('storage', 'bank_sha256')}
        d.require(hashlib.sha256(canonical(body)).hexdigest() == meta['bank_sha256'], 'bank digest differs')
        blocks[str(block)] = meta['bank_sha256']
        acceptance.append({'block': block, 'accepted': int((arrays >= 0).sum()), 'total': int(arrays.size)})
        rows.append(d.evaluate_bank(tracks, visibility, *arrays, frames, block, regions))
    collection = hashlib.sha256(canonical(blocks)).hexdigest()
    d.require(blocks == snapshot['correspondence_bank_collection']['blocks'] and collection == snapshot['correspondence_bank_collection']['collection_sha256'], 'snapshot bank collection differs')
    rows = np.concatenate(rows)
    out.mkdir()
    np.savez_compressed(out / 'points.npz', rows=rows)
    d.save(out / 'SOURCE_BINDING.json', binding)
    summaries = snapshot['forward_summaries']
    step6 = [x for x in summaries if x.get('forward_index', x.get('step')) == 6]
    result = {'schema':'r115-precompletion-first-arm-bank-diagnostic-v1', 'created_unix':time.time(),
        'status':'FIRST_ARM_BANK_VERIFIED_PAIR_OUTPUT_PENDING', 'actual_run_id':snapshot['run_id'],
        'snapshot':d.bound(ROOT/'ROUTER_SNAPSHOT.json'), 'source_binding':d.bound(out/'SOURCE_BINDING.json'),
        'source_subset':d.bound(regions_file), 'diagnostic_code':d.bound(SOURCE), 'snapshot_check_code':d.bound(Path(__file__)),
        'points':d.bound(out/'points.npz'), 'bank_collection_sha256':collection, 'token_acceptance':acceptance,
        'summary':d.grouped(rows, regions), 'step6_snapshot':step6,
        'snapshot_sampling':{k:snapshot[k] for k in ('status','completed_calls','routed_calls','last_completed_forward_index','correspondence_prefix_gate')},
        'interpretation':'First-arm frozen-bank geometry versus cached source CoTracker observations. Pair equality and generated-video outcomes are pending. Source-selected visible points have limited coverage; unselected points are not background ground truth. Position-bin representatives are not exact VAE receptive fields. Counts across 50 layers repeat the same source observations and are not independent samples.',
        'GPU_started':False, 'large_x0_downloaded':False}
    d.save(out/'RESULT.json', result)
    d.require('torch' not in sys.modules, 'unexpected torch import')
    print(json.dumps({'result':str(out/'RESULT.json'),'sha256':d.sha(out/'RESULT.json'),'full_image':result['summary']['full_image'],'groups':result['summary']['source_person_groups']}, ensure_ascii=False))

if __name__ == '__main__':
    main()
