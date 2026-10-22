"""Compare frozen proposals with a nuisance-offset diagnostic on common support."""
from pathlib import Path
import json
import numpy as np
import diagnose as d
ROOT=Path(__file__).resolve().parent


def at(features, indices, joints):
    x,c=features
    valid=(indices>=0)&(indices<len(x))
    values=np.full((len(indices),len(joints),2),np.nan)
    confidence=np.zeros((len(indices),len(joints)))
    values[valid]=x[indices[valid]][:,joints]
    confidence[valid]=c[indices[valid]][:,joints]
    return values,confidence


def compare(source,target,window,arm,lag,threshold):
    joints={'left':[0,1],'right':[2,3],'both':[0,1,2,3]}[arm]
    indices=np.arange(window[0],window[1]+1)
    s,sc=at(source,indices,joints);p,pc=at(target,indices+lag,joints)
    rows=[]
    for epsilon in range(-2,3):
        n,nc=at(target,indices+epsilon,joints)
        valid=np.isfinite(s).all(-1)&np.isfinite(p).all(-1)&np.isfinite(n).all(-1)
        w=np.where(valid,np.minimum(np.minimum(sc,pc),nc),0)
        w=np.where(w>=threshold,w,0)
        cp=d.costs(s,p,w);cn=d.costs(s,n,w)
        row={'null_lag':epsilon,'coverage':float(valid.mean()),'valid_frames':int((w.sum(-1)>0).sum())}
        if cp is None or cn is None or valid.mean()<.8 or (w.sum(-1)>0).sum()<8:
            row['status']='unknown_support'
        else:
            row.update(status='measured',raw_proposal_cost=cp['weighted_direction_error'],raw_null_cost=cn['weighted_direction_error'],centered_proposal_cost=cp['centered_direction_error'],centered_null_cost=cn['centered_direction_error'])
            row['raw_gain']=(row['raw_null_cost']-row['raw_proposal_cost'])/max(row['raw_null_cost'],1e-8)
            row['centered_gain']=(row['centered_null_cost']-row['centered_proposal_cost'])/max(row['centered_null_cost'],1e-8)
        rows.append(row)
    good=all(x['status']=='measured' for x in rows)
    return {'null_comparisons':rows,'status':'measured' if good else 'unknown','min_raw_gain':min(x['raw_gain'] for x in rows) if good else None,'min_centered_gain':min(x['centered_gain'] for x in rows) if good else None}


def main():
    d.sanity()
    # These are actual frozen proposals, taken from the archived original decisions.
    cases=[(1,[44,59],'left',15,.7717598078189633),(3,[44,59],'right',14,.9211009775663938),(4,[40,55],'right',12,.9175034033404228),(10,[4,19],'left',21,.5116731856735194)]
    rows=[]
    for index,window,arm,lag,actual_gain in cases:
        pose=ROOT/'inputs'/f'index{index:02d}.pose.json'
        measurements={}
        for threshold in [.3,.5]:
            measurements[str(threshold)]=compare(d.directions(ROOT/'inputs/source.pose.json',threshold),d.directions(pose,threshold),window,arm,lag,threshold)
        raw=min(x['min_raw_gain'] for x in measurements.values())
        assert abs(raw-actual_gain)<1e-10,(index,raw,actual_gain)
        centered=min(x['min_centered_gain'] for x in measurements.values())
        row={'index':index,'window':window,'arm':arm,'actual_proposal_lag':lag,'pose_sha256':d.digest(pose),'actual_min_raw_gain':actual_gain,'raw_gain_reproduced':raw,'min_centered_gain':centered,'passes_same_gain_threshold_0_5':centered>.5,'measurements':measurements}
        rows.append(row)
        print(json.dumps({k:row[k] for k in ['index','window','actual_proposal_lag','raw_gain_reproduced','min_centered_gain','passes_same_gain_threshold_0_5']}))
    result={'scope':'Fixed-trajectory, selected-proposal diagnostic only. Does not replay persistence, replace the observer or rerun a changed closed-loop trajectory.','script_sha256':d.digest(__file__),'diagnostic_helpers_sha256':d.digest(ROOT/'diagnose.py'),'source_pose_sha256':d.digest(ROOT/'inputs/source.pose.json'),'existing_threshold_reused':.5,'new_threshold_tuning':False,'all_original_proposal_gains_reproduced':True,'rows':rows}
    (ROOT/'CENTERED_SUPPORT_RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')

if __name__=='__main__':main()
