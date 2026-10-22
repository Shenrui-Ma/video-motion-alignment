"""Task acceptance and visible event timing, with guide/skip recommendations kept local."""
from common import *
from intervals import compare

TASKS = ('PASS','PARTIAL','FAIL','UNKNOWN')
EVENTS = ('OBSERVED','UNKNOWN','NOT_COMPARABLE','RIGHT_CENSORED','ALTERED')
COMPONENTS = ('requested_edit','original_scene_and_framing','action_sequence','motion_amplitude')

def mapped_cues(source):
    p = info(source)
    plan = read(ROOT/'configs/SOURCE_EVENT_REVIEW_CUES.json')
    row = next(x for x in plan['items'] if x['source_id'] == source)
    mapping = read(ROOT/p['provenance']['file'])['input_to_original_frame'][:p['valid_frames']]
    return [{'name':name, 'cue_frame_domain':'prepared_24fps',
             'original_frame_cue':[mapping[bracket[0]],mapping[bracket[1]]],
             'prepared_frame_cue':list(range(bracket[0],bracket[1]+1))}
            for name, bracket in row['reference_prepared_frame_brackets'].items()]

def checked_event(event, valid):
    require(event.get('status') in EVENTS, 'event observation pending')
    if event['status'] == 'OBSERVED':
        value = event.get('frames')
        require(isinstance(value,list) and len(value)==2 and all(type(x) is int for x in value)
                and 0 <= value[0] <= value[1] < valid, 'event outside physical valid frames')
    else:
        require(event.get('frames') is None and bool(str(event.get('notes','')).strip()), 'unobserved event needs reason and null frames')

def create_template(source, paired=False):
    p = info(source)
    mode = 'paired' if paired else 'native'
    arms = ('native','forced') if paired else ('native',)
    directory = ROOT/'audit/full_frame_review'/source/mode
    destination = directory/'REVIEW_TEMPLATE.json'
    if destination.exists(): return bound(destination)
    intake = ROOT/('incoming_pairs' if paired else 'incoming')/source
    pending = lambda: {'status':'PENDING','frames':None,'notes':''}
    value = {'schema':'r119-full-physical-frame-review-v1', 'source_id':source, 'mode':mode,
        'all_valid_frames_inspected':False, 'examined_frames':[], 'reviewer':None,
        'task_acceptance':{arm:{'status':'PENDING', **{key:'PENDING' for key in COMPONENTS}, 'notes':''} for arm in arms},
        'whole_clip_quality':{arm:{'status':'PENDING','notes':''} for arm in arms},
        'events':[{**cue, **{arm:pending() for arm in ('source',)+arms}} for cue in mapped_cues(source)],
        'cue_scope':'Original coarse brackets select review areas; actual event boundaries require fresh visible annotation and may lie elsewhere in the valid clip.',
        'guide_or_skip_recommendation':None if paired else {'choice':'PENDING','reason':''},
        'evidence':{'gate':bound(intake/('PAIR_RUNTIME_GATE.json' if paired else 'NATIVE_RUNTIME_GATE.json')),
            'collection':bound(intake/'COLLECTION.json'), 'frames':bound(directory/'FRAME_LEDGER.json'),
            'source_cues':bound(ROOT/'configs/SOURCE_EVENT_REVIEW_CUES.json')},
        'official_MF':'PENDING_SEPARATE_SCORE'}
    save(destination, value)
    return bound(destination)

def validate_completed(value):
    source = value['source_id']
    p = info(source)
    require(value['mode'] in ('native','paired'), 'unknown review mode')
    paired = value['mode'] == 'paired'
    arms = ('native','forced') if paired else ('native',)
    require(value['all_valid_frames_inspected'] is True and value['examined_frames']==list(range(p['valid_frames'])), 'full-frame review incomplete')
    require(isinstance(value.get('reviewer'),str) and bool(value['reviewer'].strip()), 'reviewer attribution missing')
    require(set(value['task_acceptance'])==set(arms), 'review arms differ')
    for arm in arms:
        task = value['task_acceptance'][arm]
        require(task['status'] in TASKS and all(task.get(k) in TASKS for k in COMPONENTS), 'task review incomplete')
        require(task['status'] != 'PASS' or all(task[k]=='PASS' for k in COMPONENTS), 'task PASS conflicts with component review')
        require(value['whole_clip_quality'][arm]['status'] in ('ACCEPTABLE','ARTIFACTS','UNKNOWN'), 'quality review incomplete')
    cues = mapped_cues(source)
    require(len(value['events'])==len(cues), 'registered event count differs')
    results = []
    for event, cue in zip(value['events'],cues):
        require(all(event[k]==v for k,v in cue.items()), 'registered cue changed')
        for arm in ('source',)+arms: checked_event(event[arm],p['valid_frames'])
        delays = {}
        for arm in arms:
            if event['source']['status']==event[arm]['status']=='OBSERVED':
                a,b=event['source']['frames'],event[arm]['frames']
                delays[arm]={'signed_delay_frames':[b[0]-a[1],b[1]-a[0]]}
            else: delays[arm]=None
        eligible = paired and all(value['task_acceptance'][arm]['status']=='PASS' for arm in arms) and all(event[arm]['status']=='OBSERVED' for arm in ('source',)+arms)
        results.append({'name':cue['name'], 'observed_delays':delays,
            'primary_timing_comparison_eligible':eligible,
            'paired_comparison':compare(event['source']['frames'],event['native']['frames'],event['forced']['frames']) if eligible else None})
    if not paired:
        decision=value['guide_or_skip_recommendation']
        require(decision['choice'] in ('guide','skip') and bool(str(decision['reason']).strip()), 'guide/skip recommendation pending')
    return {'source_id':source,'mode':value['mode'],'valid_frames_inspected':p['valid_frames'],
        'task_acceptance':value['task_acceptance'],'events':results,
        'guide_or_skip_recommendation':value['guide_or_skip_recommendation'],
        'decision_scope':'local recommendation; producer decision remains root-owned',
        'interval_scope':'Visible annotation uncertainty with shared source event; not a statistical confidence interval.',
        'evaluation_scope':p['evaluation_scope'],'official_MF':'REPORTED_SEPARATELY'}

if __name__=='__main__':
    import argparse
    from paired import verify_pair_intake
    a=argparse.ArgumentParser();a.add_argument('--review',required=True);a.add_argument('--output',required=True)
    args=a.parse_args();value=read(args.review);validate_static()
    verify_pair_intake(value['source_id']) if value['mode']=='paired' else verify_intake(value['source_id'])
    template=read(ROOT/'audit/full_frame_review'/value['source_id']/value['mode']/'REVIEW_TEMPLATE.json')
    require(value['evidence']==template['evidence'],'review evidence changed')
    for record in value['evidence'].values():require(bound(record['file'])==record,'review evidence file changed')
    result=validate_completed(value);result['review']=bound(args.review);save(args.output,result)
