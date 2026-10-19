#!/usr/bin/env python3
"""One task at a time, with current results and an explicit version selector."""
import argparse
import base64
import hashlib
import json
import os
import re
import shutil
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

import build_showcase as source

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'task_view_20261019'
OUTPUT = Path('/Users/researcher/Downloads/H3_视频实验_按任务查看_20261019.html')
PRIORITY = [
    ('flexiact', 'human2animal_1', 'game_man_4'),
    ('ivebench', 'short_0210', ''),
    ('ivebench', 'short_0230', ''),
    ('ivebench', 'short_0352', ''),
    ('ivebench', 'short_0114', ''),
    ('ivebench', 'short_0392', ''),
]
OVERRIDES = {
    'flex_r101_human2animal_1__game_man_4_fixed': {
        'title': '俯卧支撑 · Game Man 4', 'task_state': '动作仍待修复',
        'edit': '两版均换上目标动漫男子和白背景；末段伸臂拱背变为屈肘降胸，部分画面裁到头部。',
        'timing': '抬头、抬胸仍提前；引导后动作与普通编辑接近。',
        'next': '修复侧面构图和末段姿态，再生成同配置引导对照。'},
    'r99_short_0210': {'title': '舞台演讲 · 女人换为男人', 'task_state': '编辑已完成',
        'edit': '男讲者替换成功，蓝色舞台、构图和手势顺序保留。',
        'timing': '两版手势节奏接近参考。', 'next': '完整对照已归档。'},
    'r99_short_0230': {'title': '厨房操作 · 头巾与围裙改蓝', 'task_state': '编辑已完成',
        'edit': '两版均完成蓝色头巾和围裙，厨房与倒料动作保留。',
        'timing': '倾斜、抖动、收回包装的时间接近参考。', 'next': '完整对照已归档。'},
    'r99_short_0352': {'title': '坐姿表演 · 男人换为现代着装女人', 'task_state': '编辑已完成',
        'edit': '两版均完成现代着装女子替换。',
        'timing': '引导消除了普通编辑在第66–73帧新增的指点手势；原有抬掌动作保留。',
        'next': '完整对照已归档；当前收益为减少额外动作。'},
    'r110_short_0114_promptcontrol': {'title': '运球 · 篮球改为霓虹球', 'task_state': '构图仍待修复',
        'edit': '最新版恢复了球员、连续运球和霓虹球；镜头向下偏，人物上半身被裁切。',
        'timing': '当前展示两版普通编辑的提示词对照。新版引导待补。',
        'next': '先修复构图，通过后补同配置引导。'},
    'r108_short_0392': {'title': '手势 · 移除雕花壁炉', 'task_state': '编辑已完成',
        'edit': '两版均移除壁炉、台面和立柱，保留人物、服饰与手势。',
        'timing': '普通编辑的手部节奏已接近参考，引导保留了原有节奏。', 'next': '完整对照已归档。'},
}


def task_key(item):
    return (item['benchmark'].lower(), item['source_id'], item.get('reference_image_id') or '')


def run_number(item):
    match = re.search(r'(?:^|_)r(\d+)(?:_|$)', item['id'])
    return int(match.group(1)) if match else 0


def choose_current(items):
    # Sampler and extended-window comparisons remain available in history.
    candidates = [i for i in items if i.get('comparison_kind') != 'sampler_control'
                  and i.get('review_status_code') != 'neutral_extension']
    return max(candidates or items, key=run_number)


def short_method(item):
    if item.get('comparison_kind') == 'prompt_control': return '提示词对照'
    if item.get('comparison_kind') == 'sampler_control': return '采样器对照'
    if not item.get('guided_video_path'): return '普通编辑'
    if item.get('guidance_activation') == 'zero': return '自动检测 · 本次零触发'
    label = item.get('method_label', '')
    if '空间注意力' in label: return '空间注意力结构试验'
    if '延长' in label: return '延长时序引导'
    if '固定' in label: return '固定时序引导'
    if '自动' in label: return '自动时序引导'
    return label or '时序引导'


def task_state(item):
    status = item.get('review_status', '')
    if item.get('count_as_complete_task_success') is True or '任务完成' in status or '角色和动作已完成' in status:
        return '编辑已完成'
    if item.get('count_as_complete_task_success') is False or any(s in status for s in ['失败', '不完整', '差异', '待核验', '失真', '裁', '改变']):
        return '编辑待修复'
    return '待复核'


