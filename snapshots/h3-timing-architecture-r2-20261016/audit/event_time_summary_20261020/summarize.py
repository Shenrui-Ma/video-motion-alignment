"""Summarize existing visual event brackets without reannotating outcomes."""
import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECTS = Path('/Users/researcher/DevProjects')
INPUTS = [
    ('R73', 'short_0252', 2026101701,
     'h3-ivebench-expanded-metrics-r73-20261018/audit/physical_time_short0252/VISUAL_EVENT_INTERVALS_EXPLORATORY.json',
     ('source_boundary_frames', 'native_boundary_frames', 'forced_boundary_frames')),
    ('R89', 'short_0358', 2026101701,
     'h3-ive-subject-capacity-metrics-r89-20261018/audit/visual_review_short0358/REVIEW.json',
     ('source_frame_boundary', 'native_frame_boundary', 'forced_frame_boundary')),
    *[(f'R113_{seed}', 'short_0252', seed,
       f'h3-oxygen-seed-replication-metrics-r113-host41-20261019/audit/full98_review/{seed}/REVIEW.json',
       ('source_frames', 'native_frames', 'fixed_frames'))
      for seed in (2026101702, 2026101703)],
]


def bounds(values):
    values = list(values)
    return [min(values), max(values)]


def describe_event(event, keys):
    source, native, guided = (event[key] for key in keys)
    for interval in (source, native, guided):
        assert len(interval) == 2 and all(isinstance(x, int) for x in interval)
        assert 0 <= interval[0] <= interval[1]
    triples = list(itertools.product(*(range(a, b + 1) for a, b in (source, native, guided))))
    change = bounds(abs(g-s)-abs(n-s) for s, n, g in triples)
    if 'paired_absolute_error_change_bounds_frames' in event:
        assert change == event['paired_absolute_error_change_bounds_frames']
    return {
        'name': event.get('name', event.get('event')),
        'source_frames': source, 'native_frames': native, 'guided_frames': guided,
        'native_signed_lag_frames': bounds(n-s for s, n, g in triples),
        'guided_signed_lag_frames': bounds(g-s for s, n, g in triples),
        'native_absolute_lag_frames': bounds(abs(n-s) for s, n, g in triples),
        'guided_absolute_lag_frames': bounds(abs(g-s) for s, n, g in triples),
        'paired_absolute_error_change_frames': change,
    }


def main():
    runs = []
    for run, source, seed, relative, keys in INPUTS:
        path = PROJECTS / relative
        raw = path.read_bytes()
        review = json.loads(raw)
        assert review.get('fps', 24) == 24
        events = [describe_event(e, keys) for e in review['events'] if all(k in e for k in keys)]
        assert len(events) == 3
        average = lambda key: [sum(e[key][i] for e in events)/len(events)/24*1000 for i in (0, 1)]
        runs.append({
            'run': run, 'source_id': source, 'seed': seed, 'fps': 24,
            'annotation': {'file': str(path), 'sha256': hashlib.sha256(raw).hexdigest()},
            'events': events,
            'mean_absolute_event_lag_ms': {
                'native': average('native_absolute_lag_frames'),
                'guided': average('guided_absolute_lag_frames'),
                'paired_change': average('paired_absolute_error_change_frames'),
            },
        })
    result = {
        'scope': 'Exploratory summaries of existing visible event brackets; two source videos, four paired runs.',
        'definition': 'Mean absolute event time difference across the three annotated transitions in each run. Bounds enumerate all integer-frame timestamps within each stored bracket. Paired change shares the same source timestamp.',
        'uncertainty': 'Bracket bounds reflect annotation resolution, not statistical confidence intervals. R73 annotations used stride3; R89 and R113 were refined after full-frame review. Terminal pose presence has no arrival bracket and is excluded.',
        'selection': 'These are previously selected positive development examples, not a benchmark success-rate estimate. Missing or changed actions in newer runs remain task failures and receive no timing score.',
        'independent_source_count': len({r['source_id'] for r in runs}),
        'runs': runs,
    }
    ROOT.joinpath('RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    lines = ['已有逐事件时间区间汇总', '', '每条成片统计三个已标注过渡动作。单位毫秒；范围来自标注区间的全部整数帧取值。', '配对变化为引导减普通编辑，负值表示绝对时间误差减少。', '两条独立源视频；机舱的三个种子单独列出。', '']
    for r in runs:
        m = r['mean_absolute_event_lag_ms']
        fmt = lambda a: f'{a[0]:.1f}～{a[1]:.1f}'
        lines.append(f"{r['run']} {r['source_id']}：普通 {fmt(m['native'])}；引导 {fmt(m['guided'])}；配对变化 {fmt(m['paired_change'])}。")
    ROOT.joinpath('REPORT.txt').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
