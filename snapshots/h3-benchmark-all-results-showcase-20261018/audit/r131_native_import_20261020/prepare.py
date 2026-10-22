"""Prepare the reviewed R131 Native-only row; leave inventory unchanged until MF merge."""
from pathlib import Path
import copy
import hashlib
import json
import time

B = Path('/Users/researcher/DevProjects')
R = B / 'h3-benchmark-all-results-showcase-20261018'
A = Path(__file__).parent
C = B / 'h3-ive-prompt-envelope-metrics-r123-20261020/variants/short0177_full_context'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

inventory = R / 'inventory/ivebench.json'
items = read(inventory)['items']
assert not any(row['id'] == 'r131_short_0177_full_context' for row in items)
row = copy.deepcopy(next(row for row in items if row['id'] == 'r128_short_0362_full_context'))
handoff_path = C / 'audit/actual_release/HANDOFF.json'
handoff = read(handoff_path)
assert sha(handoff_path) == 'cff2a8282cc684fd08ad56c83ae7567a7f8a0d659abe81b1fc328ace7f338967'
assert handoff['passed'] and handoff['generated_guidance'] is False
for binding in handoff['records'].values():
    assert sha(binding['file']) == binding['sha256'], binding['file']
show = C / 'showcase/short_0177'
presentation_path = show / 'PRESENTATION.json'
presentation = read(presentation_path)
review_path = C / 'audit/full_frame_review/short_0177/native/INDEPENDENT_REVIEW.json'
review = read(review_path)
assert review['frames_inspected'] == list(range(60)) and review['task_status'] == 'PASS'
assert review['decision'] == 'SKIP_GUIDED'
incoming = C / 'incoming/short_0177'
graph_path = incoming / 'native_graph.json'
history_path = incoming / 'native_history.json'
graph = read(graph_path)
history = read(history_path)
job = read(incoming / 'native_job.json')
prompt = graph['5']['inputs']['prompt']
assert prompt == history['prompt'][2]['5']['inputs']['prompt'] == job['case_binding']['case']['prompt']
assert sha(graph_path) == job['graph_sha256']
assert all(presentation['original_task'][field] in prompt for field in ['source_prompt', 'edit_prompt', 'target_prompt'])
assert read(incoming / 'native_router.json')['routed_calls'] == 0

summary = '老虎替换为狮子，岩石姿态和背景保留；张口、开始闭嘴和闭嘴完成三个阶段与参考接近。普通编辑已同步。'
row.update(
    id='r131_short_0177_full_context', source_id='short_0177',
    variant='R131 · 完整Context-IR · 普通编辑', title='打哈欠 · 老虎替换为狮子',
    task=presentation['original_task']['edit_prompt'], display_task='打哈欠 · 老虎替换为狮子',
    original_task=presentation['original_task'], source_clip=presentation['source_clip'],
    valid_frames=60, generated_frames=73, prompt_version=presentation['prompt_version'],
    review_status=summary, review_summary=summary, display_summary=summary,
    key_same_frame_indices=[35, 51],
    judgment_source='continue_r111_r103 完整60有效帧审阅；依据口部开闭状态记录阶段区间。',
    full_frame_review_path=str(review_path),
    actual_run_id=job['name'],
)
row['event_review'] = {'file': str(review_path), 'sha256': sha(review_path), 'events': review['events'], 'scope': '全部60有效帧；虎与狮的嘴部形态不同，按开闭阶段比较。'}
for key, media in zip(['reference_video_path', 'ordinary_video_path'], presentation['inputs']):
    assert sha(media['file']) == media['sha256']
    row[key] = media['file']
row['comparison_video_path'] = str(show / presentation['videos'][0]['file'])
assert sha(row['comparison_video_path']) == presentation['videos'][0]['sha256']
row['media_sha256'] = {key: sha(row[key]) for key in ['reference_video_path', 'ordinary_video_path', 'comparison_video_path']}
row['prompt'] = prompt
row['prompt_protocol'].update(actual_prompt=prompt, official_edit_prompt=presentation['original_task']['edit_prompt'])
row['actual_prompt_by_column'] = {'ordinary': {
    'text': prompt, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
    'protocol': presentation['prompt_version'], 'exact_official_edit_prompt': False,
    'graph_bindings': [{'graph': str(graph_path), 'graph_sha256': sha(graph_path), 'node_id': '5', 'field': 'inputs.prompt'}],
    'actual_history': str(history_path), 'actual_history_sha256': sha(history_path),
    'scope': '实际图、Comfy history 与 job 文本一致；官方三个字段逐字包含。',
}}
row['execution_seconds'] = {
    'submission_to_observation': job['observed_unix'] - job['submitted_unix'],
    'source': str(incoming / 'native_job.json'),
    'scope': '提交到控制器观察成功的墙钟差，包含观察间隔。',
}
row['quantitative_metrics'] = {'motion_fidelity': {
    'native': None, 'guided': None, 'delta': None, 'status': 'pending',
    'higher_is_better': True, 'protocol': 'IVEBench official MF',
    'valid_frames': 60, 'evaluation_frames': 60, 'evaluation_fps': 24,
}}
evidence = [Path(binding['file']) for binding in handoff['records'].values()]
evidence += [handoff_path, graph_path, history_path, incoming / 'native_job.json', incoming / 'native_router.json', incoming / 'NATIVE_RUNTIME_GATE.json', review_path.parent / 'FRAME_LEDGER.json']
row['evidence_paths'] = list(dict.fromkeys(str(path) for path in evidence))
row['evidence_sha256'] = {path: sha(path) for path in row['evidence_paths']}
(A / 'DRAFT_ROW.json').write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
receipt = {'inventory_unchanged_sha256': sha(inventory), 'draft_row_sha256': sha(A / 'DRAFT_ROW.json'), 'MF': 'pending', 'created_unix': time.time()}
(A / 'PREPARED.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
