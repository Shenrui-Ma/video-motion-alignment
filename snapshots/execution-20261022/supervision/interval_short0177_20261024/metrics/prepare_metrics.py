"""Bind seven verified local clips to an isolated official nine-metric manifest."""
import argparse
import hashlib
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def validate_bindings(binding, config, probe=True):
    if binding.get('task_id') != config['task_id']:
        raise ValueError('task_id mismatch')
    if set(binding.get('videos', {})) != set(config['methods']):
        raise ValueError('Exactly source plus six specified methods are required')
    gate = Path(binding['completion_gate']).resolve()
    if json.loads(gate.read_text()).get('passed') is not True:
        raise ValueError('Root six-arm completion gate has not passed')
    checked = {}
    for method in config['methods']:
        item = binding['videos'][method]
        file = Path(item['file']).resolve()
        actual = digest(file)
        if actual != item['sha256']:
            raise ValueError(f'{method}: video SHA mismatch')
        if method == 'source' and actual != config['source_sha256']:
            raise ValueError('Source SHA differs from frozen input')
        geometry = None
        if probe:
            result = subprocess.check_output([
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,nb_frames,r_frame_rate',
                '-of', 'json', str(file)], text=True)
            geometry = json.loads(result)['streams'][0]
            expected = config['geometry']
            if (int(geometry['width']), int(geometry['height']),
                    int(geometry['nb_frames']), Fraction(geometry['r_frame_rate'])) != (
                    expected['width'], expected['height'], expected['sampled_frames'],
                    Fraction(expected['fps'])):
                raise ValueError(f'{method}: geometry mismatch {geometry}')
        checked[method] = dict(file=str(file), sha256=actual, ffprobe=geometry)
    return checked, {'file': str(gate), 'sha256': digest(gate)}


def prepare(binding_file, output):
    config = json.loads((HERE / 'config.json').read_text())
    binding = json.loads(Path(binding_file).read_text())
    checked, gate = validate_bindings(binding, config)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Use a fresh output directory; preserve existing preparation')
    output.mkdir(parents=True)
    remote = Path(config['remote_root'])
    jobs, transfers = [], []
    geometry = config['geometry']
    for method, media in checked.items():
        video = str(remote / 'videos' / (method + '.mp4'))
        jobs.append({
            'id': f'interval20261024_short_0177__{method}',
            'task_id': config['task_id'], 'dataset': config['dataset'],
            'cohort': config['cohort'], 'method': method,
            'metadata': config['metadata'],
            'metadata_file': str(remote / 'metadata/short_0177.json'),
            'source_frames_parent': str(remote / 'frames/source'),
            'target_frames_parent': str(remote / 'frames' / method),
            'video': video, 'sha256': media['sha256'],
            'valid_frames': geometry['valid_frames'],
            'crop_xywh': geometry['crop_xywh'], 'fps': geometry['fps'],
            'seed': config['seed'], 'source_manifest': 'isolated new six-arm completion gate',
            'prompt_provenance': 'verbatim_official_edit_prompt',
        })
        transfers.append(dict(local=media['file'], remote=video, sha256=media['sha256']))
    manifest = dict(schema='h3-12metrics-v1', root=str(remote), jobs=jobs,
                    numeric_metrics=config['numeric_metrics'], expected_numeric=63,
                    expected_qa_not_applicable=7, completion_gate=gate,
                    is_cf_policy=config['is_cf_policy'])
    for name, obj in [('manifest.json', manifest), ('transfers.json', transfers),
                      ('PREPARED.json', {'passed': True, 'videos': checked, 'completion_gate': gate})]:
        (output / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    for name in ['config.json', 'HOST81_READONLY.json', 'metric_worker.py',
                 'durable_metrics.py', 'prepare_frames.py', 'run_metrics.py']:
        shutil.copy2(HERE / name, output / name)
    print(json.dumps({'prepared': str(output), 'jobs': len(jobs), 'numeric_items': 63}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bindings', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    prepare(args.bindings, args.output)
