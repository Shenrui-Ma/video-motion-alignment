"""Create an independently sealed CPU-only .9 fallback for the same scientific inputs."""
from pathlib import Path
import argparse, ast, hashlib, json, shutil

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')

def main(root):
    root = Path(root).resolve()
    source = root / 'host41_package'
    original_freeze = read(source / 'CONSUMER_FREEZE.json')
    assert all(sha(source / name) == value for name, value in original_freeze['files'].items())
    package = root / 'host9_package'
    assert not package.exists(), 'preserve previous CPU fallback'
    shutil.copytree(source, package, ignore=shutil.ignore_patterns('__pycache__'))
    runtime = read(package / 'configs/RUNTIME.json')
    old_remote = runtime['remote_root']
    remote = '/home/researcher/h3_runs/' + Path(old_remote).name + '_host9'
    python = '/home/researcher/miniconda3/envs/comfyui/bin/python'
    for relative in ('runtime/official_metric/SOURCE_INPUTS.json',
                     'prepared/native/METRIC_INPUTS.json', 'prepared/guided/METRIC_INPUTS.json',
                     'prepared/native_49_8fps.mapping.json', 'prepared/guided_49_8fps.mapping.json',
                     'prepared/guided/MATCHED_GATE_BINDING.json'):
        path = package / relative
        path.write_text(path.read_text().replace(old_remote, remote))
    for method in ('native', 'guided'):
        path = package / 'prepared' / method / 'TRACK_INPUTS.json'
        manifest = read(path)
        item = manifest['inputs'][0]
        item['file'] = item['file'].replace(old_remote, remote)
        for key in ('metric_inputs', 'release_mapping'):
            binding = item['generation_binding'][key]
            relative = Path(binding['file']).relative_to(old_remote)
            binding.update(file=remote + '/' + str(relative), sha256=sha(package / relative))
        save(path, manifest)
    runtime.update(remote_root=remote, python=python, host='H3_SERVER_A', uid=1016,
                   GPU=None, status='CPU_ONLY_WAIT_ROOT_EXACT_GPU_RELEASE',
                   fresh_same_runtime_methods=['reference', 'native', 'guided'],
                   GPU_started=False, GPU_launch_entrypoint_created=False,
                   parent_host41_freeze_sha256=sha(source / 'CONSUMER_FREEZE.json'))
    save(package / 'configs/RUNTIME.json', runtime)
    authority = package / 'audit/run_authorized.py'
    authority.rename(package / 'audit/HOST41_WRAPPER_REFERENCE.txt')
    check = package / 'audit/check_package.py'
    check.write_text(check.read_text().replace("R/'audit/run_authorized.py'", "R/'audit/HOST41_WRAPPER_REFERENCE.txt'"))
    plan = package / 'scripts/tracking_plan.py'
    plan.write_text(plan.read_text().replace('/data3/researcher/ComfyUI/.venv/bin/python', python))
    inheritance = read(package / 'configs/NUMERIC_INHERITANCE.json')
    assert all(sha(package / 'runtime/official_metric' / name) == value for name, value in inheritance['files'].items())
    for directory in ('scripts', 'audit'):
        for path in (package / directory).glob('*.py'):
            ast.parse(path.read_text())
    files = {str(path.relative_to(package)): sha(path) for path in sorted(package.rglob('*'))
             if path.is_file() and path.name != 'CONSUMER_FREEZE.json'}
    save(package / 'CONSUMER_FREEZE.json', {'schema': 'flex-repair-official-numerics-host9-cpu-v1',
         'parent_host41_freeze_sha256': sha(source / 'CONSUMER_FREEZE.json'), 'files': files})
    print(json.dumps({'package': str(package), 'seal_sha256': sha(package / 'CONSUMER_FREEZE.json'),
                      'numeric_files': len(inheritance['files']), 'remote_root': remote, 'GPU_started': False}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pair_root')
    main(parser.parse_args().pair_root)
