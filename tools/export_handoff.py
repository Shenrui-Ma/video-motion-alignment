"""Publish a reproducible research handoff without running experiment code.

Live research files are read only. Large text evidence is stored as deterministic
gzip; every source and export has a SHA-256 record. Media is content addressed.
"""
from pathlib import Path
import ast
import gzip
import hashlib
import ipaddress
import json
import re
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / 'execution-20261022'
OUT = ROOT / 'snapshots/execution-20261022'
PACKAGE = ROOT / 'reports/research_sources_20261024'
TEXT = {'.py', '.md', '.txt', '.json', '.jsonl', '.csv', '.yaml', '.yml', '.sh', '.toml', '.svg'}
AREAS = ['innovation', 'inference', 'timing', 'summaries', 'showcases', 'diagnostics', 'literature', 'prompt_format_five']
SUPERVISION = ['field_environment_reproduction_20261023', 'readonly_other_lanes_20261023',
               'extension_0084_20261023', 'extension_0230_20261023', 'extension_0362_20261023',
               'extension_0370_20261023', 'gpu6_weak_followon_check', 'research_pause_20261023']
SECRET = [r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
          r'\bgh[pousr]_[A-Za-z0-9]{20,}\b', r'\bgithub_pat_[A-Za-z0-9_]{30,}\b',
          r'\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{30,}\b',
          r'https?://[^\s/:@]+:[^\s/@]+@', r'\bAKIA[0-9A-Z]{16}\b']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sanitize(text):
    for old, new in [('/Users/mashenrui', '/workspace/research-user'),
                     ('shenrui.ma', 'research-user'), ('shenrui-ma', 'research-user'),
                     ('mashenrui', 'research-user')]:
        text = text.replace(old, new)
    text = re.sub(r'CASIA_[A-Za-z0-9_.-]+', 'H3_HOST_CONFIGURE_LOCALLY', text)
    text = re.sub(r'GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',
                  'GPU-REPLACE-WITH-DEVICE-UUID', text)
    def address(match):
        try:
            ip = ipaddress.ip_address(match[0])
            if any(ip in ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
                return '192.0.2.' + str(int(match[0].split('.')[-1]) % 254 + 1)
        except ValueError:
            pass
        return match[0]
    text = re.sub(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])', address, text)
    if any(re.search(p, text) for p in SECRET):
        raise ValueError('Credential pattern detected; no credential content is printed')
    return text


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def main():
    selected = {LIVE / n for n in ['STATUS.md', 'expanded_catalog.json', 'task_catalog.json']}
    for name in AREAS + ['supervision/' + n for n in SUPERVISION]:
        selected.update(p for p in (LIVE / name).rglob('*') if p.is_file() and p.suffix in TEXT)
    selected.update(p for p in (LIVE / 'supervision/signed_phase_replay_resource_20261023/runtime_sources/H3TrustedConditionCache').rglob('*')
                    if p.is_file() and p.suffix in TEXT)
    selected.update(p for p in (LIVE / 'metrics').glob('*') if p.is_file() and
                    (p.suffix == '.py' or p.name in {'manifest.json', 'current_summary.json',
                     'latest_results_snapshot_20261022_1640.json', 'enabled_metrics.json',
                     'DEPENDENCIES.json', 'model_paths.yml', 'HANDOFF.txt'}))
    selected.update(p for p in (LIVE / 'metrics/official_source').rglob('*') if p.is_file() and p.suffix in TEXT)
    selected.update(p for p in (LIVE / 'metrics/official_source').rglob('*')
                    if p.is_file() and (p.name.upper().startswith('LICENSE') or p.name.upper().startswith('NOTICE')))
    records, skipped = [], []
    base = json.loads((ROOT / 'EXPORT_MANIFEST.json').read_text())
    base_by_path = {r['file']: r for r in base['files']}
    for p in sorted(selected):
        if not p.exists() or p.is_symlink() or '__pycache__' in p.parts:
            continue
        raw = p.read_bytes()
        try:
            cooked = sanitize(raw.decode('utf-8')).encode('utf-8')
        except UnicodeDecodeError:
            skipped.append({'source': p.relative_to(ROOT).as_posix(), 'reason': 'non-UTF8 file'})
            continue
        if p.suffix == '.py':
            ast.parse(cooked, filename=str(p))
        if p.suffix == '.json':
            json.loads(cooked)
        dest = OUT / p.relative_to(LIVE)
        compressed = len(cooked) > 5 * 1024 * 1024
        if compressed:
            dest = dest.with_name(dest.name + '.gz')
            cooked = gzip.compress(cooked, mtime=0)
        write(dest, cooked)
        row = {'file': dest.relative_to(ROOT).as_posix(), 'source_relative': p.relative_to(ROOT).as_posix(),
               'original_sha256': sha(raw), 'export_sha256': sha(cooked), 'bytes': len(cooked),
               'source_bytes': len(raw), 'sanitized': True, 'compression': 'gzip' if compressed else 'none'}
        records.append(row)
        # Existing baseline paths remain verifiable after a deliberate refresh.
        if row['file'] in base_by_path:
            base_by_path[row['file']].update({k: row[k] for k in ('original_sha256', 'export_sha256', 'bytes', 'sanitized')})
        assert p.read_bytes() == raw, 'Live source changed during export: ' + str(p)
    extras = ['extension_metrics.json', 'media_provenance.json', 'build_receipt.json', 'VALIDATION.json']
    for name in extras:
        p = ROOT / 'reports/v1_1_evidence' / name
        raw = p.read_bytes(); cooked = sanitize(raw.decode()).encode()
        dest = PACKAGE / 'evidence' / name; write(dest, cooked)
        records.append({'file': dest.relative_to(ROOT).as_posix(), 'source_relative': p.relative_to(ROOT).as_posix(),
                        'original_sha256': sha(raw), 'export_sha256': sha(cooked), 'bytes': len(cooked),
                        'source_bytes': len(raw), 'sanitized': True, 'compression': 'none'})
    media = []
    for p in sorted(LIVE.rglob('*.mp4')):
        if p.is_symlink():
            continue
        raw = p.read_bytes(); digest = sha(raw)
        if len(raw) > 95 * 1024 * 1024:
            raise ValueError('Media requires external large-file storage: ' + p.name)
        dest = ROOT / 'reports/cloud/assets' / (digest + '.mp4'); write(dest, raw)
        media.append({'source_relative': p.relative_to(ROOT).as_posix(),
                      'file': dest.relative_to(ROOT).as_posix(), 'sha256': digest, 'bytes': len(raw)})
    write(ROOT / 'EXPORT_MANIFEST.json', (json.dumps(base, ensure_ascii=False, indent=2) + '\n').encode())
    manifest = {'schema': 'research-handoff-export-v1', 'created_at': datetime.now(timezone.utc).isoformat(),
                'files': records, 'media': media, 'skipped': skipped,
                'policy': 'Research source, configuration, metric/annotation evidence, local completed videos; UTF8 paths/hosts redacted. Large text is deterministic gzip. Live files read only. Weights and GPU tensors remain external.'}
    write(PACKAGE / 'EXPORT_MANIFEST.json', (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode())
    print(json.dumps({'text_files': len(records), 'text_export_bytes': sum(r['bytes'] for r in records),
                      'local_video_files': len(media), 'unique_videos': len({r['sha256'] for r in media}),
                      'skipped': skipped}, ensure_ascii=False))


if __name__ == '__main__':
    main()
