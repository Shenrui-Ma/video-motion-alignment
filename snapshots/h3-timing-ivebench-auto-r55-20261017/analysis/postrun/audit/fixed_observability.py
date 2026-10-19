"""Read existing pose/observer evidence at four predeclared denoising indices."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path('/data3/researcher/h3_runs/timing_ivebench_auto_r55_20261017')
INDICES = (0, 5, 10, 19)
ARMS = ((5, 7), (7, 9), (6, 8), (8, 10))
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound(entry):
    path = Path(entry['file'])
    assert path.is_relative_to(ROOT) and sha(path) == entry['sha256']
    return path


def describe(raw, count):
    assert raw['video']['container_frame_count'] == len(raw['frames']) == 90
    assert raw['video']['fps'] == 24
    summaries = {}
    for threshold in (.3, .5):
        anchors, torso_lengths, validity = 0, [], []
        for index, frame in enumerate(raw['frames'][:count]):
            assert frame['frame'] == index and abs(frame['time_s'] - index/24) < 1e-8
            selected = frame['selected_person']
            if selected is None:
                validity.append([False]*4)
                continue
            person = frame['persons'][selected]
            xy, confidence = person['coco17_xy'], person['coco17_score']
            if all(confidence[joint] >= threshold for joint in (5, 6, 11, 12)):
                anchors += 1
                shoulder = [(xy[5][axis]+xy[6][axis])/2 for axis in (0, 1)]
                hip = [(xy[11][axis]+xy[12][axis])/2 for axis in (0, 1)]
                torso_lengths.append(math.hypot(shoulder[0]-hip[0], shoulder[1]-hip[1]))
            validity.append([confidence[a] >= threshold and confidence[b] >= threshold
                             and math.hypot(xy[b][0]-xy[a][0], xy[b][1]-xy[a][1]) > 1e-8
                             for a,b in ARMS])
        scale = statistics.median(torso_lengths) if torso_lengths else None
        features = {}
        for name, selected in [('both_arms', range(4)), ('left_arm', range(2)), ('right_arm', range(2,4))]:
            masks = [[row[j] for j in selected] for row in validity]
            features[name] = {'valid_bone_fraction': sum(sum(row) for row in masks)/(count*len(selected)),
                              'frames_with_any_valid_bone': sum(any(row) for row in masks)}
        summaries[str(threshold)] = {'valid_frames': count, 'torso_anchor_frames': anchors,
                                      'torso_scale': scale,
                                      'original_torso_entry_available': scale is not None and math.isfinite(scale) and scale > 1e-8,
                                      'arm_endpoint_support': features}
    return summaries


protocol = read(ROOT / 'configs/protocol.json')
case = protocol['cases'][0]
source_path = ROOT / case['source_pose_path']
assert sha(source_path) == case['source_pose_sha256']
source = describe(read(source_path), case['valid_frame_count'])
by_index = {}
for path in (ROOT / 'audit/observations').glob('step*/response.json'):
    request = read(path.parent / 'request.json')
    if request['run_id'] != case['run_id']:
        continue
    response = read(path)
    if response['physical_index'] in INDICES:
        assert response['status'] == 'complete' and sha(path.parent/'request.json') == response['request_sha256']
        by_index[response['physical_index']] = (path, response)
counterfactual = ROOT / 'audit/counterfactual' / (case['run_id'] + '.json')
decisions = {step['physical_index']: step['decision'] for step in read(counterfactual).get('counterfactual', {}).get('steps', [])} if counterfactual.exists() else {}
records = []
for index in INDICES:
    row = {'denoising_index': index, 'status': 'pending'}
    if index in by_index:
        path, response = by_index[index]
        pose_path, observation_path = bound(response['pose']), bound(response['observer'])
        observation = read(observation_path)
        assert observation['physical_index'] == index
        assert observation['source_pose_sha256'] == sha(source_path)
        assert observation['edited_pose_sha256'] == sha(pose_path)
        pairs = []
        for window in observation.get('windows', []):
            pairs.append({'window': window['window'], 'feature': window['feature'], 'baseline': window['baseline'],
                          'status': window['status'], 'confidence': {confidence: {
                              'status': diagnostic['status'], 'flags': diagnostic.get('flags', []),
                              'reliable_lag_frames': diagnostic['reliable_lag_frames'],
                              'same_frame_coverage': diagnostic['same_frame']['coverage'],
                              'same_frame_valid_count': diagnostic['same_frame']['valid_frame_count']}
                              for confidence, diagnostic in window['measurements'].items()}})
        row.update(status='complete', source=source, target=describe(read(pose_path), case['valid_frame_count']),
                   observer_status=observation['status'], original_rejection_reasons=observation.get('reasons', []),
                   original_decision=decisions.get(index),
                   window_baselines=dict(Counter(p['baseline'] for p in pairs)), paired_windows=pairs,
                   evidence={'response': {'file': str(path), 'sha256': sha(path)},
                             'source_pose': {'file': str(source_path), 'sha256': sha(source_path)},
                             'target_pose': response['pose'], 'observer': response['observer']})
    records.append(row)
print(json.dumps({'schema': 'r55-fixed-online-observability-v1', 'run_id': case['run_id'],
                  'planned_indices': list(INDICES), 'effective_frame_count': case['valid_frame_count'],
                  'scope': 'Existing original runtime pose and observer outputs; no new inference or pose extraction.',
                  'records': records}))
