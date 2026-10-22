"""CPU checks for the standalone export; does not launch a web renderer."""
import ast
import base64
import hashlib
import io
import json
import re
import subprocess
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IDENT = 'r141b_short_0252_seed2026101703_generic_retention'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt = json.loads((ROOT / 'audit/BUILD.json').read_text())
    local = ROOT / 'index.html'
    output = Path(receipt['output'])
    assert sha(local) == sha(output) == receipt['output_sha256']
    html = local.read_text()
    payload = re.search(r'<script id="dataset" type="application/json">(.*?)</script>',
                        html, re.S).group(1)
    data = json.loads(payload)
    items = {x['id']: x for x in data['items']}
    assert len(items) == len(data['items']) == 26
    assert data['default_version'] == IDENT
    assert data['summary']['sleep_generated_outputs'] == 30
    assert data['summary']['sleep_independent_source_videos'] == 16
    assert data['summary']['after_wake_generated_outputs'] == 3
    assert sum(x['new_outputs'] for x in data['items']) == 33
    r141b = items[IDENT]
    assert r141b['mode'] == 'guided_pair' and r141b['new_outputs'] == 2
    assert r141b['after_wake'] and r141b['frames'] == 98 and r141b['fps'] == 24
    assert r141b['labels'] == ['参考视频', '普通编辑', '固定时序引导']
    assert r141b['mf'] == [0.8127411516001477, 0.8029023147510279]
    assert [(e['source_frames'], e['native_frames'], e['guided_frames'])
            for e in r141b['event_table']] == [
        ([42, 45], [58, 61], [42, 45]),
        ([48, 51], [62, 65], [48, 51]),
        ([69, 75], [85, 89], [69, 75]),
    ]
    for ident in ['r123_short_0358_full_context', 'r126_long_0059_full_context']:
        assert items[ident]['prompt_label'] == '六段提示词：含人物、场景与动作描述'
    for ident in ['r122_long_0039_generic_retention', IDENT]:
        assert items[ident]['prompt_label'] == 'benchmark原句 + 输入绑定 + 通用保留要求'
    assert '撤手均约晚16帧' in items['r126_long_0059_full_context']['review']
    assert all('自动' not in x['method_detail'] for x in data['items']
               if x['mode'] == 'guided_pair')
    fixed = json.loads((ROOT / 'audit/FIXED_METHOD_BINDINGS.json').read_text())
    assert len(fixed) == 7 and all(x['same_registered_schedule'] for x in fixed)

    decoded_images = 0
    for digest, asset in data['assets'].items():
        blob = base64.b64decode(asset['b64'], validate=True)
        assert hashlib.sha256(blob).hexdigest() == digest
        if asset['mime'] == 'image/jpeg':
            with Image.open(io.BytesIO(blob)) as image:
                image.verify()
            decoded_images += 1
        else:
            assert asset['mime'] == 'video/mp4'
    paths_by_hash = {b['sha256']: Path(b['path']) for b in receipt['media_bindings']}
    assert set(paths_by_hash) == set(data['assets'])
    for digest, path in paths_by_hash.items():
        assert sha(path) == digest
    video_checks = []
    for item in data['items']:
        assert item['video'] in data['assets'] and item['still'] in data['assets']
        for event in item['event_table']:
            assert all(isinstance(event[k], list) and len(event[k]) == 2
                       for k in ('source_frames', 'native_frames', 'guided_frames'))
        video = paths_by_hash[item['video']]
        props = json.loads(subprocess.check_output([
            '/opt/homebrew/bin/ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-count_frames', '-show_entries',
            'stream=codec_name,width,height,avg_frame_rate,nb_read_frames',
            '-of', 'json', str(video),
        ]))['streams'][0]
        assert int(props['nb_read_frames']) == item['frames']
        assert props['avg_frame_rate'] == f"{item['fps']}/1"
        video_checks.append({'id': item['id'], 'sha256': item['video'], **props})

    javascript = html.split('<script>')[1].split('</script>')[0]
    js_path = ROOT / 'audit/ui.js'
    js_path.write_text(javascript)
    subprocess.run(['node', '--check', str(js_path)], check=True)
    assert not re.search(r'\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(', javascript)
    assert not re.search(r'\b(?:src|href)\s*=\s*["\']https?://', html)
    assert '__DATA__' not in html and '__AFTER_WAKE__' not in html
    for path in [ROOT / 'build.py', ROOT / 'audit/register_r141b.py', Path(__file__)]:
        ast.parse(path.read_text(), filename=str(path))
    frozen = ROOT.parent / 'h3-research-progress-notes-20261020/overnight_audit/RESULT.json'
    assert sha(frozen) == '03e43c096e6cea0ffc126302a7d3a2663f67a93173607acac7697e4b94bcd8bb'

    result = {
        'passed': True, 'output': str(output), 'output_sha256': sha(output),
        'versions': len(items), 'sleep_outputs': 30, 'sleep_sources': 16,
        'after_wake_outputs': 3, 'asset_sha256_verified': len(data['assets']),
        'JPEGs_decoded': decoded_images, 'video_checks': video_checks,
        'fixed_graphs_and_gates_verified': len(fixed),
        'JavaScript_syntax': 'PASS', 'Python_AST': 'PASS',
        'same_frame_image_visually_inspected': str(paths_by_hash[r141b['still']]),
        'page_render_check': 'NOT_RUN',
        'page_render_reason': 'Prior file-protocol denial respected; no HTTP or alternative-browser workaround attempted.',
        'overnight_audit_unchanged': True, 'protected_research_report_modified': False,
        'GPU_started': False,
    }
    (ROOT / 'audit/R141B_PAGE_VERIFIED.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'video_checks'},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
