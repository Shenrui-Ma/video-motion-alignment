"""Keep the existing visible-event definitions fixed during the R111 full-frame review."""
import copy
from common import ROOT, read, save, bound, require


def delay_interval(source, edited):
    require(len(source) == len(edited) == 2 and
            0 <= source[0] <= source[1] < 145 and 0 <= edited[0] <= edited[1] < 145,
            'event interval outside valid physical frames')
    frames = [edited[0]-source[1], edited[1]-source[0]]
    return {'frames': frames, 'seconds': [value/24 for value in frames],
            'interpretation': 'visible annotation uncertainty; not a statistical confidence interval'}


def template(incoming, showcase):
    dest = ROOT/'audit/full145_review/REVIEW_TEMPLATE.json'
    if dest.exists():
        return dest
    value = copy.deepcopy(read(ROOT/'configs/PREREGISTERED_EVENTS.json'))
    value.update({'schema': 'r111-full145-review-template-v1',
        'R111_output_viewed': False, 'all_valid_frames_inspected': False,
        'examined_spatial_frames': [], 'basic_edit_task': 'PENDING',
        'motion_preservation': 'PENDING', 'quality': 'PENDING',
        'evidence': {'gate': bound(incoming/'PAIR_RUNTIME_GATE.json'),
                     'collection': bound(incoming/'COLLECTION.json'),
                     'frame_ledger': bound(showcase/'FRAME_LEDGER.json'),
                     'preregistered_events': bound(ROOT/'configs/PREREGISTERED_EVENTS.json')}})
    save(dest, value)
    return dest


def validate_completed(value):
    expected = read(ROOT/'configs/PREREGISTERED_EVENTS.json')
    require(value['all_valid_frames_inspected'] is True and
            value['examined_spatial_frames'] == list(range(145)), 'full145 review incomplete')
    require(len(value['events']) == 3, 'registered event count changed')
    for row, old in zip(value['events'], expected['events']):
        for key in ('id', 'definition', 'source_frames', 'native_frames', 'fixed_frames', 'fixed_comparability'):
            require(row[key] == old[key], 'registered event changed: '+key)
        if row['spatial_status'] == 'OBSERVED':
            computed = delay_interval(row['source_frames'], row['spatial_frames'])
            require(row['spatial_delay'] == computed, 'event delay does not follow fixed physical intervals')
        else:
            require(row['spatial_status'] in ('UNKNOWN', 'NOT_COMPARABLE', 'RIGHT_CENSORED', 'ALTERED')
                    and row['spatial_frames'] is None and row.get('spatial_delay') is None,
                    'unobserved or incomparable event cannot have numeric delay')
    for key in ('source_frames', 'definition', 'native_status', 'fixed_status'):
        require(value['terminal_motion'][key] == expected['terminal_motion'][key],
                'registered terminal-motion definition changed')
    require(value['terminal_motion']['spatial_status'] != 'PENDING', 'terminal-motion review pending')
    return True
