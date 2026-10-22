"""R52 capability experiment, using the frozen old grouping/gain implementation."""
import importlib.util
import math
from pathlib import Path

path=Path(__file__).with_name('delayed_window_policy.py')
spec=importlib.util.spec_from_file_location('r53_frozen_delayed_policy',path)
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)


def direction(proposal):
    lags=proposal['lags']
    if set(lags)!={'0.3','0.5'} or any(type(x) not in (int,float) or not math.isfinite(x) for x in lags.values()):
        raise ValueError('two finite confidence lags required')
    values=list(lags.values())
    if abs(values[0]-values[1])>2:raise ValueError('inconsistent confidence lags')
    if min(values)>2:return 'delayed'
    if max(values)<-2:return 'advanced'
    raise ValueError('candidate lags must have one sign outside tolerance')


def eligible_rows(rows,threshold=.5):
    adapted=[]
    for row in rows:
        if row['baseline'] not in ('delayed_candidate','advanced_candidate'):
            continue
        candidate_row=dict(row,baseline='delayed_candidate')
        proposal=old.candidate(candidate_row,threshold)
        if proposal is not None:
            sign=direction(proposal)
            expected='delayed' if row['baseline']=='delayed_candidate' else 'advanced'
            if sign!=expected:raise ValueError('baseline/lag sign mismatch')
            adapted.append(candidate_row)
    return adapted


def candidate(row,threshold=.5):
    rows=eligible_rows([row],threshold)
    if not rows:return None
    result=old.candidate(rows[0],threshold)
    return dict(result,direction=direction(result))


def components(rows,threshold=.5):
    groups=old.components(eligible_rows(rows,threshold),threshold)
    for group in groups:
        for item in group['members']:item['direction']=direction(item)
    return groups


def persistent(current,previous):
    return direction(current)==direction(previous) and old.persistent(current,previous)


class Policy:
    def __init__(self,threshold=.5):
        self.threshold=threshold;self.previous=[];self.last_index=-1

    def update(self,index,rows):
        if index!=self.last_index+1:
            raise ValueError('observations must cover consecutive indices beginning at0')
        groups=components(rows,self.threshold)
        representatives=[g['representative'] for g in groups]
        selected=[r for r in representatives if any(persistent(r,p) for p in self.previous)]
        result={'index':index,'groups':groups,'selected':selected,
                'physical_intervals':[r['window'] for r in selected],
                'active':bool(selected),'reason':'persistent_signed_error' if selected else
                ('awaiting_persistence' if representatives else 'no_qualifying_signed_proposal')}
        self.previous=representatives;self.last_index=index
        return result
