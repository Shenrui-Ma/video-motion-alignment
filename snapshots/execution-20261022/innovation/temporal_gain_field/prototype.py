"""Offline causal gain field on latent-time bins; CPU sufficient statistics only.

No model, attention recomputation, RGB, VAE, scheduling or runtime modification.
The integration boundary would transfer one small A/B/count vector per layer.
"""
import math
import torch


def _runs(mask):
    result=[];start=None
    for i,valid in enumerate(list(mask)+[False]):
        if valid and start is None:start=i
        if not valid and start is not None:result.append((start,i));start=None
    return result


def _matvec(diag,off,x):
    return [diag[i]*x[i]+(off[i-1]*x[i-1] if i else 0.)
            +(off[i]*x[i+1] if i+1<len(x) else 0.) for i in range(len(x))]


def _thomas(diag,off,rhs):
    c=[];d=[]
    for i in range(len(diag)):
        pivot=diag[i]-(off[i-1]*c[-1] if i else 0.)
        if pivot<=0 or not math.isfinite(pivot):raise ValueError('nonpositive tridiagonal pivot')
        c.append(off[i]/pivot if i+1<len(diag) else 0.)
        d.append((rhs[i]-(off[i-1]*d[-1] if i else 0.))/pivot)
    x=d[:]
    for i in range(len(x)-2,-1,-1):x[i]-=c[i]*x[i+1]
    return x


def solve_box_tridiagonal(diagonal,off_diagonal,rhs,*,lower=0.,upper=.5,
                          initial=.25,tolerance=1e-10,max_iterations=None):
    """Primal-feasible active-set solve of min x^T M x - 2 b^T x.

    Positive strictly diagonally dominant symmetric tridiagonal M is required.
    Free coordinates form contiguous tridiagonal systems solved by Thomas.
    A deterministic iteration cap returns converged=False, never fake success.
    All arguments are small CPU tensors; this intentionally uses no GPU.
    """
    if any(not isinstance(t,torch.Tensor) or t.device.type!='cpu' or t.ndim!=1
           for t in (diagonal,off_diagonal,rhs)):
        raise ValueError('CPU one-dimensional tensors required')
    n=len(diagonal)
    if n<1 or len(rhs)!=n or len(off_diagonal)!=n-1:raise ValueError('incompatible tridiagonal shapes')
    if not all(math.isfinite(v) for v in (lower,upper,initial,tolerance)) or lower>=upper or tolerance<=0:
        raise ValueError('invalid box or tolerance')
    d=diagonal.double().tolist();e=off_diagonal.double().tolist();b=rhs.double().tolist()
    if not all(math.isfinite(v) for v in d+e+b):raise ValueError('finite coefficients required')
    for i in range(n):
        if not d[i] > (abs(e[i-1]) if i else 0.)+(abs(e[i]) if i+1<n else 0.):
            raise ValueError('positive strict diagonal dominance required')
    limit=4*n+16 if max_iterations is None else max_iterations
    if type(limit) is not int or limit<1:raise ValueError('positive iteration cap required')
    x=[min(upper,max(lower,initial))]*n;active=[0]*n;converged=False
    matrix_norm=max(d[i]+(abs(e[i-1]) if i else 0.)+(abs(e[i]) if i+1<n else 0.) for i in range(n))
    tol=tolerance*(1+max(abs(v) for v in b))+32*torch.finfo(torch.float64).eps*matrix_norm*(1+max(abs(lower),abs(upper)))
    for iteration in range(1,limit+1):
        free=[a==0 for a in active]
        fixed_values=[0. if free[i] else x[i] for i in range(n)]
        fixed_contribution=_matvec(d,e,fixed_values)
        candidate=x[:]
        for a,z in _runs(free):
            local=_thomas(d[a:z],e[a:z-1],[b[i]-fixed_contribution[i] for i in range(a,z)])
            candidate[a:z]=local
        direction=[candidate[i]-x[i] for i in range(n)]
        step=1.
        for i in range(n):
            if not free[i]:continue
            if candidate[i]<lower and direction[i]<0:step=min(step,(lower-x[i])/direction[i])
            if candidate[i]>upper and direction[i]>0:step=min(step,(upper-x[i])/direction[i])
        step=max(0.,min(1.,step))
        x=[min(upper,max(lower,x[i]+step*direction[i])) for i in range(n)]
        if step<1.-1e-13:
            added=False
            for i in range(n):
                if not free[i]:continue
                if direction[i]<0 and x[i]<=lower+1e-12:active[i]=-1;x[i]=lower;added=True
                elif direction[i]>0 and x[i]>=upper-1e-12:active[i]=1;x[i]=upper;added=True
            if not added:break
            continue
        gradient=[v-b[i] for i,v in enumerate(_matvec(d,e,x))]
        violations=[(-gradient[i] if active[i]==-1 else gradient[i] if active[i]==1 else 0.) for i in range(n)]
        if max(violations)<=tol:
            free_error=max([abs(gradient[i]) for i in range(n) if active[i]==0]+[0.])
            if free_error<=tol:converged=True
            break
        release=max(range(n),key=lambda i:violations[i]);active[release]=0
    gradient=[v-b[i] for i,v in enumerate(_matvec(d,e,x))]
    residual=[max(0.,-gradient[i]) if x[i]<=lower+1e-11 else
              max(0.,gradient[i]) if x[i]>=upper-1e-11 else abs(gradient[i]) for i in range(n)]
    energy=sum(x[i]*v-2*b[i]*x[i] for i,v in enumerate(_matvec(d,e,x)))
    return torch.tensor(x,dtype=torch.float64),{
        'converged':converged,'iterations':iteration,'iteration_limit':limit,
        'kkt_inf':max(residual),'numeric_tolerance':tol,'gradient':gradient,
        'active_lower':sum(v<=lower+1e-11 for v in x),
        'active_upper':sum(v>=upper-1e-11 for v in x),
        'objective_without_constant':energy,'free_system_solver':'Thomas / primal feasible active set'}


