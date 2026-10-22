from pathlib import Path
import copy
import hashlib
import json
import time

B = Path('/Users/researcher/DevProjects')
R = B / 'h3-benchmark-all-results-showcase-20261018'
A = Path(__file__).parent
H = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
inventory = R / 'inventory/ivebench.json'
data = json.loads(inventory.read_text())
template = next(r for r in data['items'] if r['id'] == 'r128_short_0362_full_context')
specs = [dict(run=136,source='short_0235',stem='otter-color',attempt='root_otter_color_attempt1',id='r136_short_0235_generic_retention',title='海獭改为绿色 · 转头往返',variant='R136 · 原始编辑句与通用保留 · 普通编辑',label='原始edit与H3绑定、通用保留要求',kind='official_edit_with_generic_retention',valid=90,total=90,aligned=True,keys=[15,23],sampling=1333,job=1481,mean=66.69,review_sha='b05035c2b7f52785d6f669ed8450b8301183525b1cdd56281a3f7c0d9d32eb56')]
rows = []
for s in specs:
    c = B / f"h3-ive-{s['stem']}-metrics-r{s['run']}-20261020"
    p = B / f"h3-timing-ive-{s['stem']}-r{s['run']}-20261020"
    src = s['source']
    inc = c / 'incoming' / src
    show = c / 'showcase' / src
    pres = show / 'PRESENTATION.json'
    presentation = json.loads(pres.read_text())
    review = c / 'audit/full_frame_review' / src / 'native/REVIEW.json'
    assert H(review) == s['review_sha']
    reviewed = json.loads(review.read_text())
    assert reviewed['examined_frames'] == list(range(s['valid']))
    assert presentation['timeline']['valid_frames'] == s['valid']
    assert presentation['timeline']['total_frames'] == s['total']
    graph = inc / 'native_graph.json'
    history = inc / 'native_history.json'
    prompt = json.loads(graph.read_text())['5']['inputs']['prompt']
    actual_history = json.loads(history.read_text())
    assert actual_history['prompt'][2]['5']['inputs']['prompt'] == prompt
    assert actual_history['status']['status_str'] == 'success'
    task = presentation['original_task']
    assert task['edit_prompt'] in prompt
    assert task['source_prompt'] not in prompt and task['target_prompt'] not in prompt
    assert json.loads((inc / 'native_router.json').read_text())['routed_calls'] == 0
    decision = p / 'audit/decisions' / (src + '.json')
    decision_data = json.loads(decision.read_text())
    assert 'skip' in decision_data.values(), decision_data
    r = copy.deepcopy(template)
    r.update(id=s['id'], source_id=src, title=s['title'], variant=s['variant'], task=task['edit_prompt'],
             display_task=s['title'], method_label=s['label'], pair_group=presentation['evaluation_scope'],
             valid_frames=s['valid'], generated_frames=s['total'], source_clip=presentation['source_clip'],
             original_task=task, prompt=prompt, prompt_version=presentation['prompt_version'],
             review_status='海獭头部和上胸浅色毛改为黄绿色，水面和漂浮位置保留；侧转14–16帧、回到低头22–24帧与参考重叠，普通版已同步。暗色腹部仍偏深。', review_summary='海獭头部和上胸浅色毛改为黄绿色，水面和漂浮位置保留；侧转14–16帧、回到低头22–24帧与参考重叠，普通版已同步。暗色腹部仍偏深。',
             display_summary='海獭头部和上胸浅色毛改为黄绿色，水面和漂浮位置保留；侧转14–16帧、回到低头22–24帧与参考重叠，普通版已同步。暗色腹部仍偏深。', review_status_code=reviewed['task_acceptance']['native']['status'],
             count_as_complete_task_success=True, clear_temporal_support=False,
             support_for_clear_whole_event_repair=False, action_alignment_bool=s['aligned'],
             action_alignment_by_method={'native': s['aligned'], 'guided': None},
             key_same_frame_indices=s['keys'], judgment_source=f"continue_r90_r104完整{s['valid']}有效帧审阅；root独立抽帧复核。",
             full_frame_review_path=str(review))
    r['event_review'] = {'file': str(review), 'sha256': H(review), 'events': reviewed['events'],
                         'scope': f"全部{s['valid']}有效帧审阅，按源视频预先定义的可见事件记录。"}
    for key, media in zip(['reference_video_path', 'ordinary_video_path'], presentation['inputs']):
        assert H(media['file']) == media['sha256']
        r[key] = media['file']
    r['comparison_video_path'] = str(show / presentation['videos'][0]['file'])
    assert H(r['comparison_video_path']) == presentation['videos'][0]['sha256']
    r['media_sha256'] = {k: H(r[k]) for k in ['reference_video_path', 'ordinary_video_path', 'comparison_video_path']}
    r['prompt_protocol'] = {'kind': s['kind'], 'label': s['label'], 'actual_prompt': prompt,
                            'official_edit_prompt': task['edit_prompt'], 'official_edit_prompt_preserved_verbatim': True}
    r['actual_prompt_by_column'] = {'ordinary': {
        'text': prompt, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
        'protocol': presentation['prompt_version'], 'exact_official_edit_prompt': False,
        'graph_bindings': [{'graph': str(graph), 'graph_sha256': H(graph), 'node_id': '5', 'field': 'inputs.prompt'}],
        'actual_history': str(history), 'actual_history_sha256': H(history),
        'scope': '实际提交图与Comfy history文本一致，官方edit原句逐字保留。'}}
    r['execution_seconds'] = {'native_sampling': s['sampling'], 'native_comfy_job': s['job'],
                              'sampling_steps': 20, 'native_sampling_mean_per_step': s['mean'],
                              'source': str(p / 'audit/ACTUAL_EFFICIENCY_LOG_EXCERPT.json')}
    r['quantitative_metrics'] = {'motion_fidelity': {'native': None, 'guided': None, 'delta': None,
        'status': 'pending', 'higher_is_better': True, 'protocol': 'IVEBench official MF',
        'valid_frames': s['valid'], 'evaluation_frames': s['valid'], 'evaluation_fps': 24}}
    evidence = [pres, review, review.parent / 'FRAME_LEDGER.json', inc / 'NATIVE_RUNTIME_GATE.json',
                inc / 'COLLECTION.json', c / 'prepared' / src / 'native/MF_INPUTS.json', graph, history,
                inc / 'native_job.json', inc / 'native_router.json', decision,
                p / 'audit/SOURCE_EVENTS_BEFORE_OUTPUT.json', p / 'audit/ACTUAL_EFFICIENCY_LOG_EXCERPT.json']
    for name in ['ROOT_EXIT_RECEIPT.json', 'COMPLETE.json']:
        receipt = p / 'audit' / s['attempt'] / name
        assert json.loads(receipt.read_text())['passed']
        evidence.append(receipt)
    if s['run'] == 130:
        evidence += [p / 'audit/ACTUAL_R124_NOISE_REUSE.json', p / 'audit/ACTUAL_GRAPH_DIFF.json']
        r['prompt_ablation_parent'] = 'r124_long_0163_full_context'
        r['causal_scope'] = '同实际AV噪声，仅删除source/target两句叙述；本片基础任务仍失败。'
    r['evidence_paths'] = [str(e) for e in evidence]
    r['evidence_sha256'] = {str(e): H(e) for e in evidence}
    assert r['guided_video_path'] is None and r['guidance_effect'] == 'NOT_RUN'
    rows.append(r)
out = {'created_unix': time.time(), 'inventory_sha256': H(inventory), 'status': 'READY_PENDING_OFFICIAL_MF', 'rows': rows}
(A / 'PREPARED_ROWS.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'rows': [r['id'] for r in rows], 'file': str(A / 'PREPARED_ROWS.json'),
                  'sha256': H(A / 'PREPARED_ROWS.json')}, ensure_ascii=False))
