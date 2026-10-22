"""Independent, denominator-aware adaptive-cohort report from explicit raw rows.

Reads planned jobs, the relayed metrics manifest, and evaluation/summary.json.
Never consumes summary.means, edits the old aggregate, accesses a queue, or runs
an evaluator. A fresh summary path is required by the CLI; no cache fallback.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys


COHORT = 'adaptive_research_20261023'
OFFICIAL_NINE = ('subject_consistency', 'background_consistency', 'temporal_flickering',
                 'motion_smoothness', 'vtss', 'overall_semantic_consistency',
                 'phrase_semantic_consistency', 'semantic_fidelity', 'motion_fidelity')
AWQ_METRICS = ('instruction_satisfaction', 'content_fidelity')
ALL_METRICS = OFFICIAL_NINE + AWQ_METRICS + ('quantity_accuracy',)
CONTROLS = ('native', 'global_weak')


class SummaryError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise SummaryError(message)


def numeric(value, label, *, nonnegative=False):
    require(type(value) in (int, float) and math.isfinite(value), label + ': finite number required')
    require(not nonnegative or value >= 0, label + ': negative value')
    return float(value)


def mean(values):
    return statistics.mean(values) if values else None


def _jobs(value, name):
    require(isinstance(value, dict) and isinstance(value.get('jobs'), list), name + ': jobs list required')
    require(all(isinstance(j, dict) and isinstance(j.get('id'), str) for j in value['jobs']), name + ': invalid job')
    ids = [j['id'] for j in value['jobs']]
    require(len(ids) == len(set(ids)), name + ': duplicate job id')
    return value['jobs']


def _plan(job):
    m=job.get('metadata', {})
    require(isinstance(m, dict), 'planned metadata required')
    out={'id':job['id'], 'task_id':m.get('task_id'), 'dataset':m.get('benchmark'),
         'method':m.get('method'), 'cohort':m.get('cohort'), 'title':m.get('title'),
         'metadata':m.get('evaluation_metadata', m.get('original_task', {})),
         'comparison_outputs':m.get('comparison_outputs', {}), 'seed':m.get('seed')}
    require(all(isinstance(out[k], str) and out[k] for k in ('task_id','dataset','method')), 'planned job identity missing')
    return out


def _case(job):
    return job['dataset'], job['task_id']


def _unique(jobs, case, method):
    candidates=[j for j in jobs if (j.get('dataset'),j.get('task_id')) == case and j.get('method') == method]
    require(len(candidates)<=1, f'ambiguous jobs for {case!r} method {method}: {[j["id"] for j in candidates]}')
    return candidates[0] if candidates else None


def applicability(metric, metadata):
    """Exact rules of this workspace's official metric_worker applicability."""
    if metric == 'quantity_accuracy' and metadata.get('category','').strip().lower() != 'quantity_modification':
        return 'Official QA applies only to quantity_modification.'
    if metric == 'motion_fidelity' and (metadata.get('category') in ('subject_motion_editing','camera_motion_editing')
                                      or metadata.get('subcategory') == 'event effect'):
        return 'Official MF excludes tasks requesting motion changes.'
    return None


def _metric(job, metric, lookup, *, registered):
    reason=applicability(metric, job.get('metadata',{}))
    row=lookup.get((job['id'], metric))
    if row is None:
        if reason:
            return {'status':'not_applicable', 'score':None, 'reason':reason,
                    'basis':'official_worker_applicability_rule; no score inferred'}
        return {'status':'pending', 'score':None,
                'reason':('awaiting_evaluation_row' if registered else 'awaiting_manifest_relay')}
    for key in ('task_id','dataset','method'):
        require(row.get(key) == job.get(key), f'{job["id"]}/{metric}: {key} mismatch')
    if row.get('cohort') is not None and job.get('cohort') is not None:
        require(row['cohort'] == job['cohort'], f'{job["id"]}/{metric}: cohort mismatch')
    status=row.get('status')
    require(isinstance(status,str), f'{job["id"]}/{metric}: missing row status')
    if status == 'done':
        require(reason is None, f'{job["id"]}/{metric}: scored although official rule is not applicable')
        score=numeric(row.get('score'), f'{job["id"]}/{metric}')
        require(score != -1, f'{job["id"]}/{metric}: official error sentinel')
    else:
        score=None
        require(row.get('score') is None, f'{job["id"]}/{metric}: non-done row carries a score')
    out={'status':status if status in ('done','not_applicable','failed') else 'pending',
         'score':score, 'raw_status':status, 'official_commit':row.get('official_commit'),
         'evaluation_seed':row.get('evaluation_seed')}
    if row.get('reason') or row.get('error'):
        out['reason']=row.get('reason') or row['error']
    return out