def normalize(item, assets, ffmpeg):
    def asset(path, mime=None):
        p = Path(path)
        digest = source.sha256(p)
        assets.setdefault(digest, {'path': str(p), 'mime': mime or 'video/mp4', 'bytes': p.stat().st_size})
        return digest

    mode = item.get('comparison_kind') or 'guided_pair'
    media = item['media']
    labels = item.get('column_labels') or ['1.参考视频', '2.普通编辑', '3.时序引导']
    players = []
    if item.get('comparison_video_path'):
        m = media['comparison_video_path']
        players.append({'asset': asset(m['path']), 'poster': asset(source.poster(m, ffmpeg), 'image/jpeg'), 'labels': labels})
    elif item.get('native_comparison_video_path'):
        p = Path(item['native_comparison_video_path'])
        m = {'path': str(p), 'sha256': source.sha256(p)}
        expected = item.get('media_sha256', {}).get('native_comparison_video_path')
        if expected and expected != m['sha256']: raise ValueError('Native comparison hash mismatch')
        players.append({'asset': asset(p), 'poster': asset(source.poster(m, ffmpeg), 'image/jpeg'), 'labels': ['1.参考视频', '2.普通编辑']})
    else:
        for field, label in [('reference_video_path', '1.参考视频'), ('ordinary_video_path', '2.普通编辑'), ('guided_video_path', '3.时序引导')]:
            if field in media:
                m = item.get('pending_display_media', {}).get(field, media[field])
                players.append({'asset': asset(m['path']), 'poster': asset(source.poster(m, ffmpeg), 'image/jpeg'), 'labels': [label]})
    if mode == 'prompt_control':
        labels = item.get('column_labels') or ['1.参考视频', '2.旧提示词编辑', '3.新版提示词编辑']
        players[0]['labels'] = labels
    review = item.get('display_summary') or item.get('review_summary') or ''
    brief = '。'.join(review.split('。')[:2]).rstrip('。') + ('。' if review else '')
    override = OVERRIDES.get(item['id'], {})
    metrics = item.get('quantitative_metrics') or {}
    result = {
        'id': item['id'], 'run': 'R' + str(run_number(item)),
        'title': re.sub(r'（.*?）|\(.*?\)', '', item['title']).strip(),
        'task': item.get('display_task') or item['task'],
        'method': short_method(item), 'method_detail': item.get('method_label', ''),
        'task_state': task_state(item), 'edit': brief, 'timing': item.get('review_status') or '待复核',
        'next': '', 'players': players, 'mode': mode,
        'reference_image': asset(media['reference_image_path']['path'], media['reference_image_path']['mime']) if item.get('reference_image_used') else None,
        'fps': item['fps'], 'frames': item['valid_frames'],
        'mf': metrics.get('motion_fidelity'), 'repair_mf': metrics.get('task_repair_motion_fidelity'),
        'events': metrics.get('event_timing'), 'prompt': item.get('prompt') or '',
        'review_full': review, 'pair_group': item.get('pair_group', ''),
        'evidence_count': len(item.get('evidence_paths', [])),
        'source_time': item.get('source_time_precision') or item.get('source_processing') or '',
    }
    result.update(override)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inventory', action='append', type=Path)
    args = parser.parse_args()
    HERE.mkdir(exist_ok=True)
    cache, raw, inventory_receipts = {}, [], []
    inputs = args.inventory or [ROOT / 'inventory' / (name + '.json') for name in ['flexiact', 'ivebench']]
    for p in inputs:
        name = p.stem.split('_')[0]
        content = p.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        (HERE / (name + '_' + digest[:16] + '.json')).write_bytes(content)
        inventory_receipts.append({'path': str(p), 'sha256': digest})
        raw += [source.validate_item(i, cache) for i in source.load_inventory(p)]
    items, duplicates = source.deduplicate(raw)
    ffmpeg = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
    source.prepare_pending(items, ffmpeg)
    assets, versions, groups = {}, {}, OrderedDict()
    for item in items:
        versions[item['id']] = normalize(item, assets, ffmpeg)
        groups.setdefault(task_key(item), []).append(item)
    tasks = []
    for key, rows in groups.items():
        current = choose_current(rows)
        version = versions[current['id']]
        tasks.append({'key': '|'.join(key), 'bench': current['benchmark'], 'source': key[1], 'target': key[2],
                      'title': version['title'], 'current': current['id'], 'state': version['task_state'],
                      'priority': PRIORITY.index(key) + 1 if key in PRIORITY else 0,
                      'versions': [x['id'] for x in sorted(rows, key=run_number, reverse=True)]})
    tasks.sort(key=lambda t: (0 if t['priority'] else 1, t['priority'], t['bench'], t['source'], t['target']))
    metadata = {'updated': datetime.now().strftime('%Y-%m-%d %H:%M'), 'tasks': tasks, 'versions': versions,
                'asset_types': {k: v['mime'] for k, v in assets.items()},
                'unique_sources': len(set((i['benchmark'].lower(), i['source_id']) for i in items))}
    (HERE / 'DATA.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    template = (HERE / 'template.html').read_text()
    rendered = template.replace('__DATA__', json.dumps(metadata, ensure_ascii=False).replace('<', '\\u003c'))
    before, after = rendered.split('<!-- MEDIA -->')
    temp = OUTPUT.with_suffix('.html.tmp')
    with temp.open('w') as out:
        out.write(before)
        for digest, media in assets.items():
            out.write('<script type="application/octet-stream" id="asset_' + digest + '">')
            h = hashlib.sha256()
            with Path(media['path']).open('rb') as f:
                for block in iter(lambda: f.read(3 * 1024 * 1024), b''):
                    h.update(block)
                    out.write(base64.b64encode(block).decode('ascii'))
            if h.hexdigest() != digest: raise ValueError('Media changed during embedding')
            out.write('</script>\n')
        out.write(after)
    temp.replace(OUTPUT)
    canonical = OUTPUT.parent / 'H3_FlexiAct_IVEBench_全部实验对比_单文件_20261018.html'
    alias_temp = canonical.with_suffix('.html.new')
    if alias_temp.exists(): alias_temp.unlink()
    os.link(OUTPUT, alias_temp)
    alias_temp.replace(canonical)
    receipt = {'output': str(OUTPUT), 'sha256': source.sha256(OUTPUT), 'bytes': OUTPUT.stat().st_size,
               'canonical_output': str(canonical),
               'tasks': len(tasks), 'versions': len(versions), 'unique_sources': metadata['unique_sources'],
               'embedded_unique_assets': len(assets), 'inventories': inventory_receipts, 'duplicates': duplicates,
               'assets': assets, 'priority_defaults': {t['title']: t['current'] for t in tasks if t['priority']}}
    (HERE / 'BUILD.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k not in ['assets', 'duplicates']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
