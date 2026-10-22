"""Torch-free replay of executed H3 causal layer budgets, not a model evaluator.

CLI: python layer_audit.py audit.json (or '-' for JSON on stdin).
The allocator is checked through primal/dual KKT conditions, not by rerunning
its active-set implementation. Current-step drift is measured, never forced to 1.
"""
import argparse
import json
import math
from pathlib import Path
import sys


class LayerAuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise LayerAuditError(message)


def number(x, label, lo=None, hi=None):
    require(type(x) in (int, float) and math.isfinite(x), label+': finite number required')
    require(lo is None or x >= lo, label+': below bound')
    require(hi is None or x <= hi, label+': above bound')
    return float(x)


def close(x, y, label, rtol=2e-5, atol=1e-10):
    x, y = number(x, label), number(y, label)
    require(abs(x-y) <= atol+rtol*abs(y), f'{label}: {x} != {y}')


def vector(x, n, label, lo=None, hi=None):
    require(isinstance(x, list) and len(x) == n, label+': vector size')
    return [number(v, label, lo, hi) for v in x]


def flags(x, n, label):
    require(isinstance(x, list) and len(x) == n and all(type(v) is bool for v in x), label+': boolean vector')
    return x


def flag(x, label):
    require(type(x) is bool, label+': boolean required')
    return x


def same_vector(actual, expected, label, rtol=2e-5, atol=1e-10):
    actual = vector(actual, len(expected), label)
    for x, y in zip(actual, expected):
        close(x, y, label, rtol, atol)


def measure(e, a):
    baseline = .0625*math.fsum(e)
    applied = math.fsum(x*y*y for x, y in zip(e, a))
    return {'baseline':baseline, 'executed':applied,
            'ratio':applied/baseline if baseline else None}


def check_measure(record, e, a, label):
    expected = measure(e, a)
    require(isinstance(record, dict), label+': budget object')
    for k, value in expected.items():
        if value is None:
            require(record.get(k) is None, label+': undefined ratio must be null')
        else:
            close(record.get(k), value, label+'.'+k, rtol=2e-9, atol=1e-12)
    return expected


