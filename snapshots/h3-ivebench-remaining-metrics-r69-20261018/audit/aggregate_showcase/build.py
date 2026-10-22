"""Publish existing completed media with receipt checks; no inference or re-encoding."""
from pathlib import Path
import base64
import datetime as dt
import hashlib
import html
import json
import math
import mimetypes
import re
import subprocess

BASE = Path('/Users/researcher/DevProjects')
HERE = Path(__file__).resolve().parent
OUTPUT = Path('/Users/researcher/Downloads/H3_已完成干预实验_视频总览_20261018.html')
BATCHES = [
    ('R73', '最新 P1 · IVEBench 动作阶段恢复', 'h3-ivebench-expanded-metrics-r73-20261018', None),
    ('R65', 'FlexiAct · 原有动作与身份', 'h3-flexiact-forced-metrics-r65-20261018', 'h3-timing-flexiact-forced-r65-20261018'),
    ('R66', 'FlexiAct · 动作与身份扩展', 'h3-flexiact-expanded-evaluation-r66-20261018', 'h3-timing-flexiact-expanded-r66-20261018'),
    ('R64', 'IVEBench · 新动作样例', 'h3-ivebench-heldout-metrics-r64-20261018', None),
    ('R69', 'IVEBench · 已选样例续测', 'h3-ivebench-remaining-metrics-r69-20261018', None),
]
TITLES = {
    'short_0252': '面罩动作：局部时差缩小',
    'short_0092': '移除房间中的植物', 'short_0114': '篮球改为霓虹发光球',
    'short_0126': '在床上男子身旁添加猫', 'short_0392': '移除装饰壁炉',
    'short_0230': '头巾与围裙由红色改为蓝色', 'short_0263': '女子替换为年轻女孩',
    'short_0352': '传统服饰男子替换为现代服饰女子', 'short_0370': '蓝色衣服改为白色',
}
REVIEWS = {
    'short_0252': '在原机舱场景内将右侧男子替换为年长女子。最终成片第32–63帧的臂方向序列匹配：普通编辑晚16帧，固定引导晚1帧；抓面罩阶段更接近原片。官方MF基本持平（0.8027→0.8024）。',
    'short_0092': '固定六时刻中，原片挥手和手靠近胸口的动作变成手机操作特写，背景植物仍可见。',
    'short_0114': '篮球出现发光纹理；原片手部运球变成脚靠近球及站立持球，动作内容和构图改变。',
    'short_0126': '猫已添加；原片背对镜头举起双手的动作变成侧面近景抚猫。',
    'short_0392': '采样时刻的主体与手势大体接近原片，壁炉结构仍保留。两种编辑的时序表现接近。',
    'short_0230': '原片侧身向碗中倾倒调料，两个结果改为正面手部特写和勺子舀拌；头巾出画，改色无法确认。',
    'short_0263': '原片女子在吊椅上读书；两个结果变为草地上站立女孩，书和吊椅消失。',
    'short_0352': '人物已替换；原片举手在采样时刻缺失，头部姿态与构图也改变。',
    'short_0370': '目标：将蓝色衣服改为白色。已有检查时刻可见白色上衣与举放杯动作；完整编辑任务待复核，暂无时序改善结论。',
}

def read(path):
    return json.loads(path.read_text())

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def binding(path):
    return {'file': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}

def local_path(root, recorded):
    p = Path(recorded)
    if p.is_file() and p.is_relative_to(root):
        return p
    parts = p.parts
    for marker in ('showcase', 'incoming', 'prepared'):
        if marker in parts:
            candidate = root.joinpath(*parts[parts.index(marker):])
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(recorded)

