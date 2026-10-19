"""Exact original31 plus12 analytic, monotone local-warp cases."""
import numpy as np
from frozen import SYNTH

PARTS=('left_arm','right_arm')

def bump(D,a,R,b):return {'D':D,'a':a,'R':R,'b':b}
def local_cases():
    rows=[]
    for D in (6,-6,12,-12):
        row=bump(D,24,10 if abs(D)==6 else 20,58 if abs(D)==6 else 76)
        rows.append({'id':f'local_single_{D}','group':'local_single','bumps':[[row],[row]],'expected':'local_positive'})
    first=bump(6,24,10,46)
    rows.extend([
        {'id':'local_double_6_6_left','group':'local_multi','bumps':[[first,bump(6,64,10,100)],[]],'expected':'local_positive'},
        {'id':'local_double_6_12_left','group':'local_multi','bumps':[[first,bump(12,64,20,100)],[]],'expected':'local_positive'},
        {'id':'local_separate_arms','group':'local_multi','bumps':[[first],[bump(12,64,20,100)]],'expected':'local_positive'},
        {'id':'local_zero_identity','group':'local_zero','bumps':[[],[]],'expected':'local_zero'},
        {'id':'local_zero_rotation','group':'local_zero','bumps':[[],[]],'rotation':SYNTH.ROTATION.tolist(),'expected':'local_zero'},
        {'id':'local_zero_smooth_shape','group':'local_zero','bumps':[[],[]],'shape_edit':'smooth','expected':'local_zero'},
        {'id':'local_zero_abrupt_shape','group':'local_zero','bumps':[[],[]],'shape_edit':'abrupt','expected':'local_zero'},
        {'id':'local_separate_arms_occluded','group':'local_occlusion','bumps':[[first],[bump(12,64,20,100)]],'missing':[60,65],'expected':'local_occlusion'},
    ])
    for row in rows:row.update(truth='analytic_source_phase_per_limb',suite='local12')
    assert len(rows)==12
    return rows

def cases():return SYNTH.cases()+local_cases()

def smooth(u):
    u=np.clip(u,0,1)
    return 3*u*u-2*u*u*u
def smooth_derivative(u):
    v=np.clip(u,0,1)
    return np.where((u>0)&(u<1),6*v*(1-v),0)
def delay(t,bumps):
    t=np.asarray(t,dtype=float);d=np.zeros_like(t);derivative=np.zeros_like(t)
    for row in bumps:
        D,a,R,b=(row[k] for k in ('D','a','R','b'))
        d+=D*(smooth((t-a)/R)-smooth((t-b)/R))
        derivative+=D/R*(smooth_derivative((t-a)/R)-smooth_derivative((t-b)/R))
    return d,derivative
def inverse_w(s,bumps):
    s=np.asarray(s,dtype=float);lo=np.zeros_like(s);hi=np.full_like(s,140)
    for _ in range(60):
        middle=(lo+hi)/2;w=middle-delay(middle,bumps)[0]
        lo=np.where(w<s,middle,lo);hi=np.where(w<s,hi,middle)
    return (lo+hi)/2
def angle(t,bone):
    return .9*np.sin(.23*t+.17*bone)+.45*np.sin(.057*t+.0009*t*t+.31*bone)

def build_local(case):
    source=SYNTH.features('identifiable');t=np.arange(141,dtype=float)
    target_angle=np.zeros((141,4));phase=np.zeros((141,2));ds=np.zeros((141,2));wd=np.ones((141,2))
    transition=np.zeros((141,2),bool);plateau=np.zeros((141,2),bool);metadata=[]
    for part,rows in enumerate(case['bumps']):
        d,dp=delay(t,rows);ds[:,part]=d;wd[:,part]=1-dp
        inverse=inverse_w(t,rows);phase[:,part]=inverse-t
        for bone in (part*2,part*2+1):target_angle[:,bone]=angle(t-d,bone)
        for index,row in enumerate(rows):
            D,a,R,b=(row[k] for k in ('D','a','R','b'))
            ps,pe=a+R-D,b-D
            plateau[:,part]|=(t>=ps)&(t<=pe)
            transition[:,part]|=((t>a)&(t<ps))|((t>pe)&(t<b+R))
            metadata.append({'part':PARTS[part],'index':index,'target_start':a+R,'target_end':b,
                'source_start':ps,'source_end':pe,'true_lag':D,'ramp_start':a,'ramp_end':b+R})
    if 'rotation' in case:target_angle+=np.asarray(case['rotation'])
    if case.get('shape_edit')=='smooth':target_angle[:,0]+=.3*(smooth((t-24)/10)-smooth((t-58)/10))
    if case.get('shape_edit')=='abrupt':target_angle[:,0]+=.3*((t>=40)&(t<=60))
    target={'directions':np.stack((np.cos(target_angle),np.sin(target_angle)),axis=-1),
            'confidence':np.ones((141,4)),'times':t/24}
    if 'missing' in case:
        a,b=case['missing'];target['directions'][a:b+1]=np.nan;target['confidence'][a:b+1]=0
    truth={'source_phase':phase,'target_delay':ds,'warp_derivative':wd,'transition':transition,'plateau':plateau}
    return source,target,truth,metadata

def build(case):
    if case.get('suite')=='local12':return build_local(case)
    a,b=SYNTH.build(case)
    truth={'source_phase':np.full((141,2),case['truth'],dtype=float),
           'transition':np.zeros((141,2),bool),'plateau':np.ones((141,2),bool)}
    return a,b,truth,[]
