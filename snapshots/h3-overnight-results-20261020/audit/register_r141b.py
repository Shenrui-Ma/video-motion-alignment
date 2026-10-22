"""Append the root-reviewed R141b pair and its two after-wake output receipts."""
import hashlib
import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT.parent
CONSUMER = PROJECTS / 'h3-oxygen-generic-retention-metrics-r141b-host9-20261020'
REVIEW = CONSUMER / 'audit/independent_pair_review'
FORMAL = CONSUMER / 'audit/full_frame_review/short_0252/paired'
INTAKE = CONSUMER / 'incoming_pairs/short_0252'
PRODUCER = PROJECTS / 'h3-timing-oxygen-generic-retention-r141b-host9-20261020'
RELEASE = PRODUCER / 'audit/host9_oxygen_generic_retention_r141b_attempt1'
INVENTORY = PROJECTS / 'h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json'
IDENT = 'r141b_short_0252_seed2026101703_generic_retention'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bound(path):
    return {'file': str(path), 'sha256': sha(path)}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    pending = read(REVIEW / 'PENDING_INVENTORY_ENTRY.json')
    root_review = read(REVIEW / 'ROOT_REVIEW.json')
    completed = read(FORMAL / 'COMPLETED_REVIEW.json')
    result = read(FORMAL / 'REVIEW_RESULT.json')
    gate = read(INTAKE / 'PAIR_RUNTIME_GATE.json')
    release = read(RELEASE / 'ROOT_EXIT_RECEIPT.json')
    complete = read(RELEASE / 'COMPLETE.json')
    assert root_review['root_reviewed'] and root_review['inventory_id'] == IDENT
    assert pending['inventory_id'] == IDENT and pending['inventory_id_confirmed_by_root']
    assert gate['passed'] and all(gate['checks'].values())
    assert complete['passed'] and complete['GPU_released']
    assert release['passed'] and release['process_absent'] and release['CUDA_allocation_absent']
    assert completed['examined_frames'] == list(range(98))
    for value in pending['media'].values():
        assert sha(Path(value['file'])) == value['sha256']

    current_bytes = INVENTORY.read_bytes()
    previous_sha = hashlib.sha256(current_bytes).hexdigest()
    inventory = json.loads(current_bytes)
    original_task = next(x['original_task'] for x in inventory['items']
                         if x['source_id'] == 'short_0252')
    media_names = {'source': 'reference_video_path', 'native': 'ordinary_video_path',
                   'guided': 'guided_video_path', 'comparison': 'comparison_video_path'}
    events = [{
        'name': e['name'], 'source_frames': e['source']['frames'],
        'native_frames': e['native']['frames'], 'guided_frames': e['forced']['frames'],
        'paired_comparison': r['paired_comparison'],
    } for e, r in zip(completed['events'], result['events'])]
    evidence = [
        REVIEW / 'ROOT_REVIEW.json', REVIEW / 'INDEPENDENT_REVIEW.json',
        REVIEW / 'FRAME_LEDGER.json', REVIEW / 'EVENT_DETAIL_INDEX.json',
        FORMAL / 'COMPLETED_REVIEW.json', FORMAL / 'REVIEW_RESULT.json',
        INTAKE / 'PAIR_RUNTIME_GATE.json', INTAKE / 'COLLECTION.json',
        CONSUMER / 'prepared/short_0252/paired/MF_INPUTS.json',
        RELEASE / 'ROOT_EXIT_RECEIPT.json', RELEASE / 'COMPLETE.json',
    ]
    prompt_by_column = {}
    outputs = []
    for arm, column in [('native', 'ordinary'), ('forced', 'guided')]:
        graph_path = INTAKE / f'{arm}_graph.json'
        history_path = INTAKE / f'{arm}_history.json'
        job_path = INTAKE / f'{arm}_job.json'
        graph, history, job = map(read, [graph_path, history_path, job_path])
        assert graph['5']['inputs']['prompt'] == pending['prompt']['text']
        assert graph['6']['inputs']['noise_seed'] == pending['seed']
        router = graph['50']['inputs']
        assert (router['step_start'], router['step_end'], router['alpha']) == (6, 15, 1.0)
        assert (router['block_start'], router['block_end']) == (0, 50)
        assert router['mode'] == ('native' if arm == 'native' else 'mass_preserve')
        prompt_by_column[column] = {
            'text': pending['prompt']['text'], 'prompt_sha256': pending['prompt']['sha256'],
            'protocol': pending['prompt']['version'], 'exact_official_edit_prompt': False,
            'graph_bindings': [{'graph': str(graph_path), 'graph_sha256': sha(graph_path),
                                'node_id': '5', 'field': 'inputs.prompt'}],
            'actual_history': str(history_path), 'actual_history_sha256': sha(history_path),
        }
        evidence.extend([graph_path, history_path, job_path, INTAKE / f'{arm}_router.json'])
        success = [message for name, message in history['status']['messages']
                   if name == 'execution_success']
        assert history['status']['completed'] and job['status'] == 'success' and len(success) == 1
        unix = success[0]['timestamp'] / 1000
        utc = datetime.fromtimestamp(unix, timezone.utc)
        outputs.append({
            'run_id': gate['runs'][arm]['run_id'],
            'generation_identity': {'prompt_id': success[0]['prompt_id'],
                                    'variant_path': str(CONSUMER)},
            'benchmark': 'IVEBench', 'source_id': 'short_0252', 'inventory_id': IDENT,
            'method_role': arm,
            'method_type': 'ordinary_edit' if arm == 'native' else 'fixed_same_bin_guidance',
            'prompt_version': pending['prompt']['version'], 'task': original_task['edit_prompt'],
            'period': 'after_wake',
            'completion': {'unix': unix, 'utc': utc.isoformat(),
                           'cst': utc.astimezone(timezone(timedelta(hours=8))).isoformat()},
            'completion_evidence': {'event': 'Comfy execution_success timestamp',
                                    'history_file': str(history_path),
                                    'history_sha256': sha(history_path), 'job': bound(job_path)},
            'actual_output_names': [Path(gate['runs'][arm]['video']['file']).name],
            'render_success': True, 'task_review_status': 'PASS',
            'task_success_not_implied_by_render_success': True,
        })

    summary = ('两版均完成老妇替换并保留儿童与机舱。固定引导的离腿、握面罩、举带三个事件'
               '落在参考观察窗口内，普通编辑分别延后约 16、14、15 帧（窗口中点）。'
               '静态 4–19 帧未见相对普通版的明显恶化；手指、透明袋和带环仍有局部生成差异。MF 待评分。')
    item = {
        'id': IDENT, 'benchmark': 'IVEBench', 'source_id': 'short_0252',
        'variant': 'R141b · P3 通用保留要求 · 固定引导',
        'title': '机舱面罩：男人替换为年长女人',
        'task': original_task['edit_prompt'], 'display_task': '将男人替换为年长女人。',
        'reference_image_used': False, 'reference_image_path': None,
        **{name: pending['media'][key]['file'] for key, name in media_names.items()},
        'alternative_video_path': None, 'comparison_kind': 'guided_pair',
        'column_labels': ['参考视频', '普通编辑', '固定时序引导'],
        'guidance_activation': 'fixed_active', 'guidance_decision': 'guide',
        'guided_status': 'complete', 'actual_routed_blocks': 450, 'routed_block_calls': 450,
        'method_label': '固定时序引导：去噪步骤 6–14（从 0 开始），α=1，50 个 DiT block。',
        'guidance_steps_zero_based': list(range(6, 15)), 'automatic_guidance': False,
        'valid_frames': 98, 'generated_frames': 107, 'fps': 24, 'seed': pending['seed'],
        'evaluation_crop_xywh': [16, 8, 1280, 720],
        'prompt': pending['prompt']['text'], 'prompt_version': pending['prompt']['version'],
        'original_task': original_task,
        'prompt_protocol': {'kind': 'official_edit_with_generic_retention',
                            'label': 'P3 · 原句 + 输入绑定 + 通用保留要求',
                            'official_edit_prompt': original_task['edit_prompt'],
                            'actual_prompt': pending['prompt']['text'],
                            'official_edit_prompt_preserved_verbatim': True},
        'actual_prompt_by_column': prompt_by_column,
        'review_status': '换人通过；三个事件接近参考窗口',
        'review_status_code': 'PASS_CORE_EDIT',
        'review_summary': summary, 'display_summary': summary,
        'count_as_complete_task_success': True, 'clear_temporal_support': True,
        'action_alignment_bool': True,
        'action_alignment_by_method': {'native': False, 'guided': True},
        'guidance_effect': 'THREE_PREDECLARED_EVENTS_IMPROVED',
        'key_same_frame_indices': [44, 50, 73],
        'full_frame_review_path': str(FORMAL / 'COMPLETED_REVIEW.json'),
        'judgment_source': '独立审阅全部 98 帧，根代理复核关键帧并确认质量。',
        'event_review': {**bound(FORMAL / 'COMPLETED_REVIEW.json'), 'events': completed['events']},
        'quantitative_metrics': {
            'motion_fidelity': {'native': None, 'guided': None, 'delta': None, 'status': 'pending',
                                'higher_is_better': True, 'protocol': 'IVEBench official MF',
                                'valid_frames': 98, 'evaluation_frames': 98, 'evaluation_fps': 24,
                                'source_files': [pending['MF_inputs']['file']],
                                'source_sha256': {pending['MF_inputs']['file']: pending['MF_inputs']['sha256']}},
            'event_timing': {'measurement': '完整 98 帧逐帧审阅与手部边界复核',
                             'fps': 24, 'events': events,
                             'source_file': str(FORMAL / 'REVIEW_RESULT.json'),
                             'source_sha256': sha(FORMAL / 'REVIEW_RESULT.json'),
                             'scope': '三个预定动作的可见转折区间；区间覆盖边界歧义。'},
        },
        'static_pose_review': read(REVIEW / 'INDEPENDENT_REVIEW.json')['static_pose_review'],
        'release_status': 'COMPLETE_EXACT_RELEASE', 'actual_pair_gate_passed': True,
        'media_sha256': {name: pending['media'][key]['sha256'] for key, name in media_names.items()},
        'comparison_properties': {'width': 1920, 'height': 412, 'avg_frame_rate': '24/1',
                                  'nb_read_frames': '98'},
        'evidence_paths': [str(p) for p in evidence],
        'evidence_sha256': {str(p): sha(p) for p in evidence},
        'new_independent_source_count': 0, 'completed_unix': max(o['completion']['unix'] for o in outputs),
    }
    existing = [x for x in inventory['items'] if x['id'] == IDENT]
    if existing:
        assert len(existing) == 1 and existing[0] == item, 'Existing R141b entry differs; do not overwrite'
    else:
        original_items = inventory['items'][:]
        inventory['items'].append(item)
        inventory['counts']['items'] = len(inventory['items'])
        inventory['counts']['guided_pairs'] += 1
        inventory['counts']['activated_fixed_pairs'] += 1
        inventory['updated_unix'] = time.time()
        inventory['previous_inventory_sha256'] = previous_sha
        assert inventory['items'][:-1] == original_items
        assert INVENTORY.read_bytes() == current_bytes, 'Inventory changed concurrently; rerun against latest'
        temp = INVENTORY.with_name('.ivebench.r141b.tmp')
        save(temp, inventory)
        os.replace(temp, INVENTORY)
    extra = {
        'schema': 'overnight-after-wake-extra-v1', 'default_inventory_id': IDENT,
        'successful_outputs': outputs,
        'scope': '醒后新增输出；已封存睡眠审计与 30/16 计数保持不变。',
        'release_evidence': [bound(RELEASE / 'COMPLETE.json'), bound(RELEASE / 'ROOT_EXIT_RECEIPT.json')],
    }
    extra_path = ROOT / 'after_wake_extra.json'
    if extra_path.exists():
        assert read(extra_path) == extra, 'After-wake extras changed; preserve existing entries'
    else:
        save(extra_path, extra)
    save(ROOT / 'audit/R141B_INVENTORY_APPEND.json', {
        'inventory_id': IDENT, 'previous_inventory_sha256': previous_sha,
        'inventory_sha256': sha(INVENTORY), 'added_items': 0 if existing else 1,
        'existing_items_unchanged': True, 'inventory_item_count': len(inventory['items']),
        'new_independent_source_count': 0, 'new_after_wake_outputs': 2,
        'extra': bound(extra_path), 'official_MF': 'PENDING',
    })
    print(json.dumps({'inventory_id': IDENT, 'inventory_items': len(inventory['items']),
                      'after_wake_new_outputs': len(outputs)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
