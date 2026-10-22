from pathlib import Path
import copy
import hashlib
import json

B = Path('/Users/researcher/DevProjects')
R = B / 'h3-benchmark-all-results-showcase-20261018'
C = B / 'h3-ive-reference-origin-metrics-r132-20261020'
P = B / 'h3-timing-ive-reference-origin-r132-20261020'
A = Path(__file__).parent
H = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
inventory = R / 'inventory/ivebench.json'
old = next(x for x in read(inventory)['items'] if x['id'] == 'r122_long_0039_generic_retention')
row = copy.deepcopy(old)
inc = C / 'incoming_exploratory'
review = C / 'audit/full106_exploratory_review/REVIEW.json'
v = read(review)
assert H(review) == 'fa54e682af82b44a5d9e5e30db56c2c80fb26fa7b0b2dd6146c1cd1fa44b99cd'
assert v['all_frames_inspected'] and v['inspected_frame_indices'] == list(range(106))
gate_file = inc / 'REFERENCE_ORIGIN_RUNTIME_GATE.json'
gate = read(gate_file)
assert gate['passed'] is False and gate['checks']['original_input_pixels_tokens_positions_equal_R122'] is False
assert gate['reference_origin']['rotation_calls'] == 450
assert gate['checks']['fixed_reference_origin_execution_counts']
diagnostic = P / 'audit/input_pixel_difference_cpu/SUMMARY.json'
diag = read(diagnostic)
assert diag['native_yuv_frames_and_metadata_all_107_equal'] and diag['each_redecode_matches_actual_hash']

summary = '蓝书修改与办公室场景保留；五个动作事件的区间与普通编辑相同，时序延后保持。跨主机解码得到的RGB值有差异，本轮按探索性参考分支相位对照记录。'
row.update(
    id='r132_long_0039_reference_origin',
    variant='R132 · 参考分支相位引导 · 探索性对照',
    title='办公拿书 · 书本改为蓝色 · 参考分支相位对照',
    comparison_kind='reference_origin_control',
    actual_result_role='reference_origin',
    column_labels=['1.参考视频', '2.普通编辑', '3.参考分支相位引导'],
    guidance_activation='fixed_active', guidance_decision='reference_origin_control',
    guided_status='complete_exploratory',
    actual_routed_blocks=450, routed_block_calls=450,
    method_label='参考分支相位引导',
    exploratory=True, paired_input_exact=False, strict_gate_pass=False,
    count_as_main_method_pair=False,
    review_status=summary, review_summary=summary, display_summary=summary,
    review_status_code='PASS_CORE_EDIT_EXPLORATORY',
    count_as_complete_task_success=True, clear_temporal_support=False,
    support_for_clear_whole_event_repair=False,
    action_alignment_bool=False,
    action_alignment_by_method={'native': False, 'reference_origin': False},
    guidance_effect='NO_CLEAR_BENEFIT',
    key_same_frame_indices=[81, 97],
    judgment_source='continue_metrics 完整106有效帧审阅；输入解码差异保留为探索性条件。',
    full_frame_review_path=str(review),
    release_status='STRICT_GATE_FAILED_OUTPUT_PRESERVED_EXACT_RELEASE',
    execution_seconds={'reference_origin_job_wall_seconds': gate['runs']['reference_origin']['job_wall_seconds']},
)
row['task_acceptance_by_method'] = {'native': 'PASS_CORE_EDIT', 'reference_origin': 'PASS_CORE_EDIT'}
pres_file = C / 'showcase_exploratory/source_native_reference_origin/PRESENTATION.json'
pres = read(pres_file)
for key, media in zip(['reference_video_path', 'ordinary_video_path', 'guided_video_path'], pres['inputs']):
    assert H(media['file']) == media['sha256']
    row[key] = media['file']
