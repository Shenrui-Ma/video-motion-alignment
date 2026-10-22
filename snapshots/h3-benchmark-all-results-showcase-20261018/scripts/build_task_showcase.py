#!/usr/bin/env python3
"""One task at a time, with current results and an explicit version selector."""
import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

import build_showcase as source

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'task_view_20261019'
OUTPUT = Path('/Users/researcher/Downloads/H3_视频实验_按任务查看_20261019.html')
EVIDENCE = HERE / 'display_evidence.json'
IVE_TITLES = {
    'long_0047': '角色替换 — 采访男人换为女人',
    'long_0123': '外观编辑 — 操作中的白面团改为红色',
    'long_0167': '外观编辑 — 三名动画角色的衣服改为白色',
    'long_0173': '角色替换 — 开盒互动中的女人换为老人',
    'long_0174': '外观编辑 — 行走女子的白衣改为黑色',
    'short_0035': '外观编辑 — 打字场景的蓝灯条改为红色',
    'short_0065': '物体编辑 — 木砧板换为大理石砧板',
    'short_0085': '外观编辑 — 持杯女子的头发改为红色',
    'short_0092': '场景编辑 — 移除室内植物',
    'short_0114': '物体编辑 — 运球中的篮球改为霓虹球',
    'short_0126': '场景编辑 — 在床边伸展男子身旁添加猫',
    'short_0131': '外观编辑 — 搬运者的黑色羽绒服改为白色',
    'short_0135': '主体编辑 — 画家的手臂换为机械臂',
    'short_0178': '外观编辑 — 白衬衫改为蓝色',
    'short_0210': '角色替换 — 舞台演讲女人换为男人',
    'short_0230': '外观编辑 — 厨房头巾与围裙改为蓝色',
    'short_0252': '角色替换 — 机舱戴面罩的男人换为年长女人',
    'short_0263': '角色替换 — 躺椅读书的女人换为小女孩',
    'short_0268': '角色替换 — 厨房餐桌右侧女人换为男孩',
    'short_0274': '角色替换 — 水中宇航员换为外星人',
    'short_0343': '角色替换 — 浴室照镜的女人换为医生',
    'short_0344': '外观编辑 — 黑色行李箱改为红色',
    'short_0352': '角色替换 — 坐姿传统服饰男人换为现代着装女人',
    'short_0358': '外观编辑 — 给饮酒男人添加眼镜',
    'short_0370': '外观编辑 — 喝水男子的蓝衣改为白色',
    'short_0392': '场景编辑 — 移除人物身后的雕花壁炉',
}
FLEX_ACTIONS = {
    'chest': '做双臂收放动作', 'crouch': '做两次下蹲起立',
    'fitness': '做侧举、合手与落臂动作', 'human2animal_1': '做俯卧支撑、抬胸与拱背动作',
    'human2animal_2': '做坐姿前屈动作', 'human2animal_3': '做低位支撑与倒立转换',
    'one_leg': '做单腿平衡与双臂上举动作', 'rotate': '做转身与回转动作',
}


def research_title(item):
    if item['benchmark'].lower() == 'ivebench':
        return IVE_TITLES.get(item['source_id'], '视频编辑 — ' + item['task'])
    target = item.get('reference_image_id', '')
    person = '动漫女子' if target.startswith('game_girl') else '动漫男子' if target.startswith('game_man') else '参考图男子'
    return '动作迁移 — ' + person + FLEX_ACTIONS.get(item['source_id'], item['task'])


