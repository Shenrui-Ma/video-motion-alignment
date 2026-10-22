"""Independent, torch-free audit of the actually applied temporal gain field."""
import math


class FieldAuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise FieldAuditError(message)


def close(a, b, tolerance=2e-5):
    return math.isfinite(a) and math.isfinite(b) and abs(a-b) <= tolerance * (1+abs(b))


def check_layer(row):
    require(row.get('applied') is True and row.get('finite_output') is True, 'inactive/nonfinite field')
    require(row.get('attention_calls') == 5, 'unexpected attention call count')
    a, e, c = row['alpha'], row['bin_energy'], row['control']
    n = len(a)
    require(n > 0 and len(e) == n, 'bin vector shape')
    require(all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= .5 for x in a), 'alpha bounds')
    require(all(math.isfinite(x) and x >= 0 for x in e), 'bin energy')
    require(close(a[0], .25) and close(a[-1], .25), 'endpoint prior')
    require(close(sum(e), row['correction_energy']), 'full correction energy')
    require(close(sum(x*x*y for x,y in zip(a,e)), row['applied_energy']), 'applied bin energy')
    for name in ('usable_evidence', 'solver_succeeded', 'fallback_to_prior', 'anchor_created',
                 'initialized', 'anchor_step', 'normalized_temporal', 'normalized_complement',
                 'quadratic_diagonal', 'quadratic_rhs', 'anchor_temporal', 'anchor_complement',
                 'temporal_energy', 'complement_energy', 'alpha'):
        require(len(c[name]) == n, 'controller vector '+name)
    require(c['step_index'] == row['forward'] and c['layer_index'] == row['block'], 'controller identity')
    require(close(c['prior_weight'], 1) and close(c['smoothness'], .625), 'frozen QP parameters')
    require(len(c['edge_weights']) == max(0,n-1), 'edge vector shape')
    usable, solved = c['usable_evidence'], c['solver_succeeded']
    require(not usable[0] and not usable[-1], 'endpoint evidence')
    for t in range(n):
        require(close(a[t], c['alpha'][t], 1e-7), 'applied alpha differs from solved alpha')
        require(bool(c['fallback_to_prior'][t]) == (not bool(solved[t])), 'fallback mask')
        require(not solved[t] or usable[t], 'solved unsupported bin')
        require(not c['anchor_created'][t] or (not usable[t] and close(a[t],.25)), 'new anchor must use prior')
        if not solved[t]:
            require(close(a[t], .25), 'fallback must use prior')
        if c['initialized'][t]:
            require(0 <= c['anchor_step'][t] <= row['forward'], 'future/invalid anchor')
            require(all(math.isfinite(c[name][t]) and c[name][t] > 0
                        for name in ('anchor_temporal','anchor_complement')), 'invalid anchor energy')
        if c['anchor_created'][t]:
            require(c['anchor_temporal'][t] == c['temporal_energy'][t]
                    and c['anchor_complement'][t] == c['complement_energy'][t], 'wrong initial anchor')
        if usable[t]:
            vt, vn = c['normalized_temporal'][t], c['normalized_complement'][t]
            require(0 <= vt <= 1 and 0 <= vn <= 1 and close(vt+vn,1), 'normalized energy')
            aa,bb = c['temporal_energy'][t],c['complement_energy'][t]
            a0,b0 = c['anchor_temporal'][t],c['anchor_complement'][t]
            require(all(math.isfinite(x) and x >= 0 for x in (aa,bb)) and max(aa,bb)>0,
                    'invalid evidence energy')
            scale,scale0 = max(aa,bb),max(a0,b0)
            x,y = (aa/scale)*(b0/scale0),(bb/scale)*(a0/scale0)
            require(x+y>0 and close(vt,x/(x+y),1e-9) and close(vn,y/(x+y),1e-9),
                    'normalized energy inconsistent with anchor')
            require(close(c['quadratic_diagonal'][t], vt+3*vn+.5), 'QP diagonal')
            require(close(c['quadratic_rhs'][t], vt+.125), 'QP linear term')
        if t+1 < n:
            require(close(c['edge_weights'][t], float(usable[t] and usable[t+1])), 'invalid smoothing edge')
    covered = set()
    max_kkt, failures = 0., 0
    for segment in c['segments']:
        lo, hi = segment['interval_half_open']
        require(0 <= lo < hi <= n and all(usable[lo:hi]), 'invalid QP segment')
        require(not covered.intersection(range(lo,hi)), 'overlapping QP segments')
        covered.update(range(lo,hi))
        if not segment['converged']:
            require(not any(solved[lo:hi]), 'unconverged QP used')
            failures += 1
            continue
        require(all(solved[lo:hi]), 'converged QP not applied')
        require(1 <= segment['iterations'] <= segment['iteration_limit'], 'QP iteration bound')
        for t in range(lo,hi):
            g = c['quadratic_diagonal'][t]*a[t]-c['quadratic_rhs'][t]
            if t > lo:
                g += .625*c['edge_weights'][t-1]*(a[t]-a[t-1])
            if t+1 < hi:
                g += .625*c['edge_weights'][t]*(a[t]-a[t+1])
            error = max(0.,-g) if a[t] <= 1e-8 else max(0.,g) if a[t] >= .5-1e-8 else abs(g)
            require(error <= 1e-6, 'actual applied gain violates QP KKT')
            max_kkt = max(max_kkt,error)
    require(covered == {t for t,x in enumerate(usable) if x}, 'unaccounted evidence bins')
    return {'bins':n, 'solver_failures':failures, 'max_kkt':max_kkt}