def _timing(job):
    if job is None:
        return {'status':'pending', 'sampling_seconds':None, 'mean_step_seconds':None,
                'per_step_seconds':None, 'scope':None, 'reason':'awaiting_manifest_relay'}
    t=job.get('timing') or job.get('producer_result',{}).get('timing') or {}
    require(isinstance(t,dict), job['id']+': timing must be object')
    original=t.get('original_record') or {}
    samples=t.get('sampling_step_seconds', t.get('per_step_seconds', original.get('per_step_seconds')))
    if samples is not None:
        require(isinstance(samples,list), job['id']+': per-step timing must be array')
        samples=[numeric(x,'per_step_seconds',nonnegative=True) for x in samples]
    total=t.get('sampling_seconds')
    if total is not None:
        total=numeric(total,'sampling_seconds',nonnegative=True)
    step=t.get('mean_sampling_step_seconds',t.get('mean_step_seconds'))
    basis='reported_mean_sampling_step_seconds'
    if step is not None:
        step=numeric(step,'mean_sampling_step_seconds',nonnegative=True)
    elif samples:
        step=mean(samples);basis='arithmetic_mean_of_recorded_step_intervals'
    else:
        basis=None
    scope=t.get('scope')
    if scope is None and (total is not None or step is not None):
        scope='scope_not_recorded'
    return {'status':'available' if total is not None or step is not None else 'pending',
            'sampling_seconds':total, 'mean_step_seconds':step, 'per_step_seconds':samples,
            'n_recorded_steps':len(samples) if samples is not None else 0,
            'scope':scope, 'mean_step_basis':basis, 'measurement_basis':t.get('measurement_basis'),
            'measurement_resolution':t.get('measurement_resolution'),
            'source':t.get('sampling_source'), 'host':t.get('host') or job.get('producer_result',{}).get('metadata',{}).get('host'),
            'gpu_uuid':t.get('gpu_uuid') or original.get('gpu_uuid'),
            'execution_seconds':t.get('execution_seconds'),
            'note':'Actual reported timing; no estimate from configured steps or evaluator wall_seconds.'}


def _counts(items):
    counts={s:sum(i['status']==s for i in items) for s in ('done','not_applicable','failed','pending')}
    require(sum(counts.values())==len(items),'unrecognized metric status')
    return {'n_expected':len(items), 'n_done':counts['done'], 'n_applicable':len(items)-counts['not_applicable'],
            'n_not_applicable':counts['not_applicable'], 'n_failed':counts['failed'], 'n_pending':counts['pending']}


def _denominator(items):
    return {'mean':mean([i['score'] for i in items if i['status']=='done']),**_counts(items)}


def _difference(value, reference):
    statuses=[value['status'],reference['status']]
    status=next((s for s in ('not_applicable','failed','pending') if s in statuses),'done')
    return {'status':status,'score':value['score']-reference['score'] if status=='done' else None,
            'method_score':value['score'],'reference_self_score':reference['score']}


def _timing_group(rows):
    def summary(tt):
        total=[t['sampling_seconds'] for t in tt if t['sampling_seconds'] is not None]
        step=[t['mean_step_seconds'] for t in tt if t['mean_step_seconds'] is not None]
        return {'mean_sampling_seconds':mean(total),'n_sampling':len(total),'mean_step_seconds':mean(step),
                'n_step':len(step),'n_expected':len(tt),'n_pending':sum(t['status']=='pending' for t in tt)}
    out=summary(rows)
    out['by_scope']={scope:summary([t for t in rows if (t['scope'] or 'pending')==scope])
                     for scope in sorted({t['scope'] or 'pending' for t in rows})}
    out['comparison_note']='Different hosts, capture scopes, or measurement bases are reported, not treated as a controlled speed benchmark.'
    return out


