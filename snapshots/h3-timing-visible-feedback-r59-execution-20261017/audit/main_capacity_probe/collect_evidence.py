"""Archive completed probe evidence; never starts or controls GPU processes."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.run_root.resolve()
    base = root.parent
    result = json.loads((root / 'audit/run_result.json').read_text())
    if not all(result['cleanup'][key] for key in ('original_generation_absent', 'own_compute_absent')):
        raise ValueError('evidence requires completed exact cleanup')
    paths = [path for name in ('audit', 'logs', 'configs', 'scripts')
             for path in (root / name).rglob('*') if path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts]
    paths += list((root / 'custom_nodes/H3MainCapacityProbe').glob('*.py'))
    launch = base / ('root_launch_' + root.name.rsplit('_', 1)[1] + '.log')
    if launch.exists():
        paths.append(launch)
    inventory = {'scope': 'completed isolated capacity probe', 'run_root': str(root), 'files': {}}
    for path in sorted(paths):
        inventory['files'][str(path.relative_to(base))] = {
            'bytes': path.stat().st_size, 'sha256': sha(path),
            'included_in_small_archive': path.stat().st_size <= 1024 * 1024,
        }
    manifest = base / (root.name + '_SHA256.json')
    with manifest.open('x') as stream:
        json.dump(inventory, stream, indent=2)
        stream.write('\n')
    archive = base / (root.name + '_small_evidence.tar.gz')
    with tarfile.open(archive, 'x:gz') as stream:
        for path in paths:
            if inventory['files'][str(path.relative_to(base))]['included_in_small_archive']:
                stream.add(path, arcname=str(path.relative_to(base)))
        stream.add(manifest, arcname=manifest.name)
    print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size,
                      'sha256': sha(archive), 'manifest_sha256': sha(manifest),
                      'hashed_files': len(paths)}))


if __name__ == '__main__':
    main()
