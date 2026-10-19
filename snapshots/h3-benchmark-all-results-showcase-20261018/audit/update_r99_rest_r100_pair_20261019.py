from pathlib import Path
import copy
import hashlib
import json
import time

D = Path('/Users/researcher/DevProjects')
ROOT = D / 'h3-benchmark-all-results-showcase-20261018'
INV = ROOT / 'inventory/ivebench.json'
OUT = ROOT / 'audit/r99_rest_r100_pair_20261019'
OUT.mkdir(exist_ok=False)


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


document = read(INV)
previous = sha(INV)
(OUT / 'PREVIOUS_INVENTORY.json').write_bytes(INV.read_bytes())
original_items = copy.deepcopy(document['items'])
C = D / 'h3-ive-p1-guidance-metrics-r99-20261019'
added = []
for source in ['short_0230', 'short_0352']:
    parent = next(x for x in document['items'] if x['id'] == 'r80_' + source)
    exemplar = next(x for x in document['items'] if x['id'] == 'r99_short_0210')
    item = copy.deepcopy(exemplar)
    presentation_file = C / 'showcase' / source / 'PRESENTATION.json'
    presentation = read(presentation_file)
    incoming = C / 'incoming' / source
    gate_file = incoming / 'PAIR_RUNTIME_GATE.json'
    gate = read(gate_file)
    review_file = C / 'audit' / ('agent_full_review_' + source.replace('_', '')) / 'REVIEW.json'
    review = read(review_file)
    assert gate['passed'] and all(gate['checks'].values())
    assert review['all_valid_frames_visually_inspected']
    assert gate['valid_frames'] == presentation['valid_frames']
    item.update(id='r99_' + source, source_id=source, title=parent['title'] + '（修复后的引导对照）',
                task=parent['task'], original_task=parent['original_task'], display_task=parent['display_task'],
                parent_inventory_id=parent['id'], valid_frames=gate['valid_frames'],
                sample_scope='同一原片；普通编辑复用R80实际P1，R99已核验6个条件、原始AV噪声和前6步预测一致后补引导。',
                reference_video_path=str(incoming / 'source.mp4'), ordinary_video_path=str(incoming / 'native.mp4'),
                guided_video_path=str(incoming / 'forced.mp4'), comparison_video_path=str(C / 'showcase' / source / presentation['video']['file']),
                review_summary=review['summary'], review_status_code=review['result'],
                review_status='任务完成，额外指点手势得到抑制' if source == 'short_0352' else '任务完成，引导无明显额外收益',
                support_for_clear_whole_event_repair=False,
                support_for_extra_action_suppression=review['support_for_extra_action_suppression'])
    item['evidence_paths'] = [str(p) for p in [presentation_file, gate_file, incoming / 'COLLECTION.json',
                                             review_file, review_file.with_name('MEDIA_BINDINGS.json'), incoming / 'graph.json']]
    item['evidence_sha256'] = {p: sha(p) for p in item['evidence_paths']}
    item['media_sha256'] = {k: sha(item[k]) for k in ['reference_video_path', 'ordinary_video_path', 'guided_video_path', 'comparison_video_path']}
    item['quantitative_metrics'] = copy.deepcopy(parent['quantitative_metrics'])
    assert not any(x['id'] == item['id'] for x in document['items'])
    document['items'].append(item)
    added.append(item['id'])

C = D / 'h3-ive-task-repair-metrics-r100-20261019'
source = 'short_0114'
item = next(x for x in document['items'] if x['id'] == 'r100_short_0114')
presentation_file = C / 'showcase_pairs' / source / 'PRESENTATION.json'
presentation = read(presentation_file)
gate_file = C / 'incoming_pairs' / source / 'PAIR_RUNTIME_GATE.json'
gate = read(gate_file)
review_file = C / 'audit/root_pair_review_' / source / 'REVIEW.json'
review = read(review_file)
assert gate['passed'] and all(gate['checks'].values()) and review['task_acceptance'] == 'partial'
assert item['media_sha256']['ordinary_video_path'] == presentation['inputs'][1]['sha256']
item.update(variant='R100 / P1-local-v1 / ordinary + fixed / .9',
            ordinary_video_path=presentation['inputs'][1]['file'], guided_video_path=presentation['inputs'][2]['file'],
            comparison_video_path=str(C / 'showcase_pairs' / source / presentation['videos'][0]['file']),
            comparison_kind='guided_pair', column_labels=['1.参考视频', '2.普通编辑', '3.时序引导'],
            method_label='固定时序引导（基础任务修复后的配对）', actual_routed_blocks=450, guidance_activation='active',
            review_summary='全105帧审阅：两版均生成发光球并保留球员与运球；相机俯仰和人物裁切偏差持续存在。前两次可见反弹在引导后约提前1帧，差异较小，后续触地位置在参考画面外，基础任务仍属部分完成。',
            review_status='基础任务部分完成；局部相位变化较小', review_status_code='task_partial_small_phase_change',
            count_as_complete_task_success=False, support_for_clear_whole_event_repair=False)
for p in [presentation_file, gate_file, C / 'incoming_pairs' / source / 'COLLECTION.json', review_file,
          review_file.with_name('FRAME_LEDGER.json')]:
    if str(p) not in item['evidence_paths']:
        item['evidence_paths'].append(str(p))
item['evidence_sha256'] = {p: sha(p) for p in item['evidence_paths']}
item['media_sha256'].update({k: sha(item[k]) for k in ['ordinary_video_path', 'guided_video_path', 'comparison_video_path']})
item['comparison_properties'] = presentation['videos'][0]['properties']
item['quantitative_metrics']['motion_fidelity']['scope'] = '实际配对的正式MF正在补测；相机/构图偏差单独记录。'
item['event_review'] = {'file': str(review_file), 'sha256': sha(review_file), 'events': review['events'],
                      'scope': review['event_intervals_are']}

for before in original_items:
    after = next(x for x in document['items'] if x['id'] == before['id'])
    if before['id'] != 'r100_short_0114':
        assert before == after, 'unrelated inventory entry changed: ' + before['id']
items = document['items']
document['counts'] = {
    'items': len(items), 'unique_sources': len({x['source_id'] for x in items}),
    'guided_pairs': sum(x['comparison_kind'] == 'guided_pair' for x in items),
    'activated_fixed_pairs': sum(x['comparison_kind'] == 'guided_pair' and x.get('guidance_activation') == 'active' for x in items),
    'zero_intervention_pairs': sum(x.get('guidance_activation') == 'zero' for x in items),
    'prompt_controls': sum(x['comparison_kind'] == 'prompt_control' for x in items),
    'native_only': sum(x['comparison_kind'] == 'native_only' for x in items),
    'native_only_skipped_after_review': sum(x['comparison_kind'] == 'native_only' and x.get('screening_decision') == 'skip' for x in items),
}
document['previous_inventory_sha256'] = previous
document['updated_unix'] = time.time()
assert sha(INV) == previous, 'inventory changed concurrently'
INV.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n')
receipt = {'before_sha256': previous, 'after_sha256': sha(INV), 'added': added, 'changed': ['r100_short_0114'],
           'counts': document['counts'], 'all_other_records_preserved': True,
           'R99_0210_single_page_touched': False, 'GPU_started_by_this_import': False}
(OUT / 'RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(receipt, ensure_ascii=False))