def probe(path):
    return read_json_command(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,avg_frame_rate,nb_frames,duration', '-of', 'json', str(path)])['streams'][0]

def read_json_command(cmd):
    return json.loads(subprocess.check_output(cmd, text=True))

def collect():
    items = []
    for batch, label, metric_name, producer_name in BATCHES:
        root = BASE / metric_name
        contract_path = root / 'configs/producer_scientific_contract.json'
        contract = read(contract_path)
        for case in contract['cases']:
            if case['arm'] != 'native':
                continue
            source = case['source_id']
            if batch == 'R73' and source != 'short_0252':
                continue
            receipt_path = root / 'showcase' / (source + '_PRESENTATION.json') if producer_name else root / 'showcase' / source / 'PRESENTATION.json'
            receipt = read(receipt_path)
            full = [v for v in receipt['videos'] if v.get('name') == 'full_valid' or Path(v['video']['file']).name.endswith('_full_valid.mp4')]
            assert len(full) == 1, (batch, source, 'full video')
            full = full[0]
            video_path = local_path(root, full['video']['file'])
            assert sha(video_path) == full['video']['sha256'], (batch, source, 'video hash')
            gate_record = receipt.get('input_gate', receipt.get('gate'))
            gate_path = local_path(root, gate_record['file'])
            assert sha(gate_path) == gate_record['sha256'], (batch, source, 'gate hash')
            gate = read(gate_path)
            assert gate['passed'] is True and gate['source_id'] == source
            prop = probe(video_path)
            assert prop['avg_frame_rate'] == '24/1'
            assert int(prop['nb_frames']) == case['valid_frame_count']
            assert int(prop['width']) % 3 == 0
            scores = {}
            for arm in ('native', 'forced'):
                score_path = root / 'scores' / arm / source / 'SCORE.json' if producer_name else root / 'results' / source / (arm + '_source1_target1.json')
                if score_path.exists():
                    score = read(score_path)
                    value = score['score'] if producer_name else score['motion_fidelity']
                    assert isinstance(value, (int, float)) and math.isfinite(value)
                    scores[arm] = {'value': value, **binding(score_path)}
                else:
                    scores[arm] = None
            portrait = None
            if producer_name:
                portrait_path = BASE / producer_name / 'inputs' / case['portrait']
                assert sha(portrait_path) == case['portrait_sha256']
                portrait = binding(portrait_path)
            review_path = root / 'results' / source / 'HUMAN_REVIEW.json'
            if batch == 'R73':
                review_path = root / 'results' / source / 'ROOT_VISUAL_REVIEW.json'
            items.append({
                'id': batch.lower() + '_' + source, 'batch': batch, 'batch_label': label,
                'source': source, 'motion_source': case.get('motion_source_id', source),
                'identity': Path(case.get('identity', '')).stem if producer_name else None,
                'group': case.get('group', 'original_pair'), 'benchmark': 'FlexiAct' if producer_name else 'IVEBench',
                'prompt_version': case.get('prompt_version'), 'prompt': case['prompt'],
                'valid_frames': case['valid_frame_count'], 'fps': 24, 'properties': prop,
                'title': TITLES.get(source, case.get('motion_source_id', source) + ' → ' + Path(case.get('identity', '')).stem),
                'video': binding(video_path), 'portrait': portrait, 'scores': scores,
                'presentation': binding(receipt_path), 'gate': binding(gate_path),
                'contract': binding(contract_path), 'router': contract['router'],
                'review': binding(review_path) if review_path.exists() else None,
                'review_text': REVIEWS.get(source, '') if review_path.exists() else '',
            })
    assert len(items) == 19
    assert {b: sum(i['batch'] == b for i in items) for b, *_ in BATCHES} == {'R73': 1, 'R65': 2, 'R66': 8, 'R64': 4, 'R69': 4}
    assert len(set(i['id'] for i in items)) == 19
    return items

STYLE = '''
:root{color-scheme:light;--ink:#172438;--muted:#55657b;--line:#dde4ed;--blue:#2356a5}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f3f5f8;color:var(--ink);font:16px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft Yahei",sans-serif}
header,main{max-width:2200px;margin:auto;padding:28px 3vw}header{padding-bottom:8px}h1{font-size:clamp(28px,3vw,46px);line-height:1.25;margin:8px 0 18px}h2{font-size:25px;margin:0}h3{font-size:22px;margin:0}.kicker{letter-spacing:.12em;font-size:12px;color:var(--blue);font-weight:700}.intro{max-width:1200px;color:var(--muted)}.facts{display:flex;gap:12px;flex-wrap:wrap;margin:22px 0}.facts span,.badge{background:white;border:1px solid var(--line);border-radius:9px;padding:6px 11px}.facts strong{color:var(--blue)}.legend{display:grid;grid-template-columns:repeat(3,1fr);text-align:center;background:#152134;color:white;border-radius:12px;padding:16px;gap:10px}.legend b{display:block;font-size:17px}.legend small{color:#b9c7da}.nav{display:flex;flex-wrap:wrap;gap:9px;margin:18px 0}.nav a{color:var(--blue);border:1px solid #cbd7e9;border-radius:30px;padding:5px 15px;text-decoration:none}.section-title{padding:22px 0 12px;scroll-margin-top:20px}.section-note{color:var(--muted);margin:4px 0 15px}.case{background:white;border:1px solid var(--line);border-radius:14px;margin:0 0 28px;overflow:hidden;scroll-margin-top:16px}.case-head{padding:22px 24px 16px;display:flex;justify-content:space-between;gap:20px;align-items:start}.case-meta{color:var(--muted);font-size:14px;margin-top:5px}.portrait{display:flex;gap:12px;align-items:center;flex-shrink:0;font-size:13px;color:var(--muted)}.portrait img{width:112px;height:84px;object-fit:contain;background:#101010;border-radius:6px}.video-wrap{background:#000}video{display:block;width:100%;height:auto;max-height:80vh;background:#000}.under{padding:14px 24px 20px}.metrics{display:flex;align-items:center;gap:22px;flex-wrap:wrap}.metric{font-size:14px;color:var(--muted)}.metric strong{font-size:24px;font-variant-numeric:tabular-nums;font-weight:600;color:var(--ink);margin-left:6px}.delta{font-variant-numeric:tabular-nums;color:var(--ink)}.tools{display:flex;gap:8px;margin-left:auto;flex-wrap:wrap}button,.download{font:inherit;font-size:13px;color:var(--blue);background:#f6f8fc;border:1px solid #cbd7e9;border-radius:7px;padding:5px 11px;cursor:pointer;text-decoration:none}button.active{background:#e5edfc}.review{margin:13px 0 0;color:#624b27;background:#fbf7ef;padding:10px 14px;border-radius:7px;font-size:14px}details{font-size:13px;color:var(--muted);margin-top:12px}summary{cursor:pointer}details p{max-width:1200px;overflow-wrap:anywhere}.hash{font-family:ui-monospace,monospace;font-size:11px}footer{max-width:2200px;margin:auto;padding:18px 3vw 44px;color:var(--muted);font-size:13px}.back{position:fixed;bottom:16px;right:18px;background:#172438;color:white;padding:8px 13px;border-radius:30px;text-decoration:none;font-size:13px}
@media(max-width:700px){header,main{padding:18px 12px}.case-head{padding:16px;display:block}.portrait{margin-top:12px}.under{padding:12px 16px}.legend{font-size:12px;padding:12px 5px}.legend b{font-size:13px}.tools{margin-left:0}.metrics{gap:12px}h3{font-size:19px}}
'''

def esc(value):
    return html.escape(str(value), quote=True)

def data_url(path, mime):
    return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode('ascii')

GROUPS = [
    ('candidate_evidence', '当前任务的候选证据', '原场景内角色替换；本例抓面罩阶段的局部时差缩小。'),
    ('needs_complete_review', '任务完成待复核', '保留已有观察，完整编辑任务与时序效果继续核对。'),
    ('task_or_action_failure', '编辑目标或原动作未保留', '逐条记录实际编辑目标和可见问题；以下结果用于诊断。'),
    ('historical_task_scope', '历史任务：动作迁移到目标图场景', '这10组的配置要求人物与场景来自目标图、动作来自视频，与当前保留原场景的编辑目的不同。'),
]


def write_page(items):
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='seconds')
    proposal = read(HERE / 'TASK_SCOPE_LAYOUT_PROPOSAL.json')
    by_id = {v['id']: v for v in proposal['items']}
    for item in items:
        item['display_group'] = by_id[item['id']]['group']
        item['task_status'] = by_id[item['id']]['status']
        item['task_scope_reason'] = by_id[item['id']]['reason']
        poster = HERE / 'posters' / (item['id'] + '.jpg')
        assert poster.is_file()
        item['poster'] = binding(poster)
    physical = BASE / 'h3-ivebench-expanded-metrics-r73-20261018/audit/physical_time_short0252/PHYSICAL_REPORT.txt'
    assert '普通+16帧' in physical.read_text() and '固定引导+1帧' in physical.read_text()
    items[0]['physical_review'] = binding(physical)
    extra_style = '.case>h3,.case>.classification{margin:18px 24px 10px}.classification{font-size:15px;color:#624b27}.playback{margin:0;font-size:inherit;color:inherit}.playback>summary{padding:10px 24px 18px;color:var(--blue);font-weight:600}.playback[open]>summary{padding-bottom:10px}.case-head{padding-top:8px}.scope-note{background:#eaf0fa;padding:15px 20px;border-radius:10px;max-width:1400px}.timing{background:#eef6f0;border:1px solid #c9dfce;border-radius:9px;padding:14px 18px;margin:0 0 18px}.timing strong{font-size:26px}.timing small{display:block;color:var(--muted);margin-top:6px}.section-title{padding-top:34px}.video-wrap video{max-height:none}.case[data-group="historical_task_scope"]{border-color:#d7d7df}'
    temp = OUTPUT.with_suffix('.html.tmp')
    with temp.open('w') as f:
        f.write('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>H3 原场景编辑 · 19组实验记录</title><style>' + STYLE + extra_style + '</style></head><body id="top">')
        f.write('<header><div class="kicker">H3 · 实验记录 · 2026.10.18</div><h1>原场景编辑：任务完成与动作时序</h1>')
        f.write('<p class="scope-note"><strong>研究目标：</strong>在原视频场景内替换人物或修改局部元素，保留原动作及其发生时刻。</p>')
        f.write('<p class="intro">以下保留全部19组已完成对照，并按任务与证据分区。面罩样例出现局部动作时差缩小；其余结果包含待复核的编辑、动作内容变化，以及任务范围不同的历史实验。</p>')
        f.write('<div class="facts"><span><strong>1</strong> 组候选证据</span><span><strong>1</strong> 组待复核</span><span><strong>7</strong> 组任务或动作问题</span><span><strong>10</strong> 组历史任务</span></div>')
        f.write('<div class="legend"><div><b>1. 参考视频</b><small>原动作与时间顺序</small></div><div><b>2. 编辑后视频</b><small>普通 H3 编辑</small></div><div><b>3. 编辑＋固定时序引导</b><small>第7–15次去噪预测加入引导</small></div></div>')
        f.write('<p class="intro">三列按同一原时间播放，配对使用相同输入与初始噪声。首组采用P1提示协议，其余18组为P0。MF衡量追踪点运动相似性，局部动作时差单独报告。</p>')
        f.write('<nav class="nav">' + ''.join(f'<a href="#{g}">{esc(label)} · {sum(i["display_group"] == g for i in items)}组</a>' for g,label,_ in GROUPS) + '</nav></header><main>')
        number = 0
        for group,label,note in GROUPS:
            f.write(f'<div class="section-title" id="{group}"><h2>{esc(label)}</h2></div><p class="section-note">{esc(note)}</p>')
            for item in (i for i in items if i['display_group'] == group):
                number += 1
                duration = item['valid_frames']/item['fps']
                group_note = '官方素材重新配对' if item['group'] == 'official_assets_crosspair_extension' else '官方任务配对'
                f.write(f'<article class="case" id="{item["id"]}" data-group="{group}"><h3>{number:02d} · {esc(item["title"])}</h3>')
                reason = item['task_scope_reason']
                if group == 'task_or_action_failure':
                    reason = '目标：' + item['title'] + '。' + reason
                if group == 'needs_complete_review':
                    reason = item['review_text']
                f.write('<p class="classification">' + esc(reason) + '</p>')
                opened = ' open' if group == 'candidate_evidence' else ''
                f.write('<details class="playback"' + opened + '><summary>查看完整三栏视频 · ' + f'{duration:.2f}秒' + '</summary>')
                f.write('<div class="case-head"><div><div class="case-meta">' + esc(item['batch']) + ' · ' + esc(item['source']) + ' · ' + ('P1' if item['prompt_version']=='P1' else 'P0') + ' · ' + group_note + '</div></div>')
                if item['portrait']:
                    p = Path(item['portrait']['file'])
                    f.write('<div class="portrait"><img alt="本组原始目标参考图" src="' + data_url(p,mimetypes.guess_type(str(p))[0] or 'image/jpeg') + '"><span>目标参考图<br>' + esc(item['identity']) + '</span></div>')
                f.write('</div><div class="video-wrap"><video id="video_' + item['id'] + '" controls playsinline preload="none" poster="' + data_url(Path(item['poster']['file']),'image/jpeg') + '" aria-label="' + esc(item['title']) + '三栏完整视频" src="')
                f.write(data_url(Path(item['video']['file']),'video/mp4'))
                f.write('"></video></div><div class="under">')
                if group == 'candidate_evidence':
                    f.write('<div class="timing">抓面罩阶段的匹配时差：<strong>+16 → +1 帧</strong><small>最终成片第32–63帧的臂方向序列匹配，约667 → 42毫秒；正值表示晚于参考视频。这个窗口在初次视频对照后选取。</small></div>')
                f.write('<div class="metrics">')
                for arm,text in [('native','普通编辑 MF'),('forced','固定时序引导 MF')]:
                    value = item['scores'][arm]
                    f.write('<span class="metric">' + text + '<strong>' + (f'{value["value"]:.4f}' if value else '待更新') + '</strong></span>')
                if all(item['scores'].values()):
                    delta=item['scores']['forced']['value']-item['scores']['native']['value']
                    f.write(f'<span class="delta">变化 {delta:+.4f}</span>')
                f.write('<div class="tools">' + ''.join(f'<button type="button" class="{"active" if rate == 1 else ""}" data-video="video_{item["id"]}" data-rate="{rate}">{rate:g}×</button>' for rate in (1,.5,.25)) + f'<button type="button" data-fullscreen="video_{item["id"]}">全屏查看</button><button type="button" data-download="video_{item["id"]}">保存本组MP4</button></div></div>')
                if item['review_text'] and group != 'needs_complete_review':
                    f.write('<p class="review">' + esc(item['review_text']) + '</p>')
                f.write('<details><summary>实际任务与核验记录</summary><p>' + esc(item['prompt']) + '</p><p>配对核验通过；完整有效帧按原顺序展示，成片字节与原收据一致。</p><p class="hash">视频 SHA-256：' + item['video']['sha256'] + '</p></details></div></details></article>')
        f.write('</main><footer>更新于 ' + esc(now) + '。19组视频与10张目标图完整嵌入，可直接发送本HTML查看。</footer><a class="back" href="#top">回到顶部</a>')
        f.write('''<script>
document.querySelectorAll('video').forEach(v=>v.addEventListener('play',()=>document.querySelectorAll('video').forEach(other=>{if(other!==v)other.pause()})));
document.querySelectorAll('details.playback').forEach(d=>d.addEventListener('toggle',()=>{if(!d.open)d.querySelectorAll('video').forEach(v=>v.pause())}));
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.rate){const v=document.getElementById(b.dataset.video);v.playbackRate=Number(b.dataset.rate);b.parentElement.querySelectorAll('[data-rate]').forEach(x=>x.classList.toggle('active',x===b));}if(b.dataset.fullscreen){const v=document.getElementById(b.dataset.fullscreen);if(v.requestFullscreen)v.requestFullscreen();else if(v.webkitEnterFullscreen)v.webkitEnterFullscreen();}if(b.dataset.download){const v=document.getElementById(b.dataset.download);const a=document.createElement('a');a.href=v.src;a.download=b.dataset.download+'.mp4';a.click();}});
</script></body></html>''')
    temp.replace(OUTPUT)
    return now

