"""Reuse pinned official FlexiAct MF only for proved-identical released inputs."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
RUNTIME = Path('/data5/researcher/h3_runs/flexiact_official_metric_20261017')
NATIVE = Path('/data5/researcher/h3_runs/flexiact_native_scores_r49_20261017')
FREEZE = 'fa573e2065d1c140ef232513d73b909d2aa2902046d4a9becf609a6e549ad580'
PINNED_SCORES = {
 'chest': '2576a54859a21c39f5008e8734f51fb800afbf15b5fd413805d05655061113b6',
 'crouch': '9afbb2aa08d6895651e1eae2c602b57dfcb697fb1a511f3a769f2545cc7436db',
 'fitness': '0d515a41abc30f37807268c7aa332d4ed058c68b8e02fde44774490b1ab0e665',
 'one_leg': 'af005b2272129c59246f8e7c5134d5153e2b80212b57182cfc7a0137219917a0',
 'rotate': 'e79b71b08710abee98414041593a299631cffc49d8ded54a7e05743dde2a559b'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bound(row):
    require(sha(row['file']) == row['sha256'], 'bound content changed: ' + row['file'])
    return read(row['file'])


def compatible(auto, native, proof, domain):
    for key in ('official_pair_id', 'original_source_sha256', 'target_sha256', 'physical_seconds',
                'source_indices', 'full_output_indices', 'source_frames', 'source_fps',
                'output_frames', 'output_fps', 'output_size'):
        require(auto[key] == native[key], 'source or time mapping differs: ' + key)
    require(proof['benchmark'] == 'flexiact' and proof['runtime_freeze_sha256'] == FREEZE,
            'official reader configuration differs')
    require(proof['same_physical_timebase'] and proof['comparison']['exact'] and not proof['cuda_initialized'],
            'official reader equality missing')
    for name, data in (('left', native), ('right', auto)):
        require(proof[name] == {'file': data[domain], 'sha256': data[domain + '_sha256']},
                'identity proof input differs')
    count, fps = (158, 24) if domain == 'full158_output' else (49, 8)
    for name in ('left', 'right'):
        metadata = proof['metadata'][name]
        require(len(metadata['timestamps_seconds']) == count and
                all(abs(t - i / fps) <= 1e-6 for i, t in enumerate(metadata['timestamps_seconds'])),
                'identity timebase differs')
    require(proof['comparison']['left_shape'][0] == count and
            proof['comparison']['right_shape'] == proof['comparison']['left_shape'], 'frame geometry differs')
    frames = proof['comparison']['frames']
    require([f['index'] for f in frames] == list(range(count)) and
            all(f['left_rgb_sha256'] == f['right_rgb_sha256'] and f['differing_channels'] == 0 for f in frames),
            'per-frame identity evidence differs')


def main():
    p = argparse.ArgumentParser(); p.add_argument('--source', required=True); a = p.parse_args()
    require(a.source in PINNED_SCORES, 'source has no independently pinned Native score')
    sys.path.insert(0, str(HERE.parent)); import remote_consume as consumer
    sys.path.insert(0, str(HERE / 'priority_v2')); from priority import pending
    consumer.online_pending = lambda: pending(consumer.P['online_priority_roots'])
    with consumer.locked():
        folder = HERE / 'media_identity' / a.source
        summary_path = folder / 'SUMMARY.json'; summary = read(summary_path)
        auto = bound(summary['auto_metric_inputs']); native = bound(summary['native_metric_inputs'])
        ready = bound(summary['case_ready'])
        require(ready['summary']['passed'] and ready['metric_inputs_sha256'] == summary['auto_metric_inputs']['sha256'],
                'Auto release differs')
        for domain in ('full158_output', 'edited49'):
            compatible(auto, native, bound(summary['proofs'][domain]), domain)
            for record in (auto, native):
                require(sha(record[domain]) == record[domain + '_sha256'], 'video changed after identity proof')
        for record in (auto, native):
            require(sha(record['original_source']) == record['original_source_sha256'] and
                    sha(record['target_image']) == record['target_sha256'], 'original source/identity changed')
        freeze_path = RUNTIME / 'RUNTIME_FREEZE.json'
        require(sha(freeze_path) == FREEZE, 'runtime freeze differs')
        freeze = read(freeze_path)
        for filename, item in freeze['files'].items():
            require(sha(RUNTIME / filename) == item['sha256'], 'runtime member changed: ' + filename)
        score_path = NATIVE / 'scores/native' / a.source / 'SCORE.json'
        require(sha(score_path) == PINNED_SCORES[a.source], 'original published Native score changed')
        score = read(score_path)
        require(score['pair_id'] == auto['official_pair_id'] and score['status'] == 'finite' and
                math.isfinite(score['score']) and score['points'] == 3025 and score['frames'] == 49,
                'cached score identity or dimensions differ')
        require(sha(score_path.parent / 'similarity.pt') == score['similarity_sha256'], 'cached similarity changed')
        sys.path.insert(0, str(RUNTIME)); import torch
        from score_pair import read_tracks
        ref_dir = RUNTIME / 'outputs/reference' / a.source
        edit_dir = NATIVE / 'tracks/native' / a.source
        _, ref = read_tracks(ref_dir, torch); _, edit = read_tracks(edit_dir, torch)
        require(sha(ref_dir / 'REPORT.json') == score['reference_report_sha256'] and
                sha(edit_dir / 'REPORT.json') == score['edit_report_sha256'], 'score tracker reports differ')
        require(ref['case']['id'] == edit['case']['id'] == score['pair_id'] and
                ref['case']['sha256'] == auto['original_source_sha256'], 'score source differs')
        require(edit['case']['file'] == native['edited49'] and edit['case']['sha256'] == native['edited49_sha256'] and
                edit['case']['generation_binding']['metric_inputs'] == summary['native_metric_inputs'],
                'cached generated video release differs')
        require(not torch.cuda.is_initialized(), 'CPU verification unexpectedly initialized CUDA')
        result = {'schema': 'official-mf-reused-identical-input-v1', 'pair_id': score['pair_id'],
                  'source_id': a.source, 'method': 'auto', 'motion_fidelity': score['score'],
                  'status': 'reused_identical_input', 'new_tracker_invocations': 0,
                  'partial_batch': True, 'planned_denominator': 5, 'runtime_freeze_sha256': FREEZE,
                  'checkpoint_sha256': ref['checkpoint_sha256'], 'metric_functions_sha256': ref['metric_functions_sha256'],
                  'vendor_manifest_sha256': ref['vendor_manifest_sha256'],
                  'auto_metric_inputs': summary['auto_metric_inputs'], 'native_metric_inputs': summary['native_metric_inputs'],
                  'release_evidence': summary['case_ready'], 'identity_summary': {'file': str(summary_path), 'sha256': sha(summary_path)},
                  'score_input_identity_proof': summary['proofs']['edited49'],
                  'full_video_identity_proof': summary['proofs']['full158_output'],
                  'cached_native_score': {'file': str(score_path), 'sha256': sha(score_path), 'json_pointer': '/score'},
                  'source_report': {'file': str(ref_dir / 'REPORT.json'), 'sha256': sha(ref_dir / 'REPORT.json')},
                  'target_report': {'file': str(edit_dir / 'REPORT.json'), 'sha256': sha(edit_dir / 'REPORT.json')},
                  'source_tracks_sha256': ref['tracks_sha256'], 'target_tracks_sha256': edit['tracks_sha256'],
                  'similarity_sha256': score['similarity_sha256'], 'receipt_code_sha256': sha(__file__),
                  'cuda_initialized': False,
                  'interpretation': 'Auto and Native have identical released RGB and timestamps; the pinned official MF score is reused. This pair has zero measured improvement.'}
        output = folder / 'REUSED_MF_SCORE.json'
        with output.open('x') as f:
            json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
        print(json.dumps({'file': str(output), 'sha256': sha(output), 'motion_fidelity': result['motion_fidelity']}))


if __name__ == '__main__':
    try:
        main()
    except BlockingIOError:
        print('ONLINE_PRIORITY_OR_CPU_LOCK'); raise SystemExit(75)