def still_image(media, frame, ffmpeg, columns=3):
    folder = HERE / 'stills'
    folder.mkdir(exist_ok=True)
    target = folder / (media['sha256'][:20] + '_f' + str(frame) + ('_triplet' if columns == 4 else '') + '.jpg')
    if not target.exists():
        filters = ['-vf', f'select=eq(n\\,{frame}),scale=min(1920\\,iw):-2']
        if columns == 4:
            # These two IVE comparisons have four equal 16:9 panels and a caption strip.
            # Show source, ordinary edit and the selected method at the identical frame.
            filters = ['-filter_complex', f'[0:v]select=eq(n\\,{frame}),split=3[a][b][c];'
                       '[a]crop=iw/4:iw*9/64:0:0[x];'
                       '[b]crop=iw/4:iw*9/64:iw/4:0[y];'
                       '[c]crop=iw/4:iw*9/64:iw*3/4:0[z];'
                       '[x][y][z]hstack=inputs=3,scale=min(1920\\,iw):-2']
        subprocess.run([ffmpeg, '-v', 'error', '-i', media['path'], *filters,
                        '-frames:v', '1', '-q:v', '2', '-threads', '2', '-y', str(target)],
                       check=True, timeout=90, stdin=subprocess.DEVNULL)
        if not target.exists() or target.stat().st_size == 0:
            raise ValueError('Selected comparison frame is unavailable')
    return target
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
    return max(candidates or items, key=lambda item: (run_number(item), bool(item.get('is_current_version'))))


def short_method(item):
    if item.get('comparison_kind') == 'prompt_control': return '提示词对照'
    if item.get('comparison_kind') == 'sampler_control': return '采样器对照'
    if item.get('comparison_kind') == 'positional_control': return 'RoPE整体对齐'
    if item.get('comparison_kind') == 'reference_origin_control': return '参考分支相位引导'
    if item.get('comparison_kind') == 'resumed_online_guidance': return '自动时序引导'
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


def normalize(item, assets, ffmpeg, evidence):
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
    result['title'] = research_title(item)
    proof = evidence.get(item['id'], {})
    result.update({k: proof[k] for k in ['alignment_native', 'alignment_guided', 'summary'] if k in proof})
    result.setdefault('alignment_native', None)
    result.setdefault('alignment_guided', None)
    if mode == 'positional_control':
        alignment = item.get('action_alignment_by_method') or {}
        result['alignment_native'] = alignment.get('native')
        result['alignment_alternative'] = alignment.get('aligned')
        result['has_alternative'] = bool(item.get('alternative_video_path'))
    if mode == 'reference_origin_control':
        alignment = item.get('action_alignment_by_method') or {}
        result['alignment_native'] = alignment.get('native')
        result['alignment_guided'] = alignment.get('reference_origin')
    if mode == 'resumed_online_guidance':
        alignment = item.get('action_alignment_by_method') or {}
        result['alignment_native'] = alignment.get('native')
        result['alignment_guided'] = alignment.get('visible_only')
    result.setdefault('summary', ' '.join(dict.fromkeys([result['edit'], result['timing']])).strip())
    frame = max(0, min(int(proof.get('still_frame', item['valid_frames'] // 2)), item['valid_frames'] - 1))
    result['still_frame'] = frame
    result['still_reason'] = proof.get('still_reason') or '同一时刻的动作对照'
    result['has_guided'] = bool(item.get('guided_video_path')) and mode not in ['prompt_control', 'sampler_control']
    for player in players:
        media_entry = assets[player['asset']]
        shot = still_image({'path': media_entry['path'], 'sha256': player['asset']}, frame, ffmpeg, len(player['labels']))
        player['still'] = asset(shot, 'image/jpeg')
        player['still_labels'] = ([player['labels'][0], player['labels'][1], re.sub(r'^4[.．]', '3.', player['labels'][-1])]
                                 if len(player['labels']) == 4 else player['labels'])
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
    evidence = json.loads(EVIDENCE.read_text()).get('versions', {}) if EVIDENCE.exists() else {}
    for item in items:
        versions[item['id']] = normalize(item, assets, ffmpeg, evidence)
        groups.setdefault(task_key(item), []).append(item)
    tasks = []
    for key, rows in groups.items():
        current = choose_current(rows)
        version = versions[current['id']]
        tasks.append({'key': '|'.join(key), 'bench': current['benchmark'], 'source': key[1], 'target': key[2],
                      'title': version['title'], 'current': current['id'], 'state': version['task_state'],
                      'priority': PRIORITY.index(key) + 1 if key in PRIORITY else 0,
                      'latest_run': max(run_number(x) for x in rows),
                      'versions': [x['id'] for x in sorted(rows, key=run_number, reverse=True)]})
    tasks.sort(key=lambda t: (t['bench'], -t['latest_run'], t['source'], t['target']))
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
