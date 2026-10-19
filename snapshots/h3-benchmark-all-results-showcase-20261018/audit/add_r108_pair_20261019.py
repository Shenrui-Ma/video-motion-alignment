from pathlib import Path
import copy
import hashlib
import json
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
CONSUMER = ROOT.parent / 'h3-ive-fireplace-recovery-metrics-r108-20261019'
ID = 'r108_short_0392'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
inventory = ROOT / 'inventory/ivebench.json'
before = sha(inventory)
doc = read(inventory)
old = copy.deepcopy(doc['items'])
assert not any(x['id'] == ID for x in old)
assert any(x['id'] == 'r64_short_0392' for x in old)
review_file = CONSUMER / 'audit/root_pair_review/short_0392/REVIEW.json'
presentation_file = CONSUMER / 'showcase_pairs/short_0392/PRESENTATION.json'
collection_file = CONSUMER / 'incoming_pairs/short_0392/COLLECTION.json'
gate_file = CONSUMER / 'incoming_pairs/short_0392/PAIR_RUNTIME_GATE.json'
assert sha(review_file) == '78b67f556a7da41af2ec730111a322b6e68472dd9aa16a354e9d2acdfe7f2698'
review, presentation, collection, gate = map(read, [review_file, presentation_file, collection_file, gate_file])
assert review['reviewed_frame_indices'] == list(range(57))
assert gate['passed'] and all(gate['checks'].values())
assert presentation['gate']['sha256'] == sha(gate_file) == collection['gate_sha256']
assert presentation['collection']['sha256'] == sha(collection_file)
for name, digest in collection['files'].items():
    assert sha(collection_file.parent / name) == digest
for value in presentation['inputs']:
    assert sha(value['file']) == value['sha256']
for index, mode in [(1, 'native'), (2, 'forced')]:
    assert presentation['inputs'][index]['sha256'] == gate['runs'][mode]['video']['sha256']
video = presentation_file.parent / presentation['videos'][0]['file']
assert sha(video) == presentation['videos'][0]['sha256']
properties = json.loads(subprocess.check_output([
    '/opt/homebrew/bin/ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames',
    '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames', '-of', 'json', str(video),
]))['streams'][0]
assert (properties['width'], properties['height'], properties['nb_read_frames'], properties['avg_frame_rate']) == (3840, 808, '57', '24/1')
contract_file = CONSUMER / 'configs/contract.json'
contract = read(contract_file)
case = contract['sources'][0]
assert case['source_id'] == 'short_0392'
evidence = [contract_file, review_file, presentation_file, collection_file, gate_file,
            CONSUMER / 'audit/root_pair_review/short_0392/FRAME_LEDGER.json',
            CONSUMER / 'inputs/short_0392_provenance.json']
html = Path('/Users/researcher/Downloads/H3_R108_short_0392_固定时序引导对照_20261019.html')
assert html.is_file()
row = {
    'id': ID, 'parent_record_id': 'r64_short_0392', 'benchmark': 'IVEBench', 'source_id': 'short_0392',
    'variant': 'R108 / P1-local-v1 / matched fixed guidance',
    'title': '手势：移除雕花壁炉 · 修复后配对',
    'task': case['original_task']['edit_prompt'], 'display_task': case['display_task'],
    'reference_image_used': False, 'reference_image_path': None,
    'reference_video_path': presentation['inputs'][0]['file'],
    'ordinary_video_path': presentation['inputs'][1]['file'],
    'guided_video_path': presentation['inputs'][2]['file'],
    'comparison_video_path': str(video), 'alternative_video_path': None, 'preview_html': str(html),
    'review_status': '壁炉移除完成；普通编辑已近同步',
    'review_status_code': 'task_pass_no_clear_timing_gain',
    'review_summary': review['conclusion'],
    'display_summary': '两版均移除雕饰壁炉、台面和立柱，保留人物、白色服饰与原房间构图。普通编辑的手部节奏已接近参考，引导后未观察到额外清楚收益。',
    'valid_frames': 57, 'generated_frames': 73, 'fps': 24,
    'method_label': contract['method'], 'comparison_kind': 'guided_pair',
    'column_labels': ['1.参考视频', '2.普通编辑', '3.固定时序引导'],
    'original_task': case['original_task'], 'prompt': case['prompt'], 'prompt_version': case['prompt_version'],
    'actual_routed_blocks': gate['runs']['forced']['routed_blocks'], 'guidance_activation': 'active',
    'screening_decision': 'guided_completed', 'count_as_basic_edit_success': True,
    'count_as_complete_task_success': True, 'clear_temporal_support': False,
    'temporal_result': 'already-aligned-preservation-control',
    'comparison_properties': properties,
    'event_review': {'file': str(review_file), 'sha256': sha(review_file), 'motion_review': review['motion_review'],
                     'scope': review['measurement_scope']},
    'quantitative_metrics': {'motion_fidelity': {'native': None, 'guided': None, 'delta': None,
        'higher_is_better': True, 'status': 'pending', 'valid_frames': 57,
        'scope': '本次真实配对待官方IVEBench MF评测；原R64分数保留于历史行。'}},
    'efficiency': {'native_job_wall_seconds': gate['runs']['native']['job_wall_seconds'],
                   'guided_job_wall_seconds': gate['runs']['forced']['job_wall_seconds'],
                   'native_capture_seconds': gate['runs']['native']['capture_seconds'],
                   'guided_capture_seconds': gate['runs']['forced']['capture_seconds'], 'NFE_per_arm': 20},
    'evidence_paths': [str(x) for x in evidence], 'evidence_sha256': {str(x): sha(x) for x in evidence},
}
row['media_sha256'] = {key: sha(row[key]) for key in ['reference_video_path', 'ordinary_video_path', 'guided_video_path', 'comparison_video_path']}
doc['items'].append(row)
assert doc['items'][:-1] == old
items = doc['items']
doc['counts'] = {
    'items': len(items), 'unique_sources': len({x['source_id'] for x in items}),
    'guided_pairs': sum(x['comparison_kind'] == 'guided_pair' for x in items),
    'activated_fixed_pairs': sum(x['comparison_kind'] == 'guided_pair' and x.get('guidance_activation') == 'active' for x in items),
    'zero_intervention_pairs': sum(x.get('guidance_activation') == 'zero' for x in items),
    'prompt_controls': sum(x['comparison_kind'] == 'prompt_control' for x in items),
    'native_only': sum(x['comparison_kind'] == 'native_only' for x in items),
    'native_only_skipped_after_review': sum(x['comparison_kind'] == 'native_only' and x.get('screening_decision') == 'skip' for x in items),
}
doc['previous_inventory_sha256'] = before
doc['updated_unix'] = time.time()
assert sha(inventory) == before
audit = ROOT / 'audit/r108_pair_20261019'
audit.mkdir(exist_ok=False)
(audit / 'PREVIOUS_INVENTORY.json').write_bytes(inventory.read_bytes())
temporary = inventory.with_suffix('.tmp')
temporary.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
temporary.replace(inventory)
receipt = {'before_sha256': before, 'after_sha256': sha(inventory), 'added': ID,
           'other_rows_unchanged': True, 'counts': doc['counts']}
(audit / 'RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