def verify(items, now):
    text = OUTPUT.read_text()
    embedded = re.findall(r'<video\b[^>]*\bid="([^"]+)"[^>]*\bsrc="data:video/mp4;base64,([A-Za-z0-9+/=]+)"', text)
    assert len(embedded) == 19
    by_id = {i['id']: i for i in items}
    checked = []
    for video_id, data in embedded:
        item = by_id[video_id.removeprefix('video_')]
        raw = base64.b64decode(data, validate=True)
        assert hashlib.sha256(raw).hexdigest() == item['video']['sha256']
        assert len(raw) == item['video']['bytes']
        checked.append({'id': item['id'], 'embedded_bytes': len(raw), 'sha256': item['video']['sha256']})
    assert not re.search(r'(?:src|href)="(?:https?://|file:|/Users/)', text)
    assert text.count('class="case"') == 19
    assert text.count('data-download=') == 19
    assert text.count('alt="本组原始目标参考图"') == 10
    assert len({i['motion_source'] for i in items if i['benchmark'] == 'FlexiAct'}) == 5
    # The original full-video files remain identical after rendering the HTML.
    for item in items:
        assert sha(Path(item['video']['file'])) == item['video']['sha256']
    receipt = {'schema': 'completed-intervention-aggregate-task-scope-v2', 'created': now,
        'passed': True, 'output': binding(OUTPUT), 'pairs': len(items),
        'per_batch': {b: sum(i['batch'] == b for i in items) for b, *_ in BATCHES},
        'fully_scored_pairs': sum(all(i['scores'].values()) for i in items),
        'all_original_media_unchanged': True, 'all_runtime_gates_passed': True,
        'all_embedded_video_bytes_exact': True, 'external_asset_dependencies': 0,
        'verification': 'Static HTML, ffprobe geometry/frame/timebase, source receipts and embedded byte hashes; browser playback not exercised.',
        'display_groups': {g: sum(i['display_group'] == g for i in items) for g, _, _ in GROUPS},
        'task_scope_proposal': binding(HERE / 'TASK_SCOPE_LAYOUT_PROPOSAL.json'),
        'embedded_videos': checked, 'items': items}
    (HERE / 'MANIFEST_AND_VERIFICATION.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: receipt[k] for k in ['passed', 'output', 'pairs', 'per_batch', 'fully_scored_pairs']}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    items = collect()
    now = write_page(items)
    verify(items, now)
