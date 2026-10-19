"""Review task completion, full physical events and terminal motion for all three outputs."""
from common import ROOT,read,save,bound,require,verify_collection
from intervals import compare

ROLES=('native','fixed_one_bin','matched_one_bin')
TASKS=('PASS','PARTIAL','FAIL','UNKNOWN')
EVENTS=('OBSERVED','UNKNOWN','NOT_COMPARABLE','RIGHT_CENSORED','ALTERED')
COMPONENTS=('requested_black_clothes','persons_and_scene','framing')

def interval(value):
    require(isinstance(value,list) and len(value)==2 and all(type(i) is int for i in value)
            and 0<=value[0]<=value[1]<145,'event outside valid physical frames')
    return value

def delay_interval(source,edited):
    interval(source);interval(edited)
    frames=[edited[0]-source[1],edited[1]-source[0]]
    return {'frames':frames,'seconds':[i/24 for i in frames]}

def template(incoming,showcase):
    destination=ROOT/'audit/full145_review/REVIEW_TEMPLATE.json'
    if destination.exists():return destination
    plan=read(ROOT/'configs/PREREGISTERED_EVENTS.json')
    value={'schema':'r115-full145-review-v1','all_valid_frames_inspected':False,
        'examined_frames_by_role':{r:[] for r in ROLES},'reviewer':None,
        'task_acceptance':{r:{'status':'PENDING',**{k:'PENDING' for k in COMPONENTS},'notes':''} for r in ROLES},
        'motion_preservation':{r:{'action_content':'PENDING','motion_amplitude':'PENDING','notes':''} for r in ROLES},
        'quality':{r:{'status':'PENDING','notes':''} for r in ROLES},
        'events':[{**row,**{r:{'status':'PENDING','frames':None,'notes':''} for r in ROLES}} for row in plan['events']],
        'terminal_motion':{**plan['terminal_motion'],**{r:{'status':'PENDING','notes':''} for r in ROLES}},
        'generation_scope':{'native':'registered existing R96 output','fixed_one_bin':'new R115 output','matched_one_bin':'new R115 output'},
        'review_rule':'Basic editing, retained motion content and event timing are recorded separately. A late event alone does not fail the editing task. A different event remains ALTERED or NOT_COMPARABLE.',
        'evidence':{'gate':bound(incoming/'PAIR_RUNTIME_GATE.json'),'collection':bound(incoming/'COLLECTION.json'),
            'frame_ledger':bound(showcase/'FRAME_LEDGER.json'),'registered_source_events':bound(ROOT/'configs/PREREGISTERED_EVENTS.json')},
        'official_MF':'PENDING_SEPARATE_SCORE'}
    save(destination,value);return destination

def validate_completed(value):
    plan=read(ROOT/'configs/PREREGISTERED_EVENTS.json')
    require(value['all_valid_frames_inspected'] is True and set(value['examined_frames_by_role'])==set(ROLES),'full review pending')
    require(isinstance(value.get('reviewer'),str) and bool(value['reviewer'].strip()),'reviewer attribution missing')
    for role in ROLES:
        require(value['examined_frames_by_role'][role]==list(range(145)),'full145 physical frames required')
        task=value['task_acceptance'][role]
        require(task['status'] in TASKS and all(task.get(k) in TASKS for k in COMPONENTS),'task review pending')
        require(task['status']!='PASS' or all(task[k]=='PASS' for k in COMPONENTS),'task PASS conflicts with components')
        require(all(value['motion_preservation'][role].get(k) in TASKS for k in ('action_content','motion_amplitude')),'motion content review pending')
        require(value['quality'][role]['status'] in ('ACCEPTABLE','ARTIFACTS','UNKNOWN'),'quality review pending')
        require(value['terminal_motion'][role]['status'] in ('OBSERVED','UNKNOWN','NOT_COMPARABLE','RIGHT_CENSORED','ALTERED'),'terminal review pending')
    for k,v in plan['terminal_motion'].items():require(value['terminal_motion'][k]==v,'terminal definition changed')
    require(len(value['events'])==len(plan['events'])==3,'registered event count changed')
    results=[]
    for row,old in zip(value['events'],plan['events']):
        require(all(row[k]==v for k,v in old.items()),'registered source event changed')
        source=interval(row['source_frames']);delays={}
        for role in ROLES:
            observation=row[role];require(observation['status'] in EVENTS,'event review pending')
            if observation['status']=='OBSERVED':delays[role]=delay_interval(source,observation['frames'])
            else:
                require(observation['frames'] is None and bool(str(observation.get('notes','')).strip()),'unobserved event needs null and reason')
                delays[role]=None
        comparisons={}
        for first,second in [('native','fixed_one_bin'),('native','matched_one_bin'),('fixed_one_bin','matched_one_bin')]:
            eligible=all(value['task_acceptance'][r]['status']=='PASS' and row[r]['status']=='OBSERVED' for r in (first,second))
            comparisons[first+'__'+second]={'primary_timing_comparison_eligible':eligible,
                'result':compare(source,row[first]['frames'],row[second]['frames']) if eligible else None,
                'generation_scope':'two new R115 operators' if first=='fixed_one_bin' else 'registered existing Native versus new R115 operator'}
        results.append({'id':row['id'],'definition':row['definition'],'source_frames':source,'observed_delays':delays,'comparisons':comparisons})
    return {'events':results,'task_acceptance':value['task_acceptance'],'motion_preservation':value['motion_preservation'],'quality':value['quality'],
        'terminal_motion':value['terminal_motion'],'all_physical_frames_per_role':145,
        'interval_scope':'Visible annotation uncertainty with shared source event; not a statistical confidence interval.',
        'official_MF':'REPORTED_SEPARATELY'}

if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--review',required=True);a.add_argument('--output',required=True);args=a.parse_args()
    value=read(args.review);verify_collection(ROOT/'incoming/long_0174')
    original=read(ROOT/'audit/full145_review/REVIEW_TEMPLATE.json')
    require(value['evidence']==original['evidence'],'review evidence changed')
    for record in value['evidence'].values():require(bound(record['file'])==record,'review evidence changed')
    result=validate_completed(value);result['review']=bound(args.review);save(args.output,result)
