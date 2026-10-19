"""CPU-only, one-time archival before a root-authorized fresh R83 service.

No signal, CUDA initialization, inference submission, or deletion is performed.
The caller supplies the exact dead generation and holds the root execution lock.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
FIRST_RUN = 'r83_short_0131_seed2026101701_native'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temp, path)


def cuda_pids():
    result = subprocess.run(['nvidia-smi', '--query-compute-apps=pid',
                             '--format=csv,noheader,nounits'], check=True,
                            capture_output=True, text=True, timeout=20)
    return {int(row.strip()) for row in result.stdout.splitlines() if row.strip()}


def check_dead_generation(root, expected_pid, expected_start, *,
                          proc_exists=None, query_cuda=None):
    root = Path(root)
    owner = read(root / 'processes/service.json')
    require(owner['pid'] == expected_pid and
            str(owner['identity']['start_ticks']) == str(expected_start),
            'service registry is a different generation')
    runtime = read(root / 'configs/runtime.json')
    require(owner['gpu_uuid'] == runtime['gpu_uuid'] and owner['port'] == runtime['port'],
            'service GPU/port differs from frozen runtime')
    require(owner['identity']['uid'] == os.getuid(), 'service owner differs')
    proc_exists = proc_exists or (lambda pid: (Path('/proc') / str(pid)).exists())
    records = []
    for path in sorted((root / 'processes').glob('*.json')):
        name = path.name
        if not re.fullmatch(r'(service|supervisor)(_[0-9]+)?\.json|controller\.json|watchdog\.json', name):
            continue
        value = read(path)
        require(isinstance(value, dict) and isinstance(value.get('pid'), int),
                'unrecognized process registry: ' + name)
        require(value.get('identity', {}).get('uid') == os.getuid(),
                'registered process owner differs: ' + name)
        pid = value['pid']
        # A reused PID or zombie also blocks archival; this function never signals it.
        require(not proc_exists(pid), 'registered PID still exists: ' + str(pid))
        records.append({'file': str(path.relative_to(root)), 'pid': pid,
                        'identity': value['identity']})
    active_cuda = (query_cuda or cuda_pids)()
    require(not any(row['pid'] in active_cuda for row in records),
            'registered PID still appears in CUDA inventory')
    return {'owner': owner, 'records': records, 'cuda_pids': sorted(active_cuda),
            'checked_unix': time.time()}


def selected_paths(root):
    root = Path(root)
    sealed = set(read(root / 'deploy_manifest.json')['files'])
    contract = read(root / 'configs/scientific_contract.json')
    sources = sorted({case['source_id'] for case in contract['cases']})
    # Only the interrupted first Native is authorized for this recovery.
    existing_jobs = sorted(p.name for p in (root / 'logs').glob('*_job.json'))
    require(all(name == FIRST_RUN + '_job.json' for name in existing_jobs),
            'later job evidence exists; recovery scope requires review')
    candidates = [root / name for name in (
        'processes', 'logs', 'output', 'temp', 'audit/tensor_blobs',
        'audit/router', 'audit/x0', 'audit/ROOT_FIRST_PAIR_APPROVAL.json',
        'audit/CONTINUE_AFTER_FIRST_PAIR.json', 'configs/runtime_provenance.json')]
    candidates += sorted((root / 'audit').glob('r83_*'))
    candidates += [root / 'analysis/postrun' / source for source in sources]
    result = []
    for path in candidates:
        if not os.path.lexists(path):
            continue
        rel = str(path.relative_to(root))
        require(not any(name == rel or name.startswith(rel + '/') for name in sealed),
                'archival selection overlaps sealed producer file: ' + rel)
        require(not any(parent.is_symlink() for parent in [path, *path.parents]
                        if parent == root or root in parent.parents),
                'archival root cannot be a symlink: ' + rel)
        if path not in result:
            result.append(path)
    return result


def inventory(base, paths):
    base = Path(base)
    rows = {}
    def visit(path):
        info = path.lstat()
        row = {'uid': info.st_uid, 'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode),
               'mtime_ns': info.st_mtime_ns}
        require(info.st_uid == os.getuid(), 'non-owned archival file: ' + str(path))
        if stat.S_ISLNK(info.st_mode):
            row.update(kind='symlink', target=os.readlink(path))
        elif stat.S_ISDIR(info.st_mode):
            row.update(kind='directory')
            for child in sorted(path.iterdir()):
                visit(child)
        elif stat.S_ISREG(info.st_mode):
            row.update(kind='file', bytes=info.st_size, sha256=sha(path))
        else:
            raise RuntimeError('special archival file: ' + str(path))
        rows[str(path.relative_to(base))] = row
    for path in paths:
        visit(path)
    return rows


def archive(root, destination, expected_pid, expected_start, *, execute=False,
            proc_exists=None, query_cuda=None):
    root, destination = Path(root), Path(destination)
    require(not destination.exists(), 'archive destination already exists')
    require(destination.parent == root / 'audit/http_observation_recovery_v2/attempts',
            'archive destination must be inside the dedicated attempt directory')
    dead = check_dead_generation(root, expected_pid, expected_start,
                                proc_exists=proc_exists, query_cuda=query_cuda)
    paths = selected_paths(root)
    rows = inventory(root, paths)
    plan = {'schema': 'r83-dead-attempt-archive-v1', 'execute': execute,
            'created_unix': time.time(), 'producer_seal_sha256': sha(root / 'deploy_manifest.json'),
            'dead_generation': dead, 'paths': [str(p.relative_to(root)) for p in paths],
            'inventory': rows, 'restart_scope': 'fresh first Native and forced, unchanged numerical graph',
            'noise_policy': 'archive interrupted caches; fresh seeded shared Native/forced cache',
            'moves_completed': []}
    if not execute:
        return plan
    # Recheck after hashing, before any move. All moves occur under root_execution.lock.
    check_dead_generation(root, expected_pid, expected_start,
                          proc_exists=proc_exists, query_cuda=query_cuda)
    destination.mkdir(parents=True, exist_ok=False)
    write(destination / 'ARCHIVE_PLAN.json', plan)
    try:
        for path in paths:
            rel = path.relative_to(root)
            target = destination / 'payload' / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            path.rename(target)
            plan['moves_completed'].append(str(rel))
            write(destination / 'ARCHIVE_PROGRESS.json', plan)
        actual = inventory(destination / 'payload',
                           [destination / 'payload' / name for name in plan['paths']])
        require(actual == rows, 'archived file inventory differs after rename')
        for name in ('processes', 'logs', 'output', 'temp'):
            (root / name).mkdir(exist_ok=True)
        plan.update(status='ARCHIVED_VERIFIED', completed_unix=time.time(),
                    inventory_equal=True)
        write(destination / 'COMPLETE.json', plan)
        return plan
    except BaseException as error:
        # Partial moves stay at recorded locations. Never delete/overwrite evidence or auto-retry.
        try:
            write(destination / 'FAILURE.json', {'error': repr(error),
                  'moves_completed': plan['moves_completed'], 'unix': time.time()})
        except BaseException as receipt_error:
            if hasattr(error, 'add_note'):
                error.add_note('failure receipt: ' + repr(receipt_error))
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-service-pid', type=int, required=True)
    parser.add_argument('--expected-start-ticks', required=True)
    parser.add_argument('--archive-name', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(re.fullmatch(r'[a-zA-Z0-9_-]+', args.archive_name), 'invalid archive name')
    require(Path(read(ROOT / 'configs/runtime.json')['remote_root']) == ROOT,
            'run only in the actual remote producer root')
    require(Path('/proc').is_dir(), 'Linux /proc required')
    with (ROOT / 'audit/root_execution.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        destination = ROOT / 'audit/http_observation_recovery_v2/attempts' / args.archive_name
        result = archive(ROOT, destination, args.expected_service_pid,
                         args.expected_start_ticks, execute=args.execute)
    print(json.dumps({'status': result.get('status', 'DRY_RUN'),
                      'destination': str(destination), 'paths': result['paths'],
                      'files': len(result['inventory']),
                      'bytes': sum(x.get('bytes', 0) for x in result['inventory'].values())}))


if __name__ == '__main__':
    main()
