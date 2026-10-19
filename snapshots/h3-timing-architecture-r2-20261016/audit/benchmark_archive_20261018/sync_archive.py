"""Copy completed full-length comparison media; keep original experiment files."""
import hashlib
import json
import shutil
import time
from pathlib import Path

DOWNLOADS = Path('/Users/researcher/Downloads')
DEST = DOWNLOADS / 'H3_Benchmark_完整对比归档_20261018'
INDEX = DOWNLOADS / 'H3_公开样例实验总索引_20261018.json'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    rows = []
    index = json.loads(INDEX.read_text())
    for batch in index['batches']:
        for video in batch['videos']:
            src = Path(video['file'])
            if 'full_valid' not in src.name:
                continue
            name = src.parent.name + '.mp4' if src.name == 'full_valid.mp4' else src.name
            rows.append((src, Path(batch['benchmark']) / batch['experiment'] / name,
                         batch['comparison'], video['sha256']))
    for src in sorted(DOWNLOADS.glob('FlexiAct_*_完整*栏对比_20261018.mp4')):
        rows.append((src, Path('FlexiAct') / '早期五组展示' / src.name,
                     'Columns follow the caption in the original video; two-column clips have no intervention column.', sha(src)))
    for experiment, diagnostic in index.get('separate_diagnostics', {}).items():
        if isinstance(diagnostic, dict) and 'full_video' in diagnostic:
            video = diagnostic['full_video']
            src = Path(video['file'])
            rows.append((src, Path('单独诊断') / experiment / src.name,
                         diagnostic['scope'], video['sha256']))
    records = []
    for src, rel, caption, expected in rows:
        assert src.is_file() and sha(src) == expected, src
        out = DEST / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            assert sha(out) == expected, f'Existing archive differs: {out}'
        else:
            shutil.copy2(src, out)
        assert sha(out) == expected
        records.append({'file': str(rel), 'source': str(src), 'sha256': expected,
                        'bytes': out.stat().st_size, 'comparison': caption})
    manifest = {'updated_unix': time.time(), 'file_count': len(records),
                'scope': 'Completed full comparison videos, including unsuccessful outputs. Files can share source motions and are not independent benchmark samples.',
                'source_index_sha256': sha(INDEX), 'videos': records}
    (DEST / 'MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    (DEST / '阅读说明.txt').write_text(
        '这里保存已完成的完整对比视频，按 benchmark 和实验批次归档。\n'
        '三栏固定引导视频：参考视频、普通编辑、编辑加时序引导；具体标注在视频底部。\n'
        '早期五组展示沿用原文件，有些为参考/普通编辑两栏，请按画面标注阅读。\n'
        '同一动作可能对应多个人物或多次实验，视频文件数不等于独立样本数。\n'
        '所有完成结果均保留，含动作改变、效果下降和没有改善的结果。\n'
        'MANIFEST.json 记录每个文件的来源与 SHA256。新增成片将继续补入。\n')
    print(json.dumps({'directory': str(DEST), 'verified_full_videos': len(records)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
