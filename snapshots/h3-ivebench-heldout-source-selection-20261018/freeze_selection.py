"""Freeze source-only selection and full-clip physical frame mapping before H3."""
import datetime
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

B = Path(__file__).resolve().parent
P = Path('/Users/researcher/DevProjects/h3-ivebench-pilot-20261017/inputs_selection')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(name, value):
    p = B / name
    if p.exists():
        raise FileExistsError(p)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

selection = json.loads((B / 'PROPOSED_SOURCE_ONLY_FIVE.json').read_text())
probes = {Path(x['file']).name: x for x in json.loads((B / 'SOURCE_TIMEBASE.json').read_text())}
receipts = {Path(x['file']).name: x for x in json.loads((B / 'DOWNLOAD_RECEIPTS.json').read_text())}
origins = {x['order_name']: x for x in json.loads((B / 'OFFICIAL_PROVENANCE_ROWS.json').read_text())}
streams = {x['src_video_name']: x for x in json.loads((B / 'ORIGINAL_AV_STREAMS.json').read_text())}
official = {x['src_video_name']: x for x in json.loads((P / 'ALL_600_TASKS.json').read_text())}
notes = {
    'short_0092': ('挥手多次后手移到胸前，动作状态转换清楚。', '后半前景摄像机逐渐遮挡目标；该段可观测性须保留为未知，不能把遮挡视为动作遗漏。', 'mixed waving and hand-to-chest transition'),
    'short_0114': ('连续运球，并有换手和侧向重心变化；多次事件适合检验动作保持。', '前段头肩部分出框，周期运动的相似姿态可能产生多解时延；评测应同时观察球与手的事件顺序。', 'repeated dribbling with hand switching'),
    'short_0126': ('双臂从胸前/头侧逐渐抬至头顶，再保持伸展；完整上肢清晰。', '后半基本保持伸展，属于单次可见转变控制，不称为密集动作；人物背面不妨碍人工分辨抬臂。', 'single arm-raise transition then hold'),
    'short_0392': ('朝镜头反复前伸、回收手并改变手势，变化在短片中多次出现。', '中近景另一侧手臂较少出现，手伸向镜头有透视缩短，低照度；单侧足够支持人工事件检查，pose是否可靠待实际测量。', 'repeated forward hand gestures'),
}
rows = []
review = []
for proposed in selection['pairs']:
    name = proposed['src_video_name']; ident = Path(name).stem
    task = official[name]
    assert all(proposed[k] == v for k, v in task.items())
    probe = probes[name]; receipt = receipts[name]
    assert sha(Path(receipt['file'])) == receipt['sha256'] == probe['sha256']
    if ident == 'short_0186':
        review.append({'pair_id': ident, 'decision': 'SOURCE_ONLY_EXCLUDED', 'reason': '官方caption写dancing，但12个跨全片源帧显示双手基本持续贴耳机，主要头肩轻摆；肘出框，没有明显动作切换。', 'source_video': receipt, 'contact_sheet': probe['contact_sheet'], 'contact_sheet_sha256': probe['contact_sheet_sha256'], 'h3_output_used': False})
        continue
    reason, risk, pattern = notes[ident]
    n = probe['decoded_frames']; fps = Fraction(probe['avg_frame_rate'])
    exact = [Fraction(i, 1) / fps for i in range(n)]
    assert all(abs(float(t) - actual) < 1e-6 for t, actual in zip(exact, probe['pts_s']))
    count = math.ceil(exact[-1] * 24) + 1
    legal = math.ceil(Fraction(count - 5, 17)) * 17 + 5
    mapping = [min(range(n), key=lambda i: (abs(exact[i] - Fraction(t, 24)), i)) for t in range(count)]
    full = mapping + [n - 1] * (legal - count)
    assert mapping[-1] == n - 1 and legal >= count and (legal - 5) % 17 == 0
    row = {**task, 'pair_id': ident, 'source': {'file': receipt['file'], 'sha256': receipt['sha256'], 'bytes': receipt['bytes'], 'hf_url': receipt['url'], 'origin_mapping_row': origins[ident], 'width': probe['width'], 'height': probe['height'], 'fps_rational': str(fps), 'frame_count': n, 'actual_pts_s': probe['pts_s'], 'av_streams': streams[name]}, 'selection_reason': reason, 'measurement_risks': risk, 'motion_pattern': pattern, 'visual_review': {'kind': '12 uniformly spaced source frames only', 'frame_indices': probe['contact_sheet_indices'], 'file': probe['contact_sheet'], 'sha256': probe['contact_sheet_sha256'], 'h3_output_seen_for_selection': False}, 'input_protocol': {'fps': 24, 'effective_frame_count': count, 'h3_frame_count': legal, 'input_to_original_frame': full, 'effective_input_to_original_frame': mapping, 'effective_frame_indices': list(range(count)), 'effective_pts_s': [t / 24 for t in range(count)], 'terminal_padding_count': legal - count, 'last_original_frame_retained': True, 'unique_original_frames_used': len(set(mapping)), 'original_frames_not_sampled': [i for i in range(n) if i not in mapping], 'max_nearest_source_pts_distance_s': max(float(abs(exact[i] - Fraction(t, 24))) for t, i in enumerate(mapping)), 'rule': 'N=ceil(last original rational PTS*24)+1; nearest original PTS for each t/24, ties earlier; repeat final frame to minimum T=17k+5; exclude padded indices from evaluation.', 'coordinate_scope': 'Full official source retained in physical time; no selected event crop, no temporal interpolation. All arms receive identical prepared bytes. The final resampling tick can lie less than 1/24s after the original last PTS.'}, 'conditioning': {'reference_images': [], 'reference_video_count': 1, 'instruction': task['edit_prompt'], 'instruction_source': 'verbatim official edit_prompt (P0); source/target captions retained only as metadata', 'prepared_audio': 'video-only MP4, exactly as frozen R54 prepare_inputs -an; original archive retained with original audio/data streams'}, 'status': 'source/task/physical mapping frozen before new H3 outputs'}
    rows.append(row)
    review.append({'pair_id': ident, 'decision': 'SELECTED_GENERAL_EDITING_EXTENSION', 'reason': reason, 'risk': risk, 'h3_output_used': False})