def check_allocation(record, quality, energy, eligible, planned):
    """Independent optimality certificate for a linear objective in an ellipsoid."""
    require(isinstance(record, dict), 'missing allocation certificate')
    n = len(quality)
    require(flags(record.get('eligible'), n, 'allocation.eligible') == eligible, 'allocation eligibility differs')
    same_vector(record.get('quality'), quality, 'allocation quality', 1e-10, 1e-12)
    same_vector(record.get('relative_energy'), energy, 'allocation energy', 1e-10, 1e-12)
    same_vector(record.get('alpha'), planned, 'allocation alpha', 1e-10, 1e-12)
    ids = [i for i in range(n) if eligible[i]]
    require(all(energy[i] > 0 for i in ids), 'eligible layer with zero energy')
    for i in range(n):
        if not eligible[i]:
            close(planned[i], .25, 'ineligible next alpha', 0, 1e-12)
    ee = [energy[i] for i in ids]
    aa = [planned[i] for i in ids]
    bm = measure(ee, aa)
    all_bm = measure(energy, planned)
    for key, value in [('eligible_target',bm['baseline']), ('eligible_assigned',bm['executed']),
                       ('all_target',all_bm['baseline']), ('all_assigned',all_bm['executed'])]:
        close(record.get(key), value, key, 2e-9, 1e-12)
    for key, value in [('eligible_budget_ratio',bm['ratio']),('predicted_budget_ratio',all_bm['ratio'])]:
        if value is None:
            require(record.get(key) is None, key+': expected null')
        else:
            close(record.get(key), value, key, 2e-9, 1e-12)
    require(bm['executed'] <= bm['baseline']+1e-10*max(1.,bm['baseline']), 'planned budget infeasible')
    require(type(record.get('iterations')) is int and 0 <= record['iterations'] <= len(ids)+1,
            'allocator iteration bound')
    reason = record.get('reason')
    uniform = ids and all(quality[i] == quality[ids[0]] for i in ids)
    if not ids or uniform:
        expected_reason = 'no_eligible_layers' if not ids else 'uniform_quality_prior' if quality[ids[0]] > 0 else 'zero_quality_prior'
        require(reason == expected_reason, 'degenerate allocation branch')
        same_vector(planned, [.25]*n, 'degenerate prior', 0, 1e-12)
        require(record['iterations'] == 0 and record.get('waterfill_multiplier') is None,
                'degenerate allocation invoked solver')
        close(record.get('energy_normalization'), 1., 'degenerate normalization', 0, 0)
        return {'max_kkt_residual':0.,'branch':reason}
    close(record.get('energy_normalization'), max(ee), 'energy normalization', 1e-12, 0)
    positive = [i for i in ids if quality[i] > 0]
    capacity = .25*math.fsum(energy[i] for i in positive)
    # A slack budget is optimal only when all positive utility coordinates cap.
    if capacity < bm['baseline']-1e-12*max(1.,bm['baseline']):
        require(reason == 'positive_quality_cap_limited', 'missing zero-quality cap branch')
        for i in ids:
            close(planned[i], .5 if quality[i] > 0 else 0., 'slack optimum', 0, 1e-10)
        return {'max_kkt_residual':0.,'branch':reason}
    require(reason in ('allocated','positive_quality_cap_limited'), 'unknown solver branch')
    close(bm['executed'], bm['baseline'], 'binding eligible budget', 2e-9, 1e-12)
    free = [i for i in positive if 1e-10 < planned[i] < .5-1e-10]
    for i in ids:
        if quality[i] == 0:
            close(planned[i], 0., 'zero-utility allocation', 0, 1e-10)
    if free:
        require(reason == 'allocated', 'free positive coordinates reported as cap-limited')
        # Stationarity gives rho=u/(2a); no active-set algorithm is duplicated.
        rho = quality[free[0]]/(2*planned[free[0]])
        residuals = []
        for i in ids:
            g = quality[i]-2*rho*planned[i]
            residual = max(g,0.) if planned[i] <= 1e-10 else max(-g,0.) if planned[i] >= .5-1e-10 else abs(g)
            require(residual <= 1e-8, 'KKT stationarity/complementarity failure')
            residuals.append(residual)
        close(record.get('waterfill_multiplier'), 1/(2*rho), 'waterfill multiplier', 2e-9, 1e-12)
        return {'max_kkt_residual':max(residuals,default=0.),'branch':reason}
    require(all(abs(planned[i]-.5) <= 1e-10 for i in positive), 'no free positive coordinate without saturation')
    return {'max_kkt_residual':0.,'branch':reason}


def normalized_ratio(a, b, a0, b0):
    """Stable log-odds replay, independent of controller cross-product arithmetic."""
    if a == b == 0:
        return 0., 0.
    if a == 0:
        return 0., 1.
    if b == 0:
        return 1., 0.
    delta = (math.log(b)-math.log(b0))-(math.log(a)-math.log(a0))
    if delta >= 0:
        z = math.exp(-delta);u = z/(1+z)
    else:
        z = math.exp(delta);u = 1/(1+z)
    return u, 1-u


