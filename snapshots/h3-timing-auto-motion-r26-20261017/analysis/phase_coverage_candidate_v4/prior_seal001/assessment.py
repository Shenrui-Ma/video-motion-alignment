"""Keep old verdicts and report the changed witness semantics explicitly."""
import numpy as np
from bindings import ORIGINAL_EVAL,BASE
from synthetic_v4 import parent

def assess(case,result,evidence,truth,plateaus,method):
    original=parent(case)
    if original.get('suite')=='local12':legacy=ORIGINAL_EVAL.local_verdict(original,result,evidence,truth,plateaus)
    else:legacy={'original_point_task':ORIGINAL_EVAL.original_point_verdict(original,result,evidence),
                 'direction_task':ORIGINAL_EVAL.original_direction_verdict(original,result,evidence)}
    t=np.arange(141);windows=[];coverage=[];witness_ok=True
    for row in result['selected']:
        part=list(BASE.PARTS).index(row['part']);frames=np.arange(row['start'],row['end']+1)
        phase=truth['source_phase'][frames,part];sign=1 if row['direction']=='delay' else -1
        correct=(np.abs(phase)>2)&(np.sign(phase)==sign)
        if method=='v4':
            i=row['diagnostic_best_lag']+24
            masks=evidence[row['part']+'__witness_mask'][i,:,row['start']:row['end']+1]
            ok=bool(masks.any(axis=-1).all())
        else:ok=bool(evidence[row['part']+'__common_mask'][frames].any(axis=-1).all())
        witness_ok&=ok
        windows.append({'part':row['part'],'start':row['start'],'end':row['end'],
                        'direction':sign,'purity':float(correct.mean()),'witness_no_empty_frame':ok,
                        'old49_common_bridge':not bool(evidence[row['part']+'__common_mask'][frames].any(axis=-1).all()),
                        'truth_phase':phase.tolist()})
    scopes=[]
    if plateaus:
        for plateau in plateaus:
            scopes.append((plateau['part'],(t>=plateau['source_start'])&(t<=plateau['source_end']),np.sign(plateau['true_lag']),plateau))
    elif original['expected'] in ('true_shift','diagnostic','partial'):
        lag=original['truth'];valid=(t+lag>=0)&(t+lag<141)
        for part in BASE.PARTS:scopes.append((part,valid,np.sign(lag),{'true_lag':lag}))
    for part,mask,sign,meta in scopes:
        covered=np.zeros(141,bool)
        for row in result['selected']:
            if row['part']==part and (1 if row['direction']=='delay' else -1)==sign:covered[row['start']:row['end']+1]=True
        coverage.append({'part':part,'truth':meta,'physical_frames':int(mask.sum()),
                         'correct_covered_frames':int((mask&covered).sum()),
                         'physical_fraction':float((mask&covered).sum()/mask.sum()) if mask.any() else None})
    expected=original['expected'];checks={'witness_no_empty_frame':witness_ok}
    if expected in ('zero','constant_rotation','uniform','periodic','fully_missing','local_zero'):checks['K_zero']=result['K']==0
    positive=expected in ('true_shift','local_positive')
    if positive:
        checks['all_scopes_half_covered']=bool(coverage) and all(c['physical_fraction'] is not None and c['physical_fraction']>=.5 for c in coverage)
        checks['all_selected_direction_purity80']=bool(windows) and all(w['purity']>=.8 for w in windows)
    safety={'witness_no_empty_frame':witness_ok,'all_selected_direction_purity80':all(w['purity']>=.8 for w in windows)}
    if 'K_zero' in checks:safety['K_zero']=checks['K_zero']
    return {'legacy_assessment':legacy,'direction_task':{'checks':checks,'pass':all(checks.values()),
            'required':expected not in ('diagnostic','local_occlusion')},
            'online_safety':{'checks':safety,'pass':all(safety.values())},'selected_windows':windows,
            'physical_coverage':coverage,'original_expected':expected,'original_case_id':original['id']}
