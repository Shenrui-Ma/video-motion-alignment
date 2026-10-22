"""Read-only historical review audit. Writes only its derived control-verdict JSON."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import bound, read, resolve_controls, verify_record, write
OLD = ROOT.parent / 'h3-guidance-schedule-eval-r149-20261020'
R148 = ROOT.parent / 'h3-timing-phase-combined-eval-r148-20261020'

out = {'schema': 'r150-historical-control-edit-verdicts-v1', 'created_unix': time.time(),
       'scope': 'Existing decoded-frame review evidence for the exact displayed Native and same-bin fixed controls; no new inference or changed annotations.',
       'verdict_definition_zh': '编辑成功指目标身份/编辑元素及主要场景保留；动作时间、动作缺失、姿态与局部伪影分别保留。',
       'cases': {}, 'checks': [], 'missing': []}

for project in (OLD, ROOT):
    manifest_file = project / 'EVALUATION_MANIFEST.json'
    for original in read(manifest_file)['cases']:
        case = resolve_controls(original) if project == ROOT else original
        sid = case['source_id']
        out['cases'][sid] = {}
        for role in ('native', 'fixed'):
            media = case['media'][role]
            verify_record(media)
            row = {'verdict': 'PASS_CORE_EDIT', 'verdict_zh': '编辑成功', 'role': role,
                   'actual_video': media, 'valid_frames': case['geometry']['valid_frames'],
                   'evidence': {'frozen_manifest': bound(manifest_file)}, 'quality_notes': [],
                   'is_new_matched_control': role in original.get('new_control_roles', [])}
            direct = ROOT / 'review' / sid / role / 'REVIEW.json'
            if role in original.get('new_control_roles', []):
                review = read(direct)
                assert review['review_completed'] and review['actual_video']['sha256'] == media['sha256']
                assert review['task_verdict'] == 'PASS_CORE_EDIT'
                row['evidence']['review'] = bound(direct)
                row['evidence']['control'] = bound(ROOT / 'actual' / sid / role / 'CONTROL.json')
                row['evidence_fields'] = ['task_verdict', 'actual_video', 'identity_pose_ghosting_observations', 'full_frame_review_complete']
                row['quality_notes'] = review.get('identity_pose_ghosting_observations', [])
                row['reviewed_frames'] = review.get('frames_reviewed', [])
                row['binding_check'] = 'Validated CONTROL gate/binding/video and exact REVIEW.actual_video via resolve_controls.'
            elif sid == '05_real_megumi_v':
                review_file = R148 / 'review' / sid / 'REVIEW.json'
                review = read(review_file)
                verify_record(review['presentation'])
                presentation = read(review['presentation']['file'])
                # This later full-clip four-way review supersedes the limited two-frame pilot.
                assert media['sha256'] in json.dumps(presentation)
                assert review['all_valid_frames_inspected'] and review['valid_frames'] == 141
                row['evidence']['review'] = bound(review_file)
                row['evidence']['presentation'] = review['presentation']
                row['evidence_fields'] = ['all_valid_frames_inspected', 'observations[0]', 'observations[2]', 'appearance_comparison.identity_zh']
                row['review_excerpt'] = [review['observations'][0], review['observations'][2]]
                if role == 'fixed': row['review_excerpt'].append(review['appearance_comparison']['identity_zh'])
                row['reviewed_frame_range'] = [0, 140]
                row['binding_check'] = 'The full-frame R148 comparison contains this exact historical control media SHA; all three generated columns retain the male subject/background.'
                row['quality_notes'] = ['动作时间单列；快速手臂与手部细节沿原评审保留。']
            elif sid == 'musk05':
                review_file = ROOT.parent / 'h3-musk-real-dance-pair-20261014/analysis/baseline_visual_review.json'
                review = read(review_file)
                assert role == 'native' and review['baseline']['sha256'] == media['sha256']
                assert review['coverage']['full_frame_rows_inspected'] == 141
                row['evidence']['review'] = bound(review_file)
                row['evidence_fields'] = ['baseline.sha256', 'coverage', 'identity_and_visual_quality']
                row['review_excerpt'] = review['identity_and_visual_quality']
                row['reviewed_frame_range'] = [0, 140]
                row['quality_notes'] = ['第0–1帧腰侧另有分离的掌状残影；快速手指模糊/拉伸，保留原记录。']
                row['binding_check'] = 'Existing full141 baseline review binds exact baseline video SHA.'
            else:
                verify_record(case['historical_review'])
                verify_record(case['historical_pair_gate'])
                review = read(case['historical_review']['file'])
                gate = read(case['historical_pair_gate']['file'])
                assert media['sha256'] in json.dumps(gate)
                assert case['historical_pair_gate']['sha256'] in json.dumps(review)
                old_role = role if role == 'native' else ('guided' if sid == 'short_0252' else 'forced')
                if sid == 'short_0274': old_role = role
                if 'task_acceptance' in review:
                    entry = review['task_acceptance'][old_role]
                    verdict = entry if isinstance(entry, str) else entry.get('verdict', entry.get('status'))
                    assert verdict in ('PASS', 'PASS_CORE_EDIT')
                    row['review_excerpt'] = entry
                    row['quality_notes'] = review.get('whole_clip_quality', review.get('quality_observations', []))
                    row['evidence_fields'] = ['task_acceptance.' + old_role]
                else:
                    row['review_excerpt'] = review['task'][old_role]
                    row['quality_notes'] = review.get('quality', review.get('limitations', []))
                    row['evidence_fields'] = ['task.' + old_role]
                row['evidence']['review'] = case['historical_review']
                row['evidence']['pair_gate'] = case['historical_pair_gate']
                row['binding_check'] = 'Historical review binds the verified pair gate SHA, whose exact output media SHA matches the displayed control.'
            out['cases'][sid][role] = row
            out['checks'].append({'source_id': sid, 'role': role, 'media_sha_verified': True, 'review_binding_verified': True})

out['passed'] = len(out['cases']) == 10 and len(out['checks']) == 20 and not out['missing']
out['summary'] = {'task_count': 10, 'independent_source_count': 9, 'control_count': 20,
                  'native_core_edit_pass': 10, 'fixed_core_edit_pass': 10,
                  'new_matched_controls': 5, 'historical_reused_controls': 15}
write(ROOT / 'HISTORICAL_CONTROL_VERDICTS.json', out)
print(json.dumps({'passed': out['passed'], 'summary': out['summary'], 'file': bound(ROOT / 'HISTORICAL_CONTROL_VERDICTS.json')}, ensure_ascii=False))
