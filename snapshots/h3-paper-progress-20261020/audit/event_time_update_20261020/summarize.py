"""Apply the existing event-interval arithmetic to the two new paired reviews."""
from pathlib import Path
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT.parents[2]
prior = PROJECTS / 'h3-timing-architecture-r2-20261016/audit/event_time_summary_20261020/summarize.py'
spec = importlib.util.spec_from_file_location('event_intervals', prior)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def bound(path):
    return {'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    inputs = [
        ('R122', 'long_0039', PROJECTS / 'h3-ive-generic-retention-metrics-r122-20261020/audit/full_frame_review/long_0039/paired/REVIEW.json'),
        ('R123_full', 'short_0358', PROJECTS / 'h3-ive-prompt-envelope-metrics-r123-20261020/variants/full_context/audit/full_frame_review/short_0358/paired/INDEPENDENT_REVIEW.json'),
    ]
    runs = []
    for name, source, path in inputs:
        review = json.loads(path.read_text())
        events = []
        for e in review['events']:
            item = e if 'source_frames' in e else {
                'name': e['name'], 'source_frames': e['source']['frames'],
                'native_frames': e['native']['frames'], 'forced_frames': e['forced']['frames'],
            }
            events.append(module.describe_event(item, ('source_frames', 'native_frames', 'forced_frames')))
        summary = {label: [sum(e[key][i] for e in events) / len(events) / 24 * 1000 for i in (0, 1)]
                   for label, key in [('native', 'native_absolute_lag_frames'), ('guided', 'guided_absolute_lag_frames'), ('paired_change', 'paired_absolute_error_change_frames')]}
        runs.append({'run': name, 'source_id': source, 'annotation': bound(path), 'fps': 24,
                     'event_count': len(events), 'events': events, 'mean_absolute_event_lag_ms': summary})
    result = {'definition': 'Equal-weight mean of the listed visible event absolute time errors; interval arithmetic shares the same source timestamp for each paired change.',
              'annotation_bounds': 'Integer-frame brackets; descriptive annotation resolution.',
              'scope': 'Two recent paired runs. Book source is new; eyeglasses source is a repeat with revised model input format.',
              'helper': bound(prior), 'script': bound(Path(__file__)), 'runs': runs}
    (ROOT / 'RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps([{k: r[k] for k in ('run', 'event_count', 'mean_absolute_event_lag_ms')} for r in runs], ensure_ascii=False))


if __name__ == '__main__':
    main()
