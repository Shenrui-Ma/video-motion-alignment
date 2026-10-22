from pathlib import Path
import base64
import hashlib
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
MEDIA = Path('/Users/researcher/Downloads/H3_后续实验对照_20261016')
OUT = Path('/Users/researcher/Downloads/H3_动作时序研究_方法与实验_单文件_20261016.html')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    old = json.loads((MEDIA / 'manifest.json').read_text())
    assets, proof = {}, {}
    for key in ['full', 'native_observer', 'stop11', 'roi', 'uniform', 'plus4', 'minus4']:
        item = old['cases'][key]
        assets[key] = {}
        proof[key] = {'title': item['binding']['title'], 'sources': [
            {'file': Path(s['path']).name, 'sha256': s['sha256']} for s in item['binding']['sources']], 'media': {}}
        for kind, filename, mime in [
            ('normal', f'{key}_5s.mp4', 'video/mp4'),
            ('slow', f'{key}_event_half.mp4', 'video/mp4'),
            ('poster', f'{key}_frame055.png', 'image/png'),
        ]:
            raw = (MEDIA / filename).read_bytes()
            assert sha(raw) == item['files'][filename]['sha256'], filename
            assets[key][kind] = f'data:{mime};base64,' + base64.b64encode(raw).decode('ascii')
            proof[key]['media'][kind] = {'file': filename, 'sha256': sha(raw), 'bytes': len(raw)}
    reverse_root = Path('/Users/researcher/DevProjects/h3-timing-reverse-reference-r25-20261017/analysis/postrun')
    assert json.loads((reverse_root / 'comparison/COMPARISON_COMPLETE.json').read_text())['passed']
    reverse_manifest = json.loads((reverse_root / 'media/manifest.json').read_text())
    reverse_assets, reverse_proof = {}, {}
    for key, filename, mime in [
        ('normal', 'source_native_forward_reverse_full_length.mp4', 'video/mp4'),
        ('frame055', 'frame055_comparison.png', 'image/png'),
        ('frame086', 'frame086_comparison.png', 'image/png'),
    ]:
        raw = (reverse_root / 'media' / filename).read_bytes()
        if key == 'normal':
            assert sha(raw) == reverse_manifest['outputs'][filename]['sha256']
        reverse_assets[key] = f'data:{mime};base64,' + base64.b64encode(raw).decode('ascii')
        reverse_proof[key] = {'file': str(reverse_root / 'media' / filename), 'sha256': sha(raw), 'bytes': len(raw)}
    assets['reverse_edges'] = reverse_assets
    fresh_root = Path('/Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/media')
    fresh_proof = {}
    for source_id in ['40372', '51304', '51317']:
        directory = fresh_root / source_id
        manifest = json.loads((directory / 'manifest.json').read_text())
        key = 'fresh_' + source_id
        assets[key], fresh_proof[source_id] = {}, {}
        for kind, filename, mime, expected in [
            ('normal', 'full_length.mp4', 'video/mp4', manifest['video']['sha256']),
            ('frame070', 'frame070_comparison.png', 'image/png', manifest['pictures']['70']['frame070_comparison.png']),
            ('frame105', 'frame105_comparison.png', 'image/png', manifest['pictures']['105']['frame105_comparison.png']),
        ]:
            raw = (directory / filename).read_bytes()
            assert sha(raw) == expected, filename
            assets[key][kind] = f'data:{mime};base64,' + base64.b64encode(raw).decode('ascii')
            fresh_proof[source_id][kind] = {'file': str(directory / filename), 'sha256': sha(raw), 'bytes': len(raw)}
    now = datetime.now(timezone.utc)
    evidence = {'built_utc': now.isoformat(),
                'snapshot_label': now.astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M CST'),
                'geometry': old['geometry'], 'timing': old['timing'], 'cases': proof,
                'asset_count': 33, 'additional_evidence': {'R25': reverse_proof, 'R26': fresh_proof},
                'interpretation': 'Development cases and three prospectively selected source-motion clips. All three new Native outcomes retained. Automatic guidance outcome pending.'}
    text = (ROOT / 'template.html').read_text()
    text = text.replace('__SNAPSHOT_TIME__', now.astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M'))
    text = text.replace('__ASSET_JSON__', json.dumps(assets, ensure_ascii=False, separators=(',', ':')))
    text = text.replace('__EVIDENCE_JSON__', json.dumps(evidence, ensure_ascii=False, separators=(',', ':')))
    assert '__ASSET_JSON__' not in text and '__EVIDENCE_JSON__' not in text
    temporary = OUT.with_suffix('.html.tmp')
    temporary.write_text(text)
    temporary.replace(OUT)
    (ROOT / 'asset_manifest.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    (ROOT / 'build_result.json').write_text(json.dumps({'output': str(OUT), 'bytes': OUT.stat().st_size,
        'sha256': sha(OUT.read_bytes()), 'template_sha256': sha((ROOT / 'template.html').read_bytes()),
        'assets': 33, 'external_runtime_dependencies': 0}, indent=2))
    print(json.dumps({'output': str(OUT), 'MB': round(OUT.stat().st_size / 1e6, 2), 'assets': 33}, ensure_ascii=False))


if __name__ == '__main__':
    main()
