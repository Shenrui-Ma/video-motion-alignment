"""Retain small readable excerpts without copying embedded video data."""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

OUT = Path(__file__).resolve().parent


class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.ignored += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.ignored -= 1

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


files = [
    Path('/Users/researcher/Downloads/H3_动作时序研究_论文式进展_20261017.html'),
    Path('/Users/researcher/Downloads/H3_自动窗口与干预验证_20261017.html'),
    Path('/Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/analysis/public_benchmark_method_text_20261017.txt'),
]
records = []
for p in files:
    raw = p.read_bytes()
    text = raw.decode()
    if p.suffix == '.html':
        parser = Text(); parser.feed(text); text = ' '.join(parser.parts)
    text = ' '.join(text.split())
    positions = []
    start = 0
    while True:
        found = text.find('51310', start)
        if found < 0:
            break
        positions.append(found); start = found + 5
    excerpts = [text[max(0, pos - 130):pos + 750] for pos in positions]
    assert excerpts, str(p)
    records.append({'file': str(p), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                    'readable_excerpt_about_51310': excerpts})
result = {
    'schema': 'legacy-published-claim-audit-v1', 'files': records,
    'finding': 'The three formal artifacts inspected retain the fixed64–95 left-arm comparison Native15→Auto3→Manual−1; the earliest page predates completed Auto and only compares Manual. The later paper-style page separately identifies Auto bilateral lag as UNKNOWN. No cross-window substitution was identified in these artifacts.',
    'correction': 'Replace the shorthand Native15,Auto/Manual≈−1 with the explicitly qualified same-window left-arm15→3→−1. Auto−1 at96–127 cannot replace its+3 at64–95.',
    'scope': 'Only these three concrete artifacts and the R40/R41 archived numerical rows were audited; not every historical chat message.',
    'artifacts_modified': False,
}
(OUT / 'PUBLISHED_CLAIMS_REVIEW.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'files': len(records), 'excerpts': sum(len(r['readable_excerpt_about_51310']) for r in records)}))
