from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import time

args = argparse.ArgumentParser()
args.add_argument('--proof', required=True)
args.add_argument('--proof-sha', required=True)
args.add_argument('--release-sha', required=True)
args = args.parse_args()
A = Path(__file__).parent
R = A.parents[1]
H = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
inventory = R / 'inventory/ivebench.json'
before = H(inventory)
assert before == '33c11bea93bead55c1983c253ec4be4b13130c29333250d1f3e68147d47dfd39'
data = read(inventory)
drafts = [R / 'audit' / folder / 'DRAFT_ROW.json' for folder in ['r126_import_20261020', 'r131_native_import_20261020', 'r132_import_20261020']]
rows = [read(p) for p in drafts]
by_id = {r['id']: r for r in rows}
proof = Path(args.proof)
release = proof.parent / 'FINAL_RELEASE_VERIFIED.json'
assert H(proof) == args.proof_sha and H(release) == args.release_sha
verified = read(proof)
assert verified['completed_targets'] == verified['requested_targets'] == 4
qualified_file = proof.parent / 'QUALIFIED_RESULTS.json'
assert H(qualified_file) == '867bca098ac1493f1b4ec544bbf24bd442e4ed12fe80e5442ae7885123639907'
qualified = read(qualified_file)
assert qualified['passed'] and qualified['official_results']['sha256'] == H(proof)
qualified_r132 = next(x for x in qualified['results'] if x['role'] == 'reference_origin')
assert qualified_r132['exploratory'] and not qualified_r132['paired_input_exact'] and not qualified_r132['strict_gate_pass']
seen = set()
for score in verified['results']:
    for binding in score['inventory_bindings']:
        row = by_id[binding['id']]
        field = binding['field']
        assert (row['id'], field) not in seen
        seen.add((row['id'], field))
        media_key = {'native': 'ordinary_video_path', 'guided': 'guided_video_path', 'reference_origin': 'guided_video_path'}[field]
        assert row['media_sha256'][media_key] == score['actual_generated_video_sha256']
        assert H(row[media_key]) == score['actual_generated_video_sha256']
        assert score['valid_frames'] == score['evaluation_frames'] == row['valid_frames']
        assert score['evaluation_fps'] == row['fps'] == 24
        assert math.isfinite(score['score'])
        for name in ['result', 'release']:
            assert H(score[name + '_file']) == score[name + '_sha256']
        metric = row['quantitative_metrics']['motion_fidelity']
        metric[field] = score['score']
        metric.setdefault('source_files', []).extend([str(proof), str(qualified_file), str(release), score['result_file'], score['release_file']])
assert seen == {
    ('r126_long_0059_full_context', 'native'),
    ('r126_long_0059_full_context', 'guided'),
    ('r131_short_0177_full_context', 'native'),
    ('r132_long_0039_reference_origin', 'reference_origin'),
}
for row in rows:
    metric = row['quantitative_metrics']['motion_fidelity']
    metric['status'] = 'complete'
    metric['scope'] = '官方IVEBench MF；任务验收与逐帧事件时刻分别记录。'
    kind = row['comparison_kind']
    if kind == 'guided_pair':
        metric['delta'] = metric['guided'] - metric['native']
    elif kind == 'reference_origin_control':
        assert metric['guided'] is None and row['actual_routed_blocks'] == 450
        assert row['exploratory'] and not row['paired_input_exact'] and not row['strict_gate_pass']
        old = next(x for x in data['items'] if x['id'] == 'r122_long_0039_generic_retention')
        assert old['media_sha256']['ordinary_video_path'] == row['media_sha256']['ordinary_video_path']
        assert old['quantitative_metrics']['motion_fidelity']['native'] == metric['native']
        metric['delta_reference_origin_minus_native'] = metric['reference_origin'] - metric['native']
        metric['scope'] += '参考分支相位对照存在跨主机RGB输入差异，按探索性结果展示。'
        metric['source_files'].extend(old['quantitative_metrics']['motion_fidelity']['source_files'])
    else:
        assert kind == 'native_only' and row['guided_video_path'] is None
        assert metric.get('guided') is None
    metric['source_files'] = list(dict.fromkeys(metric['source_files']))
    metric['source_sha256'] = {p: H(p) for p in metric['source_files']}
    row['evidence_paths'] = list(dict.fromkeys(row['evidence_paths'] + metric['source_files']))
    for p, expected in row['evidence_sha256'].items():
        assert H(p) == expected, p
    row['evidence_sha256'] = {p: H(p) for p in row['evidence_paths']}
    assert not any(x['id'] == row['id'] for x in data['items'])
    data['items'].append(row)
data['updated_unix'] = time.time()
items = data['items']
data['counts'].update(
    items=len(items), unique_sources=len({x['source_id'] for x in items}),
    guided_pairs=sum(x.get('comparison_kind') == 'guided_pair' for x in items),
    activated_fixed_pairs=sum(x.get('comparison_kind') == 'guided_pair' and (x.get('actual_routed_blocks') or x.get('routed_block_calls') or 0) > 0 for x in items),
    native_only=sum(x.get('comparison_kind') == 'native_only' for x in items),
    native_only_skipped_after_review=sum(x.get('comparison_kind') == 'native_only' and x.get('guidance_decision') == 'skip' for x in items),
    positional_controls=sum(x.get('comparison_kind') == 'positional_control' for x in items),
    reference_origin_controls=sum(x.get('comparison_kind') == 'reference_origin_control' for x in items),
)
assert len(items) == 73 and H(inventory) == before
(A / 'ivebench_before.json').write_bytes(inventory.read_bytes())
tmp = inventory.with_suffix('.tmp')
tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
os.replace(tmp, inventory)
receipt = {'created_unix': time.time(), 'before_sha256': before, 'after_sha256': H(inventory), 'added': list(by_id), 'proof': str(proof), 'proof_sha256': H(proof), 'release_sha256': H(release), 'drafts': {str(p): H(p) for p in drafts}, 'ive_counts': data['counts']}
(A / 'RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(receipt, ensure_ascii=False, indent=2))
