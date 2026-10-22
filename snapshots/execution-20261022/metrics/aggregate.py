"""Metric means, paired MF deltas and completeness-aware method comparisons."""
import argparse,json,statistics
from pathlib import Path
from metric_worker import METRICS,atomic
METHODS=['native','early','fixed','late','split','global_weak']

def mean(xs):return statistics.mean(xs) if xs else None

def aggregate(rows,expected=None):
    expected=expected or [dict(id=r['job_id'] if 'job_id' in r else r['task_id']+'__'+r['method'],task_id=r['task_id'],dataset=r['dataset'],method=r['method'],cohort=r.get('cohort','main')) for r in rows]
    expected=list({x['id']:x for x in expected}.values())
    lookup={(r.get('job_id',r['task_id']+'__'+r['method']),r['metric']):r for r in rows}
    sources={(x['dataset'],x['task_id']):x['score'] for x in rows if x.get('method')=='source' and x.get('metric')=='motion_fidelity' and x.get('status')=='done'}
    out={}
    for scope in ['main_IVEBench','main_all','expansion_IVEBench','expansion_all']:
        cohort,ds=scope.split('_',1);jobs=[j for j in expected if j.get('cohort','main')==cohort and (ds=='all' or j['dataset']=='IVEBench')];groups={}
        for method in sorted({j['method'] for j in jobs}):
            jj=[j for j in jobs if j['method']==method];entry={}
            for metric in METRICS:
                rr=[lookup.get((j['id'],metric),{}) for j in jj];valid=[r['score'] for r in rr if r.get('status')=='done']
                entry[metric]={'mean':mean(valid),'n_expected':len(jj),'n_done':len(valid),'n_not_applicable':sum(r.get('status')=='not_applicable' for r in rr),'n_failed':sum(r.get('status')=='failed' for r in rr),'n_pending':sum(r.get('status') not in ['done','not_applicable','failed'] for r in rr)}
            mf=[]
            for j in jj:
                r=lookup.get((j['id'],'motion_fidelity'),{});key=(j['dataset'],j['task_id'])
                if r.get('status')=='done' and key in sources:mf.append(r['score']-sources[key])
            entry['motion_fidelity_delta_from_reference']={'mean':mean(mf),'n_paired':len(mf),'formula':'mean_i(MF(source_i, edited_i) - MF(source_i, source_i))'}
            timings=[j.get('timing',{}) for j in jj];sample=[t['sampling_seconds'] for t in timings if isinstance(t.get('sampling_seconds'),(int,float))];steps=[t['mean_sampling_step_seconds'] for t in timings if isinstance(t.get('mean_sampling_step_seconds'),(int,float))]
            entry['timing']={'mean_sampling_seconds':mean(sample),'n_sampling':len(sample),'mean_step_seconds':mean(steps),'n_step':len(steps),'by_scope':{}}
            for tscope in sorted({t.get('scope','current_without_x0_capture') for t in timings if t}):
                tt=[t for t in timings if t and t.get('scope','current_without_x0_capture')==tscope];ss=[t['sampling_seconds'] for t in tt if isinstance(t.get('sampling_seconds'),(int,float))];sp=[t['mean_sampling_step_seconds'] for t in tt if isinstance(t.get('mean_sampling_step_seconds'),(int,float))]
                entry['timing']['by_scope'][tscope]={'mean_sampling_seconds':mean(ss),'n_sampling':len(ss),'mean_step_seconds':mean(sp),'n_step':len(sp)}
            groups[method]=entry
        paired={};methods=METHODS if cohort=='main' else ['native','global_weak'];cases={(j['dataset'],j['task_id']) for j in jobs}
        for metric in METRICS:
            complete=[]
            for case in cases:
                cj=[j for j in jobs if (j['dataset'],j['task_id'])==case and j['method'] in methods];by={j['method']:lookup.get((j['id'],metric),{}) for j in cj}
                if all(by.get(m,{}).get('status')=='done' for m in methods):complete.append((case,by))
            paired[metric]={'n_complete_cases':len(complete),'case_ids':['|'.join(k) for k,_ in complete],'method_means':{m:mean([by[m]['score'] for _,by in complete]) for m in methods}}
        out[scope]={'methods':groups,'complete_paired_subset':paired}
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',required=True);p.add_argument('--output',required=True);p.add_argument('--manifest');a=p.parse_args();rows=[]
    for file in Path(a.results).glob('*/*.json'):
        d=json.loads(file.read_text())
        if d.get('metric') in METRICS:rows.append(d)
    manifest=json.loads(Path(a.manifest).read_text()) if a.manifest else {};expected=manifest.get('expected_jobs',manifest.get('jobs'))
    # Actual job timing fills planned rows after each completed inference.
    actual={j['id']:j for j in manifest.get('jobs',[])}
    if expected:expected=[dict(j,**({'timing':actual[j['id']]['timing']} if actual.get(j['id'],{}).get('timing') else {})) for j in expected]
    atomic(a.output,{'rows':rows,'means':aggregate(rows,expected)})
