"""Independent review only: decimal active-set oracle and actual wrapper replay."""
import copy, decimal, hashlib, json, math, os, pathlib, random, sys
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=pathlib.Path('/tmp/h3_fixed_budget_cpu_20261023')
sys.path.insert(0,str(ROOT))
import torch
from feature_gain_field_fixed_budget.budget import solve_radial, fixed_budget_alpha
from feature_gain_field_fixed_budget.audit import check_budget, check_budget_layer

def decimal_oracle(a,e,mask):
    """Enumerate saturated subsets ordered by breakpoints, no root iteration."""
    with decimal.localcontext() as context:
        context.prec=100
        D=decimal.Decimal;aa=[D.from_float(x) for x in a];ee=[D.from_float(x) for x in e]
        cap=D('0.5');prior=D('0.25');selected=[i for i,m in enumerate(mask) if m]
        support=[i for i in selected if ee[i]>0 and aa[i]>0]
        target=prior**2*sum((ee[i] for i in selected),D(0))
        order=sorted(support,key=lambda i:cap/aa[i])
        fixed=set()
        for j in range(len(order)+1):
            remain=[i for i in support if i not in fixed]
            rhs=target-cap**2*sum((ee[i] for i in fixed),D(0))
            denominator=sum((ee[i]*aa[i]**2 for i in remain),D(0))
            if rhs>=0 and denominator>0:
                c=(rhs/denominator).sqrt()
                lo=max((cap/aa[i] for i in fixed),default=D(0))
                hi=min((cap/aa[i] for i in remain),default=D('Infinity'))
                if lo<=c<=hi:
                    return [float(min(cap,c*aa[i])) if mask[i] else .25 for i in range(len(a))]
            if j<len(order):fixed.add(order[j])
        raise AssertionError('no active-set oracle solution')

checks=[]
def note(name,**kw):checks.append({'name':name,'passed':True,**kw})
def rejects(label,call):
    try:call()
    except (ValueError,ArithmeticError,KeyError,OverflowError):note(label)
    else:raise AssertionError('accepted corruption '+label)

rng=random.Random(903117);max_error=0.;capped=0
for trial in range(300):
    n=rng.randint(4,19);mask=[False]+[rng.random()>.15 for _ in range(n-2)]+[False]
    if not any(mask):mask[1]=True
    a=[10**rng.uniform(-140,math.log10(.5)) if m else .25 for m in mask]
    e=[10**rng.uniform(-70,70) for _ in mask]
    actual,info=solve_radial(a,e,mask)
    oracle=decimal_oracle(a,e,mask)
    error=max(abs(x-y) for x,y in zip(actual,oracle));max_error=max(max_error,error)
    assert error<4e-12,(trial,error)
    assert not info['fallback_to_prior'];capped+=info['solver']=='bounded_log_bisection'
note('decimal_active_set_oracle_300',max_abs_error=max_error,capped_cases=capped)

# The maximal finite source energy need not overflow the weighted target.
y,info=fixed_budget_alpha(torch.tensor([.25,.1,.4,.25],dtype=torch.float64),
    torch.tensor([0,8e307,8e307,0],dtype=torch.float64),torch.tensor([False,True,True,False]))
assert math.isfinite(info['applied_total_energy']) and abs(info['energy_relative_error'])<3e-7
note('large_finite_total_safe')
rejects('finite_terms_overflow_rejected',lambda:solve_radial([.25,.1,.4,.25],[0,1e308,1e308,0],[False,True,True,False]))
for label,a,e,expected in [('zero_support',[.25,0.,0.,.25],[1,2,3,1],'zero_candidate_support'),
                          ('unreachable',[.25,0.,.1,.25],[1,9,1,1],'insufficient_positive_support'),
                          ('zero_energy',[.25,.2,.4,.25],[0,0,0,0],'near_zero_energy')]:
    y,info=solve_radial(a,e,[False,True,True,False]);assert y==[.25]*4 and info['fallback_reason']==expected and info['log_scale'] is None
    note(label+'_honest_fallback')
