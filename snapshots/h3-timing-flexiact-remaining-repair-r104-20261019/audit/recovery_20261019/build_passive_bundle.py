"""Package sealed files plus initial mutable queue/admission; never launch H3."""
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / 'PASSIVE_BUNDLE_FINAL.tar.gz'
manifest = json.loads((ROOT / 'deploy_manifest.json').read_text())
files = sorted(set(manifest['files']) | {
    'deploy_manifest.json', 'configs/queue.json', 'configs/admission.json',
    'audit/check_cpu_imports.py', 'audit/remote_cpu_validate.py',
} | {str(p.relative_to(ROOT)) for p in (ROOT / 'inputs').iterdir() if p.is_file()})
assert not OUT.exists()
with tarfile.open(OUT, 'w:gz') as archive:
    for rel in files:
        archive.add(ROOT / rel, arcname=rel, recursive=False)
    for rel in ('input', 'output', 'temp', 'user', 'custom_nodes',
                'processes', 'logs', 'audit', 'audit/router', 'audit/x0'):
        info = tarfile.TarInfo(rel)
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        archive.addfile(info)
print(json.dumps({'file': str(OUT), 'files': len(files), 'bytes': OUT.stat().st_size}))
