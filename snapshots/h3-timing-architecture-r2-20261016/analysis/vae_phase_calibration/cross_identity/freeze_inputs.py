"""Bind existing CPU tensors and fixed methods before computing new lag scores."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[key] = '1'
import datetime
import hashlib
import json
from pathlib import Path
import torch

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
R2 = BASE.parents[1]
OLD = R2.parent / 'h3-timing-autoresearch-20261016'
OBSERVER = R2 / 'analysis/latent_observer'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tensor_info(value):
    return dict(shape=list(value.shape), dtype=str(value.dtype),
                sha256=hashlib.sha256(value.contiguous().view(torch.uint8).numpy()).hexdigest())


def bind(path, snapshot):
    data = torch.load(path, map_location='cpu', weights_only=True, mmap=True)
    value = data['video'] if snapshot else data
    meta = data['metadata'] if snapshot else None
    info = tensor_info(value)
    if info['shape'] != [1, 24, 42, 46, 82] or info['dtype'] != 'torch.float32':
        raise ValueError('Unexpected tensor shape/dtype')
    if snapshot:
        if meta['normalization_stage'] != 'after_process_latent_out':
            raise ValueError('Unexpected latent normalization')
        if any(meta['video'][k] != v for k, v in info.items()):
            raise ValueError('Snapshot metadata/raw tensor mismatch')
    return dict(path=str(path), file_sha256=sha(path), tensor=info, metadata=meta)


def main():
    torch.set_num_threads(1)
    clean = json.loads((BASE / 'PROTOCOL.json').read_text())
    protocol = {
        'schema': 'h3-cross-identity-phase-observer-v1',
        'frozen_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status': 'Exploratory necessity test on previously inspected examples; not heldout validation',
        'methods': ['phase_mean_centering', 'same_phase_gap5'],
        'method_source': str(BASE / 'evaluate.py'),
        'method_source_sha256': sha(BASE / 'evaluate.py'),
        'clean_control_protocol_sha256': sha(BASE / 'PROTOCOL.json'),
        'clean_control_manifest_sha256': sha(BASE / 'manifest.json'),
        'reject_rules': clean['reject_rules'],
        'time_geometry': clean['time_geometry'],
        'lag_search_frames': clean['lag_search_frames'],
        'sign': clean['sign'],
        'interpolation': clean['interpolation'],
        'score': clean['score'],
        'normalization': 'reference native VAE output vs x0 after_process_latent_out; unchanged FP32 values promoted to FP64 for analysis',
        'regions': ['primary_full_frame', 'sensitivity_source_upper_body'],
        'sources': {},
        'pose_comparison': {
            'timing': 'Read independent frozen pose reports after computing all latent results; no selection or calibration from their labels',
            'per_threshold': 'Compare every non-null reliable_lag_frames separately at thresholds0.3 and0.5, retaining their status/flags/coverage',
            'tolerance_frames': 2,
            'direction': 'Classify abs(lag)<=2 as near_zero, otherwise delayed or advanced; does not replace exact error',
            'primary_comparison': 'Full-frame final pose known at both thresholds, agreeing within2frames; require latent accepted and within2 of both; failed/unknown all retained',
            'intermediate': 'Use only same-checkpoint pose observability. Final pose is not ground truth for intermediate x0. Unknown stays unverified even if matching final lag',
            'gate': 'Report counts and every cell; any accepted wrong-direction or >2frame final error blocks a general reliable-observer claim for that method. ROI cannot rescue the primary method.',
        },
        'limitations': [
            'Per-sequence phase means fitted on the entire current snapshot, not future sampler states; can remove genuine phase-correlated actions',
            'Gap5 integrates17physical frames and may merge brief actions',
            'Fixed pixel coordinates and channel cosine do not establish cross-identity correspondence',
            'Current rejection rules reject degeneracy, not calibrated confidence; a clear score minimum can be wrong',
            'Source05 and07 are old selected cases; not independent blind evaluation',
            'Early x0 uses all video frames of a current denoising estimate, not an online streaming video',
            'No controller/GPU/new encode/new pose; no changes to original primary RGB endpoint',
        ],
    }
    for source in ('05', '07'):
        if source == '05':
            condition = OLD / 'audit/05_sam_1312x736_shared_v3_conditioning.json'
            refpath = OBSERVER / 'reference_video_vae.pt'
            roi = clean['regions']['sensitivity_source_upper_body']
            windows = clean['windows_inclusive']
            paths = [(mode + '/' + stem, OLD / 'audit/x0' / f's05_full_seed1_{mode}_x0' / (stem + '.pt'))
                     for mode in ('native', 'mass') for stem in ('x0_step005', 'x0_step010', 'x0_step015', 'sampler_final')]
            roi_source = OBSERVER / 'protocol.json'
        else:
            condition = OLD / 'analysis/transfer_runtime_evidence/audit/07_sam_1312x736_shared_v3_conditioning.json'
            refpath = OBSERVER / 'source07/reference.pt'
            info = json.loads((OBSERVER / 'source07/results.json').read_text())
            roi, windows = info['source_only_roi_yxyx'], info['windows']
            paths = [(mode + '/sampler_final', OBSERVER / 'source07' / (mode + '.pt')) for mode in ('native', 'mass')]
            roi_source = OBSERVER / 'source07/results.json'
        reference = bind(refpath, False)
        condition_data = json.loads(condition.read_text())
        recorded = condition_data['native_vae_calls'][1]['latent']
        if any(recorded[k] != v for k, v in reference['tensor'].items()):
            raise ValueError('Reference does not match actual conditioning audit')
        runs = {name: bind(path, True) for name, path in paths}
        for name, run in runs.items():
            actual = condition.parent / f's{source}_full_seed1_{name.split("/")[0]}_x0_conditioning.json'
            other = json.loads(actual.read_text())['native_vae_calls'][1]['latent']
            if any(other[k] != v for k, v in reference['tensor'].items()):
                raise ValueError('Actual arm reference differs from shared reference')
            run['actual_conditioning'] = dict(path=str(actual), sha256=sha(actual), pointer='native_vae_calls[1].latent')
        protocol['sources'][source] = dict(
            reference=reference, runs=runs, windows_inclusive=windows,
            regions=dict(primary_full_frame=[0,46,0,82], sensitivity_source_upper_body=roi),
            roi_provenance=dict(path=str(roi_source), sha256=sha(roi_source), source_only=True),
            conditioning_audit=dict(path=str(condition), sha256=sha(condition), pointer='native_vae_calls[1].latent'))
    if torch.cuda.is_initialized():
        raise RuntimeError('CUDA unexpectedly initialized')
    with (HERE / 'PROTOCOL.json').open('x') as stream:
        json.dump(protocol, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    print('Frozen protocol SHA256', sha(HERE / 'PROTOCOL.json'))
    print('All twelve tensors bound to file/raw hashes. No lag calculation performed. CUDA initialized:', torch.cuda.is_initialized())


if __name__ == '__main__':
    main()
