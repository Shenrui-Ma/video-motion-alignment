#!/usr/bin/env python3
"""Render activated C/D difficulty controls using successful Comfy history only.
CPU derivatives only; never starts jobs or changes originals or activation metadata.
"""
from __future__ import annotations
import argparse
import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

sys.dont_write_bytecode = True
from render_review import STYLE, JS, VERSION as BASE_VERSION
from render_review import event_bounds, fingerprint, make_asset, probe, rel, render_compare

VERSION = 1
SOURCE_ID = '02_celebrate_thumbs'
LABELS = {'c': 'C: suit / general preservation', 'd': 'D: suit / explicit event'}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def activated_jobs(root):
    """Do not consult prepared_controls, queue, proposed graphs, or stray MP4 files."""
    path = root / 'configs' / 'controls.json'
    if not path.exists():
        return {}, {'status': 'not_activated', 'reason': 'configs/controls.json does not exist'}
    try:
        config = read_json(path)
    except (OSError, ValueError) as exc:
        return {}, {'status': 'invalid_activation_file', 'reason': str(exc)}
    if config.get('status') != 'activated':
        return {}, {'status': 'not_activated', 'reason': 'controls.json status is not activated', 'declared_status': config.get('status')}
    jobs = {}
    warnings = []
    for item in config.get('jobs', []):
        if not isinstance(item, dict):
            warnings.append('Non-dictionary job ignored')
            continue
        run = item.get('run_id', '')
        if not re.fullmatch(SOURCE_ID + r'_[cd]_s[12]', run):
            continue
        if item.get('source_id') != SOURCE_ID or item.get('independent_sample') is not False:
            warnings.append(f'{run}: inconsistent source / independent_sample metadata; ignored')
            continue
        if run in jobs:
            warnings.append(f'{run}: duplicate activated entry; kept first')
            continue
        jobs[run] = item
    return jobs, {'status': 'activated', 'config_path': str(path), 'config_sha256': fingerprint(path), 'analysis_label': config.get('analysis_label'), 'warnings': warnings}


def successful_output(root, run, entry):
    if entry is None:
        return {'status': 'not_activated', 'reason': 'No activated control entry for this run'}
    history_path = root / 'logs' / f'{run}_history.json'
    if not history_path.exists():
        return {'status': 'pending_history', 'reason': 'No persisted successful history yet'}
    try:
        history = read_json(history_path)
    except (OSError, ValueError) as exc:
        return {'status': 'pending_history', 'reason': f'History unreadable: {exc}'}
    status = history.get('status', {})
    messages = status.get('messages', [])
    if not (status.get('status_str') == 'success' and status.get('completed') is True and any(isinstance(m, list) and m and m[0] == 'execution_success' for m in messages)):
        return {'status': 'pending_success', 'reason': 'History lacks completed success and execution_success', 'history_path': str(history_path)}
    prompt = history.get('prompt', [])
    graph = prompt[2] if isinstance(prompt, list) and len(prompt) > 2 and isinstance(prompt[2], dict) else {}
    main_nodes = [node_id for node_id, node in graph.items() if node.get('class_type') == 'SaveVideo' and node.get('inputs', {}).get('filename_prefix') == run]
    if len(main_nodes) != 1:
        return {'status': 'history_mismatch', 'reason': 'Expected exactly one main SaveVideo with this run_id as filename_prefix', 'history_path': str(history_path)}
    node_id = main_nodes[0]
    node_output = history.get('outputs', {}).get(node_id, {})
    candidates = []
    for field in ('images', 'videos', 'gifs'):
        for item in node_output.get(field, []):
            if not isinstance(item, dict) or item.get('type') != 'output':
                continue
            filename = item.get('filename', '')
            if not re.fullmatch(re.escape(run) + r'(?:_\d+_?)?\.mp4', filename):
                continue
            path = (root / 'outputs' / item.get('subfolder', '') / filename).resolve()
            if root / 'outputs' not in path.parents:
                continue
            if path not in candidates:
                candidates.append(path)
    if len(candidates) != 1:
        return {'status': 'history_mismatch', 'reason': 'Expected one matching MP4 in successful main SaveVideo output', 'history_path': str(history_path)}
    path = candidates[0]
    if not path.is_file():
        return {'status': 'pending_download', 'reason': 'Successful history exists; its exact output is not local yet', 'expected_output': str(path), 'history_path': str(history_path)}
    try:
        info = probe(path)
    except Exception as exc:
        return {'status': 'pending_readable_output', 'reason': f'Exact output not readable: {exc}', 'history_path': str(history_path)}
    prompts = [node['inputs']['prompt'] for node in graph.values() if isinstance(node.get('inputs', {}).get('prompt'), str)]
    return {'status': 'verified_output', 'path': str(path), 'probe': info, 'history_path': str(history_path), 'history_sha256': fingerprint(history_path), 'save_node_id': node_id, 'prompt_id': prompt[1] if len(prompt) > 1 else None, 'prompt_texts': prompts, 'description': entry.get('description'), 'paired_noise_id': entry.get('paired_noise_id')}


