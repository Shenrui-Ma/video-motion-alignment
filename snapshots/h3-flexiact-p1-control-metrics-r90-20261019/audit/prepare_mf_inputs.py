"""Bind actual P0/P1 media and physical sample times for later official scoring."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import bound, require, save, validate_static, verify_intake
from render import check_time, media_info

c = validate_static()
g = verify_intake()
official = ROOT.parent / 'h3-flexiact-expanded-metrics-r85-20261018/inputs/source_one_leg_original.mp4'
require(bound(official)['sha256'] == 'c32897aadc26fff8c251aa269dbbd701e741404a7f84b978ebcfed68f32c549c', 'Original benchmark reference differs')
official_info = media_info(official, '/opt/homebrew/bin/ffprobe')
require((official_info['width'], official_info['height'], official_info['count'], official_info['avg_frame_rate']) == (720,480,49,'8/1'), 'Original benchmark geometry differs')
require(all(abs(t-i/8)<1e-6 for i,t in enumerate(official_info['pts_s'])), 'Original benchmark timestamps differ')
media = {
    'source': Path(c['media']['source']['file']),
    'old_native': Path(c['media']['old_native']['file']),
    'new_native': ROOT / 'incoming/native.mp4',
}
properties = {}
for role, path in media.items():
    properties[role] = media_info(path, '/opt/homebrew/bin/ffprobe')
    check_time(properties[role], 158, 1152, 768)
indices = list(range(0, 147, 3))
require(indices == c['original_indices'] and len(indices) == 49, 'Evaluation indices differ')
value = {
    'schema': 'r90-official-mf-ready-inputs-v2',
    'source_id': c['source_id'],
    'comparison_kind': 'prompt_control',
    'status': 'inputs_ready_score_pending',
    'protocol': 'FlexiAct official MF; bind exact evaluator, checkpoint and runtime at scoring',
    'fps': 24, 'valid_frames': 147, 'total_frames': 158,
    'evaluate_indices': indices, 'evaluation_fps': 8,
    'crop_xywh': [0, 0, 1152, 768],
    'raw_videos': {role: bound(path) for role, path in media.items()},
    'official_reference': {**bound(official), 'evaluate_indices':list(range(49)), 'fps':8, 'properties':official_info},
    'reference_input_policy': 'Official MF uses official_reference original 49-frame 8fps benchmark video. raw_videos.source binds inference/display preparation only. P0/P1 sample indices remain 0,3,...144.',
    'media_properties': properties,
    'reference_image_used': True,
    'reference_image': bound(c['media']['target']['file']),
    'scope': '49 fixed source instants, 0,3,...144 in 24fps media; no time alignment. P0 and P1 are ordinary edits with zero guidance. Basic editing acceptance and event timing are recorded separately.',
    'gate': bound(ROOT / 'incoming/NATIVE_RUNTIME_GATE.json'),
    'collection': bound(ROOT / 'incoming/COLLECTION.json'),
    'review': bound(ROOT / 'audit/full147_review/REVIEW.json'),
    'score': None, 'GPU_started': False,
}
dest = ROOT / 'prepared' / c['source_id'] / 'MF_INPUTS.json'
if dest.exists():
    previous = json.loads(dest.read_text())
    if previous.get('schema') == 'r90-official-mf-ready-inputs-v1':
        backup = dest.with_name('MF_INPUTS_v1_processed_source.json')
        require(not backup.exists(), 'Original reference correction backup already exists')
        backup.write_bytes(dest.read_bytes())
        dest.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    else:
        require(previous == value, 'Existing input binding changed')
else:
    save(dest, value)
print(json.dumps(bound(dest)))
