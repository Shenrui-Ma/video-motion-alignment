"""Exact maximum-weight chain with robust source/target interval ordering."""
import hashlib
import json
import math


def key(row):
    return row['start'],row['end'],abs(row['lag']),row['lag'],row['part']


def envelope(row):
    return row['start']+min(row['phase_set']),row['end']+max(row['phase_set'])


def relation(left,right):
    source=left['end']<right['start']
    some=left['end']+min(left['phase_set'])<right['start']+max(right['phase_set'])
    all_phases=left['end']+max(left['phase_set'])<right['start']+min(right['phase_set'])
    status=('SOURCE_OVERLAP' if not source else 'ROBUST_ORDERED' if all_phases else
            'SET_ORDER_AMBIGUITY' if some else 'NO_ORDERED_PHASE_PAIR')
    return {'source_disjoint':source,'some_phase_pair_ordered':some,'every_phase_pair_ordered':all_phases,'status':status}


def better(candidate,winner):
    return candidate[0]>winner[0]+1e-12 or (abs(candidate[0]-winner[0])<=1e-12 and
        (len(candidate[1]),tuple(map(key,candidate[1])))<(len(winner[1]),tuple(map(key,winner[1]))))


def compact(row):
    return {k:row[k] for k in ('part','start','end','lag','phase_set','value')}


def solve(rows,total=141):
    rows=sorted(rows,key=key)
    if len({r['part'] for r in rows})>1:raise ValueError('Solve each limb independently')
    for row in rows:
        if not 0<=row['start']<=row['end']<total:raise ValueError('Invalid source interval')
        if not row['phase_set'] or not all(isinstance(d,int) for d in row['phase_set']):raise ValueError('Invalid phase set')
        if not math.isfinite(row['value']) or row['value']<=1e-12:raise ValueError('Candidate must have positive finite value')
    starts=[[] for _ in range(total)];ends=[[] for _ in range(total)]
    for index,row in enumerate(rows):starts[row['start']].append(index);ends[row['end']].append(index)
    coordinates=sorted({envelope(row)[1] for row in rows})
    slots={value:index for index,value in enumerate(coordinates)}
    completed=[(0.,[]) for _ in coordinates];states={};winner=(0.,[])
    for a in range(total):
        # All activated rows end before a; their own predecessor states are finalized.
        if a:
            for index in ends[a-1]:
                slot=slots[envelope(rows[index])[1]];candidate=states[index]
                if better(candidate,completed[slot]):completed[slot]=candidate
        prefix=[];running=(0.,[])
        for state in completed:
            if better(state,running):running=state
            prefix.append(running)
        import bisect
        for index in starts[a]:
            row=rows[index];position=bisect.bisect_left(coordinates,envelope(row)[0])-1
            predecessor=prefix[position] if position>=0 else (0.,[])
            state=(predecessor[0]+row['value'],predecessor[1]+[row]);states[index]=state
            if better(state,winner):winner=state
    compact_rows=[compact(r) for r in rows]
    fingerprint=hashlib.sha256(json.dumps(compact_rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    selected=[]
    for row in winner[1]:selected.append(dict(row,target_envelope=list(envelope(row))))
    pairs=[relation(a,b) for a,b in zip(selected,selected[1:])]
    if any(p['status']!='ROBUST_ORDERED' for p in pairs):raise AssertionError('Invalid selected chain')
    return {'objective':winner[0],'selected':selected,'K':len(selected),
            'selector_audit':{'all_candidates':compact_rows,'candidate_sha256':fingerprint,
                              'selected_pair_relations':pairs,'candidate_count':len(rows),
                              'scope':'per-limb selected anomaly windows only; singleton order is vacuous'}}