def complete_derivative(render):
    if not render or render.get('status') != 'ready':
        return False
    return all(Path(p).exists() for p in [render.get('comparison', ''), render.get('quarter_speed', '')] + render.get('event_sheets', []))


def build(root):
    out = root / 'review' / 'difficulty'
    out.mkdir(parents=True, exist_ok=True)
    jobs, activation = activated_jobs(root)
    meta = read_json(root / 'inputs' / f'{SOURCE_ID}.json')
    source_path = root / 'inputs' / f'{SOURCE_ID}.mp4'
    bounds = event_bounds(meta)
    cache_path = out / 'asset_cache.json'
    cache = read_json(cache_path) if cache_path.exists() else {}
    source = make_asset(source_path, out, SOURCE_ID + '_source', cache)
    parts = [f'<!doctype html><html lang="zh"><meta charset="utf-8"><title>H3 同源换衣难度对照</title><style>{STYLE}</style>', '<h1>同源结构化换衣 · C/D 次级探索对照</h1>', '<p><b>复用原来的 02_celebrate_thumbs 素材，不是第 4 个独立样本。</b>目标：将黄色连帽卫衣改为深炭灰色翻领西装外套＋纯白有领衬衫，保持手部无遮挡。</p>', '<p>C：普通动作保持。D：同样换衣要求，额外明确保留原双手竖拇指。两个 seed 只提供重复生成，不增加独立素材数。本页不自动评分，不代表提出了新方法。</p>', '<p>只有 configs/controls.json 的 status 为 activated、对应任务有 execution_success 且匹配主 SaveVideo 的本地原始输出，才显示正式结果。prepared_controls、候选图和孤立 MP4 都不能证明已启动。</p>', '<p>原片 24 FPS；帧号从 0 开始。0.25×和逐帧按钮用于复核；精确对应请看编号图或同步横排 MP4。派生慢放保留原帧数、6 FPS，无生成插帧。</p>', f'<p class="warn">Activation: {html.escape(activation["status"])}\n{html.escape(activation.get("reason", ""))}</p>', '<p><a href="../index.html">返回原 A/B 主实验</a></p>']
    records = []
    errors = []
    for seed in (1, 2):
        key = f'{SOURCE_ID}_difficulty_s{seed}'
        record = {'source_id': SOURCE_ID, 'independent_new_source': False, 'seed_index': seed, 'status': 'pending', 'runs': {}, 'event_review_bounds_inclusive': bounds}
        parts.append(f'<section id="{key}"><h2>原素材 02 · 换衣 C/D · seed {seed}</h2><p>{html.escape(meta["event"]["label"])}；事件复核窗口 {bounds[0]}–{bounds[1]} 帧（含前后余量）。</p><div class="panels">')
        assets = {'source': source}
        for arm in ('c', 'd'):
            run = f'{SOURCE_ID}_{arm}_s{seed}'
            result = successful_output(root, run, jobs.get(run))
            record['runs'][arm] = result
            if result['status'] == 'verified_output':
                try:
                    assets[arm] = make_asset(Path(result['path']), out, Path(result['path']).stem, cache)
                except Exception as exc:
                    result['status'] = 'render_asset_error'
                    result['reason'] = str(exc)
                    errors.append({'run': run, 'error': str(exc)})
        for arm, label in [('source', 'SOURCE'), ('c', 'C：普通保持'), ('d', 'D：明确原事件')]:
            asset = assets.get(arm)
            if asset:
                url = rel(Path(asset['path']), out)
                info = asset['probe']
                parts.append(f'<figure><figcaption><b>{label}</b> · {info["frames"]} 帧 · {info["fps"]:.4g} FPS</figcaption><video class="sync" muted controls preload="metadata" src="{url}"></video><p><a href="{url}">原始视频</a></p><details><summary>全部编号帧图</summary>' + ''.join(f'<a href="{quote(p)}" target="_blank">第 {i+1} 页</a>' for i, p in enumerate(asset['sheets'])) + '</details></figure>')
            else:
                state = record['runs'][arm]
                parts.append(f'<figure><figcaption><b>{label}</b></figcaption><p class="pending">PENDING · {html.escape(state["status"])}</p><p>{html.escape(state.get("reason", ""))}</p></figure>')
        parts.append(f'</div><p><button onclick="play(\'{key}\')">同步播放</button><button onclick="pause(\'{key}\')">暂停</button><button onclick="rate(\'{key}\',0.25)">0.25×</button><button onclick="rate(\'{key}\',1)">1×</button><button onclick="step(\'{key}\',-1)">前一帧</button><button onclick="step(\'{key}\',1)">后一帧</button><button onclick="seekFrame(\'{key}\',{bounds[0]})">事件起点</button><span class="frame-label"></span></p>')
        for arm, asset in assets.items():
            if asset['probe']['frames'] != 107 or abs(asset['probe']['fps'] - 24) > 0.02:
                parts.append(f'<p class="warn">{arm.upper()}: 预期 107 帧／24 FPS，实际 {asset["probe"]["frames"]} 帧／{asset["probe"]["fps"]} FPS。不会裁掉差异。</p>')
        if 'c' in assets and 'd' in assets:
            signature = ':'.join([str(VERSION), str(BASE_VERSION), str(bounds)] + [assets[a]['sha256'] for a in ('source', 'c', 'd')])
            ledger_path = out / 'derived' / f'{key}.json'
            old = read_json(ledger_path) if ledger_path.exists() else {}
            rendered = old.get('render') if old.get('signature') == signature else None
            try:
                if not complete_derivative(rendered):
                    rendered = render_compare([source_path, Path(assets['c']['path']), Path(assets['d']['path'])], ['SOURCE', LABELS['c'], LABELS['d']], out / 'derived' / f'{key}_source_C_D.mp4', bounds)
                    ledger_path.parent.mkdir(exist_ok=True)
                    ledger_path.write_text(json.dumps({'signature': signature, 'render': rendered}, indent=2))
                record['render'] = rendered
                record['status'] = rendered['status']
                if rendered.get('warning'):
                    parts.append(f'<p class="warn">{html.escape(rendered["warning"])}</p>')
                if rendered['status'] == 'ready':
                    parts.append(f'<p>派生比较：<a href="{rel(Path(rendered["comparison"]), out)}">SOURCE–C–D 同步 24 FPS</a><a href="{rel(Path(rendered["quarter_speed"]), out)}">1/4 速（相同帧数）</a></p><details><summary>事件窗口每一帧横排</summary>' + ''.join(f'<a href="{rel(Path(p), out)}" target="_blank">第 {i+1} 页</a>' for i, p in enumerate(rendered['event_sheets'])) + '</details>')
            except Exception as exc:
                record['status'] = 'render_error'
                errors.append({'pair': key, 'error': str(exc)})
                parts.append(f'<p class="warn">渲染错误：{html.escape(str(exc))}</p>')
        parts.append('<details><summary>实际成功历史与提示词／事件定义</summary><pre>' + html.escape(json.dumps({'event': meta['event'], 'controls': record['runs']}, ensure_ascii=False, indent=2)) + '</pre></details></section>')
        records.append(record)
        print(key, record['status'], flush=True)
    parts.append(f'<script>{JS}</script></html>')
    (out / 'index.html').write_text('\n'.join(parts), encoding='utf-8')
    cache_path.write_text(json.dumps(cache, indent=2))
    report = {'renderer_version': VERSION, 'base_renderer_version': BASE_VERSION, 'created_local_time': time.strftime('%Y-%m-%d %H:%M:%S %z'), 'activation': activation, 'source_id': SOURCE_ID, 'independent_new_source': False, 'additional_independent_sample_count': 0, 'description': 'Secondary exploratory difficulty control on original source 02, not a fourth independent video.', 'pairs': records, 'errors': errors, 'rating_policy': 'No automatic event or edit quality scores; pending remains pending.'}
    (out / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    build(args.root.resolve())


if __name__ == '__main__':
    main()
