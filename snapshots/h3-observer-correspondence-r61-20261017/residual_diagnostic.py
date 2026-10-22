"""Extract the remaining fixed-cycle false correspondence; no new search or gate."""
import gzip
import json

import study


def main():
    study.verify()
    path = study.HERE / 'results/whole_arm/fixed_cycle/short_0370__short_0210.json.gz'
    data = json.loads(gzip.decompress(path.read_bytes()))
    chosen = data['variants']['AB']['selected']
    assert len(chosen) == 1 and chosen[0]['window'] == [40, 55]
    selected_window, context_windows = None, []
    for i, row in enumerate(data['observation']['windows']):
        if row['feature'] != 'right_arm_direction':
            continue
        a, b = row['window']
        if [a, b] == [40, 55] or (b - a + 1 == 32 and a <= 40 and b >= 55):
            item = {'original_row_index': i, 'original_row': row,
                    'gates_if_original_qualified': data['candidate_gates'].get(str(i))}
            if [a, b] == [40, 55]:
                selected_window = item
            else:
                context_windows.append(item)
    assert selected_window is not None and len(context_windows) == 5
    output = {'schema': 'r61-residual-readonly-diagnostic-v1',
              'source_artifact': str(path.relative_to(study.HERE)), 'artifact_sha256': study.sha(path),
              'protocol_sha256': study.sha(study.HERE / 'PROTOCOL.json'),
              'source_pose_sha256': data['observation']['source_pose_sha256'],
              'target_pose_sha256': data['observation']['edited_pose_sha256'],
              'selected_window': selected_window, 'all_containing_32frame_windows': context_windows,
              'interpretation': 'AB retains the16frame window. One containing32frame window passes the original gate but fails both A and B. The other four already fail the original gate. This extraction does not change policy or establish a new context gate.',
              'new_metric_calls': 0, 'new_pose_calls': 0, 'GPU_calls': 0}
    study.write(study.HERE / 'RESIDUAL_CASE_DIAGNOSTIC.json', output)
    print(json.dumps({'sha256': study.sha(study.HERE / 'RESIDUAL_CASE_DIAGNOSTIC.json')}))


if __name__ == '__main__':
    main()
