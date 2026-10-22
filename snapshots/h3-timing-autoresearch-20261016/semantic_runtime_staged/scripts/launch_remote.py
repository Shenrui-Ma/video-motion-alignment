"""Isolated preparation/readiness helpers; only the coordinator may start work.

Derived from the audited primary launch_remote.py. Model/core verification and
node/backend selection are unchanged. Importing this module has no side effects.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request

import service


def prepare():
    r = service.RUN
    for name in ['custom_nodes', 'input', 'output', 'temp', 'user', 'logs', 'processes', 'audit', 'analysis']:
        (r / name).mkdir(exist_ok=True)
    for name in ['H3EventAudit', 'H3PairAudit', 'H3EventEmphasis', 'H3TemporalRouter', 'H3X0Readout', 'H3PhaseRoPE', 'H3SemanticClock']:
        target = r / 'extensions' / name
        assert (target / '__init__.py').is_file(), target
        link = r / 'custom_nodes' / name
        if link.exists() or link.is_symlink():
            assert link.is_symlink() and link.resolve() == target.resolve(), link
        else:
            link.symlink_to(target, target_is_directory=True)
    kj = r / 'custom_nodes/ComfyUI-KJNodes'
    kj_target = Path('/data5/researcher/h3_runs/short_event_pilot_20261013/custom_nodes/ComfyUI-KJNodes')
    if kj.exists() or kj.is_symlink():
        assert kj.is_symlink() and kj.resolve() == kj_target.resolve()
    else:
        kj.symlink_to(kj_target, target_is_directory=True)
    for p in (r / 'inputs').iterdir():
        if p.suffix in ('.mp4', '.jpg', '.png'):
            dest = r / 'input' / p.name
            assert not dest.is_symlink()
            shutil.copy2(p, dest)
    parent = json.loads((r / 'configs/parent_runtime_provenance.json').read_text())
    hashes = json.loads((r / 'configs/model_hashes_host9.json').read_text())
    prov = {'models': {}, 'core_matches': {}, 'code': {}, 'observed_unix': time.time()}
    for name, old in parent['models'].items():
        p = Path(service.MODELS) / name
        stat = p.stat()
        assert (stat.st_size, stat.st_mtime_ns) == (old['bytes'], old['mtime_ns']), name
        assert hashes[name]['sha256'] == old['prior_full_sha256'], name
        prov['models'][name] = dict(old, path=str(p), full_hash_recomputed=False, size_mtime_match=True)
    for rel, expected in json.loads((r / 'configs/parent_core_hashes.json').read_text()).items():
        prov['core_matches'][rel] = hashlib.sha256((service.CORE / rel).read_bytes()).hexdigest() == expected
    assert all(prov['core_matches'].values())
    for p in list((r / 'scripts').glob('*.py')) + list((r / 'extensions').rglob('*.py')):
        prov['code'][str(p.relative_to(r))] = hashlib.sha256(p.read_bytes()).hexdigest()
    service.write_json(r / 'configs/runtime_provenance.json', prov)


def spawn(role, name):
    r = service.RUN
    env = dict(os.environ, LC_ALL='C', LANG='C', PYTHONDONTWRITEBYTECODE='1')
    with (r / 'logs' / f'{role}.log').open('ab', buffering=0) as log:
        child = subprocess.Popen(['python3', '-u', str(r / 'scripts' / name)], cwd=r / 'scripts',
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                 start_new_session=True, env=env)
    record = {'pid': child.pid, 'identity': service.identity(child.pid), 'role': role}
    service.write_json(r / 'processes' / f'{role}_spawn.json', record)
    return child, record


def wait_readiness(supervisor, guard, timeout=300):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        guard()
        if supervisor.poll() is not None:
            raise RuntimeError('Supervisor exited before readiness')
        try:
            for name in ('H3TemporalRouter', 'H3X0Readout', 'H3PhaseRoPE', 'H3SemanticClockReference', 'H3SemanticClockNoise', 'H3SemanticClockGate'):
                with urllib.request.urlopen(f'http://127.0.0.1:{service.PORT}/object_info/{name}', timeout=2) as f:
                    info = json.load(f)
                if name not in info:
                    raise RuntimeError('Required node missing: ' + name)
            return
        except (OSError, ValueError, RuntimeError):
            time.sleep(2)
    raise TimeoutError('Readiness timeout')


if __name__ == '__main__':
    raise SystemExit('Use coordinate_launch.py with an explicit reviewed decision; direct launch is disabled.')
