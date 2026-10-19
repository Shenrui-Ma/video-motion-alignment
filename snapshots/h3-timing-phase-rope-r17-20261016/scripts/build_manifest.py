"""Seal a reviewable R17 local bundle. Never launch services or change sources."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected(root):
    paths = []
    for directory in ('configs', 'extensions', 'scripts', 'tests', 'inputs'):
        for path in (root / directory).rglob('*'):
            if (path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts
                    and path.suffix not in ('.pyc', '.log', '.tmp') and path.name not in ('runtime_provenance.json',)):
                paths.append(path)
    return sorted(set(paths))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--tar', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.check:
        data = json.loads(args.manifest.read_text())
        for relative, expected in data['files'].items():
            path = root / relative
            if Path(relative).is_absolute() or '..' in Path(relative).parts or path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError('unsafe manifest path: ' + relative)
            if not path.is_file() or digest(path) != expected['sha256'] or path.stat().st_size != expected['bytes']:
                raise ValueError('manifest mismatch: ' + relative)
        print(json.dumps({'verified_files': len(data['files']), 'manifest_sha256': digest(args.manifest)}))
        return
    if args.manifest.exists() or (args.tar and args.tar.exists()):
        raise FileExistsError('keep old seals; choose a new manifest/archive filename')
    files = selected(root)
    data = {'schema': 'h3-r17-immutable-manifest-v1',
            'scope': 'runtime/config/test sources and immutable inputs; no outputs, logs, caches or generated tensor blobs',
            'files': {str(p.relative_to(root)): {'bytes': p.stat().st_size, 'sha256': digest(p)} for p in files}}
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(data, indent=2) + '\n')
    if args.tar:
        args.tar.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(args.tar, 'w:gz') as archive:
            for path in files:
                archive.add(path, arcname=str(path.relative_to(root)), recursive=False)
    print(json.dumps({'files': len(files), 'manifest': str(args.manifest),
                      'manifest_sha256': digest(args.manifest),
                      'tar': str(args.tar) if args.tar else None,
                      'tar_sha256': digest(args.tar) if args.tar else None}))


if __name__ == '__main__':
    main()