def summarize(planned, manifest, evaluation, cohort=COHORT):
    """Build a complete planned-cohort report using evaluation.rows only."""
    plans=[_plan(j) for j in _jobs(planned,'planned') if j.get('metadata',{}).get('cohort')==cohort]
    require(plans,'no planned jobs for '+cohort)
    identities=[(_case(j),j['method']) for j in plans]
    require(len(set(identities))==len(identities),'duplicate planned task/method')
    actual=_jobs(manifest,'manifest')
    require(isinstance(evaluation,dict) and isinstance(evaluation.get('rows'),list),'evaluation.rows required; aggregate means are not an input')
    lookup={}
    for row in evaluation['rows']:
        require(isinstance(row,dict),'metric row must be object')
        if row.get('metric') not in ALL_METRICS:
            continue
        require(isinstance(row.get('job_id'),str),'metric row job_id required')
        key=(row['job_id'],row['metric'])
        require(key not in lookup,'duplicate/ambiguous evaluation row: '+repr(key))
        lookup[key]=row
    actual_ids={j['id']:j for j in actual}
    cases=[]
    for plan in plans:
        key=_case(plan);method=plan['method'];job=_unique(actual,key,method)
        for candidate_method in (method,)+CONTROLS+('source',):
            ids={r['job_id'] for r in lookup.values() if
                 (r.get('dataset'),r.get('task_id'))==key and r.get('method')==candidate_method}
            ids.update(j['id'] for j in actual if (j.get('dataset'),j.get('task_id'))==key and j.get('method')==candidate_method)
            require(len(ids)<=1,f'ambiguous result jobs for {key!r} method {candidate_method}: {sorted(ids)}')
            if candidate_method==method and ids:
                require(ids=={plan['id']},'adaptive result job differs from plan: '+plan['id'])
        if job is not None:
            require(job['id']==plan['id'],f'planned job id differs from registered {key}/{method}')
            require(job.get('cohort')==cohort,'registered adaptive cohort mismatch')
        elif plan['id'] in actual_ids:
            raise SummaryError('registered job identity differs from plan: '+plan['id'])
        score_job=job or plan
        scores={m:_metric(score_job,m,lookup,registered=job is not None) for m in ALL_METRICS}
        comparisons={}
        for control in CONTROLS+('source',):
            cj=_unique(actual,key,control)
            if cj is not None:
                expected_hash=plan.get('comparison_outputs',{}).get(control,{}).get('sha256')
                if expected_hash and cj.get('sha256'):
                    require(expected_hash==cj['sha256'],f'{key}/{control}: frozen control sha256 mismatch')
                identity=cj
            else:
                identity={'id':plan['task_id']+'__'+control,'task_id':plan['task_id'],
                          'dataset':plan['dataset'],'method':control,'metadata':plan['metadata']}
            comparisons[control]={'job_id':cj['id'] if cj else None,
                'metrics':{m:_metric(identity,m,lookup,registered=cj is not None) for m in OFFICIAL_NINE},
                'timing':_timing(cj)}
        cases.append({'job_id':plan['id'],'dataset':plan['dataset'],'task_id':plan['task_id'],
            'title':plan['title'],'method':method,'cohort':cohort,'registered_in_manifest':job is not None,
            'metrics':{m:scores[m] for m in OFFICIAL_NINE},
            'awq_metrics':{m:{**scores[m],**({'integration_status':'awaiting_external_result_or_relay'}
                           if scores[m]['status']=='pending' else {})} for m in AWQ_METRICS},
            'quantity_accuracy':scores['quantity_accuracy'], 'controls':comparisons,
            'motion_fidelity_delta_from_reference':_difference(scores['motion_fidelity'],comparisons['source']['metrics']['motion_fidelity']),
            'timing':_timing(job)})
    groups={}
    for method in sorted({c['method'] for c in cases}):
        rr=[c for c in cases if c['method']==method]
        paired={}
        for metric in OFFICIAL_NINE:
            complete=[];statuses=[]
            for c in rr:
                tri={method:c['metrics'][metric],**{k:c['controls'][k]['metrics'][metric] for k in CONTROLS}}
                states=[v['status'] for v in tri.values()]
                status=next((s for s in ('not_applicable','failed','pending') if s in states),'done')
                statuses.append({'status':status,'score':None})
                if status=='done':complete.append((c,tri))
            counts=_counts(statuses)
            paired[metric]={**counts,'n_paired':len(complete),
                'case_ids':[c['dataset']+'|'+c['task_id'] for c,_ in complete],
                'method_means':{m:mean([tr[m]['score'] for _,tr in complete]) for m in CONTROLS+(method,)},
                'mean_delta_from_native':mean([tr[method]['score']-tr['native']['score'] for _,tr in complete]),
                'mean_delta_from_global_weak':mean([tr[method]['score']-tr['global_weak']['score'] for _,tr in complete])}
        groups[method]={'n_planned':len(rr),'n_registered':sum(c['registered_in_manifest'] for c in rr),
            'metrics':{m:_denominator([c['metrics'][m] for c in rr]) for m in OFFICIAL_NINE},
            'paired_against_controls':paired,
            'motion_fidelity_delta_from_reference':{**_denominator([c['motion_fidelity_delta_from_reference'] for c in rr]),
                'formula':'mean_i(MF(source_i, edited_i) - MF(source_i, source_i)); measured reference score, not assumed 1'},
            'awq_metrics':{m:_denominator([c['awq_metrics'][m] for c in rr]) for m in AWQ_METRICS},
            'quantity_accuracy':_denominator([c['quantity_accuracy'] for c in rr]),
            'timing':_timing_group([c['timing'] for c in rr])}
    return {'schema':'h3-adaptive-independent-summary-v1','cohort':cohort,
            'evidence_scope':'explicit evaluation.rows and manifest timing; no old aggregate means or score imputation',
            'official_nine_metrics':list(OFFICIAL_NINE),'awq_metrics':list(AWQ_METRICS),
            'qa_scope':'quantity_accuracy separately; official applicability applies',
            'n_planned':len(plans),'n_registered':sum(c['registered_in_manifest'] for c in cases),
            'methods':groups,'cases':cases,
            'denominator_rule':'method means use completed applicable rows; each paired metric uses the same native/global_weak/method cases; pending and not_applicable stay explicit'}


