"""Bind actual R111 output to unchanged IVE MF code; create no GPU execution entry."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT.parent
CONSUMER = PROJECTS/'h3-ive-long0174-spatial-marginal-metrics-r111-20261019'
BASE = PROJECTS/'h3-ive-followup-quantitative-r97-r99-r100-20261019'
OLD = BASE/'audit/recovery_20261019/r107_long_0174'
OLD_CASE = OLD/'cases/r107_long_0174'
OLD_ACTUAL = OLD/'actual_host41/cases/r107_long_0174'
NAME = 'r111_long_0174_spatial'
DEST = ROOT/'actual_package'
PYTHON = '/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def prepare():
    contract = read(ROOT/'configs/INPUT_CONTRACT.json')
    assert sha(CONSUMER/'CONSUMER_FREEZE.json') == contract['consumer_freeze_sha256']
    incoming = CONSUMER/'incoming/long_0174'
    manifest = CONSUMER/'prepared/long_0174/MF_INPUTS.json'
    if not manifest.exists():
        return {'state': 'WAIT_ACTUAL_R111_CONSUMER', 'GPU_started': False, 'scores': None}
    assert not DEST.exists(), 'Preserve prior package; inspect before recovery.'
    code = 'import sys;sys.path.insert(0,'+repr(str(CONSUMER/'scripts'))+');import common;common.verify_collection(common.ROOT/"incoming/long_0174")'
    subprocess.run([PYTHON, '-c', code], check=True, timeout=120)
    m = read(manifest)
    assert m['scores'] is None and m['valid_frames'] == 145 and m['fps'] == 24
    assert m['pair_gate']['sha256'] == sha(incoming/'PAIR_RUNTIME_GATE.json')
    for item in m['roles'].values():
        for key in ('full_video', 'score_video'):
            assert sha(Path(item[key]['file'])) == item[key]['sha256']
    prior_manifest, prior_spec = read(OLD_CASE/'INPUTS.json'), read(OLD_CASE/'SPEC.json')
    assert sha(OLD/'RESULT_VERIFIED.json') == contract['R107_verified_result_sha256']
    returned = read(OLD/'actual_host41/audit/RETURN_SHA.json')
    for role in ('source', 'native', 'forced'):
        for name in ('REPORT.json', 'tracks.npz'):
            file = OLD_ACTUAL/'tracks'/role/name
            assert sha(file) == returned[str(file.relative_to(OLD/'actual_host41'))]
    report = read(OLD_ACTUAL/'tracks/source/REPORT.json')
    assert report['passed'] and report['tracks_shape'] == [1, 145, 100, 2]
    assert m['roles']['source']['full_video']['sha256'] == report['source_prepared_sha256']
    assert m['roles']['source']['frame_md5'] == report['decoded_frame_md5']
    assert m['roles']['native']['full_video']['sha256'] == prior_manifest['roles']['native']['full_sha256']
    assert m['roles']['fixed']['full_video']['sha256'] == prior_manifest['roles']['forced']['full_sha256']
    DEST.mkdir()
    for folder in ('scripts', 'runtime', 'configs'):
        shutil.copytree(BASE/folder, DEST/folder)
    (DEST/'audit').mkdir()
    case = DEST/'cases'/NAME
    (case/'inputs').mkdir(parents=True)
    copies = {'source_full.mp4': incoming/'source.mp4',
        'source_original.mp4': OLD_CASE/prior_spec['source']['original_file'],
        'source_provenance.json': OLD_CASE/prior_spec['source']['provenance_file'],
        'source_score.mp4': OLD_CASE/prior_manifest['roles']['source']['score_file'],
        'SOURCE_CACHE_INPUTS.json': OLD_CASE/'INPUTS.json',
        'spatial.mp4': incoming/'spatial.mp4',
        'spatial_score.mp4': Path(m['roles']['spatial']['score_video']['file']),
        'spatial_history.json': incoming/'history.json',
        'PAIR_RUNTIME_GATE.json': incoming/'PAIR_RUNTIME_GATE.json',
        'COLLECTION.json': incoming/'COLLECTION.json', 'CONSUMER_MF_INPUTS.json': manifest}
    for name, path in copies.items():
        shutil.copy2(path, case/'inputs'/name)
    shutil.copytree(OLD_ACTUAL/'tracks/source', case/'tracks/source')
    cfg = read(DEST/'configs/RUNTIME.json')
    cfg['remote_root'] = '/data4/researcher/h3_runs/ive_spatial_marginal_mf_r111_20261019'
    cfg['GPU_execution_status'] = 'CPU_PREPARED_ROOT_GPU_SCHEDULING_REQUIRED'
    (DEST/'configs/RUNTIME.json').write_text(json.dumps(cfg, indent=2)+'\n')
    gate = read(incoming/'PAIR_RUNTIME_GATE.json')
    spec = {'case_id': NAME, 'source_id': 'long_0174', 'valid_frames': 145,
        'total_frames': 158, 'fps': 24, 'crop_xywh': [16, 8, 1280, 720],
        'gate': {'file': 'inputs/PAIR_RUNTIME_GATE.json', 'sha256': sha(incoming/'PAIR_RUNTIME_GATE.json'),
                 'schema': gate['schema']}, 'source': prior_spec['source'],
        'targets': {'spatial': {'full_file': 'inputs/spatial.mp4',
            'full_sha256': m['roles']['spatial']['full_video']['sha256'],
            'history_file': 'inputs/spatial_history.json', 'history_sha256': sha(incoming/'history.json'),
            'run_id': gate['runs']['forced']['run_id'], 'gate_video_keys': ['runs', 'forced', 'video'],
            'gate_run_keys': ['runs', 'forced', 'run_id'], 'method_label': 'spatial_marginal steps6..14'}},
        'source_cache_reuse': {'original_cache_dir': str(OLD_ACTUAL/'tracks/source'),
            'cache_inputs_file': 'inputs/SOURCE_CACHE_INPUTS.json', 'cache_inputs_sha256': sha(OLD_CASE/'INPUTS.json'),
            'selection_sha256': report['selection_sha256'],
            'source_report_sha256': sha(OLD_ACTUAL/'tracks/source/REPORT.json'),
            'source_tracks_sha256': sha(OLD_ACTUAL/'tracks/source/tracks.npz'),
            'source_score_sha256': report['source_score_sha256'],
            'host': report['admission_before_cuda']['hostname'],
            'gpu_name': report['admission_before_cuda']['gpu_name'],
            'torch_version': report['torch_version'], 'cuda_version': report['cuda_version']}}
    put(case/'SPEC.json', spec)
    put(case/'INTAKE_RECEIPT.json', {'consumer_manifest': {'file': str(manifest), 'sha256': sha(manifest)},
        'files': {name: {'file': str(path), 'sha256': sha(path)} for name, path in copies.items()},
        'R107_actual_evidence': {'file': str(OLD/'RESULT_VERIFIED.json'), 'sha256': sha(OLD/'RESULT_VERIFIED.json')},
        'GPU_started': False, 'scores': None})
    result = subprocess.run([PYTHON, str(DEST/'scripts/prepare.py'), '--case', NAME,
        '--ffmpeg', '/opt/homebrew/bin/ffmpeg', '--ffprobe', '/opt/homebrew/bin/ffprobe'],
        capture_output=True, text=True, timeout=300)
    (DEST/'audit/CPU_PREPARE.log').write_text(result.stdout+result.stderr)
    assert result.returncode == 0, 'Inspect retained CPU preparation log.'
    receipt = {'state': 'ACTUAL_INPUTS_READY_ROOT_TRACKER_BINDING_REQUIRED',
        'fresh_roles': ['spatial'], 'cached_roles': ['source'], 'valid_frames': 145, 'fps': 24,
        'source_pixels_and_cached_native_fixed_media_verified': True,
        'inputs': {'file': str(case/'INPUTS.json'), 'sha256': sha(case/'INPUTS.json')},
        'GPU_started': False, 'scores': None}
    put(DEST/'audit/READY.json', receipt)
    return receipt


if __name__ == '__main__':
    print(json.dumps(prepare(), ensure_ascii=False))
