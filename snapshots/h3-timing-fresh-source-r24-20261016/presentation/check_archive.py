"""Check the portable research archive against its build manifest, offline."""
import base64
import hashlib
import json
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class Archive(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = Counter()
        self.assets = []
        self.external_runtime = []
        self.videos_have_controls = True

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        self.tags[tag] += 1
        if tag == 'video':
            self.videos_have_controls &= 'controls' in attrs
        if tag in ('video', 'img'):
            uri = attrs.get('src', '')
            header, encoded = uri.split(',', 1)
            if not header.startswith('data:') or not header.endswith(';base64'):
                raise ValueError('Media is not embedded')
            raw = base64.b64decode(encoded, validate=True)
            self.assets.append((header[5:-7], hashlib.sha256(raw).hexdigest(), len(raw)))
        if tag in ('script', 'iframe', 'source') and attrs.get('src'):
            self.external_runtime.append(attrs['src'])
        if tag == 'link' and attrs.get('href'):
            self.external_runtime.append(attrs['href'])


def main():
    manifest = json.loads((ROOT / 'build_result.json').read_text())
    raw = Path(manifest['output']).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == manifest['output_sha256']
    page = Archive()
    page.feed(raw.decode('utf-8'))
    expected = Counter((a['mime'], a['sha256'], a['bytes']) for a in manifest['assets'])
    assert Counter(page.assets) == expected
    pairs = len(manifest['pairs'])
    assert page.tags['article'] == 4 and page.tags['table'] == pairs
    assert page.tags['video'] == 3 * pairs and page.tags['img'] == 2 * pairs
    assert page.videos_have_controls and not page.external_runtime
    result = dict(passed=True, output_sha256=digest, embedded_assets=len(page.assets),
                  completed_runs=manifest['completed_runs'], pairs=pairs,
                  videos=page.tags['video'], images=page.tags['img'],
                  external_runtime_dependencies=0,
                  rendered_layout='unassessed; offline archive integrity only')
    (ROOT / 'OFFLINE_CHECK.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
