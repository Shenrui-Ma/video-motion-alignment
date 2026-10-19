from pathlib import Path
import base64
import hashlib
import json
import re
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


details = {
    'short_0230': {
        'n': 86,
        'task': '头巾和围裙改蓝，人物、厨房、碗与绿色包装保留。',
        'summary': '全86帧审阅：两版均完成改蓝；倾斜包装、反复抖动倒料以及末段收回包装的动作阶段接近参考视频，固定引导未见明确额外收益。',
        'result': 'neutral',
        'timing_support': False,
        'extra_action_support': False,
        'observations': [
            {'frames': [0, 71], 'description': '三列都保留包装向碗倾斜及反复抖动，普通编辑已呈现对应动作。'},
            {'frames': [72, 85], 'description': '三列都完成最后抖动、抬离碗沿和收回包装；未观察到明确延迟修复。'}
        ],
        'limitations': '审阅基于全部有效帧的同帧三栏图；细小液流和手指接触未赋予精确事件帧。',
    },
    'short_0352': {
        'n': 78,
        'task': '传统服饰男人替换为现代连衣裙女人，木屋和坐姿保留。',
        'summary': '全78帧审阅：两版完成角色替换。普通编辑在第66–73帧额外抬手并斜向指点，参考视频该段没有这一可见手势；固定引导消除了这段新增手势。原有第13–25帧抬掌及放下在两版均保留。当前证据支持减少额外动作。',
        'result': 'extra_gesture_suppressed',
        'timing_support': False,
        'extra_action_support': True,
        'observations': [
            {'frames': [0, 12], 'description': '三列头部、上身的起伏阶段近似；人物替换和现代裙装明确。'},
            {'frames': [13, 25], 'description': '原有抬掌到脸侧再放下的阶段在普通与引导版均保留，峰值和回落接近参考。'},
            {'frames': [26, 65], 'description': '原场景、坐姿、头部起伏保持；生成的嘴形和表情有变化。'},
            {'frames': [66, 73], 'seconds': [2.75, 3.0416666666666665], 'description': '普通版右臂从胸前抬起，手指朝画面右上方指点再回落；参考和引导版该段均没有可见的抬手指点。'},
            {'frames': [74, 77], 'description': '普通版额外手势结束，三列恢复手部在画外的坐姿。'}
        ],
        'limitations': '这是新增动作被抑制的单例，尚不构成整体时间偏移被修复的证据；角色表情与口型仍有差别。',
    },
}

for source, detail in details.items():
    folder = ROOT / 'audit' / ('agent_full_review_' + source.replace('_', ''))
    bindings_file = folder / 'MEDIA_BINDINGS.json'
    bindings = json.loads(bindings_file.read_text())
    assert bindings['coverage'] == list(range(detail['n']))
    for page in bindings['pages']:
        assert sha(page['file']) == page['sha256']
    review = {
        'source_id': source, 'reviewer': 'recover_r99_r101', 'unix': time.time(),
        'frame_domain': [0, detail['n'] - 1], 'fps': 24,
        'review_method': 'Visually inspected every valid frame in consecutive six-row contact sheets at matched physical indices; no playback/UI claim.',
        'task_acceptance': 'pass', 'task_observation': detail['task'],
        'summary': detail['summary'], 'result': detail['result'],
        'support_for_clear_timing_repair': detail['timing_support'],
        'support_for_extra_action_suppression': detail['extra_action_support'],
        'observations': detail['observations'], 'limitations': detail['limitations'],
        'official_MF': 'pending actual official evaluator',
        'media_bindings': {'file': str(bindings_file), 'sha256': sha(bindings_file)},
        'gate_sha256': bindings['gate_sha256'], 'inputs': bindings['inputs'],
        'all_valid_frames_visually_inspected': True,
    }
    path = folder / 'REVIEW.json'
    assert not path.exists()
    path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
    (folder / 'REPORT.txt').write_text(detail['summary'] + '\n' + detail['limitations'] + '\n')
    html = Path('/Users/researcher/Downloads') / f'H3_R99_{source}_普通编辑与时序引导_20261019.html'
    before = html.read_text()
    old = '<p>编辑完成情况、动作时间及官方 Motion Fidelity 待本组成片评测。</p>'
    assert before.count(old) == 1
    after = before.replace(old, '<p id="actual-review">' + detail['summary'] + '</p><p>官方 Motion Fidelity 正在补测。</p>')
    old_assets = re.findall(r'data:(?:video/mp4|image/jpeg);base64,([^"\s]+)', before)
    new_assets = re.findall(r'data:(?:video/mp4|image/jpeg);base64,([^"\s]+)', after)
    assert old_assets == new_assets
    backup = folder / 'HTML_BEFORE.html'
    backup.write_text(before)
    html.write_text(after)
    receipt = {'html': str(html), 'before_sha256': sha(backup), 'after_sha256': sha(html),
               'embedded_assets_unchanged': True, 'asset_count': len(old_assets),
               'review_sha256': sha(path), 'browser_visual_check': 'not run; browser disabled'}
    (folder / 'HTML_UPDATE.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'source': source, 'review': str(path), **receipt}, ensure_ascii=False))
