"""CPU-only reference policy for the declared automatic-control baseline.

Inputs are current-state detector results. This module does not perform model
inference or claim that the detector proposals are ground-truth action errors.
"""
PARTS={'left_arm_direction':{'left'},'right_arm_direction':{'right'},
       'arm_direction':{'left','right'}}

def candidate(row,threshold=.5):
    if row['status']!='measured' or row['baseline']!='delayed_candidate' or row['min_gain']<=threshold:
        return None
    comparisons=[r for d in row['comparison'].values() for r in d['null_comparisons']]
    absolute=min(r['null_cost']-r['proposal_cost'] for r in comparisons)
    if absolute<=0:raise ValueError('positive normalized gain has nonpositive absolute gain')
    return {'window':list(row['window']),'feature':row['feature'],
            'min_gain':row['min_gain'],'absolute_gain':absolute,
            'lags':{c:d['proposal_lag'] for c,d in row['comparison'].items()}}

def components(rows,threshold=.5):
    selected=[x for r in rows if (x:=candidate(r,threshold)) is not None]
    selected.sort(key=lambda x:(x['window'][0],x['window'][1],x['feature']))
    groups=[]
    for item in selected:
        a,b=item['window']
        if groups and a<=groups[-1]['span'][1]:
            groups[-1]['span'][1]=max(groups[-1]['span'][1],b)
            groups[-1]['members'].append(item)
        else:groups.append({'span':[a,b],'members':[item]})
    for group in groups:
        group['representative']=min(group['members'],key=lambda x:(-x['absolute_gain'],
            x['window'][1]-x['window'][0]+1,x['window'][0],x['feature']))
    return groups

def persistent(current,previous):
    a,b=current['window'];c,d=previous['window']
    shared=max(0,min(b,d)-max(a,c)+1)
    return bool(PARTS[current['feature']] & PARTS[previous['feature']]) and \
        shared/min(b-a+1,d-c+1)>=.5

class Policy:
    def __init__(self,threshold=.5):
        self.threshold=threshold;self.previous=[];self.last_index=-1

    def update(self,index,rows):
        if index!=self.last_index+1:
            raise ValueError('observations must cover actual consecutive indices beginning at0')
        groups=components(rows,self.threshold)
        representatives=[g['representative'] for g in groups]
        selected=[r for r in representatives if any(persistent(r,p) for p in self.previous)]
        result={'index':index,'groups':groups,'selected':selected,
                'physical_intervals':[r['window'] for r in selected],
                'active':bool(selected),'reason':'persistent_delay' if selected else
                ('awaiting_persistence' if representatives else 'no_qualifying_delayed_proposal')}
        self.previous=representatives;self.last_index=index
        return result
