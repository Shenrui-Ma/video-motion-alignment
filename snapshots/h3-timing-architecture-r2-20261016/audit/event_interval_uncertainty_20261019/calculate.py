"""Derive time-error bounds from existing, hash-bound visual annotations."""
from pathlib import Path
import hashlib
import json
import time

from intervals import compare

ROOT = Path(__file__).resolve().parent
INVENTORY = Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    content = INVENTORY.read_bytes()
    snapshot = ROOT / ('inventory_' + digest(content)[:16] + '.json')
    if snapshot.exists():
        assert snapshot.read_bytes() == content
    else:
        snapshot.write_bytes(content)
    rows = {x['id']: x for x in json.loads(content)['items']}
    cases = []
    for key in ('r73_short_0252', 'r89_short_0358', 'r107_long_0174', 'r106_short_0252_sampler_control'):
        row = rows[key]
        is_solver = row['comparison_kind'] == 'sampler_control'
        if key == 'r107_long_0174':
            path = next(p for p in row['evidence_sha256'] if p.endswith('/full_frame_review/REVIEW.json'))
            expected = row['evidence_sha256'][path]
            annotation_bytes = Path(path).read_bytes()
            assert digest(annotation_bytes) == expected
            events = json.loads(annotation_bytes)['events']
            scope = 'Full-frame AI visual review; joint turn/arm-lift event remains NOT_COMPARABLE.'
        else:
            quant = row['quantitative_metrics']['event_timing']
            path, expected = quant['source_file'], quant['source_sha256']
            annotation_bytes = Path(path).read_bytes()
            assert digest(annotation_bytes) == expected
            events, scope = quant['events'], quant['scope']
        case = {
            'case_id': key, 'comparison_kind': row['comparison_kind'], 'title': row['title'],
            'annotation': {'file': path, 'sha256': expected, 'scope': scope},
            'ordinary': 'Euler' if is_solver else 'ordinary edit',
            'alternative': 'res_multistep' if is_solver else 'fixed timing guidance',
            'events': [],
        }
        for event in events:
            name = event.get('name', event.get('definition'))
            fields = ('source_frames', 'euler_frames', 'res_multistep_frames') if is_solver else ('source_frames', 'native_frames', 'guided_frames')
            spans = [event.get(k) for k in fields]
            result = {'name': name, **dict(zip(fields, spans))}
            if all(isinstance(span, list) and len(span) == 2 for span in spans):
                result.update(compare(*spans))
                result['absolute_error_change_seconds'] = [x / 24 for x in result['absolute_error_change_frames']]
            else:
                result.update(status='UNKNOWN_OR_NOT_COMPARABLE', reason=event.get('arrival_time', event.get('guided_comparability', 'No common event interval')))
            case['events'].append(result)
        cases.append(case)
    result = {
        'schema': 'visual-event-interval-arithmetic-v1', 'created_unix': time.time(),
        'inventory': {'file': str(snapshot), 'sha256': digest(content)},
        'method': 'Exact extrema of |alternative-source|-|ordinary-source| over annotated time intervals, sharing one source time. Negative values mean less absolute timing error.',
        'interpretation': 'Conditional arithmetic bounds, not confidence intervals or a new benchmark metric. Annotation error outside the visual brackets is not covered. Existing exploratory versus preregistered annotation status is retained. No aggregate dataset claim.',
        'fps': 24, 'cases': cases,
        'code_sha256': {p.name: digest(p.read_bytes()) for p in [Path(__file__), ROOT/'intervals.py', ROOT/'test_intervals.py']},
    }
    output = ROOT / 'RESULT.json'
    assert not output.exists()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    for case in cases:
        print(case['case_id'], case['alternative'])
        for event in case['events']:
            print(event['name'], event.get('absolute_error_change_frames'), event.get('verdict', event.get('status')))
    print('RESULT_SHA256', digest(output.read_bytes()))


if __name__ == '__main__':
    main()