def check_field(doc):
    require(doc.get('schema') == 'h3-temporal-gain-field-v1', 'wrong schema')
    require(doc.get('status') in ('sampling','complete','completed') and not doc.get('error'), 'failed runtime')
    require(not doc.get('offline_counterfactual'), 'counterfactual is not executed evidence')
    for name in ('started_calls','completed_calls','native_override_calls','routed_calls'):
        require(doc.get(name) == 1000, 'incomplete '+name)
    require(doc.get('completed_forward_calls') == 20, 'incomplete completed forwards')
    for name in ('calls_by_forward','routed_by_forward'):
        require(doc.get(name) == [50]*20, 'incorrect '+name)
    for name in ('calls_by_block','routed_by_block'):
        require(doc.get(name) == [20]*50, 'incorrect '+name)
    require(doc.get('step_interval_half_open') == [0,20] and doc.get('block_interval_half_open') == [0,50],
            'wrong applied intervals')
    cfg = doc['feature_config']
    require(cfg['mode'] == 'gain_field' and cfg['alpha_prior'] == .25 and cfg['alpha_max'] == .5,
            'wrong field configuration')
    require(cfg['probes'] == 8 and cfg['basis'] == 'centered' and cfg['smoothness'] == .625
            and cfg['prior_weight'] == 1, 'unfrozen controller')
    require(doc.get('full_dit_forward_calls_added') == 0 and doc.get('intermediate_vae_decode_calls') == 0,
            'unexpected forward/decode')
    forwards = doc['feature_forward_summaries']
    require(len(forwards) == 20 and [x['forward'] for x in forwards] == list(range(20)), 'sampling coverage')
    alpha, seen, summaries, anchors = [], set(), [], {}
    for f in forwards:
        require(len(f['layers']) == 50 and sorted(x['block'] for x in f['layers']) == list(range(50)), 'block coverage')
        for row in f['layers']:
            require(row['forward'] == f['forward'], 'forward identity')
            key = (row['forward'],row['block'])
            require(key not in seen, 'duplicate layer')
            seen.add(key)
            summaries.append(check_layer(row))
            c = row['control']
            for t,(initialized,created,step) in enumerate(zip(c['initialized'],c['anchor_created'],c['anchor_step'])):
                k = (row['block'],t)
                value=(step,c['anchor_temporal'][t],c['anchor_complement'][t])
                if k in anchors:
                    require(initialized and not created and value == anchors[k], 'anchor overwritten')
                elif initialized:
                    require(created and step == row['forward'], 'anchor absent from earlier trace')
                    anchors[k] = value
            alpha.extend(row['alpha'])
    return {'passed':True, 'status':'passed', 'forwards':20, 'blocks':len(seen), 'alpha_min':min(alpha),
            'alpha_max':max(alpha), 'alpha_mean':sum(alpha)/len(alpha),
            'solver_failures':sum(s['solver_failures'] for s in summaries),
            'max_kkt':max(s['max_kkt'] for s in summaries), 'created_bin_anchors':len(anchors)}
