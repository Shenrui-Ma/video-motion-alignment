"""Create separate immutable evaluation packages; preserve every earlier attempt."""
from pathlib import Path
import hashlib, json, shutil, subprocess, sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
OLD_R96 = BASE / 'audit/r96_long0173_mf_v1/package'
PYTHON = '/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def build(lane, source):
    case = f'{lane}_{source}'
    root = HERE / case
    if (root / 'SEAL.json').exists():
        raise RuntimeError(f'Existing sealed package preserved: {root}')
    root.mkdir(exist_ok=True)
    for dirname in ('scripts', 'runtime', 'configs'):
        shutil.copytree(BASE / dirname, root / dirname, dirs_exist_ok=True)
    (root / 'audit').mkdir(exist_ok=True)
    (root / 'cases').mkdir(exist_ok=True)
    runtime = json.loads((root / 'configs/RUNTIME.json').read_text())
    runtime['remote_root'] = f'/data4/researcher/h3_runs/ive_recovery_{case}_20261019'
    runtime['GPU_execution_status'] = 'ROOT_AUTHORIZED_ACTUAL_PAIR_THREE_TRACKERS'
    save(root / 'configs/RUNTIME.json', runtime)
    if lane == 'r96':
        shutil.copytree(OLD_R96 / 'cases' / case, root / 'cases' / case, dirs_exist_ok=True)
    else:
        staging = root / 'audit' / ('staging_' + case)
        if staging.exists():
            staging.rename(root / 'audit' / ('prior_incomplete_staging_' + case))
        subprocess.run([PYTHON, str(root / 'scripts/intake_followups.py'), '--lane', lane, '--source', source], check=True)
    result = subprocess.run([PYTHON, str(root / 'scripts/prepare.py'), '--case', case, '--ffmpeg', '/opt/homebrew/bin/ffmpeg', '--ffprobe', '/opt/homebrew/bin/ffprobe'], check=True, capture_output=True, text=True)
    (root / 'audit/PREPARE.log').write_text(result.stdout + result.stderr)
    manifest = root / 'cases' / case / 'INPUTS.json'
    count = json.loads(manifest.read_text())['valid_frames']
    template = (OLD_R96 / 'audit/run_authorized.py').read_text()
    template = template.replace('r96_long0173', case).replace('r96_long_0173', case)
    template = template.replace('a4ad92aac5693d9cd9bec4b4f41dffe71e340a32445e17b396b00dfb774f8e98', sha(manifest))
    template = template.replace('[1,145,100,2]', f'[1,{count},100,2]').replace("==145,'authorized physical domain", f"=={count},'authorized physical domain")
    template = template.replace("headroom['effective_headroom_bytes']>=8*1024**3,'effective cgroup headroom below8GiB'", "headroom['effective_headroom_bytes']>=12*1024**3,'effective preload cgroup headroom below12GiB'")
    template = template.replace('R96 long0173 source/native/forced', f'{case} source/native/forced')
    (root / 'audit/run_authorized.py').write_text(template)
    inherited = {}
    for p in (root / 'runtime').rglob('*'):
        if p.is_file():
            rel = p.relative_to(root)
            assert sha(p) == sha(BASE / rel)
            inherited[str(rel)] = sha(p)
    save(root / 'audit/RECOVERY_BINDING.json', {'case': case, 'valid_frames': count, 'input_sha256': sha(manifest), 'numeric_parent': str(BASE), 'numeric_files': inherited, 'old_r100_attempt_preserved': True, 'fresh_roles': ['source', 'native', 'forced'], 'preload_cgroup_GiB': 12, 'runtime_cgroup_GiB': 8, 'coordinator': 'root/recover_metrics_preparation', 'GPU_started': False})
    files = {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    save(root / 'SEAL.json', {'schema': 'ive-metric-recovery-20261019-v1', 'files': files})
    print(json.dumps({'package': str(root), 'remote': runtime['remote_root'], 'case': case, 'seal': sha(root/'SEAL.json'), 'files': len(files)}))

if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
