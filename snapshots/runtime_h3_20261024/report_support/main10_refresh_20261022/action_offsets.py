"""Validate frame annotations and overlay paired-event measurements on the display."""
import csv
import json
from pathlib import Path

ROLES = ['source', 'native', 'early', 'fixed', 'late', 'split', 'global_weak']
ANNOTATIONS = Path('/workspace/research-user/DevProjects/video-motion-alignment/execution-20261022/timing/event_offset_completion_20261022')


def measure(annotation):
    events = annotation['events']
    offsets, intervals = {}, {}
    for event in events:
        assert event['id'] not in offsets, 'Duplicate event'
        assert event.get('source') is not None, 'Reference event required'
        offsets[event['id']], intervals[event['id']] = {}, {}
        for role in ROLES:
            pair = event.get(role)
            if pair is not None:
                assert len(pair) == 2 and all(isinstance(x, int) for x in pair)
                assert 0 <= pair[0] <= pair[1] < annotation['valid_frames'], (event['id'], role, pair)
                offsets[event['id']][role] = (sum(pair) - sum(event['source'])) / 2
                intervals[event['id']][role] = [pair[0] - event['source'][1], pair[1] - event['source'][0]]
            else:
                assert event.get('status_by_role', {}).get(role), (event['id'], role, 'Missing reason')
                offsets[event['id']][role] = None
                intervals[event['id']][role] = None
    common = [e['id'] for e in events if all(offsets[e['id']][r] is not None for r in ROLES)]
    means = {r: sum(abs(offsets[e][r]) for e in common) / len(common) if common else None for r in ROLES}
    available = {r: [offsets[e['id']][r] for e in events if offsets[e['id']][r] is not None] for r in ROLES}
    return dict(event_offsets=offsets, offset_intervals=intervals, mean_absolute_offset=means,
                common_events=common, coverage={r: len(v) for r, v in available.items()},
                available_event_means={r: sum(map(abs, v))/len(v) if v else None for r,v in available.items()})


def apply_annotations(cases):
    audit, rows = [], []
    for case in cases.values():
        if not case.get('main_cohort'):
            continue
        path = ANNOTATIONS / case['source_id'] / 'ANNOTATION.json'
        if not path.exists():
            continue
        a = json.loads(path.read_text())
        assert a['case_id'] == case['source_id']
        assert a['fps'] == 24 and a['valid_frames'] == case['geometry']['valid_frames']
        m = measure(a)
        case['events'] = a['events']
        case.update({k: m[k] for k in ['event_offsets', 'mean_absolute_offset']})
        case['timing_measurement'] = dict(m, annotation_source=a['annotation_source'], notes=a.get('notes', []))
        case['display_summary'] = f"动作偏移已检查：{len(a['events'])}个参考动作事件，{len(m['common_events'])}个事件在六种编辑中均可定位。"
        specific = {
            'short_0343': '六种编辑均改为医院走廊开门、行走，参考中的镜前抬手机动作无法对应。',
            'short_0114': '六种编辑改变了连续换手运球的动作序列，原动作事件无法逐一对应。',
            'crouch__movie_man_4': '全程弱引导恢复第一次蹲起，第二次缺失；其余五种编辑未保留蹲起序列。恢复直立的定位受下肢裁切影响。',
            'long_0167': '六种编辑改变为地面特写，参考人物的转身、伸手与举扫帚动作无法定位。',
            'short_0085': '六种编辑的下放杯子起始在标注区间内近同步，中点差为0帧，定位范围±2帧。杯子最低点被画面下沿遮挡，已排除。',
            'short_0274': '六种编辑的首次抬头结束在标注区间内近同步，中点差为0帧，定位范围±3帧。',
        }
        case['display_summary'] += ' ' + specific.get(a['case_id'], '')
        audit.append(dict(case_id=a['case_id'], **m))
        for e in a['events']:
            for role in ROLES:
                rows.append(dict(case_id=a['case_id'], event=e['id'], label=e['label'], method=role,
                                 source_interval=json.dumps(e['source']), edited_interval=json.dumps(e.get(role)),
                                 signed_offset_frames=m['event_offsets'][e['id']][role],
                                 offset_bounds=json.dumps(m['offset_intervals'][e['id']][role]),
                                 status=json.dumps(e.get('status_by_role', {}).get(role, 'measured'), ensure_ascii=False),
                                 included_in_paired_mean=e['id'] in m['common_events']))
    scopes = {}
    for name, subset in [('main10', audit), ('IVE9', [a for a in audit if cases[a['case_id']]['dataset']=='IVEBench'])]:
        valid = [a for a in subset if a['common_events']]
        scopes[name] = dict(checked=len(subset), measured=len(valid),
                           case_ids=[a['case_id'] for a in valid],
                           means={r: sum(a['mean_absolute_offset'][r] for a in valid)/len(valid) if valid else None for r in ROLES})
    result = dict(protocol='AI逐帧事件标注；零基闭区间中点差；正数延后；共同事件内取绝对值均值，再按视频等权平均。',
                  cases=audit, scopes=scopes)
    (ANNOTATIONS/'SUMMARY.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    if rows:
        with (ANNOTATIONS/'EVENT_OFFSETS.csv').open('w', newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return result
