"""Administrative bindings for a bounded cached-Native observer check."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor'))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


# Skip the Comfy node __init__, while importing the exact frozen modules.
package = types.ModuleType('H3AutomaticWindowRouter')
package.__path__ = [str(ROOT / 'extensions/H3AutomaticWindowRouter')]
sys.modules.setdefault('H3AutomaticWindowRouter', package)
from H3AutomaticWindowRouter import transport as lifetime
from H3AutomaticWindowRouter.geometry import Geometry
from H3AutomaticWindowRouter.selector import Controller


def config():
    value = read(ROOT / 'configs/PRECHECK.json')
    require(value['indices'] == list(range(10)), 'only sequential indices0..9')
    require(value['arm'] == 'visible_only' and value['stop'] == 'first_Controller_chosen_full', 'frozen visible controller')
    require(value['formal_H3_authorized'] is False and value['precheck_calls_DiT'] == 0, 'decoder-only scope')
    require(value['run_id'] == 'r113_short_0252_seed2026101703_native', 'actual parent run')
    require(value['geometry'] == dict(width=1312, height=736, frames=107, fps=24) and value['valid_frames'] == 98, 'valid time domain')
    return value


def geometry(value):
    return Geometry(**value['geometry'], valid_frames=value['valid_frames'])


def validate_package(external=False):
    seal = read(ROOT / 'FREEZE.json')
    for name, expected in seal['files'].items():
        require(sha(ROOT / name) == expected, 'sealed file differs: ' + name)
    for row in read(ROOT / 'configs/INHERITED.json'):
        require(sha(ROOT / row['file']) == row['sha256'], 'frozen implementation differs')
    value = config()
    gate = read(ROOT / 'configs/R113_SEED1703_PAIR_GATE.json')
    require(sha(ROOT / 'configs/R113_SEED1703_PAIR_GATE.json') == value['parent_gate_sha256'], 'parent gate SHA')
    require(gate['passed'] and all(gate['checks'].values()), 'completed historical pair')
    require(gate['runs']['native']['snapshots'][:10] == value['snapshots'], 'snapshot bindings')
    require(gate['runs']['native']['NFE'] == gate['runs']['native']['solver_updates'] == 20, 'historical Native protocol')
    if external:
        c = value['runtime']
        require(os.getuid() == c['expected_uid'] and str(ROOT) == c['remote_root'], 'actual host path/UID')
        require(sha(value['parent_manifest']) == value['parent_manifest_sha256'], 'actual historical manifest')
        for row in value['snapshots']:
            require(sha(row['file']) == row['sha256'], 'actual historical snapshot file')
        for name, expected in c['core_sha256'].items():
            require(sha(Path(c['core']) / name) == expected, 'core file differs: ' + name)
        require(sha(c['vae']) == c['vae_sha256'], 'VAE weight differs')
        for name, expected in c['pose_external'].items():
            require(sha(name) == expected, 'pose external differs: ' + name)
    return value


def apps():
    raw = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,used_gpu_memory', '--format=csv,noheader,nounits'], text=True, timeout=20)
    result = []
    for line in raw.splitlines():
        fields = [part.strip() for part in line.split(',')]
        if len(fields) != 3:
            continue
        gpu, pid, memory = fields
        try:
            uid = Path('/proc', pid).stat().st_uid
        except FileNotFoundError:
            continue
        result.append(dict(gpu_uuid=gpu, pid=int(pid), uid=uid, memory_mib=memory))
    return result


def validate_own_processes(rows, runtime, decoder=None):
    preserved = runtime['preserved_user_service']
    require(lifetime.alive(preserved), 'preserved8189 exact identity changed')
    for row in rows:
        if row['uid'] != runtime['expected_uid']:
            continue
        if row['pid'] == preserved['pid']:
            require(row['gpu_uuid'] == runtime['preserved_user_service_gpu'], '8189 device changed')
        elif decoder is not None and row['pid'] == decoder['pid']:
            require(lifetime.alive(decoder) and row['gpu_uuid'] == runtime['gpu_uuid'], 'decoder generation/device changed')
        else:
            raise ValueError('unregistered own research CUDA process: ' + str(row['pid']))


def admission(value):
    from cgroup_memory import check
    c = value['runtime']
    release = c['MF_release']
    require(sha(release['file']) == release['sha256'], 'MF final release SHA')
    receipt = read(release['file'])
    require(receipt['passed'] and receipt['all_spawned_trackers_released'] and receipt['exact_processes_absent'] and receipt['exact_CUDA_allocations_absent'], 'MF release incomplete')
    rows = apps()
    validate_own_processes(rows, c)
    gpu = subprocess.check_output(['nvidia-smi', '--id=' + c['gpu_uuid'], '--query-gpu=uuid,memory.free,temperature.gpu', '--format=csv,noheader,nounits'], text=True, timeout=20).strip().split(',')
    uuid, free, temperature = [x.strip() for x in gpu]
    require(uuid == c['gpu_uuid'] and int(free) >= c['required_free_mib'] and int(temperature) < 85, 'decoder GPU admission')
    return dict(gpu_uuid=uuid, free_mib=int(free), temperature=int(temperature), processes=rows, cgroup=check(ROOT))


def assert_released(identity):
    require(not lifetime.alive(identity), 'exact child still alive')
    rows = apps()
    require(all(row['pid'] != identity['pid'] for row in rows), 'child CUDA allocation remains')
    return dict(identity=identity, process_absent=True, CUDA_absent=True)


def approved():
    review = read(ROOT / 'audit/ROOT_REVIEW.json')
    require(review.get('approved') is True and review.get('scope') == 'decoder_precheck_only', 'root precheck approval missing')
    require(review['freeze_sha256'] == sha(ROOT / 'FREEZE.json'), 'root review seal mismatch')
    return review


def measurement(index, observation, request_sha, response_sha):
    return dict(status='complete', physical_index=index, observer=observation,
                request_sha256=request_sha, response_sha256=response_sha)


def stop_after(decision):
    return bool(decision['chosen_full'])