y,info=solve_radial([.25,5e-324,1e-323,.25],[1,1,2,1],[False,True,True,False])
assert all(math.isfinite(v) for v in y) and info['scale'] is None and info['log_scale']>709
note('smallest_positive_candidates_log_scale')

fixture=ROOT/'fixture/budget_complete.json';raw=fixture.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='c13d7c84d3a0e372f0e803570042b1fb506c5386bb1cb08ae175da1065ca517f'
doc=json.loads(raw);proof=check_budget(doc);assert proof['blocks']==1000 and proof['forwards']==20
note('actual_20x50_wrapper_fixture',proof=proof)
row=next(r for f in doc['feature_forward_summaries'] for r in f['layers'] if max(r['candidate_alpha'])-min(r['candidate_alpha'])>.01)

def energy_logs(r):
    b=r['fixed_budget'];e=r['bin_energy'];a=r['alpha'];candidate=r['candidate_alpha'];mask=b['modifiable_mask']
    b['applied_alpha']=copy.deepcopy(a);b['candidate_alpha']=copy.deepcopy(candidate)
    b['applied_total_energy']=math.fsum(x*y*y for x,y in zip(e,a));r['applied_energy']=b['applied_total_energy']
    b['candidate_total_energy']=math.fsum(x*y*y for x,y in zip(e,candidate))
    b['applied_modifiable_energy']=math.fsum(x*y*y for x,y,m in zip(e,a,mask) if m)
    b['candidate_modifiable_energy']=math.fsum(x*y*y for x,y,m in zip(e,candidate,mask) if m)
    b['energy_error']=b['applied_total_energy']-b['target_total_energy']
    b['energy_relative_error']=b['energy_error']/b['target_total_energy']

# Rotate two sqrt(E)*a coordinates: preserves exactly the norm but is not radial.
bad=copy.deepcopy(row);ids=[i for i,m in enumerate(bad['fixed_budget']['modifiable_mask']) if m];i,j=ids[:2]
e=bad['bin_energy'];a=bad['alpha'];z1,z2=math.sqrt(e[i])*a[i],math.sqrt(e[j])*a[j];theta=.02
bad['alpha'][i]=(z1*math.cos(theta)-z2*math.sin(theta))/math.sqrt(e[i])
bad['alpha'][j]=(z1*math.sin(theta)+z2*math.cos(theta))/math.sqrt(e[j]);energy_logs(bad)
assert abs(bad['fixed_budget']['energy_relative_error'])<3e-7
rejects('same_energy_nonradial_coherent_forgery',lambda:check_budget_layer(bad))
# Change both candidate and applied coherently using the true radial solver;
# only the unchanged QP evidence exposes the fabricated candidate.
bad=copy.deepcopy(row);bad['candidate_alpha'][i]=min(.49,bad['candidate_alpha'][i]+.04)
a,info=fixed_budget_alpha(torch.tensor(bad['candidate_alpha'],dtype=torch.float32),torch.tensor(bad['bin_energy'],dtype=torch.float32),torch.tensor(bad['fixed_budget']['modifiable_mask']))
bad['alpha']=a.tolist();bad['fixed_budget']=info;bad['candidate_alpha']=info['candidate_alpha'];bad['control']['alpha']=info['candidate_alpha'];energy_logs(bad)
rejects('coherent_candidate_applied_energy_forgery_qp',lambda:check_budget_layer(bad))
bad=copy.deepcopy(doc);bad['feature_forward_summaries'][10]['layers'][3]['control']['anchor_step'][1]=19
rejects('future_anchor_rejected',lambda:check_budget(bad))
bad=copy.deepcopy(doc);bad['independent_field_trajectory_energy_matched']=True
rejects('cross_trajectory_claim_rejected',lambda:check_budget(bad))
bad=copy.deepcopy(doc);bad['feature_forward_summaries'][1]['layers'][0]['finite_output']=False
rejects('nonfinite_runtime_rejected',lambda:check_budget(bad))
assert not torch.cuda.is_initialized()
print(json.dumps({'status':'passed','checks':checks,'cuda_initialized':False,'fixture_sha256':hashlib.sha256(raw).hexdigest(),
    'runtime_asset_shas':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'feature_gain_field_fixed_budget').glob('*.py')}},indent=2))
