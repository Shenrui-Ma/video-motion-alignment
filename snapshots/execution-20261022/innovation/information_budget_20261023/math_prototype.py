"""CPU-only scalar prototype; no model imports or inference integration.

Maximize sum_i weight_i * cost_i * alpha[group_i] subject to exact
sum_i weight_i * KL_i(alpha[group_i]) <= information_budget,
and optionally sum_i weight_i * alpha[group_i] <= dose_budget.
weight_i includes reference mass m_i and any fixed probe quadrature weight.
cost_i is E_p[c(j,t)], not the conditional off-target cost.
"""
import math


def logaddexp(a, b):
    hi = max(a, b)
    if hi == -math.inf:
        return hi
    return hi + math.log1p(math.exp(min(a, b) - hi))


def log1mexp(x):
    if x > 0 or not math.isfinite(x):
        raise ValueError('log probability must be finite and <= 0')
    if x == 0:
        return -math.inf
    return math.log(-math.expm1(x)) if x > -math.log(2) else math.log1p(-math.exp(x))


def kl(log_s, alpha):
    """Exact mixture KL from log same-time mass, stable even when exp(log_s)=0."""
    if not math.isfinite(log_s) or log_s > 0:
        raise ValueError('strictly positive support required; do not epsilon-clip zeros')
    if not 0 <= alpha < 1:
        raise ValueError('alpha outside [0,1)')
    if alpha == 0 or log_s == 0:
        return 0.
    log_r = logaddexp(math.log(alpha), math.log1p(-alpha) + log_s)
    complement = math.exp(log1mexp(log_s))
    value = math.exp(log_r) * (log_r - log_s)
    value += (1-alpha) * complement * math.log1p(-alpha)
    return max(0., value)  # only roundoff of the analytically nonnegative KL


def kl_prime(log_s, alpha):
    if alpha == 0 or log_s == 0:
        return 0.
    log_r = logaddexp(math.log(alpha), math.log1p(-alpha)+log_s)
    return -math.expm1(log_s) * (log_r-log_s-math.log1p(-alpha))


def kl_second(log_s, alpha):
    if log_s == 0:
        return 0.
    complement = -math.expm1(log_s)
    r = alpha + (1-alpha)*math.exp(log_s)
    return complement**2 / (r*(1-r))


def dual_alpha(log_s, cost, multiplier, dose_multiplier=0., cap=.5):
    """Exact one-row maximizer of cost*a - lambda*KL(a) - nu*a."""
    if cost <= dose_multiplier or log_s == 0:
        return 0.
    if multiplier <= 0:
        return cap
    complement = -math.expm1(log_s)
    z = (cost-dose_multiplier)/(multiplier*complement)
    cap_z = kl_prime(log_s, cap)/complement
    if z >= cap_z:
        return cap
    log_r = log_s+z
    log_den = logaddexp(log1mexp(log_s), log_r)
    return max(0., min(cap, math.exp(log_r-log_den)*(-math.expm1(-z))))


def total_kl(log_s, alpha, weights):
    return sum(w*kl(s,a) for s,a,w in zip(log_s,alpha,weights))


def total_dose(alpha, weights):
    return sum(w*a for a,w in zip(alpha,weights))


def utility(cost, alpha, weights):
    return sum(w*c*a for w,c,a in zip(weights,cost,alpha))


