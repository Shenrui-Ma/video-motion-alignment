"""CPU-only algebra checks. Synthetic features are not H3 generation evidence."""
import json
import math
from pathlib import Path


def cosine(a, b):
    n = math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b))/n if n else -math.inf


def unique_max(row):
    best = max(row)
    winners = [i for i,x in enumerate(row) if abs(x-best) <= 1e-12]
    return winners[0] if len(winners) == 1 and math.isfinite(best) else None


def mutual(a, b):
    scores = [[cosine(x,y) for y in b] for x in a]
    forward = [unique_max(row) for row in scores]
    backward = [unique_max([row[j] for row in scores]) for j in range(len(b))]
    return {i:j for i,j in enumerate(forward) if j is not None and backward[j] == i}


def target(t, tau, valid):
    return t if t >= valid else t + ((tau > t) - (tau < t))


def distribution(weights, values, tau, mode, valid=None, maps=None):
    valid = len(values) if valid is None else valid
    result = {}
    for t,row in enumerate(weights):
        for s,w in enumerate(row):
            if mode == 'same_time':
                if t != tau: continue
                u,j=t,s
            elif mode == 'spatial_marginal':
                u,j=tau,s
            elif mode == 'fixed_one_bin':
                u,j=target(t,tau,valid),s
            elif mode == 'matched_one_bin':
                u=target(t,tau,valid)
                if u == t: j=s
                else:
                    matches = maps[t,u] if maps is not None else mutual(values[t],values[u])
                    if s in matches: j=matches[s]
                    else: u,j=t,s
            elif mode == 'native': u,j=t,s
            else: raise ValueError(mode)
            result[u,j]=result.get((u,j),0)+w
    if mode == 'same_time':
        z=sum(result.values())
        if not z: raise ValueError('zero same-time mass')
        result={k:v/z for k,v in result.items()}
    return result


def read(weights, values, tau, mode, **kwargs):
    p=distribution(weights,values,tau,mode,**kwargs)
    return [sum(w*values[t][s][d] for (t,s),w in p.items()) for d in range(len(values[0][0]))]


def close(a,b):
    return len(a)==len(b) and all(abs(x-y)<1e-12 for x,y in zip(a,b))


def main():
    checks=[]
    def check(name,condition):
        if not condition: raise AssertionError(name)
        checks.append(name)
    ids=[[0,1,2],[2,0,1],[1,2,0]]
    values=[[[float(i==k) for k in range(3)]+[.4*t if i==0 else 0.] for i in row] for t,row in enumerate(ids)]
    weights=[[.7,0,0],[0,.2,0],[0,0,.1]]
    modes=['native','same_time','spatial_marginal','fixed_one_bin','matched_one_bin']
    outputs={mode:read(weights,values,2,mode) for mode in modes}
    expected={'native':[1,0,0,.16], 'same_time':[1,0,0,.8],
              'spatial_marginal':[.1,.7,.2,.08], 'fixed_one_bin':[.1,0,.9,.08],
              'matched_one_bin':[1,0,0,.52]}
    for mode in modes: check(mode+'_expected',close(outputs[mode],expected[mode]))
    for t in range(2):
        matches=mutual(values[t],values[t+1])
        check('adjacent_identity_match_'+str(t),all(ids[t][s]==ids[t+1][j] for s,j in matches.items()) and len(matches)==3)
    for mode in modes:
        p=distribution(weights,values,2,mode)
        check(mode+'_nonnegative_unit_mass',all(x>=0 for x in p.values()) and abs(sum(p.values())-1)<1e-12)
    check('one_bin_distance_bound',all(abs(target(t,tau,3)-t)<=1 for tau in range(3) for t in range(3)))
    empties={(t,u):{} for t in range(3) for u in range(3)}
    check('unmatched_native',close(read(weights,values,2,'matched_one_bin',maps=empties),outputs['native']))
    check('tie_rejected',mutual([[1,0],[1,0]],[[1,0],[1,0]])=={})
    check('zero_vectors_rejected',mutual([[0,0]],[[0,0]])=={})
    only_tau=[[0,0,0],[0,0,0],[.2,.3,.5]]
    check('same_time_native',close(read(only_tau,values,2,'matched_one_bin'),read(only_tau,values,2,'native')))
    track_constant=[[[float(i==k) for k in range(3)] for i in row] for row in ids]
    check('track_constant_invariance',close(read(weights,track_constant,2,'matched_one_bin'),read(weights,track_constant,2,'native')))
    # A quantity constant at image coordinate s need not be constant along a moving track.
    static_field=[[[float(s+1)] for s in range(3)] for t in range(3)]
    maps={(t,u):mutual(values[t],values[u]) for t in range(3) for u in range(3)}
    check('static_pixel_invariance_is_lost',not close(read(weights,static_field,2,'matched_one_bin',maps=maps),read(weights,static_field,2,'native')))
    bad={(t,u):{s:s for s in range(3)} for t in range(3) for u in range(3)}
    check('wrong_match_leaks_identity',read(weights,values,2,'matched_one_bin',maps=bad)[0]<1)
    padded_values=values+[[[7,8,9,10]]*3]
    padded_weights=[[0,0,0]]*3+[[.2,.3,.5]]
    check('padding_native',close(read(padded_weights,padded_values,2,'matched_one_bin',valid=3),read(padded_weights,padded_values,2,'native')))
    nonref=[.6,.1,.2,.3];mass=.1442568262
    native=[n+mass*r for n,r in zip(nonref,outputs['native'])]
    corrected=[o+mass*(r-n) for o,r,n in zip(native,outputs['matched_one_bin'],outputs['native'])]
    check('original_reference_mass_nonreference_contribution',close(corrected,[n+mass*r for n,r in zip(nonref,outputs['matched_one_bin'])]))
    result={'schema':'r111-cpu-correspondence-proposal-v1','scope':'Synthetic algebra only; no learned features, model execution, or empirical success claim.',
            'checks':checks,'passed':len(checks),'moving_identity_example':{'values':values,'weights':weights,'tau':2,'outputs_identity_ABC_then_phase':outputs},
            'counterexamples':['Mutual nearest matching can be semantically wrong.','Track-constant values yield zero correction, including an identity-only pure-translation representation.','Static image-coordinate feature invariance is lost.'],
            'pending':'Validate native H3 correspondence and result quality before any architecture contribution claim.'}
    Path(__file__).with_name('CPU_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':len(checks),'outputs':outputs},indent=2))


if __name__=='__main__': main()
