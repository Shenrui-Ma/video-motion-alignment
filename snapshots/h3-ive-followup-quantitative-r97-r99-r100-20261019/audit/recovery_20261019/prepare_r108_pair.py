"""CPU-only IVE MF entry for completed R108 pair; wait for real media."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
PROJECTS = BASE.parent
PYTHON = '/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'
SOURCES = {'r108': ('short_0392',)}
NAMES = {'r108': 'h3-ive-fireplace-recovery-metrics-r108-20261019'}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def inputs(lane, source):
    assert source in SOURCES[lane]
    consumer = PROJECTS / NAMES[lane]
    config = read(consumer / 'configs/contract.json')
    dest = consumer / ('incoming_pairs' if lane == 'r108' else 'incoming') / source
    gatefile = dest / 'PAIR_RUNTIME_GATE.json'
    if not gatefile.is_file() or not (dest / 'COLLECTION.json').is_file():
        return {'case': f'{lane}_{source}', 'status': 'PENDING_ACTUAL_PAIRED_INTAKE',
                'required_gate': str(gatefile), 'GPU_started': False}

    # Run the original consumer's actual checks in its own import namespace.
    if lane == 'r108':
        code = 'import common,paired;common.validate_static();paired.verify_pair_intake(' + repr(source) + ')'
    else:
        code = 'import consume;consume.verify_gate(' + repr(source) + ',consume.read(consume.ROOT/"incoming"/' + repr(source) + '/"PAIR_RUNTIME_GATE.json"))'
    command = 'import sys;sys.path.insert(0,' + repr(str(consumer / 'scripts')) + ');' + code
    subprocess.run([PYTHON, '-c', command], cwd=consumer, check=True, timeout=120)
    freeze = read(consumer / 'CONSUMER_FREEZE.json')
    for rel, entry in freeze['files'].items():
        assert sha(consumer / rel) == (entry['sha256'] if isinstance(entry, dict) else entry)
    collection = read(dest / 'COLLECTION.json')
    for name, digest in collection['files'].items():
        assert Path(name).name == name and sha(dest / name) == digest
    gate = read(gatefile)
    assert gate['passed'] and all(v is True for v in gate['checks'].values())
    assert gate['runtime_profile_sha256'] == config['producer_runtime_sha256']
    assert set(gate['runs']) == {'native', 'forced'}
    if lane == 'r108':
        source_consumer = consumer
        row = next(x for x in config['sources'] if x['source_id'] == source)
        histories = {r: dest / (r + '_history.json') for r in ('native', 'forced')}
    else:
        source_consumer = PROJECTS / 'h3-ive-native-screen-metrics-r96-20261018'
        prior = read(source_consumer / 'configs/contract.json')
        row = next(x for x in prior['sources'] if x['source_id'] == source)
        histories = {'native': source_consumer / 'incoming' / source / 'native_history.json',
                     'forced': dest / 'history.json'}
    source_file = source_consumer / row['source']['file']
    original = Path(row['original_media']['file'])
    provenance = source_consumer / row['provenance']['file']
    assert sha(source_file) == row['source']['sha256']
    assert sha(original) == row['original_media']['sha256']
    assert sha(provenance) == row['provenance']['sha256']
    for role in ('native', 'forced'):
        actual = gate['runs'][role]
        assert actual['NFE'] == 20 and actual['routed_blocks'] == (0 if role == 'native' else 450)
        assert actual['valid_frames'] == row['valid_frames']
        assert sha(dest / (role + '.mp4')) == actual['video']['sha256']
    return consumer, config, dest, gatefile, gate, row, source_file, original, provenance, histories


def prepare(lane, source):
    evidence = inputs(lane, source)
    if isinstance(evidence, dict):
        return evidence
    consumer, config, dest, gatefile, gate, row, full, original, provenance, histories = evidence
    name = f'{lane}_{source}'
    root = HERE / name
    assert not root.exists(), 'Existing attempt preserved; inspect it before recovery.'
    root.mkdir()
    for folder in ('scripts', 'runtime', 'configs'):
        shutil.copytree(BASE / folder, root / folder)
    (root / 'audit').mkdir()
    case = root / 'cases' / name
    (case / 'inputs').mkdir(parents=True)
    runtime = read(root / 'configs/RUNTIME.json')
    runtime['remote_root'] = f'/data4/researcher/h3_runs/ive_recovery_{name}_20261019'
    runtime['GPU_execution_status'] = 'CPU_READY_ROOT_SCHEDULING_REQUIRED'
    save(root / 'configs/RUNTIME.json', runtime)
    copies = {'source_full.mp4': full, 'source_original.mp4': original,
              'source_provenance.json': provenance, 'PAIR_RUNTIME_GATE.json': gatefile,
              'COLLECTION.json': dest / 'COLLECTION.json',
              'CONSUMER_CONTRACT.json': consumer / 'configs/contract.json'}
    for role in ('native', 'forced'):
        copies[role + '.mp4'] = dest / (role + '.mp4')
        copies[role + '_history.json'] = histories[role]
    manifest = consumer/'prepared'/source/'paired/MF_INPUTS.json'
    assert manifest.is_file(), 'actual paired MF manifest missing'
    copies['MF_INPUTS.json'] = manifest
    copies['ACTUAL_NATIVE_VISUAL_REVIEW.json'] = consumer/'audit/root_native_review'/source/'REVIEW.json'
    for target, path in copies.items():
        shutil.copy2(path, case / 'inputs' / target)
    spec = {'case_id': name, 'source_id': source, 'valid_frames': row['valid_frames'],
            'total_frames': row['geometry']['frames'], 'fps': 24, 'crop_xywh': [16, 8, 1280, 720],
            'gate': {'file': 'inputs/PAIR_RUNTIME_GATE.json', 'sha256': sha(gatefile),
                     'schema': gate['schema'], 'valid_frame_keys': ['runs', 'native', 'valid_frames'],
                     'crop_keys': ['runs', 'native', 'evaluation_crop_xywh']},
            'source': {'full_file': 'inputs/source_full.mp4', 'full_sha256': sha(full),
                       'original_file': 'inputs/source_original.mp4', 'original_sha256': sha(original),
                       'provenance_file': 'inputs/source_provenance.json', 'provenance_sha256': sha(provenance)},
            'targets': {}}
    if lane == 'r107':
        spec['gate']['valid_frame_keys'] = ['valid_frames']
        spec['gate']['crop_keys'] = ['evaluation_crop_xywh']
    for role in ('native', 'forced'):
        spec['targets'][role] = {'full_file': 'inputs/' + role + '.mp4',
            'full_sha256': gate['runs'][role]['video']['sha256'],
            'history_file': 'inputs/' + role + '_history.json', 'history_sha256': sha(histories[role]),
            'run_id': gate['runs'][role]['run_id'], 'gate_video_keys': ['runs', role, 'video'],
            'gate_run_keys': ['runs', role, 'run_id'],
            'method_label': 'ordinary' if role == 'native' else 'fixed same-bin steps6..14'}
    save(case / 'SPEC.json', spec)
    save(case / 'INTAKE_RECEIPT.json', {'consumer': str(consumer),
         'consumer_freeze_sha256': sha(consumer / 'CONSUMER_FREEZE.json'),
         'input_sources': {key: {'file': str(path), 'sha256': sha(path)} for key, path in copies.items()},
         'GPU_started': False})
    result = subprocess.run([PYTHON, str(root / 'scripts/prepare.py'), '--case', name,
                             '--ffmpeg', '/opt/homebrew/bin/ffmpeg', '--ffprobe', '/opt/homebrew/bin/ffprobe'],
                            capture_output=True, text=True, timeout=300)
    (root / 'audit/PREPARE.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, 'CPU media preparation failed; inspect saved log.'
    # Tracker launch is deliberately a separate root-coordinated step after H3 release.
    save(root / 'audit/READY_FOR_TRACKER_BINDING.json', {'case': name, 'passed': True,
         'inputs_sha256': sha(case / 'INPUTS.json'), 'roles': ['source', 'native', 'forced'],
         'valid_frames': row['valid_frames'], 'GPU_started': False,
         'requirements': 'Fresh same .41 GPU for all three tracks; official IVE runtime; root schedules after R111 release.'})
    return {'case': name, 'status': 'CPU_INPUTS_READY_FOR_ROOT_TRACKER_BINDING',
            'package': str(root), 'input_sha256': sha(case / 'INPUTS.json'), 'GPU_started': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--lane', choices=SOURCES, required=True)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.lane, args.source)))
