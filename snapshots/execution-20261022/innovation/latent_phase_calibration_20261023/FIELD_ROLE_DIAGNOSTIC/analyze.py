"""Posthoc descriptive role statistics from actual field attention-controller audit.

No torch, model imports, inference, parameter fitting, or mutation of input results.
All bins are retained; window endpoints are explicitly excluded from estimation.
"""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

METRICS = ('raw_temporal_share', 'normalized_temporal_share',
           'raw_marginal_gain', 'normalized_marginal_gain',
           'raw_local_optimum', 'normalized_local_optimum', 'alpha')


def mean(xs):
    return statistics.fmean(xs) if xs else None


def var(xs):
    return statistics.pvariance(xs) if xs else None


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def group_metric(rows, name):
    """One step/layer: all eligible bins, population variance decomposition."""
    groups = [[r[name] for r in rows if r['role'] == k] for k in range(5)]
    means = [mean(g) for g in groups]
    values = [r[name] for r in rows]
    center = mean(values)
    total_ss = sum((v-center)**2 for v in values)
    between_ss = sum(len(g)*(m-center)**2 for g, m in zip(groups, means) if g)
    return {'role_n': [len(g) for g in groups], 'role_means': means,
            'role_variances': [var(g) for g in groups],
            'grand_mean': center, 'bin_variance': var(values),
            'between_role_variance_equal_weight': var([m for m in means if m is not None]),
            'between_role_ss': between_ss, 'total_ss': total_ss,
            'role_eta_squared': between_ss/total_ss if total_ss > 1e-24 else None}


def local_optimum(share, prior_weight=1.):
    # J=(1-a)^2*T+3*a^2*N+mu*(a-.25)^2*(T+N)/2; T+N=1.
    return min(.5, max(0., (share+prior_weight*.125)/(3-2*share+prior_weight*.5)))


def summarize_calls(calls):
    result = {'calls': len(calls)}
    for metric in METRICS:
        summaries = [c['metrics'][metric] for c in calls]
        role_means = [mean([s['role_means'][k] for s in summaries]) for k in range(5)]
        eta_num = sum(s['between_role_ss'] for s in summaries)
        eta_den = sum(s['total_ss'] for s in summaries)
        result[metric] = {
            'mean_role_means': role_means,
            'role_profile_variance': var(role_means),
            'mean_within_call_between_role_variance': mean([s['between_role_variance_equal_weight'] for s in summaries]),
            'mean_within_call_bin_variance': mean([s['bin_variance'] for s in summaries]),
            'within_call_ss_pooled_role_eta_squared': eta_num/eta_den if eta_den > 1e-24 else None,
            'max_minus_min_role_profile': max(role_means)-min(role_means),
            'role_max_call_counts': dict(collections.Counter(str(max(range(5), key=lambda k:s['role_means'][k])) for s in summaries)),
        }
    for name in ('temporal_energy_per_probe', 'complement_energy_per_probe', 'pooled_temporal_share'):
        result[name] = [mean([c['role_energy'][k][name] for c in calls]) for k in range(5)]
    return result


