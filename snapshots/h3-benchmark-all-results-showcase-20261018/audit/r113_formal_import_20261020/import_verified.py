from pathlib import Path
import copy
import hashlib
import json
import os
import time

P = Path('/Users/researcher/DevProjects')
SHOW = P / 'h3-benchmark-all-results-showcase-20261018'
CONSUMER = P / 'h3-oxygen-seed-replication-metrics-r113-host41-20261019'
OUT = Path(__file__).parent

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def verify(record):
    assert sha(record['file']) == record['sha256'], record['file']
    return Path(record['file'])

proof_path = CONSUMER / 'audit/FULL98_REVIEW_VERIFIED.json'
proof = read(proof_path)
assert proof['passed'] and proof['all_four_actual'] and proof['source_count'] == 1
for section in ['reviews', 'presentations']:
    for record in proof[section].values():
        verify(record)
aggregate_path = verify(proof['formal_batch'])
release_path = verify(proof['release'])
assert read(aggregate_path)['passed'] and read(release_path)['passed']

mf_path = P / 'h3-ive-r113-seed-replication-mf-host41-20261020/audit/RESULTS_VERIFIED.json'
assert sha(mf_path) == '3ccd19e66b3942b3073b156978ccef3d1291d60842222f634f1ec4ab31e44032'
mf = read(mf_path)
assert mf['completed_targets'] == mf['requested_targets'] == 4
draft = read(SHOW / 'audit/r113_pending_inventory/seed2026101702_DRAFT.json')
new_rows = []
for seed in [2026101702, 2026101703]:
    ss = str(seed)
    review_path = Path(proof['reviews'][ss]['file'])
    presentation_path = Path(proof['presentations'][ss]['file'])
    review = read(review_path)
    presentation = read(presentation_path)
    assert review['all_valid_frames_inspected']
    assert review.get('frames_reviewed', review.get('examined_frames')) == list(range(98))
    assert presentation['valid_frames'] == 98 and presentation['fps'] == 24
    gate_path = CONSUMER / f'incoming/actual/seed{seed}_PAIR_GATE.json'
    gate = read(gate_path)
    assert gate['passed'] and gate['seed'] == seed
    assert gate['runs']['native']['routed_blocks'] == 0
    assert gate['runs']['fixed']['routed_blocks'] == 450
    r = copy.deepcopy(draft)
    r.update(id=f'r113_short_0252_seed{seed}_fixed', seed=seed,
             variant=f'R113 / seed{seed} / .41',
             method_label='固定时序引导（第7–15步）',
             release_status='COMPLETE_EXACT_RELEASED', formal_batch_gate_pending=False,
             full_frame_review_path=str(review_path),
             review_attribution=review['reviewer'], review_summary=review['summary'],
             events=review['events'], guidance_effect=review['conclusion'],
             action_alignment_bool={'native': review['alignment']['native'],
                                    'guided': review['alignment']['fixed']},
             alignment_scope=review['alignment'].get('scope', '三项预登记可见事件及全片动作顺序'),
             key_same_frame_indices=[review['suggested_still_frame'], review['suggested_secondary_frame']])
    r['review_status'] = ('前两项动作时刻改善，第三阶段仍延后' if seed == 2026101702
                          else '三项预登记动作时刻均回到参考区间')
    r['review_status_code'] = review['conclusion'].lower()
    r['whole_sequence_alignment_established'] = bool(review['alignment']['fixed'])
    r['whole_sequence_alignment_scope'] = '三项预登记可见事件与粗动作顺序；不代表每一手形与轨迹逐帧相同。'
    r['terminal_pose'] = review.get('terminal_pose', review.get('terminal_pose_presence'))
    r['supports_timing_improvement'] = True
    r['media_sha256'] = {}
    for role, field in [('source', 'reference_video_path'), ('native', 'ordinary_video_path'),
                        ('fixed', 'guided_video_path')]:
        record = presentation['inputs'][role]
        r[field] = str(verify(record))
        r['media_sha256'][field] = record['sha256']
        if role != 'source':
            assert record['sha256'] == gate['runs'][role]['video']['sha256']
    r['comparison_video_path'] = str(verify(presentation['video']))
    r['media_sha256']['comparison_video_path'] = presentation['video']['sha256']
    evidence = {proof_path, aggregate_path, release_path, review_path, presentation_path,
                gate_path, mf_path}
    for record in review.get('evidence', {}).values():
        if isinstance(record, dict) and 'file' in record and 'sha256' in record:
            evidence.add(verify(record))
    r['actual_prompt_by_column'] = {}
    for role, column in [('native', 'ordinary'), ('fixed', 'guided')]:
        run = gate['runs'][role]['run_id']
        graph_path = CONSUMER / f'incoming/actual/{run}_graph.json'
        history_path = CONSUMER / f'incoming/actual/{run}_history.json'
        job_path = CONSUMER / f'incoming/actual/{run}_job.json'
        graph, history, job = read(graph_path), read(history_path), read(job_path)
        assert graph == history['prompt'][2]
        assert sha(graph_path) == job['graph_sha256']
        assert history['prompt'][1] == job['prompt_id']
        assert history['status']['completed'] and history['status']['status_str'] == 'success'
        nodes = [(k, v['inputs']['prompt']) for k, v in graph.items()
                 if isinstance(v.get('inputs', {}).get('prompt'), str)]
        assert len(nodes) == 1 and nodes[0][1] == r['prompt']
        r['actual_prompt_by_column'][column] = {
            'text': r['prompt'], 'prompt_sha256': hashlib.sha256(r['prompt'].encode()).hexdigest(),
            'protocol': 'structured_adaptation', 'exact_official_edit_prompt': False,
            'graph_bindings': [{'graph': str(graph_path), 'graph_sha256': sha(graph_path),
                                'node_id': nodes[0][0], 'field': 'inputs.prompt'}],
            'actual_history': str(history_path), 'actual_history_sha256': sha(history_path),
            'run_id': run, 'scope': f'Actual {column} column; graph equals successful history.'}
        evidence.update([graph_path, history_path, job_path])
    values = {}
    score_files = [str(mf_path)]
    for result in mf['results']:
        targets = [b for b in result['inventory_bindings'] if b['id'] == r['id']]
        if not targets:
            continue
        assert len(targets) == 1 and result['valid_frames'] == 98 and result['evaluation_fps'] == 24
        field = targets[0]['field']
        media_field = 'ordinary_video_path' if field == 'native' else 'guided_video_path'
        assert result['actual_generated_video_sha256'] == r['media_sha256'][media_field]
        for name in ['result', 'release']:
            path = Path(result[name + '_file'])
            assert sha(path) == result[name + '_sha256']
            evidence.add(path)
            score_files.append(str(path))
        values[field] = result['score']
    assert set(values) == {'native', 'guided'}
    r['quantitative_metrics']['motion_fidelity'] = dict(
        values, delta=values['guided']-values['native'], status='complete', higher_is_better=True,
        valid_frames=98, fps=24, implementation='IVEBench official Motion Fidelity',
        source_files=score_files, evidence_sha256=sha(mf_path))
    r['evidence_paths'] = sorted(str(p) for p in evidence)
    r['evidence_sha256'] = {str(p): sha(p) for p in sorted(evidence)}
    new_rows.append(r)