def solve(log_s, cost, weights=None, groups=None, information_budget=None,
          dose_budget=None, prior=.25, cap=.5, iterations=64):
    """Nested monotone dual roots. Independent or shared bin alpha variables.

    Grouping retains every sampled row's s/cost/m in objective and KL;
    replacing these by a mean probability is deliberately not implemented.
    """
    log_s=list(log_s);cost=list(cost)
    n = len(log_s)
    if not n or len(cost) != n:
        raise ValueError('nonempty equal lengths required')
    weights = [1.]*n if weights is None else list(weights)
    groups = list(range(n)) if groups is None else list(groups)
    if len(weights) != n or len(groups) != n or not 0 <= prior <= cap < 1:
        raise ValueError('invalid shapes or alpha bounds')
    if any(not math.isfinite(x) or x < 0 for x in cost+weights):
        raise ValueError('finite nonnegative costs and weights required')
    for s in log_s:
        kl(s,prior)
    group_rows = {}
    for i,g in enumerate(groups):
        group_rows.setdefault(g,[]).append(i)
    information_budget = (total_kl(log_s,[prior]*n,weights)
        if information_budget is None else information_budget)
    if not math.isfinite(information_budget) or information_budget < 0:
        raise ValueError('finite nonnegative information budget required')
    if dose_budget is not None and (not math.isfinite(dose_budget) or dose_budget < 0):
        raise ValueError('finite nonnegative dose budget required')

    def allocate(lam,nu):
        answer=[prior]*n
        for ids in group_rows.values():
            active=[i for i in ids if weights[i]>0]
            if not active:
                continue
            if len(active)==1:
                i=active[0];a=dual_alpha(log_s[i],cost[i],lam,nu,cap)
            else:
                def derivative(a):
                    return sum(weights[i]*(cost[i]-nu-lam*kl_prime(log_s[i],a)) for i in active)
                if derivative(0)<=0:
                    a=0.
                elif derivative(cap)>=0:
                    a=cap
                else:
                    low,high=0.,cap
                    for _ in range(iterations):
                        middle=(low+high)/2
                        if derivative(middle)>0:low=middle
                        else:high=middle
                    a=(low+high)/2
            for i in ids:answer[i]=a
        return answer

    def dose_feasible(lam):
        a=allocate(lam,0.)
        if dose_budget is None or total_dose(a,weights)<=dose_budget:
            return a,0.
        low,high=0.,max(cost)
        for _ in range(iterations):
            nu=(low+high)/2;a=allocate(lam,nu)
            if total_dose(a,weights)>dose_budget:low=nu
            else:high=nu
        return allocate(lam,high),high

    # A positive numerical lower bound avoids nonunique bang-bang ties when
    # only the linear dose constraint is active. Report it in the diagnostics.
    lower=1e-12
    a,nu=dose_feasible(lower)
    if total_kl(log_s,a,weights)<=information_budget:
        lam=lower
    else:
        upper=1.
        while total_kl(log_s,dose_feasible(upper)[0],weights)>information_budget:
            upper*=2
            if not math.isfinite(upper):raise ArithmeticError('dual bracket overflow')
        for _ in range(iterations):
            mid=(lower+upper)/2
            if total_kl(log_s,dose_feasible(mid)[0],weights)>information_budget:lower=mid
            else:upper=mid
        lam=upper;a,nu=dose_feasible(lam)
    return {'alpha':a,'lambda':lam,'nu':nu,
        'information_budget':information_budget,'actual_kl':total_kl(log_s,a,weights),
        'dose_budget':dose_budget,'actual_dose':total_dose(a,weights),
        'utility':utility(cost,a,weights),'prior_utility':utility(cost,[prior]*n,weights),
        'scope':'exact supplied rows; group constraints retain individual s; no unseen-query guarantee',
        'dual_numeric_lower_bound':1e-12}


def categorical_kl(p,q):
    return sum(x*math.log(x/y) for x,y in zip(p,q) if x)


def mixture(p,t,alpha):
    result=[(1-alpha)*x for x in p]
    result[t]+=alpha
    return result


def probability_from_bin_lse(lse):
    maximum=max(lse);weights=[math.exp(x-maximum) for x in lse]
    z=sum(weights)
    return [x/z for x in weights]


def h3_video_coordinates(n,origin=0.,rescale=5/3):
    spans=(1,4,4,4,4);cursor=origin;result=[]
    for i in range(n):
        result.append(cursor);cursor+=rescale*spans[i%5]
    return result


def relative_time_cost(reference_coordinates,target_coordinate,
                       reference_origin,target_origin,duration):
    if duration<=0:raise ValueError('positive duration required')
    return [((x-reference_origin-(target_coordinate-target_origin))/duration)**2
            for x in reference_coordinates]
