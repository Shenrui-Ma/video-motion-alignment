"""Install reviewed PhaseRoPE only after the exact phase2 service has exited."""
import hashlib
import fcntl
import json
from pathlib import Path
import shutil
import time

import service


def install_locked():
    root = service.RUN
    state = json.loads((root/'logs/controller_state.json').read_text())
    required = ['s05_full_seed1_native_x0', 's05_full_seed1_mass_x0']
    if state.get('status') != 'all_queued_jobs_complete' or state.get('completed') != required:
        raise RuntimeError('phase2 controller has not finished successfully')
    old = json.loads((root/'processes/service.json').read_text())
    if service.current_identity(old['pid']) is not None:
        raise RuntimeError('phase2 service is still present; never modify live extensions')
    cleanup = json.loads((root/'processes/cleanup.json').read_text())
    if cleanup['pid'] != old['pid'] or not cleanup['process_absent'] or not cleanup['own_compute_absent']:
        raise RuntimeError('phase2 cleanup is not verified')
    if cleanup['service_record'] != old:
        raise RuntimeError('cleanup belongs to a different exact service record')
    for name in required:
        job = json.loads((root/'logs'/f'{name}_job.json').read_text())
        history = json.loads((root/'logs'/f'{name}_history.json').read_text())
        if (job['status'] != 'success' or history['status']['status_str'] != 'success'
                or job['service_pid'] != old['pid'] or job['service_identity'] != old['identity']):
            raise RuntimeError('phase2 job/history identity or success mismatch: '+name)
    for role in ('controller', 'watchdog'):
        previous = json.loads((root/f'processes/{role}.json').read_text())
        if service.current_identity(previous['pid']) == previous['identity']:
            raise RuntimeError(f'previous {role} has not exited yet')
    smoke = json.loads((root/'audit/phase_rope_gpu_smoke.json').read_text())
    if not smoke['success'] or not smoke['actual_installed_kitchen_verified']:
        raise RuntimeError('PhaseRoPE numerical gate missing')
    manifest = json.loads((root/'analysis/x0_phase_rope_staged_manifest.json').read_text())
    expected_extension = {name for name in manifest['files'] if name.startswith('extensions_staged/')}
    actual_extension = {str(p.relative_to(root)) for p in (root/'extensions_staged/H3PhaseRoPE').rglob('*')
                        if p.is_file() and '__pycache__' not in p.parts}
    if actual_extension != expected_extension:
        raise RuntimeError('staged extension file set differs from reviewed manifest')
    for name, expected in manifest['files'].items():
        if name.startswith('extensions_staged/'):
            if hashlib.sha256((root/name).read_bytes()).hexdigest() != expected:
                raise RuntimeError('reviewed extension hash mismatch: '+name)
    graphs = json.loads((root/'configs/phase_rope_graph_manifest.json').read_text())
    names = [f's05_full_seed1_phase_{label}_x0' for label in ('zero', 'plus12', 'minus12')]
    if [arm['run_id'] for arm in graphs['arms']] != names:
        raise RuntimeError('unexpected phase3 graph set/order')
    for arm in graphs['arms']:
        if hashlib.sha256((root/'configs'/f"{arm['run_id']}.json").read_bytes()).hexdigest() != arm['sha256']:
            raise RuntimeError('reviewed graph hash mismatch')
    deployment = json.loads((root/'configs/phase3_deployment_manifest.json').read_text())
    if set(deployment['scripts']) != {'service.py', 'launch_remote.py'}:
        raise RuntimeError('unexpected staged launcher file set')
    for name, expected in deployment['scripts'].items():
        if hashlib.sha256((root/'scripts_staged/phase3'/name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('reviewed staged launcher hash mismatch: '+name)
    archive = root/'configs/phase2_completed'
    if archive.exists() or (root/'extensions/H3PhaseRoPE').exists():
        raise FileExistsError('phase3 has already been installed or partially installed; inspect first')
    archive.mkdir()
    for source in ['configs/queue.json', 'configs/runtime_provenance.json',
                   'scripts/service.py', 'scripts/launch_remote.py',
                   'processes/service.json', 'processes/controller.json', 'processes/watchdog.json',
                   'processes/cleanup.json', 'logs/controller_state.json']:
        shutil.copy2(root/source, archive/source.replace('/', '__'))
    shutil.copytree(root/'extensions_staged/H3PhaseRoPE', root/'extensions/H3PhaseRoPE',
                    ignore=shutil.ignore_patterns('__pycache__'))
    for name in ('service.py', 'launch_remote.py'):
        shutil.copy2(root/'scripts_staged/phase3'/name, root/'scripts'/name)
    service.write_json(root/'configs/queue.json', {'jobs': names, 'sealed': True})
    record = {'installed_unix': time.time(), 'previous_pid': old['pid'],
              'jobs': names, 'gpu': service.GPU, 'port': service.PORT,
              'scope': 'fresh isolated service after verified phase2 cleanup; no live core edits',
              'native_zero': 'full video zero replay retained as end-to-end no-op control'}
    service.write_json(root/'audit/phase3_install.json', record)
    print(json.dumps(record))


def main():
    # Same lock inherited by the live service from service.start(). Hold it
    # across all checks and replacements, so another launcher cannot race us.
    with (service.RUN/'processes/service.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        install_locked()


if __name__ == '__main__':
    main()
