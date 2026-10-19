"""Read frozen policy outputs to explain candidate representative switching."""
from collections import Counter
import gzip,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'audit/consumer_attempt1'
read=lambda p:json.loads(Path(p).read_text())
def load(rep,i):
    path=ROOT/'results/attempt1'/rep/f'step{i:03d}.json.gz'
    with gzip.open(path,'rt') as f:return json.load(f)
records={};rows_equal=[];decisions_equal=[]
for rep in ('original','visible'):
    rows=[];previous=[]
    for i in range(20):
        result=load(rep,i);o,d=result['observation'],result['decision'];reps=[g['representative'] for g in d['groups']]
        alternatives=[]
        for row in o['windows']:
            if row['window']==[44,59] and row['status']=='measured':
                c=[v for x in row['comparison'].values() for v in x['null_comparisons']]
                alternatives.append({'feature':row['feature'],'min_gain':row['min_gain'],'qualified_gain':row['min_gain']>.5,
                                     'absolute_gain':min(x['null_cost']-x['proposal_cost'] for x in c),
                                     'lags':{k:v['proposal_lag'] for k,v in row['comparison'].items()}})
        rows.append({'index':i,'reason':d['reason'],'active':d['active'],'previous_representatives':previous,'current_representatives':reps,
                     'same_window_alternatives':alternatives})
        previous=reps
    records[rep]=rows
for i in range(20):
    a,b=load('original',i),load('visible',i)
    rows_equal.append(a['observation']['windows']==b['observation']['windows']);decisions_equal.append(a['decision']==b['decision'])
z=load('original',0)['observation']['windows'];measured=[r for r in z if r['status']=='measured']
counts=Counter(r['status'] for r in z)
first=load('original',1); proposals=first['decision']['groups']
out={'schema':'r81-representative-continuity-diagnosis-v1','all20_observation_rows_equal':all(rows_equal),'all20_policy_decisions_equal':all(decisions_equal),
     'first_qualified_candidate_index':1,'first_candidate_group_representatives':[g['representative'] for g in proposals],
     'index0_final_row_status_counts':dict(counts),'index0_max_min_gain_among_measured':max((r['min_gain'] for r in measured),default=None),
     'records':records,'interpretation':'At indices4/8 best absolute-gain representative changes right to left in the same physical window; indices5/9 reverse it. The original shared-arm persistence therefore fails despite qualifying alternatives. No policy/threshold was changed. Index1-to2 lag values differ4frames; existing persistence checks sign, shared arm and overlap, not lag-magnitude stability.'}
(OUT/'POLICY_CONTINUITY_DIAGNOSIS.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='records'},indent=2))
