"""Build a portable snapshot from verified, completed R24 pair artifacts."""
from pathlib import Path
import base64
import hashlib
import html
import json
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
POST = ROOT / 'analysis/postrun'
OUT = Path('/Users/researcher/Downloads/H3_新素材泛化_四组对照_20261017.html')
CASES = {
    'fresh_a': ('车旁舞蹈', (44, 61), (17, 34), (82, 99), 45, 57),
    'fresh_b': ('篮球场舞蹈', (64, 81), (23, 40), (103, 120), 65, 77),
}
SEEDS = (2026101610, 2026101611)


def read(path):
    return json.loads(path.read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def esc(text):
    return html.escape(str(text), quote=True)


def main():
    compact_raw = (POST / 'COMPACT_RESULTS.json').read_bytes()
    compact = json.loads(compact_raw)
    assets, panels = [], []
    seen_pairs = []

    def embed(path, mime, expected=None):
        raw = path.read_bytes()
        digest = sha(raw)
        if expected and digest != expected:
            raise ValueError(f'Changed asset: {path}')
        assets.append({'path': str(path), 'sha256': digest, 'bytes': len(raw), 'mime': mime})
        return f'data:{mime};base64,' + base64.b64encode(raw).decode('ascii')

    def metric(case, seed, arm, window, feature, confidence):
        matches = [x for x in compact['timing'] if x['case'] == case and x['seed'] == seed
                   and x['arm'] == arm and x['window'] == list(window)
                   and x['feature'] == feature and x['confidence'] == confidence]
        if len(matches) != 1:
            raise ValueError(f'Timing row count {len(matches)}: {case}/{seed}/{arm}/{window}/{feature}/{confidence}')
        row = matches[0]
        if sha(Path(row['file']).read_bytes()) != row['sha256']:
            raise ValueError('Changed timing evidence')
        lag = row['reliable_lag_frames']
        value = 'UNKNOWN' if lag is None else f'{lag:+d}'
        note = ', '.join(row.get('flags') or [])
        return f'<span title="{esc(note)}">{value}</span>'

    for case, spec in CASES.items():
        for seed in SEEDS:
            key = f'{case}_seed{seed}'
            media = POST / 'media' / key
            gate_path = POST / 'pairs' / key / 'PAIR_COMPLETE.json'
            manifest_path = media / 'manifest.json'
            title = f'{spec[0]} · seed {seed}'
            if not gate_path.exists() or not manifest_path.exists():
                panels.append(f'<article class="pending"><h2>{esc(title)}</h2><p>配对实验与归档进行中。</p></article>')
                continue
            gate, manifest = read(gate_path), read(manifest_path)
            if not gate.get('passed'):
                raise ValueError(f'Pair did not pass: {key}')
            if key not in compact['pairs']:
                raise ValueError(f'Pair absent in frozen summary: {key}')
            seen_pairs.append({'key': key, 'pair_sha256': sha(gate_path.read_bytes()),
                               'media_manifest_sha256': sha(manifest_path.read_bytes())})
            rows = []
            for label, window in [('主窗口', spec[1]), ('前窗口', spec[2]), ('后窗口', spec[3])]:
                for confidence in (0.3, 0.5):
                    cells = ''.join('<td>' + metric(case, seed, arm, window, feature, confidence) + '</td>'
                                    for feature in ('arm_direction', 'wrist_relative')
                                    for arm in ('native', 'full_6to14'))
                    rows.append(f'<tr><td>{label} {window[0]}–{window[1]}</td><td>{confidence}</td>{cells}</tr>')
            videos = []
            for filename, label in [('full_length.mp4', '完整 5.875 秒'),
                                    ('primary_normal.mp4', '主窗口附近 · 原速'),
                                    ('primary_half_speed.mp4', '同一组帧 · 半速')]:
                uri = embed(media / filename, 'video/mp4', manifest['outputs'][filename]['sha256'])
                videos.append(f'<figure><figcaption>{label}</figcaption><video controls loop playsinline preload="metadata" src="{uri}"></video></figure>')
            pictures = []
            for frame in spec[4:]:
                path = media / f'frame{frame:03d}_triptych.png'
                uri = embed(path, 'image/png')
                pictures.append(f'<figure><figcaption>原片预定帧 {frame} · {frame/24:.3f} 秒</figcaption><img src="{uri}" alt="{esc(title)} frame {frame}"></figure>')
            table = '<div class="scroll"><table><thead><tr><th>窗口 / 帧</th><th>置信阈值</th><th>方向：原生</th><th>方向：引导</th><th>腕位置：原生</th><th>腕位置：引导</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'
            panels.append(f'<article><h2>{esc(title)}</h2><p>主窗口 {spec[1][0]}–{spec[1][1]} 帧；同一原片、提示词、种子与初始噪声。引导在去噪索引 6–14 对选中视频时间格施加同时间参考路由。</p>{table}{videos[0]}<details><summary>查看动作窗口与固定帧</summary>{"".join(videos[1:]+pictures)}</details></article>')
    now = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M CST')
    evidence = {'built_at': now, 'compact_sha256': sha(compact_raw), 'pairs': seen_pairs, 'assets': assets,
                'completed_runs': len(compact['runs']), 'planned_runs': 8,
                'rendered_layout': 'unassessed; offline artifact checks only'}
    style = '''body{margin:0;background:#0d1017;color:#ecf0f6;font:16px/1.65 system-ui,-apple-system,sans-serif}main{max-width:1560px;margin:auto;padding:38px 28px}h1{font-size:34px;line-height:1.25}h2{margin-top:0;font-size:24px}p{max-width:1100px}.muted,figcaption{color:#acb8cd}.lead{padding:20px;border-left:4px solid #7bcdbd;background:#162529}article{margin:26px 0;padding:26px;border:1px solid #344154;border-radius:15px;background:#141c28}article.pending{opacity:.7}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}td,th{padding:10px 14px;text-align:left;border-bottom:1px solid #344154;white-space:nowrap}th{color:#a8d6ee}.scroll{overflow:auto}figure{margin:24px 0}video,img{display:block;width:100%;height:auto;background:black;border-radius:5px}figcaption{margin-bottom:9px}summary{cursor:pointer;padding:14px 0;font-weight:600}a{color:#9edccd}.badge{display:inline-block;padding:6px 14px;background:#26364d;border-radius:30px;margin:0 9px 9px 0}@media(max-width:720px){main{padding:20px 12px}article{padding:14px}h1{font-size:27px}}'''
    text = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>H3 新素材泛化实验</title><style>{style}</style><main><p class="muted">研究证据快照 · {now}</p><h1>H3 动作时序：新素材配对实验</h1><span class="badge">{len(compact['runs'])} / 8 条已完成分析</span><span class="badge">{len(seen_pairs)} / 4 组完整对照</span><p class="lead">两段新参考视频，各使用两个预定种子；每组比较原生编辑与固定同时间参考路由。动作窗口和展示帧在生成前依据原片登记，全部四组结果按预定顺序呈现。</p><p>视频列依次为参考、编辑、编辑＋时序引导；各列完整画面按相同原始帧号同步。正时差表示编辑动作较晚，负值表示较早，单位为 24fps 下的帧。两个置信阈值属于测量敏感性检查。UNKNOWN 保留检测覆盖或可靠性不足的情况。</p><p>当前检验的核心是固定引导在新素材上的作用，以及原本接近同步的动作是否受到影响。两个源视频、两个种子的规模仅支持样例层面的观察；视觉身份、肢体形状、背景与时间指标分别检查。</p>{''.join(panels)}<p class="muted">素材来源：<a href="https://mixkit.co/free-stock-video/young-black-haired-girl-dancing-40367/">Mixkit 40367</a>、<a href="https://mixkit.co/free-stock-video/talented-urban-woman-dancing-at-night-on-a-basketball-court-51314/">Mixkit 51314</a>。本页包含所展示的视频与图片，可作为单个 HTML 文件传送。</p></main><script type="application/json" id="evidence">{json.dumps(evidence,ensure_ascii=False).replace('</','<\\/')}</script></html>'''
    temporary = OUT.with_suffix('.html.tmp')
    temporary.write_text(text)
    temporary.replace(OUT)
    report = dict(evidence, output=str(OUT), output_sha256=sha(OUT.read_bytes()), output_bytes=OUT.stat().st_size)
    (Path(__file__).parent / 'build_result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('output','completed_runs','output_bytes')},ensure_ascii=False))


if __name__ == '__main__':
    main()