def check_calibration(c, previous, step, block, current_valid, floor):
    require(isinstance(c, dict), 'missing quality calibration')
    require(c.get('step_index') == step and c.get('layer_index') == block, 'calibration identity')
    a = number(c.get('temporal_energy'), 'A', 0)
    b = number(c.get('complement_energy'), 'B', 0)
    count = number(c.get('valid_probe_count'), 'valid count', 0)
    require(count.is_integer(), 'fractional probe count')
    inputs_valid = count > 0
    require(flag(c.get('inputs_valid'), 'inputs_valid') == inputs_valid, 'calibration inputs mask')
    require(inputs_valid == current_valid, 'masked count does not match local evidence')
    if not inputs_valid:
        require(a == b == 0, 'invalid calibration inputs not excluded')
    scale = max(a,b)
    can_anchor = inputs_valid and scale > sys.float_info.min and a > floor*scale and b > floor*scale
    created = previous is None and can_anchor
    initialized = previous is not None or created
    a0,b0,anchor_step = (a,b,step) if created else previous if previous else (1.,1.,-1)
    adequate = scale > sys.float_info.min and scale > floor*max(a0,b0)
    used = previous is not None and inputs_valid and adequate
    for name, expected in [('anchor_created',created),('initialized',initialized),('used_anchor',used),
                           ('fallback',not used and not created),('low_current_energy',not adequate)]:
        require(flag(c.get(name),name) == expected, 'calibration '+name)
    require(c.get('anchor_step') == anchor_step, 'anchor step overwritten/future')
    expected_anchor = (a0,b0) if initialized else (0.,0.)
    require((c.get('anchor_temporal'),c.get('anchor_complement')) == expected_anchor, 'A0/B0 changed or wrong initial anchor')
    vt,vn = normalized_ratio(a,b,a0,b0)
    close(c.get('normalized_temporal'),vt,'normalized temporal quality',1e-9,1e-12)
    close(c.get('normalized_complement'),vn,'normalized complement quality',1e-9,1e-12)
    close(c.get('effective_collateral'),3.,'reused anchor collateral',0,0)
    close(c.get('prior_weight'),1.,'reused anchor prior',0,0)
    require('alpha' not in c and 'alpha_unclipped' not in c, 'instantaneous anchor alpha must not masquerade as applied layer alpha')
    return ((a0,b0,anchor_step) if initialized else None), (created or used), (.5 if created else vt), (not adequate)


