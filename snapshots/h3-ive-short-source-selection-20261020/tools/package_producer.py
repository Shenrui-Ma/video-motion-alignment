"""Build a complete local H3 deployment archive, including mutable queue state."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import tarfile
import tempfile

REQUIRED = ('deploy_manifest.json', 'configs/queue.json', 'configs/admission.json')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def deployment_files(root):
    root = Path(root).resolve()
    seal = json.loads((root / 'deploy_manifest.json').read_text())
    expected = {name: value['sha256'] for name, value in seal['files'].items()}
    # Inputs are bound separately in older producer seals.
    prepared = json.loads((root / 'PREPARED_INPUTS_MANIFEST.json').read_text())
    for pair in prepared['pairs']:
        for value in pair['files'].values():
            name, checksum = value['file'], value['sha256']
            if name in expected and expected[name] != checksum:
                raise ValueError('Input and seal disagree: ' + name)
            expected[name] = checksum
    for name in REQUIRED:
        if not (root / name).is_file():
            raise ValueError('Required deployment file absent: ' + name)
        expected.setdefault(name, digest(root / name))
    queue = json.loads((root / 'configs/queue.json').read_text())
    contract = json.loads((root / 'configs/scientific_contract.json').read_text())
    if queue.get('jobs') != contract['case_order'] or type(queue.get('finalize')) is not bool:
        raise ValueError('Queue does not match the frozen case order')
    for name, checksum in expected.items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or (root / path).is_symlink():
            raise ValueError('Unsafe deployment path: ' + name)
        if digest(root / path) != checksum:
            raise ValueError('Deployment file differs from its binding: ' + name)
    return dict(sorted(expected.items()))


def verify_archive(archive, expected):
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError('Archive file list differs: ' + json.dumps({
                'absent': sorted(set(expected) - set(names)),
                'extra': sorted(set(names) - set(expected)),
                'duplicates': sorted({n for n in names if names.count(n) > 1})}))
        for member in members:
            if not member.isfile():
                raise ValueError('Archive contains a non-file entry')
            h = hashlib.sha256(tar.extractfile(member).read()).hexdigest()
            if h != expected[member.name]:
                raise ValueError('Archive bytes differ: ' + member.name)


def package(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError('Keep the existing archive; choose a new output path')
    expected = deployment_files(root)
    fd, temporary = tempfile.mkstemp(prefix='.producer-', suffix='.tar.gz', dir=output.parent)
    os.close(fd)
    try:
        with tarfile.open(temporary, 'w:gz') as tar:
            for name in expected:
                tar.add(root / name, arcname=name, recursive=False)
        verify_archive(temporary, expected)
        if deployment_files(root) != expected:
            raise ValueError('Producer changed during packaging')
        os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {'archive': str(output), 'sha256': digest(output), 'files': len(expected), 'required_files': list(REQUIRED)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('producer', type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--output', type=Path)
    action.add_argument('--verify-archive', type=Path)
    action.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if args.output:
        result = package(args.producer, args.output)
    else:
        files = deployment_files(args.producer)
        if args.verify_archive:
            verify_archive(args.verify_archive, files)
        result = {'passed': True, 'files': len(files), 'required_files': list(REQUIRED)}
    print(json.dumps(result))
