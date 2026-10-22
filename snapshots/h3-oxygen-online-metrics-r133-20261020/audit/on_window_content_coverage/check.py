"""Describe already measured joints only; never change the frozen controller."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path('/data4/researcher/h3_runs/timing_oxygen_online_r133_20261020')
OUT = Path('/data4/researcher/h3_runs/oxygen_online_metrics_r133_20261020/on_window_content_coverage')
JOINTS = {'left_shoulder': 5, 'left_elbow': 7, 'left_wrist': 9,
          'right_shoulder': 6, 'right_elbow': 8, 'right_wrist': 10}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def bound(p):
    return {'file': str(p), 'sha256': sha(p)}

def inside(xy):
    return all(math.isfinite(v) for v in xy) and 16 <= xy[0] < 1296 and 8 <= xy[1] < 728

def coverage(pose, interval):
    frames = {r['frame']: r for r in pose['frames']}
    result = {'interval_inclusive': interval, 'denominator': interval[1]-interval[0]+1, 'thresholds': {}}
    for threshold in (.3, .5):
        joints = {name: {'confident': [], 'confident_and_in_content': [], 'confident_out_of_content': [], 'unknown': []} for name in JOINTS}
        arms = {side: [] for side in ('left', 'right')}
        evidence = []
        for i in range(interval[0], interval[1]+1):
            r = frames[i]
            person = r['persons'][r['selected_person']] if r['selected_person'] is not None else None
            row = {'frame': i, 'joints': {}}
            for name, j in JOINTS.items():
                xy = person['coco17_xy'][j] if person else None
                conf = person['coco17_score'][j] if person else None
                confident = conf is not None and math.isfinite(conf) and conf >= threshold
                in_content = xy is not None and inside(xy)
                bucket = joints[name]
                bucket['confident' if confident else 'unknown'].append(i)
                if confident:
                    bucket['confident_and_in_content' if in_content else 'confident_out_of_content'].append(i)
                row['joints'][name] = {'xy': xy, 'confidence': conf, 'in_content': in_content}
            for side in arms:
                if all(i in joints[f'{side}_{part}']['confident_and_in_content'] for part in ('shoulder', 'elbow', 'wrist')):
                    arms[side].append(i)
            evidence.append(row)
        result['thresholds'][str(threshold)] = {'joints': joints, 'all_three_arm_joints_confident_and_in_content': arms}
    result['coordinate_evidence'] = evidence
    return result

audit_path = ROOT/'audit/counterfactual/r133_short_0252_seed2026101703_visible_only.json'
audit = json.loads(audit_path.read_text())['counterfactual']
source_path = ROOT/'configs/source.pose.json'
source = json.loads(source_path.read_text())
result = {'schema': 'r133-existing-ON-joint-content-coverage-v1', 'scope': 'descriptive only; confidence and image bounds are reported separately; no policy edits, no new pose extraction', 'audit': bound(audit_path), 'source_pose': bound(source_path), 'content_rectangle_xyxy_exclusive': [16, 8, 1296, 728], 'valid_frames': 98, 'frame_timebase': 'original physical index at 24fps', 'steps': [], 'GPU_started': False}
for index in (1, 3, 4):
    step = audit['steps'][index]
    selected = step['decision']['selected']
    assert len(selected) == 1 and step['decision']['active']
    selected = selected[0]
    m = audit['measurements'][index]
    response_path = Path(m['response_file'])
    assert sha(response_path) == m['response_sha256']
    response = json.loads(response_path.read_text())
    pose_path = Path(response['pose']['file'])
    assert sha(pose_path) == response['pose']['sha256']
    pose = json.loads(pose_path.read_text())
    window = selected['window']
    shifted = {str(lag): [window[0]+lag, window[1]+lag] for lag in set(selected['lags'].values())}
    result['steps'].append({'physical_index': index, 'actual_selected': selected, 'response': bound(response_path), 'filtered_pose': bound(pose_path), 'source_union_40_59': coverage(source, [40, 59]), 'prediction_union_40_59': coverage(pose, [40, 59]), 'source_selected_window': coverage(source, window), 'prediction_same_window': coverage(pose, window), 'prediction_lag_shifted_window': {k: coverage(pose, v) for k, v in shifted.items()}, 'positive_lag_rule': 'source frame f corresponds to prediction frame f+lag'})
OUT.mkdir(parents=True, exist_ok=True)
p = OUT/'RESULT.json'
p.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
compact = []
for row in result['steps']:
    side = row['actual_selected']['feature'].split('_')[0]
    compact.append({'index': row['physical_index'], 'selected': row['actual_selected'], 'source_counts': {t: len(v['all_three_arm_joints_confident_and_in_content'][side]) for t,v in row['source_selected_window']['thresholds'].items()}, 'prediction_same_counts': {t: len(v['all_three_arm_joints_confident_and_in_content'][side]) for t,v in row['prediction_same_window']['thresholds'].items()}, 'prediction_shifted_counts': {lag:{t:len(v['all_three_arm_joints_confident_and_in_content'][side]) for t,v in cov['thresholds'].items()} for lag,cov in row['prediction_lag_shifted_window'].items()}})
print(json.dumps({'file': str(p), 'sha256': sha(p), 'selected_arm_complete_support': compact}))