def summarize_probe_components(components):
    """Aggregate existing [H,T,P] energy statistics over head and spatial probe."""
    A,B,valid=(components[k] for k in ('temporal_energy','complement_energy','valid'))
    if A.ndim!=3 or B.shape!=A.shape or valid.shape!=A.shape:raise ValueError('[H,T,P] components required')
    return A.sum((0,2)),B.sum((0,2)),valid.sum((0,2))


@torch.no_grad()
def update_gain_field(temporal_energy,complement_energy,valid_probe_count,*,
                      state=None,step_index,layer_index,prior_weight=1.,smoothness=.625,
                      relative_floor=1e-8,bin_coordinates=None,solver_iterations=None):
    """Per-layer/per-bin anchored alpha[time] with no coupling through no-evidence bins.

    Frozen proposal: alpha_prior=.25, alpha_max=.5, collateral=3. CPU vectors are
    explicit; no hidden tensor transfer. First/last valid-window bins are not
    controller evidence. All those bins still receive ordinary alpha=.25.
    """
    if type(step_index) is not int or step_index<0 or type(layer_index) is not int or layer_index<0:
        raise ValueError('nonnegative integer step/layer indices required')
    if not all(math.isfinite(v) for v in (prior_weight,smoothness,relative_floor)) or prior_weight<0 or smoothness<0 or not 0<=relative_floor<1:
        raise ValueError('invalid nonnegative objective settings')
    ts=(temporal_energy,complement_energy,valid_probe_count)
    if any(not isinstance(x,torch.Tensor) or x.ndim!=1 or x.device.type!='cpu' for x in ts):
        raise ValueError('explicit CPU vectors required')
    n=len(temporal_energy)
    if n<1 or any(len(x)!=n for x in ts):raise ValueError('matching nonempty time vectors required')
    A,B=(x.detach().double() for x in ts[:2]);count=valid_probe_count.detach()
    coords=torch.arange(n,dtype=torch.float64) if bin_coordinates is None else bin_coordinates.detach().double()
    if coords.device.type!='cpu' or coords.shape!=(n,) or not bool(torch.isfinite(coords).all()) or (n>1 and not bool((coords[1:]>coords[:-1]).all())):
        raise ValueError('finite increasing CPU bin coordinates required')
    settings=(prior_weight,smoothness,relative_floor,tuple(coords.tolist()))
    if state is None:
        initialized=torch.zeros(n,dtype=torch.bool);a0=torch.ones(n,dtype=torch.float64);b0=a0.clone()
        anchor_step=torch.full((n,),-1,dtype=torch.long)
    else:
        if state['layer_index']!=layer_index or state['settings']!=settings or len(state['initialized'])!=n:
            raise ValueError('state layer/configuration/geometry changed')
        if step_index<=state['last_step']:raise ValueError('duplicate or out-of-order layer step')
        initialized=state['initialized'];a0=state['anchor_temporal'];b0=state['anchor_complement'];anchor_step=state['anchor_step']
    valid=(torch.isfinite(A)&torch.isfinite(B)&(A>=0)&(B>=0)&torch.isfinite(count)&(count>0))
    valid[0]=False;valid[-1]=False
    a=torch.where(valid,A,0.);b=torch.where(valid,B,0.);scale=torch.maximum(a,b);tiny=torch.finfo(torch.float64).tiny
    eligible=valid&(scale>tiny)&(a>relative_floor*scale)&(b>relative_floor*scale)
    created=(~initialized)&eligible
    A0=torch.where(created,a,a0);B0=torch.where(created,b,b0);next_initialized=initialized|created
    next_anchor_step=torch.where(created,torch.full_like(anchor_step,step_index),anchor_step)
    anchor_scale=torch.maximum(A0,B0).clamp_min(tiny)
    usable=initialized&valid&(scale>tiny)&(scale>relative_floor*anchor_scale)
    vt=(a/scale.clamp_min(tiny))*(B0/anchor_scale)
    vn=(b/scale.clamp_min(tiny))*(A0/anchor_scale)
    total=(vt+vn).clamp_min(tiny);vt,vn=vt/total,vn/total
    c=vt+3*vn+prior_weight*(vt+vn)/2
    rhs=vt+prior_weight*.25*(vt+vn)/2
    alpha=torch.full((n,),.25,dtype=torch.float64)
    local_alpha=alpha.clone();local_alpha[usable]=(rhs[usable]/c[usable]).clamp(0,.5)
    edge_weights=torch.zeros(max(0,n-1),dtype=torch.float64)
    if n>1:
        spacings=coords[1:]-coords[:-1]
        edge_weights=torch.median(spacings)/spacings
        edge_weights*=usable[:-1]&usable[1:]
    segment_reports=[];solved=torch.zeros(n,dtype=torch.bool)
    for start,end in _runs(usable.tolist()):
        edges=smoothness*edge_weights[start:end-1]
        diagonal=c[start:end].clone()
        if end-start>1:
            diagonal[:-1]+=edges;diagonal[1:]+=edges
        solution,report=solve_box_tridiagonal(diagonal,-edges,rhs[start:end],max_iterations=solver_iterations)
        if report['converged']:
            alpha[start:end]=solution;solved[start:end]=True
        report.update(interval_half_open=[start,end],evidence_bins=end-start)
        segment_reports.append(report)
    next_state={'initialized':next_initialized.clone(),'anchor_temporal':A0.clone(),'anchor_complement':B0.clone(),
                'anchor_step':next_anchor_step.clone(),'last_step':step_index,'layer_index':layer_index,'settings':settings}
    return alpha,next_state,{
        'alpha':alpha.clone(),'unsmoothed_alpha':local_alpha,'temporal_energy':a,'complement_energy':b,
        'valid_probe_count':torch.where(torch.isfinite(count)&(count>0),count,torch.zeros_like(count)),
        'anchor_created':created,'initialized':next_initialized.clone(),'anchor_step':next_anchor_step.clone(),
        'anchor_temporal':A0.clone(),'anchor_complement':B0.clone(),
        'usable_evidence':usable,'solver_succeeded':solved,'fallback_to_prior':~solved,
        'normalized_temporal':vt,'normalized_complement':vn,'quadratic_diagonal':c,'quadratic_rhs':rhs,
        'edge_weights':edge_weights,'segments':segment_reports,'prior_weight':prior_weight,'smoothness':smoothness,
        'step_index':step_index,'layer_index':layer_index,'endpoint_rule':'exclude statistics; fixed prior; no smoothing edge',
        'signal':'relative temporal-feature energy, not measured action delay'}
