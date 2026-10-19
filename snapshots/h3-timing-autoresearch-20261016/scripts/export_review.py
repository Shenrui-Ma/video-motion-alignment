"""Copy this research run into a portable review folder; leave originals intact."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import quote, unquote, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ('review', 'analysis', 'audit', 'configs', 'literature', 'inputs', 'outputs',
           'scripts', 'tests', 'extensions', 'extensions_staged', 'logs', 'processes',
           'scripts_staged', 'transfer_runtime_staged', 'semantic_clock_staged',
           'semantic_runtime_staged')
SKIP = {'.pt', '.pth', '.safetensors', '.pyc', '.zip', '.gz'}


def portable_links(raw, source_page, destination):
    """Resolve links against the original page before moving it to package root."""
    def rewrite(match):
        attr, address = match.groups()
        url = urlsplit(address)
        if url.scheme not in ('', 'file'):
            return match.group(0)
        if not url.path and not url.netloc:
            return match.group(0)  # Same-page anchor.
        if url.netloc:
            raise ValueError(f'Unsupported local link authority: {address}')
        path = Path(unquote(url.path))
        if not path.is_absolute():
            path = source_page.parent / path
        path = path.resolve()
        try:
            relative = path.relative_to(ROOT.resolve())
        except ValueError:
            raise ValueError(f'Unpackaged external local link: {path}')
        if path == source_page.resolve():
            relative = Path('index.html')
        elif not (destination / relative).exists():
            raise FileNotFoundError(f'Missing linked artifact: {relative}')
        target = urlunsplit(('', '', quote(str(relative), safe='/'), url.query, url.fragment))
        return f'{attr}="{target}"'

    return re.sub(r'(href|src)="([^"]+)"', rewrite, raw)


def export(destination):
    destination = destination.expanduser().resolve()
    if destination.exists():
        raise FileExistsError('Use a fresh destination to preserve earlier exports')
    destination.mkdir(parents=True)
    copied = []
    for folder in FOLDERS:
        for source in sorted((ROOT / folder).rglob('*')):
            if not source.is_file() or source.is_symlink():
                continue
            if source.suffix in SKIP or '__pycache__' in source.parts:
                continue
            relative = source.relative_to(ROOT)
            if relative == Path('review/index.html'):
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(relative)
    for name in ('progress.json',):
        shutil.copy2(ROOT / name, destination / name)
        copied.append(Path(name))

    # The landing page is promoted from review/ to the package root.
    source_page = ROOT / 'review/index.html'
    page = portable_links(source_page.read_text(), source_page, destination)
    page = page.replace(
        '当前本地页面含绝对路径，发送单独 HTML 不会自动带走素材；正式归档时需使用打包版本。',
        '此页使用相对路径。分享时请发送整个文件夹或压缩包，解压后打开 index.html；单独发送 HTML 不含视频。')
    (destination / 'index.html').write_text(page)
    copied.append(Path('index.html'))
    (destination / 'READ_ME.txt').write_text(
        '打开 index.html 查看本轮结果。请分享整个文件夹或压缩包。\n'
        '原始模型权重、中间大型张量和缓存未复制；它们的来源及哈希保留在原研究目录的审计记录。\n'
        '配置中的服务器绝对路径是复现记录，不代表在接收者电脑可以直接运行。\n'
        '视频为 AI 角色替换研究样例，不表示画面中的公众人物实际参与该活动。\n'
        f'原研究目录：{ROOT}\n')
    copied.append(Path('READ_ME.txt'))
    records = [{'path': str(p), 'bytes': (destination / p).stat().st_size,
                'sha256': hashlib.sha256((destination / p).read_bytes()).hexdigest()}
               for p in copied]
    manifest = {'source': str(ROOT), 'files': records,
                'total_bytes': sum(x['bytes'] for x in records),
                'presentation_links_checked': True,
                'large_tensor_and_weight_files_included': False}
    (destination / 'PACKAGE_MANIFEST.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2))
    return {'destination': str(destination), 'files': len(records),
            'bytes': manifest['total_bytes']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path)
    print(json.dumps(export(parser.parse_args().destination), ensure_ascii=False))
