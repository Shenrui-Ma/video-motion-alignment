"""Frozen point-task and new direction-task evidence are reported separately."""
import copy
import numpy as np
from frozen import SYNTH
from synthetic_v2 import PARTS

def row_lag(row):return row.get('diagnostic_best_lag',row.get('lag'))
def row_sign(row):return 1 if row.get('direction')=='delay' else (-1 if row.get('direction')=='advance' else int(np.sign(row['lag'])))
def verdict(checks,required=True):
    return {'checks':{k:bool(v) for k,v in checks.items()},'pass':bool(all(checks.values())) if checks else None,'required':required}

def original_point_verdict(case,result,evidence):
    view=copy.deepcopy(result)
    for row in view['selected']:row['lag']=row_lag(row)
    # A removed reason must remain a failed old reason check, not a renamed success.
    for part in view['parts'].values():part['counts'].setdefault('UNKNOWN_IDENTIFIABILITY',0)
    return SYNTH.verdict(case,view,evidence)

def original_direction_verdict(case,result,evidence):
    expected=case['expected'];checks={};truth=case['truth']
    if expected in ('zero','constant_rotation','uniform','periodic','fully_missing'):checks['K_zero']=result['K']==0
    if expected=='constant_rotation':checks['null_profile_exact']=all(max(p['diagnostics']['central_null_profile_rms'])<=2e-7 for p in result['parts'].values())
    if expected in ('true_shift','diagnostic'):
        checks['both_limbs']=all(p['K']>=1 for p in result['parts'].values())
        checks['all_selected_correct_direction']=bool(result['selected']) and all(row_sign(w)==np.sign(truth) for w in result['selected'])
        checks['truth_in_each_phase_set']=bool(result['selected']) and all(truth in w['phase_set'] for w in result['selected'])
    if expected=='fully_missing':checks['support_unknown']=all(p['counts']['UNKNOWN_SUPPORT']>0 for p in result['parts'].values())
    if expected=='partial':
        checks['no_unknown_bridge']=all(evidence[w['part']+'__common_mask'][w['start']:w['end']+1].any(axis=1).all() for w in result['selected'])
        checks['invalid_removed']=all(np.isfinite(evidence[p+'__common_mask']).all() for p in result['parts'])
    return verdict(checks,expected!='diagnostic')

def local_verdict(case,result,evidence,truth,plateaus):
    t=np.arange(141);windows=[];per_plateau=[];by_region={};no_bridges=True
    for row in result['selected']:
        part=PARTS.index(row['part']);frames=np.arange(row['start'],row['end']+1)
        true_phase=truth['source_phase'][frames,part]
        correct=(np.abs(true_phase)>2)&(np.sign(true_phase)==row_sign(row))
        point=np.abs(true_phase-row_lag(row))<=2
        windows.append({'part':row['part'],'start':row['start'],'end':row['end'],
            'direction':int(row_sign(row)),'true_phase_min':float(true_phase.min()),'true_phase_max':float(true_phase.max()),
            'direction_fraction':float(correct.mean()),'point_within2_fraction_diagnostic':float(point.mean())})
        hits=[p for p in plateaus if p['part']==row['part'] and max(p['source_start'],row['start'])<=min(p['source_end'],row['end'])]
        for left,right in zip(hits,hits[1:]):
            between=(t>left['source_end'])&(t<right['source_start'])&(t>=row['start'])&(t<=row['end'])
            if np.any(between&(np.abs(truth['source_phase'][:,part])<=2)):no_bridges=False
    for plateau in plateaus:
        part=PARTS.index(plateau['part']);mask=evidence[plateau['part']+'__common_mask'].any(axis=1)
        nominal=(t>=plateau['source_start'])&(t<=plateau['source_end']);usable=nominal&mask
        covered=np.zeros(141,bool);point_covered=np.zeros(141,bool)
        for row in result['selected']:
            if row['part']!=plateau['part']:continue
            inside=(t>=row['start'])&(t<=row['end'])
            if row_sign(row)==np.sign(plateau['true_lag']):covered|=inside
            if abs(row_lag(row)-plateau['true_lag'])<=2:point_covered|=inside
        denominator=int(usable.sum())
        per_plateau.append(plateau|{'nominal_frames':int(nominal.sum()),'common_supported_frames':denominator,
            'direction_covered_frames':int((usable&covered).sum()),
            'direction_fraction':float((usable&covered).sum()/denominator) if denominator else None,
            'point_within2_fraction_diagnostic':float((usable&point_covered).sum()/denominator) if denominator else None})
    for part_index,part in enumerate(PARTS):
        selected=np.zeros(141,bool)
        for row in result['selected']:
            if row['part']==part:selected[row['start']:row['end']+1]=True
        known=evidence[part+'__common_mask'].any(axis=1)
        regions={'plateau':truth['plateau'][:,part_index],
                 'transition':truth['transition'][:,part_index],
                 'remaining':~(truth['plateau'][:,part_index]|truth['transition'][:,part_index])}
        by_region[part]={name:{'physical_frames':np.flatnonzero(mask).tolist(),
             'true_phase':truth['source_phase'][mask,part_index].tolist(),'common_supported_frames':np.flatnonzero(mask&known).tolist(),
             'selected_frames':np.flatnonzero(mask&selected).tolist()} for name,mask in regions.items()}
    no_unknown=all(evidence[w['part']+'__common_mask'][w['start']:w['end']+1].any(axis=1).all() for w in result['selected'])
    checks={'no_unknown_bridge':no_unknown}
    if case['expected']=='local_zero':checks['K_zero']=result['K']==0
    if case['expected']=='local_positive':
        checks.update(each_plateau_half_covered=bool(per_plateau) and all(p['direction_fraction'] is not None and p['direction_fraction']>=.5 for p in per_plateau),
            each_selected_direction_fraction_80=bool(windows) and all(w['direction_fraction']>=.8 for w in windows),
            no_cross_null_plateau_merge=no_bridges)
    point_checks={}
    if case['expected']=='local_positive':
        point_checks={'each_plateau_half_point_covered':all(p['point_within2_fraction_diagnostic'] is not None and p['point_within2_fraction_diagnostic']>=.5 for p in per_plateau),
                      'each_selected_point_fraction_80':bool(windows) and all(w['point_within2_fraction_diagnostic']>=.8 for w in windows),'no_cross_null_plateau_merge':no_bridges}
    if case['expected']=='local_zero':point_checks={'K_zero':result['K']==0}
    return {'direction_task':verdict(checks,case['expected']!='local_occlusion'),
            'draft_point_task_diagnostic':verdict(point_checks,False),'plateaus':per_plateau,'selected_windows':windows,
            'regions':by_region,'transition_constant_lag_requirement':False}