def analyze(path, graph_path):
    obj=json.loads(path.read_text());points=obj['points']
    graph=json.loads(graph_path.read_text());cfg=graph['50']['inputs']
    assert cfg['start_frame']==0, 'Absolute t%5 needs runtime bin coordinates for nonzero start'
    assert cfg['step_start']==0 and cfg['step_end']==20
    assert len(points)==1000 and {(p['step'],p['layer']) for p in points}=={(s,l) for s in range(20) for l in range(50)}
    assert all(p['boundary_probes_excluded'] for p in points)
    nbin=len(points[0]['alpha']);calls=[];allrows=[];checks=collections.Counter()
    anchors={};max_normalization_error=0.;max_sum_error=0.
    for p in sorted(points,key=lambda x:(x['step'],x['layer'])):
        step,layer=p['step'],p['layer'];call_rows=[]
        keys=('alpha','temporal_energy','complement_energy','valid_probe_count','anchor_temporal',
              'anchor_complement','anchor_step','normalized_temporal','normalized_complement',
              'fallback_to_prior','usable_evidence','solver_succeeded')
        assert all(len(p[k])==nbin for k in keys)
        for t in range(nbin):
            A,B,A0,B0=(p[k][t] for k in ('temporal_energy','complement_energy','anchor_temporal','anchor_complement'))
            count=p['valid_probe_count'][t];alpha=p['alpha'][t]
            endpoint=t in (0,nbin-1)
            assert all(math.isfinite(v) for v in (A,B,A0,B0,count,alpha))
            assert A>=0 and B>=0 and 0<=alpha<=.5
            eligible=not endpoint and count>0 and A+B>0 and A0>0 and B0>0
            row={'step':step,'layer':layer,'bin':t,'role':t%5,'endpoint':endpoint,
                 'included_in_group_estimate':eligible,'exclusion':'window_endpoint' if endpoint else None,
                 'temporal_energy':A,'complement_energy':B,'valid_probe_count':count,
                 'anchor_temporal':A0,'anchor_complement':B0,'anchor_step':p['anchor_step'][t],
                 'alpha':alpha,'fallback_to_prior':p['fallback_to_prior'][t],
                 'solver_succeeded':p['solver_succeeded'][t]}
            if endpoint:
                assert count==0 and A==0 and B==0 and alpha==.25
                checks['endpoints_retained_and_excluded']+=1
            else:
                assert eligible and 0<count<=448 and p['anchor_step'][t]==0
                if count<448: checks['interior_bins_with_some_probes_masked']+=1
                pair=(A0,B0)
                if step==0: anchors[layer,t]=pair;assert pair==(A,B) and alpha==.25
                else: assert anchors[layer,t]==pair
                q=A/(A+B);T=(A/A0)/(A/A0+B/B0);N=1-T
                err=abs(T-p['normalized_temporal'][t]);max_normalization_error=max(max_normalization_error,err)
                max_sum_error=max(max_sum_error,abs(p['normalized_temporal'][t]+p['normalized_complement'][t]-1))
                assert err<1e-12
                assert p['usable_evidence'][t]==(step>0)
                assert p['fallback_to_prior'][t]==(step==0) and p['solver_succeeded'][t]==(step>0)
                row.update(raw_temporal_share=q,raw_complement_share=1-q,
                           normalized_temporal_share=T,normalized_complement_share=N,
                           temporal_growth=A/A0,complement_growth=B/B0,
                           raw_marginal_gain=1.5*(2*q-1),normalized_marginal_gain=1.5*(2*T-1),
                           raw_local_optimum=local_optimum(q,cfg['prior_weight']),
                           normalized_local_optimum=local_optimum(T,cfg['prior_weight']))
                call_rows.append(row);checks['interior_formula_and_anchor_checks']+=1
            allrows.append(row)
        role_energy=[]
        for role in range(5):
            rs=[r for r in call_rows if r['role']==role]
            a=sum(r['temporal_energy'] for r in rs);b=sum(r['complement_energy'] for r in rs)
            probes=sum(r['valid_probe_count'] for r in rs)
            role_energy.append({'role':role,'bins':len(rs),'probes':probes,
                                'temporal_energy_per_probe':a/probes,'complement_energy_per_probe':b/probes,
                                'pooled_temporal_share':a/(a+b)})
        # Secondary descriptive contrast: remove each available 5-bin chunk's mean.
        # Partial chunks remain; no bin selected based on its score.
        chunk_contrasts={}
        for metric in ('raw_temporal_share','normalized_temporal_share','alpha'):
            chunk_mean={c:mean([r[metric] for r in call_rows if r['bin']//5==c]) for c in {r['bin']//5 for r in call_rows}}
            chunk_contrasts[metric]=[mean([r[metric]-chunk_mean[r['bin']//5] for r in call_rows if r['role']==k]) for k in range(5)]
        calls.append({'step':step,'layer':layer,'included_bins':len(call_rows),'role_energy':role_energy,
                      'metrics':{m:group_metric(call_rows,m) for m in METRICS},
                      'chunk_centered_role_contrasts':chunk_contrasts})
    by_step=[{'step':s,**summarize_calls([c for c in calls if c['step']==s])} for s in range(20)]
    by_layer=[{'layer':l,**summarize_calls([c for c in calls if c['layer']==l and c['step']>0])} for l in range(50)]
    by_bin=[]
    for t in range(nbin):
        rs=[r for r in allrows if r['bin']==t]
        by_bin.append({'bin':t,'role':t%5,'endpoint':t in (0,nbin-1),
                       'alpha_by_step':[mean([r['alpha'] for r in rs if r['step']==s]) for s in range(20)],
                       **{m:mean([r[m] for r in rs if m in r and r['step']>0]) for m in METRICS}})
    dynamic=[c for c in calls if c['step']>0]
    return {'input':{'path':str(path),'sha256':digest(path),'audit_sha256':obj['audit_sha256'],
                     'graph':str(graph_path),'graph_sha256':digest(graph_path),'job_id':obj['job_id'],
                     'attempt_id':obj['actual_attempt_id'],'config':obj['feature_config'],'first_absolute_bin':0},
            'checks':dict(checks),'max_normalization_replay_error':max_normalization_error,
            'max_normalized_share_sum_error':max_sum_error,'bins':nbin,
            'interior_role_counts':calls[0]['metrics']['alpha']['role_n'],
            'all_steps':summarize_calls(calls),'post_anchor_steps_1_to_19':summarize_calls(dynamic),
            'chunk_centered_role_contrasts_steps_1_to_19':{m:[mean([c['chunk_centered_role_contrasts'][m][k] for c in dynamic]) for k in range(5)] for m in ('raw_temporal_share','normalized_temporal_share','alpha')},
            'by_step':by_step,'by_layer_steps_1_to_19':by_layer,'by_bin':by_bin,'calls':calls,'all_bins':allrows}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--batch',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();started=time.monotonic();args.out.mkdir(exist_ok=True,parents=True)
    results=[]
    for case in ('short_0252','short_0358'):
        name=f'adapt41_{case}_temporal_gain_field.json'
        result=analyze(args.batch/'results_tools/latest/alpha_curves'/name,args.batch/'field_pilots/graphs'/name)
        (args.out/f'{case}_statistics.json').write_text(json.dumps(result,allow_nan=False,separators=(',',':'))+'\n')
        results.append({k:v for k,v in result.items() if k not in ('calls','all_bins')})
    summary={'scope':'posthoc descriptive; observed runtime controller statistics; no causal attribution',
             'script_sha256':digest(__file__),'wall_seconds':time.monotonic()-started,'cases':results,
             'metric_definition':{'A':'sum over heads and probes of ||m projection_b(S-R)||^2',
                                  'B':'sum of ||m(S-R)-m projection_b(S-R)||^2',
                                  'b':'S_plus(Q_t,K/V_t+1)-S_minus(Q_t,K/V_t-1), Q held fixed',
                                  'raw_share':'A/(A+B)',
                                  'normalized_share':'(A/A0)/(A/A0+B/B0)',
                                  'marginal_gain':'-dJ/dalpha at alpha=.25 after dividing by T+N = 1.5*(T-N)/(T+N)',
                                  'local_optimum':'offline objective summary, no smoothing; NOT an additional generated run',
                                  'role_eta_squared':'sum within-call between-role SS / sum within-call total SS; descriptive, not p-value'}}
    (args.out/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
    print(json.dumps({'cases':len(results),'wall_seconds':summary['wall_seconds'],'checks':[r['checks'] for r in results]}))


if __name__=='__main__':main()
