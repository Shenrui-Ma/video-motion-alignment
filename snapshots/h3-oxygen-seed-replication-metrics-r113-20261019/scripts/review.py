"""Keep task acceptance, visible event timing and full-frame coverage separate."""
from common import ROOT, ARMS, SEEDS, VALID, FPS, read, save, bound, require
from intervals import compare

UNOBSERVED = ('UNKNOWN', 'NOT_COMPARABLE', 'RIGHT_CENSORED', 'ALTERED')
TASKS = ('PASS', 'PARTIAL', 'FAIL', 'UNKNOWN')

def checked_interval(value):
    require(isinstance(value, list) and len(value) == 2
            and all(type(x) is int for x in value) and 0 <= value[0] <= value[1] < VALID,
            'event interval outside valid physical frames')
    return value

def evaluate_event(source, native, fixed, task_status):
    checked_interval(source)
    delays = {}
    for arm, value in zip(ARMS, (native, fixed)):
        require(value['status'] in ('OBSERVED',)+UNOBSERVED, 'event visibility pending or unknown status')
        if value['status'] == 'OBSERVED':
            observed = checked_interval(value['frames'])
            delta = [observed[0]-source[1], observed[1]-source[0]]
            delays[arm] = {'signed_delay_frames': delta, 'signed_delay_seconds': [x/FPS for x in delta]}
        else:
            require(value['frames'] is None, 'unobserved event cannot carry arrival frames')
            delays[arm] = None
    eligible = all(task_status[arm] == 'PASS' for arm in ARMS) and all(value['status'] == 'OBSERVED' for value in (native, fixed))
    return {'per_arm_observation': delays, 'primary_timing_comparison_eligible': eligible,
            'reason': 'BOTH_TASKS_PASS_AND_EVENTS_OBSERVED' if eligible else 'TASK_OR_EVENT_COMPARABILITY_INCOMPLETE',
            'paired_comparison': compare(source, native['frames'], fixed['frames']) if eligible else None,
            'interval_scope': 'visible annotation uncertainty with shared source event; not a statistical confidence interval'}

def template(incoming, showcase, seed):
    require(seed in SEEDS, 'unregistered seed')
    destination = ROOT/'audit/full98_review'/str(seed)/'REVIEW_TEMPLATE.json'
    if destination.exists():
        return destination
    events = read(ROOT/'configs/PREREGISTERED_EVENTS.json')
    value = {'schema': 'r113-independent-full98-review-v1', 'seed': seed,
             'all_valid_frames_inspected': False, 'examined_frames': [],
             'task_acceptance': {arm: {'status': 'PENDING', 'elderly_woman_identity': 'PENDING',
                'cabin_child_mask_retained': 'PENDING', 'action_sequence_retained': 'PENDING',
                'framing_and_motion_amplitude': 'PENDING', 'notes': ''} for arm in ARMS},
             'events': [{'name': row['name'], 'source_frames': row['source_frames'],
                        **{arm: {'status': 'PENDING', 'frames': None, 'notes': ''} for arm in ARMS}}
                       for row in events['events']],
             'terminal_pose_presence': {arm: {'status': 'PENDING', 'notes': ''} for arm in ARMS},
             'whole_clip_quality': {arm: {'status': 'PENDING', 'notes': ''} for arm in ARMS},
             'reviewer': None, 'evidence': {'pair_gate': bound(incoming/f'seed{seed}_PAIR_GATE.json'),
                'aggregate_gate': bound(incoming/'AGGREGATE_GATE.json'), 'collection': bound(incoming/'COLLECTION.json'),
                'frame_ledger': bound(showcase/'FRAME_LEDGER.json'), 'registered_events': bound(ROOT/'configs/PREREGISTERED_EVENTS.json')},
             'official_MF': 'PENDING_SEPARATE_AUTHORIZED_SCORE', 'all_seeds_reported': True}
    save(destination, value)
    return destination

def validate_completed(value):
    require(value['seed'] in SEEDS and value['all_valid_frames_inspected'] is True
            and value['examined_frames'] == list(range(VALID)), 'full98 review incomplete')
    require(isinstance(value.get('reviewer'), str) and bool(value['reviewer'].strip()), 'reviewer attribution missing')
    source = read(ROOT/'configs/PREREGISTERED_EVENTS.json')
    require(len(value['events']) == len(source['events']) == 3, 'registered event count changed')
    task_status = {arm: value['task_acceptance'][arm]['status'] for arm in ARMS}
    require(all(status in TASKS for status in task_status.values()), 'task review pending')
    for arm in ARMS:
        for key in ('elderly_woman_identity', 'cabin_child_mask_retained', 'action_sequence_retained', 'framing_and_motion_amplitude'):
            require(value['task_acceptance'][arm][key] in TASKS, 'task component review pending')
        if task_status[arm] == 'PASS':
            require(all(value['task_acceptance'][arm][key] == 'PASS' for key in
                ('elderly_woman_identity', 'cabin_child_mask_retained', 'action_sequence_retained', 'framing_and_motion_amplitude')), 'task PASS conflicts with components')
        require(value['terminal_pose_presence'][arm]['status'] in ('PRESENT', 'ABSENT', 'UNKNOWN', 'ALTERED'), 'terminal pose presence pending')
        require(value['whole_clip_quality'][arm]['status'] in ('ACCEPTABLE', 'ARTIFACTS', 'UNKNOWN'), 'quality review pending')
    result = []
    for row, original in zip(value['events'], source['events']):
        require(row['name'] == original['name'] and row['source_frames'] == original['source_frames'], 'registered event definition changed')
        for arm in ARMS:
            if row[arm]['status'] in UNOBSERVED:
                require(isinstance(row[arm].get('notes'), str) and bool(row[arm]['notes'].strip()), 'unobserved event requires a reason')
        result.append({'name': row['name'], **evaluate_event(row['source_frames'], row['native'], row['fixed'], task_status)})
    return {'seed': value['seed'], 'events': result, 'task_status': task_status,
            'all_frames_checked': VALID, 'official_MF': 'REPORTED_SEPARATELY',
            'scope': 'Two predeclared new seeds; both outputs retained, visible events assessed independently'}

if __name__ == '__main__':
    import argparse
    from common import verify_collection
    parser = argparse.ArgumentParser()
    parser.add_argument('--review', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    value = read(args.review)
    verify_collection(ROOT/'incoming/actual')
    original = read(ROOT/'audit/full98_review'/str(value['seed'])/'REVIEW_TEMPLATE.json')
    require(value['evidence'] == original['evidence'], 'review evidence binding changed')
    for evidence in value['evidence'].values():
        require(bound(evidence['file']) == evidence, 'review evidence file changed')
    result = validate_completed(value)
    result['review'] = bound(args.review)
    save(args.output, result)
