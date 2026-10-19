"""Verify the exported snapshot without importing or running experiment code."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'EXPORT_MANIFEST.json').read_text())
for item in manifest['files']:
    path = root / item['file']
    assert path.is_file() and not path.is_symlink(), item['file']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item['export_sha256'], item['file']
print(json.dumps({'passed': True, 'files': len(manifest['files']),
                  'projects': manifest['source_projects']}))
