"""Verify published research references without running experiment code."""
from pathlib import Path
from urllib.parse import unquote
import gzip
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'reports/research_sources_20261024'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    errors = []
    manifest = json.loads((PKG / 'EXPORT_MANIFEST.json').read_text())
    reference_sources = json.loads((PKG / 'REFERENCE_SOURCE_MANIFEST.json').read_text())
    for row in manifest['files'] + reference_sources['files']:
        p = ROOT / row['file']
        if not p.is_file() or p.is_symlink() or sha(p) != row['export_sha256']:
            errors.append({'kind': 'export_hash', 'path': row['file']})
            continue
        if row.get('compression') == 'gzip':
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                content = f.read()
            if row['source_relative'].endswith('.json'):
                json.loads(content)
    media = {r['file']: r['sha256'] for r in manifest['media']}
    reports = json.loads((ROOT / 'reports/cloud/manifest.json').read_text())
    for report in reports['reports']:
        p = ROOT / 'reports/cloud' / report['file']
        if sha(p) != report['export_sha256']:
            errors.append({'kind': 'report_hash', 'path': report['file']})
        for asset in report['asset_references']:
            media['reports/cloud/' + asset['path']] = asset['sha256']
    for name, digest in media.items():
        p = ROOT / name
        if not p.is_file() or sha(p) != digest:
            errors.append({'kind': 'media_hash', 'path': name})
    docs = [ROOT / 'README.md', ROOT / 'reports/RELATED_WORK_RESEARCH_20261024.md']
    links = 0
    for p in docs:
        if not p.is_file():
            errors.append({'kind': 'document_missing', 'path': str(p.relative_to(ROOT))})
            continue
        for target in re.findall(r'\]\(([^)]+)\)', p.read_text()):
            if target.startswith(('https:', 'http:', 'mailto:', '#')):
                continue
            target = unquote(target.split('#')[0].strip('<>'))
            links += 1
            resolved = (p.parent / target).resolve()
            if not resolved.exists():
                errors.append({'kind': 'broken_local_link', 'document': str(p.relative_to(ROOT)), 'target': target})
            elif resolved.is_file() and subprocess.run(
                    ['git', 'check-ignore', '-q', str(resolved)], cwd=ROOT).returncode == 0:
                errors.append({'kind': 'unpublished_link', 'document': str(p.relative_to(ROOT)), 'target': target})
    for row in json.loads((PKG / 'PROJECT_FILE_INDEX.json').read_text())['files']:
        p = ROOT / row['file']
        if not p.is_file() or p.stat().st_size != row['bytes']:
            errors.append({'kind': 'file_index', 'path': row['file']})
    result = {'passed': not errors, 'text_exports': len(manifest['files']),
              'compressed_text_exports': sum(r['compression'] == 'gzip' for r in manifest['files']),
              'reports': len(reports['reports']), 'unique_media_verified': len(media),
              'reference_source_files': len(reference_sources['files']),
              'local_document_links': links, 'errors': errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