def check_layer_budget(doc, expected_steps=20, blocks=50):
    """Audit a complete full-window layer-budget trace; raises LayerAuditError."""
    require(type(expected_steps) is int and expected_steps >= 2 and type(blocks) is int and blocks > 0,
            'positive complete dimensions required')
    require(isinstance(doc, dict), 'runtime audit must be an object')
    require(doc.get('schema') == 'h3-causal-layer-budget-v1', 'wrong layer schema')
    require(doc.get('status') in ('sampling','complete','completed') and not doc.get('error'), 'failed/unrun runtime')
    require(not doc.get('offline_counterfactual'), 'offline counterfactual is not runtime evidence')
    for key in ('started_calls','completed_calls','native_override_calls','routed_calls'):
        require(type(doc.get(key)) is int and doc[key] == expected_steps*blocks, 'incomplete '+key)
    require(doc.get('completed_forward_calls') == expected_steps, 'incomplete forwards')
    for k in ('calls_by_forward','routed_by_forward'):
        require(doc.get(k) == [blocks]*expected_steps, k+' counts')
    for k in ('calls_by_block','routed_by_block'):
        require(doc.get(k) == [expected_steps]*blocks, k+' counts')
    require(doc.get('expected_sampling_steps') == expected_steps, 'sigma step count')
    require(doc.get('step_interval_half_open') == [0,expected_steps] and doc.get('block_interval_half_open') == [0,blocks], 'not full applied window')
    require(doc.get('full_dit_forward_calls_added') == doc.get('intermediate_vae_decode_calls') == 0, 'unexpected model/decode calls')
    require(doc.get('current_step_exact_budget_conservation') is False, 'misdeclared exact current budget')
    require('pre-Wo' in doc.get('metric_scope','') and 'selected output queries' in doc.get('metric_scope',''), 'wrong metric scope')
    cfg=doc.get('feature_config',{})
    require(cfg.get('mode')=='layer_budget' and cfg.get('alpha_prior')==.25 and cfg.get('alpha_max')==.5 and cfg.get('probes')==8 and cfg.get('basis')=='centered' and cfg.get('relative_floor')==1e-8, 'unfrozen config')
    dtype=doc.get('first_attention',{}).get('dtype')
    require(dtype in ('torch.float16','torch.bfloat16','torch.float32','torch.float64'), 'unknown accumulation dtype')
    tiny=sys.float_info.min if dtype=='torch.float64' else 1.1754943508222875e-38
    heads=doc.get('first_attention',{}).get('heads')
    require(type(heads) is int and heads>0,'missing head count')
    forwards=doc.get('feature_forward_summaries');budgets=doc.get('layer_budget_summaries');base=doc.get('forward_summaries')
    require(all(isinstance(x,list) and len(x)==expected_steps for x in (forwards,budgets,base)), 'missing complete summaries')
    anchors={};previous_e=[0.]*blocks;plan=[.25]*blocks;all_alpha=[];by_layer=[[] for _ in range(blocks)]
    fallback_count=anchor_low=0;max_kkt=0.;curves=[];branches={}
    for step,(forward,summary,basic) in enumerate(zip(forwards,budgets,base)):
        label=f'forward {step}'
        require(forward.get('forward')==summary.get('forward')==basic.get('forward_index')==step, 'unordered forward identity')
        require(basic.get('completed_blocks')==basic.get('routed_blocks')==blocks,'basic block summary')
        layers=forward.get('layers',[])
        require(len(layers)==blocks and [r.get('block') for r in layers]==list(range(blocks)), 'ordered layer coverage')
        require(summary.get('plan_source_forward')==step-1 and summary.get('plan_for_forward')==step and summary.get('next_plan_for_forward')==step+1,'causal plan source')
        same_vector(summary.get('planned_alpha'),plan,'plan continuity',1e-12,1e-12)
        same_vector(summary.get('previous_relative_energy'),previous_e,'previous energy continuity',1e-12,1e-12)
        actual=[];energy=[];quality=[];eligible=[]
        for block,row in enumerate(layers):
            require(row.get('forward')==step and row.get('plan_source_forward')==step-1 and row.get('plan_for_forward')==step,'layer causal identity')
            require(row.get('mode')=='layer_budget' and row.get('applied') is True and row.get('finite_output') is True and row.get('attention_calls')==5,'inactive/nonfinite layer')
            require(row.get('boundary_probes_excluded') is True,'endpoint statistics mask')
            alpha=vector(row.get('alpha'),heads,'alpha',0,.5)
            require(all(x==alpha[0] for x in alpha),'per-layer alpha differs across heads')
            aa=alpha[0];actual.append(aa);all_alpha.append(aa);by_layer[block].append(aa)
            for k in ('alpha_mean','alpha_min','alpha_max'):close(row.get(k),aa,k,1e-10,1e-12)
            close(row.get('requested_alpha'),plan[block],'requested plan',1e-12,1e-12)
            head_e=vector(row.get('head_energy'),heads,'head energy',0)
            d2=number(row.get('correction_energy'),'D2',0);o2=number(row.get('native_energy'),'O2',0)
            close(d2,math.fsum(head_e),'full correction energy')
            close(row.get('applied_energy'),math.fsum(e*a*a for e,a in zip(head_e,alpha)),'applied energy')
            valid_e=o2>tiny and d2>tiny and o2>cfg['relative_floor']*max(o2,d2)
            require(flag(row.get('relative_energy_valid'),'energy_valid')==valid_e,'relative energy validity')
            ee=d2/(o2+tiny) if valid_e else 0.
            close(row.get('relative_correction_energy'),ee,'relative correction energy')
            # Runtime e was reduced in FP32; retain its recorded rounded value.
            energy.append(number(row.get('relative_correction_energy'),'relative energy',0))
            raw=flag(row.get('raw_probe_evidence_valid'),'raw evidence')
            current=flag(row.get('current_evidence_valid'),'current evidence')
            require(current==(raw and valid_e),'current/raw evidence mask')
            local=flag(row.get('local_fallback_to_prior'),'local fallback')
            require(local==(not current),'local fallback mask')
            close(aa,.25 if local else plan[block],'actual alpha/fallback',2e-7,1e-8)
            if step<2:close(aa,.25,'first two steps prior',0,1e-12)
            state,anchor_valid,u,low=check_calibration(row.get('quality_calibration'),anchors.get(block),step,block,current,cfg['relative_floor'])
            if state is not None:anchors[block]=state
            ev=anchor_valid and current and energy[-1]>0
            require(flag(row.get('current_anchor_evidence_valid'),'anchor mask')==anchor_valid,'anchor eligibility mask')
            require(flag(row.get('anchor_low_current_energy'),'low anchor energy')==low,'old-anchor low energy mask')
            require(flag(row.get('next_plan_eligible'),'next eligibility')==ev and flag(row.get('allocation_eligible'),'allocation eligibility')==ev,'next/current eligibility conflated')
            qu=u if ev else .5;quality.append(qu);eligible.append(ev)
            close(row.get('allocation_quality'),qu,'quality for next plan',1e-9,1e-12)
            number(row.get('reference_mass_mean'),'reference mass',0,1)
            number(row.get('controller_gpu_dispatch_seconds'),'host dispatch seconds',0)
            fallback_count+=local;anchor_low+=low
        same_vector(summary.get('actual_alpha'),actual,'summary actual alpha',1e-12,1e-12)
        same_vector(summary.get('current_relative_energy'),energy,'summary current energy',1e-12,1e-12)
        same_vector(summary.get('current_quality'),quality,'summary quality',1e-9,1e-12)
        require(flags(summary.get('current_eligible'),blocks,'summary eligible')==eligible,'summary eligibility')
        pm=check_measure(summary.get('predicted_plan_budget'),previous_e,plan,label+' planned old metric')
        em=check_measure(summary.get('predicted_executed_budget'),previous_e,actual,label+' actual old metric')
        cm=check_measure(summary.get('current_actual_drift'),energy,actual,label+' current drift')
        next_plan=vector(summary.get('next_alpha'),blocks,'next alpha',0,.5)
        certificate=check_allocation(summary.get('allocation',{}),quality,energy,eligible,next_plan)
        max_kkt=max(max_kkt,certificate['max_kkt_residual']);branch=certificate['branch'];branches[branch]=branches.get(branch,0)+1
        for key in ('statistics_transfer_seconds','waterfill_cpu_seconds','finish_controller_host_seconds'):number(summary.get(key),key,0)
        require(summary.get('statistics_transfer_bytes')==blocks*8*8,'sufficient-statistics buffer size')
        curves.append({'step':step,'alpha':actual,'alpha_mean':math.fsum(actual)/blocks,'planned_previous_metric_ratio':pm['ratio'],'executed_previous_metric_ratio':em['ratio'],'current_actual_ratio':cm['ratio'],'eligible_layers':sum(eligible)})
        previous_e,plan=energy,next_plan
    return {'passed':True,'status':'passed','forwards':expected_steps,'layer_calls':len(all_alpha),
            'alpha_mean':math.fsum(all_alpha)/len(all_alpha),'alpha_min':min(all_alpha),'alpha_max':max(all_alpha),
            'created_layer_anchors':len(anchors),'local_fallback_count':fallback_count,'anchor_low_energy_count':anchor_low,
            'max_kkt_residual':max_kkt,'allocation_branches':branches,'step_curves':curves,
            'layer_alpha_mean':[math.fsum(x)/len(x) for x in by_layer],
            'budget_scope':'previous-step pre-Wo local relative energy; current actual ratio is measured drift',
            'timing_scope':'controller_gpu_dispatch_seconds is host dispatch, not measured GPU elapsed; transfer_bytes counts only sufficient-statistics buffer'}


check_layer = check_layer_budget


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('audit');args=parser.parse_args()
    try:
        doc=json.load(sys.stdin) if args.audit=='-' else json.loads(Path(args.audit).read_text())
        print(json.dumps(check_layer_budget(doc),ensure_ascii=False,allow_nan=False))
    except (LayerAuditError,KeyError,TypeError,ValueError,OverflowError) as exc:
        print(json.dumps({'passed':False,'error':str(exc)},ensure_ascii=False));return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
