"""Fixed synthetic cases; no real data access."""
import itertools
import numpy as np

SEED=2026101707
ROTATION=np.array([.25,-.35,.6,-.8])


def features(signal='old',shift=0,rotation=None):
    t=np.arange(141,dtype=float)[:,None]-shift
    b=np.arange(4)[None]
    if signal=='old':angle=.013*t+.00019*t*t+.17*np.sin(.083*t+.4*b)
    elif signal=='identifiable':angle=.9*np.sin(.23*t+.17*b)+.45*np.sin(.057*t+.0009*t*t+.31*b)
    elif signal=='uniform':angle=.013*t+.4*b
    elif signal=='periodic':angle=.8*np.sin(2*np.pi*t/12+.2*b)+.3*np.sin(4*np.pi*t/12+.1*b)
    else:raise ValueError(signal)
    if rotation is not None:angle=angle+np.asarray(rotation)
    return {'directions':np.stack((np.cos(angle),np.sin(angle)),axis=-1),
            'confidence':np.ones((141,4)),'times':np.arange(141)/24}


def cases():
    rows=[]
    for block,amplitude,sign in itertools.product((8,16),(.05,.1),(-1,1)):
        rotation=sign*amplitude*np.where((np.arange(141)//block)%2,-1,1)
        rows.append({'id':f'old8_b{block}_a{amplitude}_s{sign}', 'group':'old8',
                     'signal':'old','shift':0,'rotation':rotation[:,None].tolist(),
                     'expected':'zero','truth':0,'block':block,'amplitude':amplitude,'sign':sign})
    rows.append({'id':'constant_rotation','group':'constant_rotation','signal':'identifiable',
                 'shift':0,'rotation':ROTATION.tolist(),'expected':'constant_rotation','truth':0})
    for shift,rotated in itertools.product((-12,-6,6,12),(False,True)):
        rows.append({'id':f'true_{shift}_rot{int(rotated)}','group':'identifiable_true_shifts',
                     'signal':'identifiable','shift':shift,'rotation':ROTATION.tolist() if rotated else None,
                     'expected':'true_shift','truth':shift})
    for shift in (-2,-1,0,1,2):
        rows.append({'id':f'null_{shift}','group':'null_shifts','signal':'identifiable',
                     'shift':shift,'rotation':None,'expected':'zero','truth':shift})
    rows.append({'id':'uniform','group':'uniform','signal':'uniform','shift':6,
                 'rotation':ROTATION.tolist(),'expected':'uniform','truth':6})
    rows.append({'id':'periodic','group':'periodic','signal':'periodic','shift':6,
                 'rotation':None,'expected':'periodic','truth':6})
    rows.append({'id':'fully_missing','group':'occlusion_invalid','signal':'identifiable','shift':6,
                 'rotation':None,'missing':'all','expected':'fully_missing','truth':6})
    rows.append({'id':'partly_missing','group':'occlusion_invalid','signal':'identifiable','shift':6,
                 'rotation':None,'missing':[60,65],'expected':'partial','truth':6})
    rows.append({'id':'nonfinite','group':'occlusion_invalid','signal':'identifiable','shift':6,
                 'rotation':None,'invalid':True,'expected':'partial','truth':6})
    for shift in (-12,-6,6,12):
        rows.append({'id':f'old_true_{shift}','group':'old_true_shift_diagnostic','signal':'old',
                     'shift':shift,'rotation':None,'expected':'diagnostic','truth':shift})
    return rows


def build(row):
    source=features(row['signal'])
    target=features(row['signal'],row['shift'],row['rotation'])
    if row.get('missing')=='all':
        target['directions'][:]=np.nan;target['confidence'][:]=0
    elif isinstance(row.get('missing'),list):
        a,b=row['missing'];target['directions'][a:b+1]=np.nan;target['confidence'][a:b+1]=0
    if row.get('invalid'):
        target['confidence'][70,0]=np.inf
        target['confidence'][80,1]=np.nan
        target['directions'][65,2]=np.nan
    return source,target


def verdict(case,result,evidence):
    expected=case['expected']; checks={}
    if expected in ('zero','constant_rotation','uniform','periodic','fully_missing'):
        checks['K_zero']=result['K']==0
    if expected=='constant_rotation':
        checks['null_profile_exact']=all(max(p['diagnostics']['central_null_profile_rms'])<=2e-7 for p in result['parts'].values())
    if expected=='true_shift':
        checks['both_limbs']=all(p['K']>=1 for p in result['parts'].values())
        checks['all_lags_within2']=bool(result['selected']) and all(abs(w['lag']-case['truth'])<=2 for w in result['selected'])
    if expected in ('uniform','periodic','fully_missing'):
        reason={'uniform':'UNKNOWN_IDENTIFIABILITY','periodic':'UNKNOWN_MULTIPLE_PHASES','fully_missing':'UNKNOWN_SUPPORT'}[expected]
        checks['required_rejection']=all(p['counts'][reason]>0 for p in result['parts'].values())
    if expected=='partial':
        checks['no_unknown_bridge']=all(evidence[w['part']+'__common_mask'][w['start']:w['end']+1].any(axis=1).all() for w in result['selected'])
        checks['invalid_removed']=all(np.isfinite(evidence[p+'__common_mask']).all() for p in result['parts'])
    return {'checks':{k:bool(v) for k,v in checks.items()},
            'pass':all(checks.values()) if checks else None,'required':expected!='diagnostic'}