assert [x['pair_id'] for x in rows] == ['short_0092', 'short_0114', 'short_0126', 'short_0392']
assert [x['input_protocol']['h3_frame_count'] for x in rows] == [73,107,124,73]
manifest = {'schema': 'ivebench-source-only-extension-v1', 'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'official_repository_commit': '2dcf8900ee65197f43854c76f61c66a32bb8dbfc', 'official_dataset_revision': selection['original_dataset_revision'], 'selection_type': 'purposive source-only general editing extension, held out from preceding H3 result examination; not random or full official benchmark', 'scope': 'Preserve human movement while editing an object or background. These four differ from the preceding five person/clothing editing tasks; report groups separately.', 'excluded_original_h3_sources': selection['excluded_previous_h3_case_ids'], 'denominators': {'official_tasks': 600, 'source_review_candidates': 5, 'source_only_excluded': 1, 'fixed_selected_tasks': 4, 'new_h3_outputs_examined': 0}, 'geometry': {'canvas': [1312,736], 'content_rectangle_xywh': [16,8,1280,720], 'transform': 'isotropic 16:9 source downscale to1280x720 with lanczos, black pad16 horizontally and8 vertically, SAR1; exact explicit temporal frame map; lossless yuv420p libx264 crf0', 'evaluation': 'crop fixed padding, compare same physical valid prefix; no result-selected person crop'}, 'future_evaluation': 'Retain all four task denominators, including editing failures, unchanged outputs and unobservable pose. Report editing success/content preservation separately from timing or official motion fidelity. This freezes sources, not an unmeasured guarantee of detector availability or method improvement.', 'pairs': rows}
write('SELECTED_4_MANIFEST.json', manifest)
write('SOURCE_REVIEW_DECISIONS.json', review)
paths = [B / x for x in ['SELECTED_4_MANIFEST.json','SOURCE_REVIEW_DECISIONS.json','PROPOSED_SOURCE_ONLY_FIVE.json','STRICT_TASK_SCOPE_AUDIT.json','OFFICIAL_LFS_INFO.json','OFFICIAL_PROVENANCE_ROWS.json','ORIGINAL_AV_STREAMS.json','DOWNLOAD_RECEIPTS.json','SOURCE_TIMEBASE.json','SCOPE_DECISION.json','freeze_selection.py']]
paths += [Path(x['source']['file']) for x in rows] + [Path(x['visual_review']['file']) for x in rows]
write('SELECTION_FREEZE.json', {'files': [{'file': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in paths]})
print('selection sha', sha(B / 'SELECTED_4_MANIFEST.json'))
print([(r['pair_id'],r['input_protocol']['effective_frame_count'],r['input_protocol']['h3_frame_count']) for r in rows])
