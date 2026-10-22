"""Describe adjacent-event duration errors from existing frame annotations."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT.parents[2]
INPUTS = [
    (ROOT.parent / 'event_time_summary_20261020/RESULT.json',
     '43acba83fa59ca5018374c2fc223ba605860006dfdea440e0e3955031f1e6cf7'),
    (PROJECTS / 'h3-paper-progress-20261020/audit/event_time_update_20261020/RESULT.json',
     None),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def midpoint(interval):
    return sum(interval) / 2


def duration(first, second):
    return [second[0] - first[1], second[1] - first[0]]


def main():
    assert duration([2, 4], [8, 10]) == [4, 8]
    assert midpoint([8, 10]) - midpoint([2, 4]) == 6
    # Constant delay preserves all adjacent-event durations.
    source = [1, 4, 10]
    shifted = [x + 7 for x in source]
    assert [b-a for a,b in zip(source, source[1:])] == [b-a for a,b in zip(shifted, shifted[1:])]
    rows = []
    bindings = []
    for file, expected in INPUTS:
        digest = sha(file)
        assert expected is None or digest == expected
        bindings.append({'file': str(file), 'sha256': digest})
        for run in json.loads(file.read_text())['runs']:
            annotation = run['annotation']
            assert sha(annotation['file']) == annotation['sha256']
            events = run['events']
            phases = []
            for first, second in zip(events, events[1:]):
                row = {'from': first['name'], 'to': second['name']}
                intervals = {role: duration(first[role+'_frames'], second[role+'_frames'])
                             for role in ('source', 'native', 'guided')}
                row['duration_frames'] = intervals
                for role in ('native', 'guided'):
                    r, s = intervals[role], intervals['source']
                    row[role+'_duration_error_frames'] = [r[0]-s[1], r[1]-s[0]]
                    row[role+'_midpoint_duration_error_frames'] = midpoint(r)-midpoint(s)
                phases.append(row)
            rows.append({
                'run': run['run'], 'source_id': run['source_id'], 'fps': run['fps'],
                'annotation': annotation, 'phases': phases,
                'mean_absolute_midpoint_duration_error_frames': {
                    role: sum(abs(p[role+'_midpoint_duration_error_frames']) for p in phases)/len(phases)
                    for role in ('native', 'guided')},
            })
    result = {
        'definition': 'For every adjacent annotated event pair, compare edited elapsed time with source elapsed time. Constant overall delay cancels.',
        'scope': 'Descriptive analysis of all already annotated comparable events in these six runs; preserve missing-event cases separately.',
        'uncertainty': 'Per-phase ranges propagate endpoint annotation bounds. Midpoint summaries are descriptive point estimates; no inferential confidence interval or significance test.',
        'relation_to_MF': 'Alongside official MF and event-time error; no new benchmark-wide score is claimed.',
        'inputs': bindings, 'script_sha256': sha(__file__), 'runs': rows,
    }
    ROOT.joinpath('RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    for row in rows:
        print(row['run'], row['mean_absolute_midpoint_duration_error_frames'])


if __name__ == '__main__':
    main()
