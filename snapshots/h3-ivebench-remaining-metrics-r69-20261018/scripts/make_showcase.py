"""Embed actual videos and keep the original five tasks, including prior 0210."""
import argparse
import base64
import html
import math
from common import *

def summary():
    folder=ROOT/'retained/short_0210';prior=read(folder/'RETAINED.json')
    for name,digest in prior['files'].items():require(sha(folder/name)==digest,'retained prior evidence changed')
    rows = [{'source':'short_0210','prompt':'Replace the woman with a man','generation':'COMPLETE_RETAINED',
             'native_mf':prior['native_mf'],'forced_mf':prior['forced_mf'],
             'mf_delta':prior['forced_mf']-prior['native_mf'],'editing_success':'STRUCTURE_MISMATCH',
             'motion_preservation':'SOURCE_ACTION_NOT_PRESERVED','host':'.9','qualitative':prior['qualitative']}]
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
        review = ROOT / 'results' / source / 'HUMAN_REVIEW.json'
        if review.exists():
            value = read(review)
            require(value['source'] == source and value['source_selection_sha256'] == sha(SELECTION), 'human assessment source differs')
            for key in ('editing_success', 'motion_preservation'):
                row[key] = value[key]
        rows.append(row)
    means = {}
    for method in METHODS:
        values = [row[method + '_mf'] for row in rows if row[method + '_mf'] is not None]
        new_values=[row[method+'_mf'] for row in rows[1:] if row[method+'_mf'] is not None]
        means[method] = {'fixed_denominator': 5, 'valid_count': len(values), 'mean_if_all_five_valid': sum(values) / 5 if len(values) == 5 else None,
                         'remaining_four_complete_count':len(new_values),'remaining_four_mean_if_complete':sum(new_values)/4 if len(new_values)==4 else None}
    return {'fixed_denominator': 5, 'new_sources':list(PAIRS),'prior_source':'short_0210','rows': rows, 'means': means}

def build(output):
    report = summary(); blocks = []
    for row in report['rows']:
        source = row['source']; presentation = ROOT / 'showcase' / source / 'PRESENTATION.json'
        body = '<p>生成与评测待完成。</p>'
        if source=='short_0210':
            path=ROOT/'retained/short_0210/full_valid.mp4';prior=read(ROOT/'retained/short_0210/RETAINED.json')
            require(sha(path)==prior['video_sha256'],'retained prior video changed')
            body=f'<p>此前 .9 的同机对照。{html.escape(prior["qualitative"])}</p><video controls preload="metadata" src="data:video/mp4;base64,{base64.b64encode(path.read_bytes()).decode()}"></video>'
        if presentation.exists():
            record = read(presentation); body = ''
            for item in record['videos']:
                path = ROOT / 'showcase' / source / (item['name'] + '.mp4')
                require(sha(path) == item['video']['sha256'], 'presentation media changed')
                label = '完整有效片段' if item['name'] == 'full_valid' else '前2秒'
                body += f'<h3>{label}</h3><video controls preload="metadata" src="data:video/mp4;base64,{base64.b64encode(path.read_bytes()).decode()}"></video>'
        values = ['待评测' if row[method + '_mf'] is None else f"{row[method + '_mf']:.4f}" for method in METHODS]
        blocks.append(f'<section><h2>{source} · {html.escape(row["prompt"])}</h2><p>MF：普通编辑 {values[0]}；固定时序引导 {values[1]}。</p>{body}</section>')
    document = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IVEBench 原五条任务对照</title><style>body{margin:0;padding:24px;background:#0b0c10;color:#eee;font:18px/1.65 system-ui}main{max-width:1800px;margin:auto}section{margin:40px 0}h1{font-size:30px}h2{font-size:23px}h3{font-size:18px;color:#bbb}video{display:block;width:100%;background:#000}p{color:#c9cbd0}</style><main><h1>IVEBench · 原五条任务的固定时序引导对照</h1><p>保留此前0210结果，继续完成0230、0263、0352、0370。每对使用同机新生成的普通编辑与时序引导结果；三列依次为参考视频、普通编辑、编辑加固定时序引导，按相同物理帧展示。MF衡量轨迹相似性；编辑完成度和动作阶段另行核查。所有五条结果保留。</p>' + ''.join(blocks) + '</main></html>'
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(document)
    output.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return {'html': str(output), 'sha256': sha(output), 'fixed_denominator': 5}

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); a = p.parse_args(); verify_runtime(); print(json.dumps(build(a.output)))