path = SHOW / 'inventory/ivebench.json'
before_bytes = path.read_bytes()
before = json.loads(before_bytes)
assert sha(path) == '4c5d90e470014c794892397c8f6152a487feb828d0f2883f9a74ec56bb6743d2'
ids = {r['id'] for r in before['items']}
assert all(r['id'] not in ids for r in new_rows)
after = copy.deepcopy(before)
after['items'].extend(new_rows)
assert after['items'][:-2] == before['items']
after['counts'].update(items=54, guided_pairs=41, activated_fixed_pairs=36)
after['updated_unix'] = time.time()
after['previous_inventory_sha256'] = hashlib.sha256(before_bytes).hexdigest()
(OUT / 'ivebench_before.json').write_bytes(before_bytes)
(OUT / 'ADDED_ROWS.json').write_text(json.dumps(new_rows, ensure_ascii=False, indent=2) + '\n')
temp = path.with_suffix('.json.tmp')
temp.write_text(json.dumps(after, ensure_ascii=False, indent=2) + '\n')
os.replace(temp, path)
receipt = {'created_unix': time.time(), 'before_sha256': hashlib.sha256(before_bytes).hexdigest(),
           'after_sha256': sha(path), 'added_ids': [r['id'] for r in new_rows],
           'old_records_unchanged': True, 'IVE_records': len(after['items']),
           'independent_IVE_sources': len({r['source_id'] for r in after['items']}),
           'formal_proof_sha256': sha(proof_path), 'mf_proof_sha256': sha(mf_path)}
(OUT / 'RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(receipt, ensure_ascii=False))
