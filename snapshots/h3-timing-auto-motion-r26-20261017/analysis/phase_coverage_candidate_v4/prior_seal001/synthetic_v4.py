"""Original43 unchanged, followed by the12 registered masked controls."""
import copy
import numpy as np
from bindings import ORIGINAL_SYNTH

def cases():
    original=ORIGINAL_SYNTH.cases();rows=list(original)
    for shift in (-12,-6,6,12):
        for mask in ('S','B'):
            rows.append({'id':f'mask_{mask}_true_{shift}_rot1','suite':'mask12',
                         'base_id':f'true_{shift}_rot1','mask':mask,'mask_task':'positive'})
    for base,mask in [('old8_b8_a0.1_s1','S'),('constant_rotation','S'),
                      ('local_zero_smooth_shape','A'),('local_zero_abrupt_shape','A')]:
        rows.append({'id':f'mask_{mask}_{base}','suite':'mask12','base_id':base,'mask':mask,'mask_task':'zero'})
    assert len(rows)==55
    return rows

def parent(case):
    if case.get('suite')=='mask12':return next(c for c in ORIGINAL_SYNTH.cases() if c['id']==case['base_id'])
    return case

def build(case):
    source,target,truth,plateaus=ORIGINAL_SYNTH.build(parent(case))
    if case.get('suite')!='mask12':return source,target,truth,plateaus
    target=copy.deepcopy(target)
    if case['mask']=='S':mask=np.isin(np.arange(141),[35,70,105])[:,None]*np.ones((1,4),bool)
    elif case['mask']=='B':mask=((np.arange(141)>=60)&(np.arange(141)<=62))[:,None]*np.ones((1,4),bool)
    elif case['mask']=='A':
        mask=np.zeros((141,4),bool);u=np.arange(24,117)
        q=np.sum((source['directions'][u-12]-target['directions'][u])**2,axis=2)-np.sum((source['directions'][u]-target['directions'][u])**2,axis=2)
        for b in range(4):mask[u[np.lexsort((u,-q[:,b]))[:14]],b]=True
    else:raise ValueError('Unknown registered mask')
    target['directions'][mask]=np.nan;target['confidence'][mask]=0
    return source,target,truth,plateaus
