"""Draw a standalone SVG from existing, completed attention readouts."""
from pathlib import Path
from html import escape
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parent
SOURCE = Path('/Users/researcher/DevProjects/h3-timing-ive-long0174-spatial-marginal-r111-20261019/audit/EXISTING_TEMPORAL_READOUT_PARTIAL.json')
data = json.loads(SOURCE.read_text())
completed = data['results'][:2]
assert all(r['completed_forwards'] == 20 for r in completed)
panels = []
for run, step, title in [(completed[0], 5, '普通编辑 · 去噪索引 5'),
                         (completed[0], 19, '普通编辑 · 去噪索引 19'),
                         (completed[1], 19, '同帧引导 · 去噪索引 19')]:
    raw = next(r for r in run['raw_readouts'] if r['forward_index'] == step)
    rows = raw['query_records']
    assert raw['block_index'] == 25 and raw['reference_temporal_bins'] == 47
    assert [r['query_latent_bin'] for r in rows] == list(range(43))
    assert all(len(r['p_ref_frame']) == 47 and abs(sum(r['p_ref_frame']) - 1) < 1e-5 for r in rows)
    panels.append({'title': title, 'run': run['run'], 'raw': raw, 'source_sha256': run['sha256_at_read']})
snapshot = ROOT / 'attention_readouts_completed.json'
snapshot.write_text(json.dumps({'scope': data['scope'], 'panels': panels}, ensure_ascii=False, indent=2) + '\n')
vmax = math.ceil(max(p for panel in panels for row in panel['raw']['query_records'] for p in row['p_ref_frame']) * 20) / 20
parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="545" viewBox="0 0 1300 545">',
         '<rect width="1300" height="545" fill="white"/>',
         '<style>text{font-family:Arial,"PingFang SC",sans-serif;fill:#202631} .label{font-size:14px}.title{font-size:18px;font-weight:600}.small{font-size:13px}</style>',
         '<text x="650" y="27" text-anchor="middle" class="title">实际参考读取的时间分布</text>']

def text(x, y, label, cls='label', anchor='start'):
    parts.append(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{escape(label)}</text>')

def color(p):
    a = max(0, min(1, p / vmax))
    return '#%02x%02x%02x' % tuple(round(s + a * (e-s)) for s, e in zip((247, 250, 254), (27, 80, 139)))

cell = 7.4
for i, panel in enumerate(panels):
    x, y = 58 + i * 405, 82
    text(x + 47 * cell / 2, 61, panel['title'], 'title', 'middle')
    for row in panel['raw']['query_records']:
        q = row['query_latent_bin']
        for t, p in enumerate(row['p_ref_frame']):
            parts.append(f'<rect x="{x+t*cell:.2f}" y="{y+q*cell:.2f}" width="{cell+.02}" height="{cell+.02}" fill="{color(p)}"/>')
    parts.append(f'<rect x="{x}" y="{y}" width="{47*cell}" height="{43*cell}" fill="none" stroke="#7f8b99"/>')
    parts.append(f'<path d="M{x+.5*cell},{y+.5*cell} L{x+42.5*cell},{y+42.5*cell}" stroke="#bd6537" stroke-dasharray="3,3" fill="none"/>')
    parts.append(f'<path d="M{x+43*cell},{y} V{y+43*cell}" stroke="#555" stroke-dasharray="3,3" fill="none"/>')
    for n in (0, 10, 20, 30, 42):
        text(x - 8, y + (n+.5)*cell + 5, str(n), anchor='end')
    for n in (0, 10, 20, 30, 40, 46):
        text(x + (n+.5)*cell, y + 43*cell + 20, str(n), anchor='middle')
    text(x + 47*cell/2, 447, '参考 latent 时间 bin', anchor='middle')
    same = sum(r['same_bin_mass'] for r in panel['raw']['query_records']) / 43
    text(x + 47*cell/2, 471, f'同 bin 概率均值 {same:.3f}', anchor='middle')
parts.append('<text transform="translate(18,240) rotate(-90)" text-anchor="middle" class="label">输出 latent 时间 bin</text>')
for j in range(100):
    parts.append(f'<rect x="1250" y="{82+j*3.18:.2f}" width="16" height="3.2" fill="{color(vmax*(1-j/99))}"/>')
text(1273, 88, f'{vmax:g}', 'small')
text(1273, 403, '0', 'small')
text(650, 504, 'block 25；固定 8 个 heads × 8 个画面中心邻点；参考组内条件概率', 'small', 'middle')
text(650, 527, '橙色虚线：相同 latent bin。竖虚线右侧：填充时间 bin。展示的是 QK 读取分布。', 'small', 'middle')
parts.append('</svg>')
out = ROOT / 'attention_readout.svg'
out.write_text(''.join(parts))
receipt = {'svg': str(out), 'sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
           'snapshot': str(snapshot), 'snapshot_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
           'vmax': vmax, 'scope': 'Existing sampled QK distributions. Averaging may hide head/spatial specificity. This is not a motion ground truth or the intervention-effective value distribution.'}
(ROOT / 'attention_readout_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(receipt, ensure_ascii=False))
