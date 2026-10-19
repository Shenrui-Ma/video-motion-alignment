"""Embed actual completed videos while retaining all two task denominators."""
import argparse
import base64
import html
import math
from common import *

def summary():
    rows = []
    for source in PAIRS:
        row = {'source': source, 'prompt': entry(source)['edit_prompt'], 'generation': 'PENDING', 'native_mf': None, 'forced_mf': None, 'mf_delta': None, 'editing_success': 'UNREVIEWED', 'motion_preservation': 'UNREVIEWED'}
        gate = ROOT / 'incoming' / source / 'PAIR_RUNTIME_GATE.json'
        if gate.is_file():
            row['generation'] = 'COMPLETE' if read(gate).get('passed') is True else 'FAILED_GATE'
        for method in METHODS:
            path = ROOT / 'results' / source / (method + '_source1_target1.json')
            if path.exists():
                value = read(path)['motion_fidelity']; require(math.isfinite(value), 'nonfinite score')
                row[method + '_mf'] = value
        if all(row[method + '_mf'] is not None for method in METHODS):
            row['mf_delta'] = row['forced_mf'] - row['native_mf']
        row['task_fidelity'] = {method: {key: 'UNREVIEWED' for key in ('requested_edit', 'unedited_content', 'action_content')} for method in METHODS}
        review = ROOT / 'results' / source / 'HUMAN_REVIEW.json'
        if review.exists():
            value = read(review)
            require(value['source'] == source and value['source_selection_sha256'] == sha(SELECTION), 'human assessment source differs')
            require(gate.exists() and value['pair_gate_sha256'] == sha(gate), 'human assessment actual pair differs')
            for method in METHODS:
                for key in ('requested_edit', 'unedited_content', 'action_content'):
                    status = value['arms'][method][key]
                    require(status in ('PASS', 'FAIL', 'UNKNOWN', 'UNREVIEWED'), 'invalid task fidelity status')
                    row['task_fidelity'][method][key] = status
        row['eligible_for_timing'] = all(v == 'PASS' for method in METHODS for v in row['task_fidelity'][method].values())
        rows.append(row)
    means = {}
    for method in METHODS:
        values = [row[method + '_mf'] for row in rows if row[method + '_mf'] is not None]
        means[method] = {'fixed_denominator': 2, 'valid_count': len(values), 'mean_if_all_two_valid': sum(values) / 2 if len(values) == 2 else None}
    fidelity = {method: {key: {status: sum(row['task_fidelity'][method][key] == status for row in rows) for status in ('PASS', 'FAIL', 'UNKNOWN', 'UNREVIEWED')} for key in ('requested_edit', 'unedited_content', 'action_content')} for method in METHODS}
    return {'fixed_denominator': 2, 'rows': rows, 'means': means, 'task_fidelity_counts': fidelity, 'timing_eligible_pair_count': sum(row['eligible_for_timing'] for row in rows), 'timing_summary': 'PENDING separate physical-time assessment; MF is not timing accuracy'}

def build(output):
    report = summary(); blocks = []
    for row in report['rows']:
        source = row['source']; presentation = ROOT / 'showcase' / source / 'PRESENTATION.json'
        body = '<p>生成与评测待完成。</p>'
        if presentation.exists():
            record = read(presentation); body = ''
            for item in record['videos']:
                path = ROOT / 'showcase' / source / (item['name'] + '.mp4')
                require(sha(path) == item['video']['sha256'], 'presentation media changed')
                label = '完整有效片段' if item['name'] == 'full_valid' else '前2秒'
                body += f'<h3>{label}</h3><video controls preload="metadata" src="data:video/mp4;base64,{base64.b64encode(path.read_bytes()).decode()}"></video>'
        values = ['待评测' if row[method + '_mf'] is None else f"{row[method + '_mf']:.4f}" for method in METHODS]
        fidelity_text = {method: ' / '.join(row['task_fidelity'][method].values()) for method in METHODS}
        blocks.append(f'<section><h2>{source} · {html.escape(row["prompt"])}</h2><p>MF：普通编辑 {values[0]}；固定时序引导 {values[1]}。</p><p>任务检查（编辑完成 / 未编辑内容 / 动作内容）：普通编辑 {fidelity_text["native"]}；固定引导 {fidelity_text["forced"]}。</p>{body}</section>')
    document = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IVEBench 两条局部编辑对照</title><style>body{margin:0;padding:24px;background:#0b0c10;color:#eee;font:18px/1.65 system-ui}main{max-width:1800px;margin:auto}section{margin:40px 0}h1{font-size:30px}h2{font-size:23px}h3{font-size:18px;color:#bbb}video{display:block;width:100%;background:#000}p{color:#c9cbd0}</style><main><h1>IVEBench · 两条局部编辑的固定时序引导</h1><p>两条官方原场景局部编辑任务：背景屏幕换成数字广告牌、狗换成猫。先检查指定编辑是否完成、未编辑人物与场景是否保留、动作内容是否保留，再评价合格配对的时序。合法遮挡和不可观测事件单独记录。两组均使用相同的 P1-local-v1 提示词。三列依次为参考视频、普通编辑、编辑加固定时序引导；展示相同物理帧。MF 衡量轨迹相似性，编辑是否成功与动作时序另行检查。固定分母为2，待完成、失败与不可测结果保留在汇总中。</p>' + ''.join(blocks) + '</main></html>'
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(document)
    output.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return {'html': str(output), 'sha256': sha(output), 'fixed_denominator': 2}

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); a = p.parse_args(); verify_runtime(); print(json.dumps(build(a.output)))
