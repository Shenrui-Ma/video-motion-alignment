"""Bounded read-only result aggregation and target-order mechanism audit."""
import collections
import fcntl
import json
from pathlib import Path
import statistics
import time
import run_once as io

P=Path(__file__).resolve().parent
with io.LOCK.open('a+') as lock:
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:print('BUSY');raise SystemExit(75)
    start=time.perf_counter();summary=io.read(P/'results/SUMMARY.json')
    for item in summary['files']:io.verify(item)
    for freeze in ('PROTOCOL_FREEZE.json','CODE_FREEZE.json'):
        f=io.read(P/freeze)
        for item in f['files']+f.get('external_inputs',[]):io.verify(item)
    original_matches=[];order_rows=[];group_rows={}
    for row in summary['rows']:
        case=row['case'];m=row['methods'];g=group_rows.setdefault(case['group'],{'cases':0,'v1K':0,'v2K':0,'v1_direction_pass':0,'v2_direction_pass':0})
        g['cases']+=1
        for name in ('v1','v2'):
            g[name+'K']+=m[name]['K'];g[name+'_direction_pass']+=m[name]['assessment']['direction_task']['pass'] is True
        if case.get('suite')!='local12':
            oldmarker=io.read(P.parent/'phase_shape_profile_candidate_v1/results'/case['id']/'COMPLETE.json')
            old=io.read(oldmarker['result']['path']);now=io.read(row['result']['path'])['methods']['v1']
            same=old['parts']==now['result']['parts'] and old['selected']==now['result']['selected'] and old['verdict']==now['assessment']['original_point_task']
            if not same:raise ValueError('v1 original result did not reproduce: '+case['id'])
            original_matches.append(case['id'])
        if case['expected']=='local_positive':
            pairs=[]
            for part in ('left_arm','right_arm'):
                windows=sorted([w for w in m['v2']['selected'] if w['part']==part],key=lambda w:w['start'])
                for a,b in zip(windows,windows[1:]):
                    any_order=a['end']+min(a['phase_set']) < b['start']+max(b['phase_set'])
                    all_order=a['end']+max(a['phase_set']) < b['start']+min(b['phase_set'])
                    pairs.append({'part':part,'left_source':[a['start'],a['end']],'right_source':[b['start'],b['end']],
                        'left_D':a['phase_set'],'right_D':b['phase_set'],
                        'left_target_start_range':[a['start']+min(a['phase_set']),a['start']+max(a['phase_set'])],
                        'left_target_end_range':[a['end']+min(a['phase_set']),a['end']+max(a['phase_set'])],
                        'right_target_start_range':[b['start']+min(b['phase_set']),b['start']+max(b['phase_set'])],
                        'right_target_end_range':[b['end']+min(b['phase_set']),b['end']+max(b['phase_set'])],
                        'exists_ordered_pair_in_D':any_order,'every_pair_in_D_is_ordered':all_order,
                        'unavoidable_target_overlap_or_reversal':not any_order})
            wrong=[w for w in m['v2']['assessment']['selected_windows'] if w['direction_fraction']<.8]
            order_rows.append({'case':case['id'],'wrong_direction_windows':wrong,'adjacent_pairs':pairs,
                               'has_unavoidable_target_collision':any(p['unavoidable_target_overlap_or_reversal'] for p in pairs)})
    receipts=[io.read(p) for p in (P/'audit').glob('case*.json')];times=[r['seconds'] for r in receipts if r['status']=='pass']
    stats={'groups':group_rows,'original_v1_exact_JSON_reproductions':len(original_matches),'verified_case_artifacts':len(summary['files']),
           'required_direction_pass':summary['required_direction_pass'],'required_direction_cases':summary['required_direction_cases'],
           'v2_scientific_pass':summary['scientific_pass'],'timing':{'paired_phase_sum_s':sum(times),'paired_phase_median_s':statistics.median(times),'paired_phase_min_s':min(times),'paired_phase_max_s':max(times),'v1_analysis_sum_s':sum(r['methods']['v1']['seconds'] for r in summary['rows']),'v2_analysis_sum_s':sum(r['methods']['v2']['seconds'] for r in summary['rows']),'busy':sum(r['status']=='busy' for r in receipts),'technical_failed':sum(r['status']=='failed' for r in receipts)},
           'original_point_task':{n:{'required':sum(r['methods'][n]['assessment']['original_point_task']['required'] for r in summary['rows'][:31]),'pass':sum(r['methods'][n]['assessment']['original_point_task']['required'] and r['methods'][n]['assessment']['original_point_task']['pass'] is True for r in summary['rows'][:31])} for n in ('v1','v2')},
           'aggregation_seconds':time.perf_counter()-start}
    io.write(P/'RESULT_STATISTICS.json',stats)
    io.write(P/'TARGET_ORDER_MECHANISM.json',{'status':'read_only_of_frozen_selected_sets','definition':'For adjacent source windows I then J, an ordered constant-phase pair exists iff endI+min(DI)<startJ+max(DJ); all pairs ordered iff endI+max(DI)<startJ+min(DJ). This does not prove causality or truth coverage.','rows':order_rows})
    print(json.dumps(stats,indent=2));print('COLLISIONS',[(r['case'],len(r['wrong_direction_windows']),r['has_unavoidable_target_collision']) for r in order_rows])