def markdown(report):
    def fmt(v):return '—' if v is None else f'{v:.6f}'
    lines=['# Adaptive research 独立汇总','',f"计划 {report['n_planned']} 项，已回传 {report['n_registered']} 项。官方 9 指标独立于旧 aggregate 汇总。",'']
    for method,g in report['methods'].items():
        lines.extend([f'## {method}','', '| 指标 | 本方法均值 | 已完成/计划 | 待算 | 不适用 | 配对 n | native | global_weak | 本方法配对均值 | Δ weak |',
            '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|'])
        for metric in OFFICIAL_NINE:
            v=g['metrics'][metric];p=g['paired_against_controls'][metric]
            lines.append(f"| {metric} | {fmt(v['mean'])} | {v['n_done']}/{v['n_expected']} | {v['n_pending']} | {v['n_not_applicable']} | {p['n_paired']} | {fmt(p['method_means']['native'])} | {fmt(p['method_means']['global_weak'])} | {fmt(p['method_means'][method])} | {fmt(p['mean_delta_from_global_weak'])} |")
        d=g['motion_fidelity_delta_from_reference'];t=g['timing']
        lines.extend(['',f"MF-reference：{fmt(d['mean'])}（{d['n_done']}/{d['n_expected']}）；sampling：{fmt(t['mean_sampling_seconds'])} s（n={t['n_sampling']}），per-step：{fmt(t['mean_step_seconds'])} s（n={t['n_step']}）。",''])
        for metric, label in (('instruction_satisfaction','AWQ IS'),('content_fidelity','AWQ CF')):
            v=g['awq_metrics'][metric]
            lines.append(f"{label}：{fmt(v['mean'])}；完成 {v['n_done']}/{v['n_expected']}，待算／待接入 {v['n_pending']}，失败 {v['n_failed']}。")
        qa=g['quantity_accuracy']
        lines.extend([f"QA（独立适用性）：{fmt(qa['mean'])}；完成 {qa['n_done']}/{qa['n_expected']}，不适用 {qa['n_not_applicable']}，待算 {qa['n_pending']}。",''])
    lines.extend(['## 逐例数据','', '| 任务 | 方法 | '+' | '.join(OFFICIAL_NINE)+' | sampling s | mean step s |','|---|---|'+'---:|'*(len(OFFICIAL_NINE)+2)])
    for c in report['cases']:
        cells=[fmt(c['metrics'][m]['score']) if c['metrics'][m]['status']=='done' else c['metrics'][m]['status'] for m in OFFICIAL_NINE]
        lines.append('| '+c['task_id']+' | '+c['method']+' | '+' | '.join(cells)+f" | {fmt(c['timing']['sampling_seconds'])} | {fmt(c['timing']['mean_step_seconds'])} |")
    lines.extend(['','IS/CF 为独立 AWQ 两项；未接入的结果保留 pending。QA 单列按官方适用范围统计。历史控制组带 x0 capture 等计时范围，不能据未经匹配的耗时直接归因加速。',''])
    return '\n'.join(lines)


def main(argv=None):
    here=Path(__file__).resolve().parent
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--jobs',type=Path,default=here/'jobs.json')
    p.add_argument('--manifest',type=Path,default=here.parents[2]/'metrics/manifest.json')
    p.add_argument('--summary',type=Path,required=True,help='fresh evaluation/summary.json or explicit fetched copy; rows are used')
    p.add_argument('--cohort',default=COHORT)
    p.add_argument('--output',type=Path)
    p.add_argument('--markdown',type=Path)
    a=p.parse_args(argv)
    try:
        data=[json.loads(path.read_text()) for path in (a.jobs,a.manifest,a.summary)]
        result=summarize(*data,cohort=a.cohort)
        result['inputs']={k:{'path':str(v.resolve()),'mtime_unix':v.stat().st_mtime,
                             'sha256':hashlib.sha256(v.read_bytes()).hexdigest()}
                          for k,v in (('planned_jobs',a.jobs),('metrics_manifest',a.manifest),('evaluation_summary',a.summary))}
        raw=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        if a.output:a.output.write_text(raw)
        else:sys.stdout.write(raw)
        if a.markdown:a.markdown.write_text(markdown(result))
        return 0
    except (SummaryError,ValueError,KeyError,TypeError,OSError) as e:
        sys.stderr.write(json.dumps({'status':'failed','error':str(e)},ensure_ascii=False)+'\n')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
