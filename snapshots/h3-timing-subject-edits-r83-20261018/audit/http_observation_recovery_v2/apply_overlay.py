"""Passive R83 administrative overlay. Requires all registered old processes absent."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
import time

OLD = '1c875d1a82110a362975e1c31454250f0ae1f6e3dbc8634c5bcf55a34671bddc'
NEW = 'df7e77df54f0197f4f7b29a6ce6432729aa4c3dda861b43a4c87a3120433a6cb'
ADMIN = 'audit/http_observation_recovery_v2/'
CHANGED = {'scripts/job.py', 'scripts/run_queue.py'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise RuntimeError(message)


def apply(root, archive, proc_exists=None):
    root, archive = Path(root), Path(archive)
    proc_exists = proc_exists or (lambda pid: (Path('/proc') / str(pid)).exists())
    with tarfile.open(archive, 'r:gz') as tf:
        payload = {}
        for member in tf.getmembers():
            path = PurePosixPath(member.name)
            require(member.isfile() and not path.is_absolute() and '..' not in path.parts,
                    'non-file or unsafe archive member')
            require(member.name not in payload, 'duplicate archive member')
            require(member.name in CHANGED | {'deploy_manifest.json'} or member.name.startswith(ADMIN),
                    'archive member outside administrative scope')
            payload[member.name] = tf.extractfile(member).read()
    prior_path = ADMIN + 'producer_before_restart/deploy_manifest.json'
    require(sha(payload[prior_path]) == OLD, 'old manifest SHA differs')
    require(sha(payload['deploy_manifest.json']) == NEW, 'new manifest SHA differs')
    old, new = json.loads(payload[prior_path]), json.loads(payload['deploy_manifest.json'])
    require(set(old['files']) == set(new['files']), 'sealed file set changed')
    require({p for p in old['files'] if old['files'][p] != new['files'][p]} == CHANGED,
            'unexpected sealed changes')
    current_seal = sha((root / 'deploy_manifest.json').read_bytes())
    require(current_seal in (OLD, NEW), 'remote producer manifest differs')
    for rel, info in old['files'].items():
        require(sha(payload[ADMIN + 'producer_before_restart/' + rel]) == info['sha256'],
                'original snapshot mismatch: ' + rel)
        actual = sha((root / rel).read_bytes())
        require(actual in {info['sha256'], new['files'][rel]['sha256']},
                'unexpected remote file mutation: ' + rel)
        if rel in CHANGED:
            require(sha(payload[rel]) == new['files'][rel]['sha256'], 'overlay file mismatch')
    for path in (root / 'processes').glob('*.json'):
        if not re.fullmatch(r'(service|supervisor)(_[0-9]+)?\.json|controller\.json|watchdog\.json', path.name):
            continue
        owner = json.loads(path.read_text())
        require(isinstance(owner.get('pid'), int), 'unknown process record')
        require(not proc_exists(owner['pid']), 'registered process still exists')
    # Validate destinations before any writes. Existing old snapshots must match byte for byte.
    for rel, data in payload.items():
        target = root / rel
        require(not any(p.is_symlink() for p in [target, *target.parents]
                        if p == root or root in p.parents), 'symlink destination: ' + rel)
        if rel.startswith(ADMIN + 'producer_before_restart/') and target.exists():
            require(target.read_bytes() == data, 'existing historical snapshot differs')
    # The manifest is published last. A partial application is verifiable and resumable.
    ordered = sorted(name for name in payload if name != 'deploy_manifest.json') + ['deploy_manifest.json']
    for rel in ordered:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + '.overlay-tmp')
        temp.write_bytes(payload[rel])
        os.replace(temp, target)
    for rel, info in new['files'].items():
        require(sha((root / rel).read_bytes()) == info['sha256'], 'post-deploy seal mismatch')
    value = {'schema': 'r83-passive-admin-overlay-v2', 'passed': True,
             'unix': time.time(), 'old_seal_sha256': OLD, 'new_seal_sha256': NEW,
             'files_verified': len(new['files']), 'changed_files': sorted(CHANGED),
             'archive_sha256': sha(archive.read_bytes()), 'GPU_started': False,
             'runtime_evidence_archived': False}
    (root / ADMIN / 'REMOTE_DEPLOYMENT.json').write_text(json.dumps(value, indent=2) + '\n')
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    args = parser.parse_args()
    runtime = json.loads((args.root / 'configs/runtime.json').read_text())
    require(args.root.resolve() == Path(runtime['remote_root']).resolve(), 'actual remote root required')
    require(Path('/proc').is_dir(), 'Linux /proc required')
    with (args.root / 'audit/root_execution.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        value = apply(args.root, args.archive)
    print(json.dumps(value))


if __name__ == '__main__':
    main()
