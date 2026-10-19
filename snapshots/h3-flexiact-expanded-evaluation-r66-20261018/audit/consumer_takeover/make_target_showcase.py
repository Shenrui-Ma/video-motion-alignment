"""Portable actual-result gallery with unchanged target-image bytes and grouped scores."""
import argparse
import base64
import hashlib
import html
import json
import math
import mimetypes
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PRODUCER = Path('/Users/researcher/DevProjects/h3-timing-flexiact-expanded-r66-20261018')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def data_uri(path):
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()


def score(pair, method):
    path = ROOT / 'scores' / method / pair / 'SCORE.json'
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    assert value['pair_key'] == pair and value['method'] == method
    return value['score']


def guidance_summary(pair):
    source = ROOT / 'audit/consumer_takeover/guidance_effect_source.py'
    binding = json.loads(source.with_suffix('.binding.json').read_text())
    assert digest(source) == binding['copied_script_sha256'] == binding['source_sha256']
    output = ROOT / 'reports/guidance_effect' / (pair + '.json')
    incoming = ROOT / 'incoming' / pair
    if not output.exists():
        cmd = [sys.executable, str(source), '--pair-gate', str(incoming / 'PAIR_RUNTIME_GATE.json'), '--output', str(output)]
        for method in ('native', 'forced'):
            cmd += ['--' + method + '-router', str(incoming / (method + '_router.json')), '--' + method + '-job', str(incoming / (method + '_job.json'))]
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
    result = json.loads(output.read_text())
    for method in ('native', 'forced'):
        for key in ('router_file', 'job_file'):
            record = result['runs'][method][key]
            assert digest(record['file']) == record['sha256']
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--video', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    contract = json.loads((ROOT / 'configs/contract.json').read_text())
    cases = json.loads((ROOT / 'configs/producer_scientific_contract.json').read_text())['cases']
    sections = {}
    evidence = []
    grouped_scores = {}
    for video in args.video:
        assert video.name.endswith('_full_valid.mp4') and video.is_file()
        pair = video.name.removesuffix('_full_valid.mp4')
        internal_report = guidance_summary(pair)
        info = next(x for x in contract['pairs'] if x['pair_key'] == pair)
        case = next(x for x in cases if x['pair_key'] == pair and x['arm'] == 'native')
        portrait = PRODUCER / 'inputs' / case['portrait']
        assert digest(portrait) == case['portrait_sha256']
        presentation = json.loads((ROOT / 'showcase' / (pair + '_PRESENTATION.json')).read_text())
        declared = next(x for x in presentation['videos'] if x['physical_frame_interval'] == [0, 146])
        assert digest(video) == declared['video']['sha256']
        a, b = score(pair, 'native'), score(pair, 'forced')
        score_text = '官方 MF：待评分'
        if a is not None and b is not None:
            assert math.isfinite(a) and math.isfinite(b)
            score_text = f'官方 MF：编辑后 {a:.4f}；时序引导后 {b:.4f}；差值 {b-a:+.4f}。'
            grouped_scores.setdefault(info['group'], []).append((a, b))
        elif all((ROOT / 'scores' / method / pair / 'SCORE.json').exists() for method in ('native', 'forced')):
            av = '—' if a is None else f'{a:.4f}'
            bv = '—' if b is None else f'{b:.4f}'
            score_text = f'官方 MF：编辑后 {av}；时序引导后 {bv}。— 表示原公式结果未定义。'
        label = html.escape(pair.replace('__', ' · '))
        section = f'<section><h3>{label}</h3><figure class="target"><img src="{data_uri(portrait)}" alt="目标人物原始参考图"><figcaption>目标人物参考图</figcaption></figure><video controls playsinline loop preload="metadata" src="{data_uri(video)}"></video><p class="scores">{score_text}</p>'
        visual_note = ROOT / 'reports/visual_notes' / (pair + '.json')
        if visual_note.exists():
            review = json.loads(visual_note.read_text())
            assert review['pair'] == pair and review['visual_review_complete'] is True
            section += '<p>' + html.escape(review['observation']) + '</p>'
        figure = ROOT / 'showcase' / (pair + '_fixed_checkpoints.jpg')
        if figure.exists():
            fixed = json.loads(figure.with_suffix('.json').read_text())
            assert digest(figure) == fixed['figure_sha256']
            section += f'<details><summary>预先选定的同帧检查点</summary><img class="checkpoints" src="{data_uri(figure)}" alt="同帧动作对照"></details>'
        section += '</section>'
        sections.setdefault(info['group'], []).append(section)
        evidence.append({'pair': pair, 'video': str(video), 'video_sha256': digest(video), 'portrait': str(portrait), 'portrait_sha256': digest(portrait), 'group': info['group'], 'sampled_attention_execution_summary': {'file': str(internal_report), 'sha256': digest(internal_report)}})
    groups = []
    for key, title, denominator in [('official_csv_identity_generalization', '官方 CSV 配对', 2), ('official_assets_crosspair_extension', '官方素材构造的交叉配对', 6)]:
        content = sections.get(key, [])
        values = grouped_scores.get(key, [])
        note = f'已完成展示 {len(content)}/{denominator} 对；双方 MF 均有有限值 {len(values)}/{denominator} 对。'
        if values:
            note += f'这 {len(values)} 对的 MF 均值：编辑后 {sum(x[0] for x in values)/len(values):.4f}，时序引导后 {sum(x[1] for x in values)/len(values):.4f}。'
        groups.append(f'<div class="group"><h2>{title}（{denominator} 对）</h2><p>{note}</p>'+''.join(content)+'</div>')
    document = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>R66 FlexiAct 扩充样例</title><style>body{margin:0;background:#111;color:#eee;font:17px system-ui;line-height:1.6}main{max-width:2400px;margin:auto;padding:24px}h1{font-size:28px}h2{font-size:23px;border-top:1px solid #555;padding-top:24px}h3{font-size:19px;font-weight:500}p,figcaption{color:#bbb}a{color:#b5caff}section{margin:30px 0 56px}video{display:block;width:100%;max-height:82vh;background:#000}.target{display:flex;align-items:center;gap:18px;margin:12px 0 18px}.target img{height:160px;max-width:260px;object-fit:contain}.checkpoints{width:100%;display:block;margin-top:16px}summary{cursor:pointer}.scores{margin-top:8px}</style><main><h1>固定时序引导：FlexiAct 扩充样例</h1><p>本批计划 8 对，覆盖 5 个动作源，其中 3 个为新增动作源：6 对由官方素材构造交叉配对，2 对沿用官方 CSV 配对。下方展示已完成的 '+str(len(evidence))+' 对。</p><p>视频从左到右：参考视频、编辑后视频、编辑＋时序引导后视频。展示完整有效 147 帧，共 6.125 秒，各列对应同一物理时刻。目标人物参考图用于检查角色编辑是否完成。本批任务同时要求采用参考图的人物外观与场景，动作保留参考视频的阶段、方向、幅度和时刻。human2animal_2 为低运动变化对照；预定检查点用于同帧观察。</p><p>官方 MF 衡量轨迹相似度，越高越好。本批属于开发性子集；<a href="https://arxiv.org/abs/2505.03730">原论文完整基准</a>含 25 类动作 × 10 个目标人物，共 250 对。以下分组均值仅汇总本批对应的成对结果。</p>'+''.join(groups)+'</main></html>'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix('.html.tmp')
    temp.write_text(document)
    temp.replace(args.output)
    receipt = {'html': str(args.output), 'html_sha256': digest(args.output), 'pairs_shown': len(evidence), 'prespecified_pairs': 8, 'distinct_motion_sources': 5, 'new_motion_sources': 3, 'portrait_bytes_unchanged': True, 'assets_embedded': True, 'evidence': evidence}
    (ROOT / 'audit/consumer_takeover/SHOWCASE_LATEST.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'html': str(args.output), 'pairs_shown': len(evidence)}))


if __name__ == '__main__':
    main()
