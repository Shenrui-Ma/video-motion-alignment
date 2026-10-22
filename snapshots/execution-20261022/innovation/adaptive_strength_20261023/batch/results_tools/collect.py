"""Incremental, read-only adaptive-batch audit and fresh metric collection."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import shlex
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
sys.path.insert(0, str(BATCH))
import audit as audit_check
import field_audit
import layer_audit
import role5_audit
import uniform_audit
import summarize as metric_summary


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def read(path, default):
    return json.loads(path.read_text()) if path.is_file() else default


def merge_plans(base, additions, holds=(), receipts=(), sources=()):
    """Build a collector-only plan; canonical inputs remain untouched."""
    result = copy.deepcopy(base)
    jobs = result.get('jobs', [])
    seen = {j['id'] for j in jobs}
    if len(seen) != len(jobs):
        raise ValueError('duplicate base job id')
    for extra in additions:
        for job in extra['jobs']:
            if job['id'] in seen:
                raise ValueError('duplicate extra job id: '+job['id'])
            seen.add(job['id']);jobs.append(copy.deepcopy(job))
    identities = [(j['metadata']['task_id'],j['metadata']['method']) for j in jobs]
    if len(set(identities)) != len(identities):
        raise ValueError('ambiguous planned task/method')
    by_id = {j['id']:j for j in jobs}
    for receipt in holds:
        jid = receipt['job_id']
        if jid not in by_id or not receipt.get('status','').startswith('research_hold') or receipt.get('unsubmitted_verified') is not True:
            raise ValueError('unverified research hold: '+jid)
        by_id[jid]['collection_hold'] = {'status':'research_hold','reason':receipt['status'],
                                       'receipt':receipt.get('_receipt')}
    ownership = assign_sources(result, {'sources':list(sources)}) if sources else {}
    anchor_proofs=set()
    for receipt in receipts:
        owner=receipt['owner_host']
        if receipt.get('status') != 'ready':
            raise ValueError('anchor ownership receipt is not ready')
        for job in receipt.get('pilots',{}).get('jobs',[]):
            if job['id'] in seen and ownership.get(job['id']) != owner:
                raise ValueError('resource receipt owner differs: '+job['id'])
            if job['id'] in seen and job.get('metadata',{}).get('method')=='dynamic_anchor':
                if job['id'] in anchor_proofs:
                    raise ValueError('duplicate anchor ownership receipt: '+job['id'])
                anchor_proofs.add(job['id'])
    if receipts:
        expected_anchors={j['id'] for j in jobs if j['metadata']['method']=='dynamic_anchor'}
        if anchor_proofs != expected_anchors:
            raise ValueError('anchor owner receipt coverage differs from planned anchors')
    result['collection_plan']={'canonical_base_count':len(base['jobs']),
        'added_count':len(jobs)-len(base['jobs']), 'ownership':ownership,
        'holds':[j['id'] for j in jobs if j.get('collection_hold')],
        'scope':'collector only; canonical manifests and remote queues unchanged'}
    return result


def assign_sources(planned, config):
    ids=[j['id'] for j in planned['jobs']]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate planned job identity')
    ownership={}
    names=[s['name'] for s in config['sources']]
    if len(set(names)) != len(names):
        raise ValueError('duplicate source name')
    for source in config['sources']:
        include=set(source.get('job_ids',[]));exclude=set(source.get('exclude_job_ids',[]))
        if not (include|exclude)<=set(ids) or include&exclude:
            raise ValueError('invalid explicit producer job selection: '+source['name'])
        for job in planned['jobs']:
            selected=(job['metadata']['task_id']==source.get('task_id') or job['id'] in include)
            if not selected or job['id'] in exclude:
                continue
            if job['id'] in ownership:
                raise ValueError('duplicate producer ownership: '+job['id'])
            ownership[job['id']]=source['name']
    if set(ownership) != set(ids):
        raise ValueError('not all planned jobs have one producer')
    expected=planned.get('collection_plan',{}).get('ownership',{})
    if expected and expected != ownership:
        raise ValueError('configured producers differ from collector plan')
    return ownership


def artifacts(snapshot):
    return {v['path']: v for row in snapshot.get('jobs', []) for k, v in row.items()
            if k in ('audit', 'timing', 'result', 'graph') and isinstance(v, dict) and 'data' in v}


def fetch(host, request):
    code = (HERE / 'remote_probe.py').read_text()
    cmd = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12', host,
           'python3 -c ' + shlex.quote(code)]
    proc = subprocess.run(cmd, input=json.dumps(request), text=True, capture_output=True, timeout=180)
    if proc.returncode:
        raise RuntimeError(host + ': ' + proc.stderr[-1500:])
    return json.loads(proc.stdout)


def hydrate(snapshot, previous):
    old = artifacts(previous)
    for row in snapshot.get('jobs', []):
        for name in ('audit', 'timing', 'result', 'graph'):
            value = row.get(name, {})
            if value.get('status') == 'unchanged':
                cached = old.get(value['path'])
                if cached is None or cached.get('version') != value['version']:
                    raise ValueError('incremental cache mismatch: ' + value['path'])
                value.update(data=cached['data'], sha256=cached['sha256'])
    return snapshot


def check_live(doc):
    """Check only recorded complete layers; missing future steps stay pending."""
    problems = []
    if doc.get('offline_counterfactual') or doc.get('evidence_kind') == 'offline_counterfactual':
        problems.append('offline counterfactual is not executed inference evidence')
    if doc.get('error') or doc.get('status') in ('failed', 'error'):
        problems.append('runtime audit error: ' + str(doc.get('error', doc.get('status'))))
    if doc.get('schema') in ('h3-feature-guidance-v1','h3-anchored-guidance-v1'):
        cfg = doc.get('feature_config', {})
        mode, prior, cap = cfg.get('mode'), cfg.get('alpha_prior'), cfg.get('alpha_max')
        anchors={}
        tiny=2.**-1022 if doc.get('first_attention',{}).get('dtype')=='torch.float64' else 2.**-126
        for n,forward in enumerate(doc.get('feature_forward_summaries', [])):
            seen=set()
            for row in forward.get('layers', []):
                label = f"step {row.get('forward')} layer {row.get('block')}"
                try:
                    audit_check.require(forward.get('forward')==n and row.get('forward')==n,
                                        'unordered live forward')
                    layer=audit_check.integer(row.get('block'),'live block')
                    audit_check.require(layer not in seen,'duplicate live layer');seen.add(layer)
                    if row.get('finite_output') is False:
                        raise audit_check.AuditError('nonfinite output')
                    if row.get('applied'):
                        values = audit_check.vector(row.get('alpha'), label+' alpha', minimum=0, maximum=cap)
                        audit_check.require(bool(values), 'empty alpha')
                        if mode=='anchor':
                            anchors[layer],_=audit_check._anchor_control(row,prior,cap,cfg,anchors.get(layer),n,layer,tiny)
                        else:
                            audit_check._control(row, mode, prior, cap, cfg)
                        energies = audit_check.vector(row.get('head_energy'), 'head_energy', length=len(values), minimum=0)
                        audit_check.close(row.get('applied_energy'), sum(a*a*e for a,e in zip(values,energies)), 'applied energy')
                except (audit_check.AuditError, TypeError, KeyError, ZeroDivisionError) as error:
                    problems.append(label + ': ' + str(error))
    elif doc.get('schema') == 'h3-causal-layer-budget-v1':
        # Partial liveness checks only. The independent full causal/KKT replay
        # runs below once a complete result and its output SHA exist.
        for n,forward in enumerate(doc.get('feature_forward_summaries', [])):
            seen=set()
            for row in forward.get('layers', []):
                try:
                    layer_audit.require(forward.get('forward')==n and row.get('forward')==n,'live forward identity')
                    block=row.get('block')
                    layer_audit.require(type(block) is int and 0<=block<50 and block not in seen,'live block identity');seen.add(block)
                    layer_audit.require(row.get('finite_output') is True and row.get('applied') is True,'nonfinite/inactive layer')
                    values=layer_audit.vector(row.get('alpha'),doc['first_attention']['heads'],'actual alpha',0,.5)
                    layer_audit.require(all(a==values[0] for a in values),'layer alpha varies across heads')
                    layer_audit.require(row.get('plan_source_forward')==n-1 and row.get('plan_for_forward')==n,'noncausal layer plan')
                    local=layer_audit.flag(row.get('local_fallback_to_prior'),'local fallback')
                    layer_audit.close(values[0],.25 if local else row.get('requested_alpha'),'applied plan',2e-7,1e-8)
                    if n<2:layer_audit.close(values[0],.25,'first two steps',0,1e-12)
                    energy=layer_audit.vector(row.get('head_energy'),len(values),'head energy',0)
                    layer_audit.close(row.get('applied_energy'),sum(e*a*a for e,a in zip(energy,values)),'actual correction energy')
                except (layer_audit.LayerAuditError,TypeError,KeyError,ZeroDivisionError) as error:
                    problems.append(f'step {n} layer {row.get("block")}: {error}')
    elif doc.get('schema') == 'h3-temporal-gain-field-uniform-energy-v1':
        if doc.get('feature_config', {}).get('mode') != 'gain_field_uniform_energy':
            problems.append('uniform-energy mode mismatch')
        if doc.get('independent_field_trajectory_energy_matched') is not False:
            problems.append('invalid cross-trajectory energy claim')
        for n, forward in enumerate(doc.get('feature_forward_summaries', [])):
            seen = set()
            for row in forward.get('layers', []):
                try:
                    uniform_audit.require(forward.get('forward') == n and row.get('forward') == n,
                                          'live uniform forward identity')
                    block = row.get('block')
                    uniform_audit.require(type(block) is int and 0 <= block < 50 and block not in seen,
                                          'live uniform block identity')
                    seen.add(block)
                    uniform_audit.check_uniform_layer(row)
                except (uniform_audit.FieldAuditError, TypeError, KeyError, ZeroDivisionError) as error:
                    problems.append(f'step {n} layer {row.get("block")}: {error}')
    elif doc.get('schema') in ('h3-temporal-gain-field-v1','h3-temporal-gain-field-role5-v1'):
        for forward in doc.get('feature_forward_summaries', []):
            for row in forward.get('layers', []):
                try:
                    checked=row
                    if doc['schema']=='h3-temporal-gain-field-role5-v1':
                        bins=row['latent_bin_indices'];lo,hi=bins[0],bins[-1]+1
                        mask=[lo+5<=i<hi-5 for i in bins]
                        shadow=forward['forward'] in (0,9,19) and row['block'] in (8,25,42) and len(bins)>=11
                        field_audit.require(row['role5_mask']==mask,'live role5 mask')
                        field_audit.require(row['neighbor_previous']==[max(lo,i-(5 if m else 1)) for i,m in zip(bins,mask)],'live previous indices')
                        field_audit.require(row['neighbor_following']==[min(hi-1,i+(5 if m else 1)) for i,m in zip(bins,mask)],'live following indices')
                        field_audit.require(('shadow' in row)==shadow and row['shadow_attention_calls']==2*shadow,'live shadow schedule')
                        field_audit.require(row['attention_calls']==5+2*shadow,'live role5 call count')
                        checked=dict(row,attention_calls=5)
                    field_audit.check_layer(checked)
                except (field_audit.FieldAuditError,TypeError,KeyError,ZeroDivisionError) as error:
                    problems.append(f"step {row.get('forward')} layer {row.get('block')}: {error}")
    elif doc.get('schema') == 'h3-temporal-coverage-blend':
        for row in doc.get('coverage_calls', []):
            try:
                audit_check.close(row.get('coverage_mix'), .25, 'coverage mix')
                audit_check.number(row.get('mean_diagonal_probability'), 'identity anchor', minimum=.75-1e-6, maximum=1+1e-6)
            except (audit_check.AuditError, TypeError) as error:
                problems.append(f"step {row.get('forward')} layer {row.get('block')}: {error}")
        for forward in doc.get('forward_summaries', []):
            if forward.get('sampled_finite') is False:
                problems.append('nonfinite coverage forward ' + str(forward.get('forward_index')))
    else:
        problems.append('unrecognized audit schema: ' + str(doc.get('schema')))
    return problems


def curves(doc):
    points = []
    for forward in doc.get('feature_forward_summaries', []):
        for row in forward.get('layers', []):
            if not row.get('applied'):
                continue
            control = row.get('control') or row.get('quality_calibration', {})
            points.append({'step': row['forward'], 'layer': row['block'], 'alpha': row.get('alpha'),
                'alpha_mean': row.get('alpha_mean'), 'alpha_min': row.get('alpha_min'), 'alpha_max': row.get('alpha_max'),
                'reference_mass_mean': row.get('reference_mass_mean'),
                'correction_energy': row.get('correction_energy'), 'applied_energy': row.get('applied_energy'),
                'fallback': row.get('local_fallback_to_prior',control.get('fallback')), 'valid_probe_count': control.get('valid_probe_count'),
                'plan_source_forward':row.get('plan_source_forward'),
                'requested_alpha':row.get('requested_alpha'),
                'relative_correction_energy':row.get('relative_correction_energy'),
                'temporal_variance': control.get('temporal_variance'),
                'complement_variance': control.get('complement_variance'),
                'temporal_energy': control.get('temporal_energy'),
                'complement_energy': control.get('complement_energy'),
                'anchor_temporal': control.get('anchor_temporal'),
                'anchor_complement': control.get('anchor_complement'),
                'anchor_step': control.get('anchor_step'),
                'anchor_created': control.get('anchor_created'),
                'used_anchor': control.get('used_anchor'),
                'normalized_temporal': control.get('normalized_temporal'),
                'normalized_complement': control.get('normalized_complement'),
                'fallback_to_prior': control.get('fallback_to_prior'),
                'solver_succeeded': control.get('solver_succeeded'),
                'usable_evidence': control.get('usable_evidence'),
                'boundary_probes_excluded': row.get('boundary_probes_excluded', doc.get('boundary_probes_excluded'))})
    if doc.get('schema') == 'h3-temporal-gain-field-uniform-energy-v1':
        recorded = [row for f in doc.get('feature_forward_summaries', [])
                    for row in f.get('layers', []) if row.get('applied')]
        for point, row in zip(points, recorded):
            # alpha and alpha_mean always describe the actually applied gain.
            point.update(candidate_alpha=row.get('candidate_alpha'),
                         uniform_energy=row.get('uniform_energy'),
                         uniform_host_dispatch_seconds=row.get('uniform_host_dispatch_seconds'),
                         qp_scope='candidate_alpha only; alpha is applied uniform RMS')
    if doc.get('schema') == 'h3-temporal-coverage-blend':
        points = [{'step': r['forward'], 'layer': r['block'], 'alpha': [doc.get('alpha')],
                   'alpha_mean': doc.get('alpha'), 'coverage_mix': r.get('coverage_mix'),
                   'mean_diagonal_probability': r.get('mean_diagonal_probability'),
                   'routing_solved': r.get('routing_solved')} for r in doc.get('coverage_calls', [])]
    return {'audit_schema': doc.get('schema'),
            'indexing': 'zero-based actual denoising forward and DiT block',
            'scope': 'recorded complete layer calls only; no interpolation',
            'controller_statistics_scope': 'valid-window first/last bins excluded; centered temporal features in interior',
            'applied_correction_scope': 'all selected valid video bins, including endpoints; attention output before W_o',
            'feature_config': doc.get('feature_config'), 'coverage_config': doc.get('coverage_config'),
            'timing_scope': 'actual producer timing; cross-host differences are not isolated module cost',
            'layer_budget_summaries':doc.get('layer_budget_summaries'),
            'points': points}


def inspect_row(plan, row, producer, output):
    state = row.get('queue_state', {})
    result = row.get('result', {}).get('data', {})
    doc = row.get('audit', {}).get('data')
    out = {'job_id': plan['id'], 'task_id': plan['metadata']['task_id'], 'method': plan['metadata']['method'],
           'producer_host': producer, 'queue_status': state.get('status', 'pending'),
           'actual_attempt_id': row.get('actual_attempt_id'), 'prompt_id': result.get('prompt_id', state.get('prompt_id')),
           'attempts': state.get('attempts', 0), 'status': 'pending', 'issues': [],
           'audit_sha256': row.get('audit', {}).get('sha256'),
           'result_sha256': row.get('result', {}).get('sha256'),
           'graph_sha256': row.get('graph', {}).get('sha256'), 'media': row.get('media', []),
           'timing': result.get('timing') or row.get('timing', {}).get('data'),
           'reason': 'awaiting_attempt_audit'}
    hold=plan.get('collection_hold')
    if hold:
        out.update(status='research_hold', reason=hold['reason'], research_hold=hold)
        if result or state.get('status') in ('submitted','submitting','running','submission_unknown'):
            out.update(status='attention_required', reason='held_job_has_execution_evidence')
            out['issues'].append('research hold conflicts with execution evidence; reconcile ownership receipt')
        return out
    if doc:
        if doc.get('run_id') != out['actual_attempt_id']:
            out['issues'].append('audit run_id differs from actual attempt')
        method = plan['metadata']['method']
        expected_mode = {'dynamic_dof': 'dynamic_strength_dof', 'heads_budget': 'heads_budget',
                         'fixed0375': 'fixed', 'dynamic_anchor':'anchor', 'temporal_gain_field':'gain_field',
                         'causal_layer_budget':'layer_budget','temporal_gain_field_role5':'gain_field',
                         'temporal_gain_field_uniform_energy':'gain_field_uniform_energy'}.get(method)
        if expected_mode and doc.get('feature_config', {}).get('mode') != expected_mode:
            out['issues'].append('audit feature mode differs from planned method')
        if method == 'coverage_blend25' and doc.get('schema') != 'h3-temporal-coverage-blend':
            out['issues'].append('coverage blend audit schema mismatch')
        if method == 'dynamic_anchor' and doc.get('schema') != 'h3-anchored-guidance-v1':
            out['issues'].append('anchor audit schema mismatch')
        if method == 'temporal_gain_field_role5' and doc.get('schema') != 'h3-temporal-gain-field-role5-v1':
            out['issues'].append('role5 audit schema mismatch')
        if method == 'temporal_gain_field_uniform_energy' and doc.get('schema') != 'h3-temporal-gain-field-uniform-energy-v1':
            out['issues'].append('uniform-energy audit schema mismatch')
        out['issues'].extend(check_live(doc))
        out['completed_forward_calls'] = doc.get('completed_forward_calls', 0)
        out['alpha_curve_file'] = 'alpha_curves/' + plan['id'] + '.json'
        curve = curves(doc)
        values = [a for point in curve['points'] for a in (point.get('alpha') or [])]
        if values and all(type(a) in (int, float) and math.isfinite(a) for a in values):
            cap = doc.get('feature_config', {}).get('alpha_max', doc.get('alpha'))
            out['live_alpha_statistics'] = {'count': len(values), 'mean': sum(values)/len(values),
                'min': min(values), 'max': max(values),
                'fraction_at_cap': sum(a >= cap-1e-6 for a in values)/len(values),
                'recorded_layer_calls': len(curve['points']),
                'layer_fraction_at_cap': sum(all(a >= cap-1e-6 for a in p['alpha']) for p in curve['points'])/len(curve['points']),
                'fallback_layer_fraction': sum(p.get('fallback') is True for p in curve['points'])/len(curve['points']),
                'fraction_at_prior': sum(abs(a-doc.get('feature_config',{}).get('alpha_prior',doc.get('alpha'))) <= 1e-6 for a in values)/len(values)}
        write(output / out['alpha_curve_file'], dict(curve, job_id=plan['id'],
              actual_attempt_id=out['actual_attempt_id'], audit_sha256=out['audit_sha256']))
        out.update(status='in_progress', reason='recorded_layers_checked; waiting_complete_result')
    if state.get('status') in ('failed', 'invalid', 'failed_attempt'):
        out['issues'].append('queue ' + state['status'] + ': ' + str(state.get('error')))
    if result:
        if result.get('job_id') != plan['id'] or result.get('attempt_id') != out['actual_attempt_id']:
            out['issues'].append('producer result identity mismatch')
        if doc:
            try:
                check = {'coverage_blend25':audit_check.check_coverage_blend,
                         'temporal_gain_field':field_audit.check_field,
                         'temporal_gain_field_role5':role5_audit.check_role5,
                         'temporal_gain_field_uniform_energy':uniform_audit.check_uniform,
                         'causal_layer_budget':layer_audit.check_layer_budget,
                         'dynamic_anchor':audit_check.check_anchor}.get(plan['metadata']['method'],audit_check.check_feature)
                out['complete_audit'] = check(doc)
            except (audit_check.AuditError, field_audit.FieldAuditError, layer_audit.LayerAuditError,
                    uniform_audit.FieldAuditError, TypeError, KeyError) as error:
                out['issues'].append('complete audit: ' + str(error))
        else:
            out['reason'] = 'completed_result_missing_audit'
        if not out['media'] or any(m.get('status') != 'verified' for m in out['media']):
            out['issues'].append('completed output absent or SHA verification failed')
        if doc and not out['issues']:
            out.update(status='verified', reason='audit_result_media_verified')
    if out['issues']:
        out['status'] = 'attention_required'
    return out


def completed_metrics(planned, rows, metrics):
    """Only SHA-verified completed media enter scientific metric denominators."""
    verified={r['job_id'] for r in rows if r['status']=='verified'}
    selected=[j for j in planned['jobs'] if j['id'] in verified and not j.get('collection_hold')]
    if selected:
        scores=metric_summary.summarize({'jobs':selected},metrics['manifest'],metrics['evaluation'])
    else:
        scores={'schema':'h3-adaptive-independent-summary-v1','cohort':metric_summary.COHORT,
                'n_planned':0,'n_registered':0,'cases':[],'methods':{},
                'official_nine_metrics':list(metric_summary.OFFICIAL_NINE),
                'awq_metrics':list(metric_summary.AWQ_METRICS),
                'qa_scope':'quantity_accuracy separately; official applicability applies',
                'evidence_scope':'no completed SHA-verified media; no metric values reported'}
    scores['collection_selection']={'total_planned':len(planned['jobs']),
        'completed_media':len(selected),'research_hold':sum(bool(j.get('collection_hold')) for j in planned['jobs']),
        'excluded':[{'job_id':r['job_id'],'status':r['status'],'reason':r['reason']} for r in rows if r['job_id'] not in verified],
        'denominator_scope':'completed media only; research hold and unfinished jobs do not enter metric denominators'}
    return scores


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='no SSH; absent evidence remains pending')
    parser.add_argument('--config', type=Path, default=HERE/'sources.json')
    parser.add_argument('--jobs', type=Path, default=HERE/'all_jobs.json' if (HERE/'all_jobs.json').is_file() else BATCH/'jobs.json',
                        help='explicit canonical or collector-only combined job manifest')
    parser.add_argument('--output', type=Path, default=HERE/'latest')
    args = parser.parse_args()
    planned = read(args.jobs, {})
    config = read(args.config, {})
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {'schema': 'h3-adaptive-live-results-v1', 'collected_at_unix': time.time(),
              'dry_run': args.dry_run, 'jobs': [], 'source_errors': [], 'read_only_remote': True}
    ownership = assign_sources(planned,config)
    report['planned_jobs']={'path':str(args.jobs.resolve()),'sha256':hashlib.sha256(args.jobs.read_bytes()).hexdigest(),
                            'count':len(planned['jobs']),'ownership':ownership}
    for source in config['sources']:
        jobs = [j for j in planned['jobs'] if ownership[j['id']] == source['name']]
        cache_path = output/'snapshots'/(source['name']+'.json')
        previous = read(cache_path, {})
        request = dict(source, jobs=jobs, known={k: v['version'] for k,v in artifacts(previous).items()},
                       known_media={m['path']: m for row in previous.get('jobs', []) for m in row.get('media', [])})
        try:
            snapshot = {'jobs': []} if args.dry_run else hydrate(fetch(source['host'], request), previous)
            if not args.dry_run:
                write(cache_path, snapshot)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            report['source_errors'].append({'source': source['name'], 'error': str(error)})
            snapshot = {'jobs': []}  # Never pass an old snapshot as current evidence.
        lookup = {r['job_id']: r for r in snapshot['jobs']}
        report['jobs'].extend(inspect_row(j, lookup.get(j['id'], {}), source['name'], output) for j in jobs)
    metrics = {'manifest': {'jobs': []}, 'evaluation': {'rows': []}, 'sources': {}}
    if not args.dry_run:
        try:
            metrics = fetch(config['metrics']['host'], dict(config['metrics'], kind='metrics',
                tasks=sorted({j['metadata']['task_id'] for j in planned['jobs']}), job_ids=sorted(ownership)))
            if any(x.get('status') != 'read' for x in metrics['sources'].values()):
                report['source_errors'].append({'source': 'metrics', 'error': 'fresh metrics file missing/unreadable'})
            write(output/'snapshots/metrics_fresh.json', metrics)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            report['source_errors'].append({'source': 'metrics', 'error': str(error)})
    try:
        scores = completed_metrics(planned,report['jobs'],metrics)
        scores['fresh_sources'] = metrics['sources']
        scores['fetched_at_unix'] = metrics.get('fetched_at_unix')
        write(output/'official_metrics.json', scores)
        report['official_metrics_file'] = 'official_metrics.json'
        report['metric_rows_fetched'] = len(metrics['evaluation']['rows'])
    except (metric_summary.SummaryError, ValueError, KeyError, TypeError) as error:
        report['source_errors'].append({'source': 'metric_join', 'error': str(error)})
        write(output/'official_metrics.json', {'status':'failed','error':str(error),
              'cases':[],'methods':{},'evidence_scope':'current join failed; old metric report not reused'})
    report['counts'] = {s: sum(r['status'] == s for r in report['jobs'])
                        for s in ('pending', 'in_progress', 'verified', 'research_hold', 'attention_required')}
    write(output/'status.json', report)
    print(json.dumps({'counts': report['counts'], 'source_errors': report['source_errors'],
                      'output': str(output), 'metric_rows_fetched': report.get('metric_rows_fetched', 0)}, ensure_ascii=False))
    return 1 if report['source_errors'] or report['counts']['attention_required'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