row['alternative_video_path'] = None
row['comparison_video_path'] = str(pres_file.parent / pres['videos'][0]['file'])
assert H(row['comparison_video_path']) == pres['videos'][0]['sha256']
row['media_sha256'] = {k: H(row[k]) for k in ['reference_video_path', 'ordinary_video_path', 'guided_video_path', 'comparison_video_path']}
row['event_review'] = {'file': str(review), 'sha256': H(review), 'events': v['events'], 'all_adjacent_phases': v['all_adjacent_phases'], 'scope': '完整106有效帧探索性审阅；当前条件存在跨主机RGB输入差异。'}
row['input_difference_diagnostic'] = {'file': str(diagnostic), 'sha256': H(diagnostic), 'prepared_sample_rms': diag['cross_environment_sample_stats']['actual_prepared_samples']['rms'], 'native_yuv_and_pts_equal': True}

graph_file, hist_file = inc / 'binding_00.json', inc / 'binding_01.json'
graph, hist = read(graph_file), read(hist_file)
prompt = graph['5']['inputs']['prompt']
assert prompt == old['prompt'] == hist['prompt'][2]['5']['inputs']['prompt']
assert H(graph_file) == gate['runs']['reference_origin']['binding_artifacts']['configs/graphs/r132_long_0039_seed2026101701_reference_origin.json']
row['actual_prompt_by_column'] = {
    'ordinary': copy.deepcopy(old['actual_prompt_by_column']['ordinary']),
    'reference_origin': {
        'text': prompt, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
        'protocol': old['prompt_version'], 'exact_official_edit_prompt': False,
        'graph_bindings': [{'graph': str(graph_file), 'graph_sha256': H(graph_file), 'node_id': '5', 'field': 'inputs.prompt'}],
        'actual_history': str(hist_file), 'actual_history_sha256': H(hist_file),
        'scope': '实际提交图与 Comfy history 的文本一致；普通编辑来自R122历史成片。',
    },
}
row['quantitative_metrics'] = {'motion_fidelity': {
    'native': old['quantitative_metrics']['motion_fidelity']['native'],
    'reference_origin': None, 'guided': None, 'delta_reference_origin_minus_native': None,
    'status': 'pending_reference_origin', 'higher_is_better': True,
    'protocol': 'IVEBench official MF', 'valid_frames': 106, 'evaluation_frames': 106,
    'evaluation_fps': 24, 'native_reuse_from_id': old['id'],
}}
alt = C / 'showcase_exploratory/source_fixed_reference_origin/PRESENTATION.json'
row['additional_comparisons'] = [{'roles': ['source', 'fixed', 'reference_origin'], 'presentation_path': str(alt), 'sha256': H(alt), 'scope': 'R122同时间段Value引导与参考分支相位对照；跨主机解码差异保留。'}]
evidence = [review, pres_file, alt, diagnostic, gate_file, inc / 'ROOT_EXIT_RECEIPT.json', inc / 'COLLECTION.json']
handoff = C / 'audit/EXPLORATORY_HANDOFF.json'
assert H(handoff) == 'bb93be335291ed0669a6d1c19e4ce29c3d6d2f78fd8c9222f824a3990f5a1aae'
evidence.append(handoff)
evidence += sorted(inc.glob('binding_*.json'))
evidence += [Path(v[k]['file']) for k in ['frame_ledger', 'event_plan']]
for q in row['actual_prompt_by_column']['ordinary']['graph_bindings']:
    evidence.append(Path(q['graph']))
evidence.append(Path(row['actual_prompt_by_column']['ordinary']['actual_history']))
row['evidence_paths'] = [str(p) for p in evidence]
row['evidence_sha256'] = {str(p): H(p) for p in evidence}
dest = A / 'DRAFT_ROW.json'
dest.write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
receipt = {'draft': str(dest), 'draft_sha256': H(dest), 'inventory_unchanged_sha256': H(inventory), 'strict_gate_pass': False, 'exploratory': True, 'main_pair_excluded': True, 'actual_reference_origin_calls': 450}
(A / 'PREPARED.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(receipt, ensure_ascii=False))
