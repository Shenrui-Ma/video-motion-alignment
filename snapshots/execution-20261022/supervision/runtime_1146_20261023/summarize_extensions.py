"""Read-only pre-specified six-pair official metric summary; missing stays null."""
from pathlib import Path
import json,math,hashlib,time
ROOT=Path('/data/research-user/h3_metrics_20261022/evaluation/results')
CASES=[('short_0135','expand_short_0135'),('long_0161','expand_long_0161'),('short_0166','expand2_short_0166'),('short_0185','expand2_short_0185'),('short_0220','expand2_short_0220'),('long_0174','expand2_long_0174')]
METRICS=['motion_fidelity','subject_consistency','background_consistency','temporal_flickering','motion_smoothness','overall_semantic_consistency','phrase_semantic_consistency','semantic_fidelity','vtss']
def score(job,metric):
 p=ROOT/job/(metric+'.json')
 if not p.exists():return {'status':'pending','score':None}
 d=json.loads(p.read_text());value=d.get('score');done=d.get('status')=='done' and type(value) in (int,float) and math.isfinite(value)
 return {'status':'done' if done else d.get('status','pending'),'score':value if done else None,'file':str(p),'file_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'official_commit':d.get('official_commit')}
rows=[]
for case,prefix in CASES:
 native={m:score(prefix+'_native',m) for m in METRICS};weak={m:score(prefix+'_global_weak',m) for m in METRICS};ref=score(case+'__source','motion_fidelity');deltas={m:weak[m]['score']-native[m]['score'] if native[m]['score'] is not None and weak[m]['score'] is not None else None for m in METRICS}
 timing={}
 for method in ['native','global_weak']:
  p=ROOT/(prefix+'_'+method)/'job.json';d=json.loads(p.read_text()) if p.exists() else {};t=d.get('timing',{});timing[method]={k:t.get(k) for k in ['sampling_seconds','mean_sampling_step_seconds']}
 rows.append({'case':case,'native_job':prefix+'_native','weak_job':prefix+'_global_weak','reference_mf':ref,'native':native,'global_weak':weak,'weak_minus_native':deltas,'qa':{m:score(prefix+'_'+m,'quantity_accuracy') for m in ['native','global_weak']},'timing':timing})
summary={}
for m in METRICS:
 complete=[r for r in rows if r['weak_minus_native'][m] is not None];n=len(complete);a=sum(r['native'][m]['score'] for r in complete)/n if n else None;b=sum(r['global_weak'][m]['score'] for r in complete)/n if n else None
 summary[m]={'planned_pairs':6,'completed_pairs':n,'pending_cases':[r['case'] for r in rows if r['weak_minus_native'][m] is None],'available_paired_native_mean':a,'available_paired_weak_mean':b,'available_mean_paired_delta':b-a if n else None,'all_six_native_mean':a if n==6 else None,'all_six_weak_mean':b if n==6 else None,'weak_higher_count':sum(r['weak_minus_native'][m]>0 for r in complete),'weak_lower_count':sum(r['weak_minus_native'][m]<0 for r in complete)}
print(json.dumps({'schema':'h3-six-extension-pairs-official-v1','time':time.time(),'cohort':'six_preselected_extensions_only','fixed_planned_denominator':6,'selection':'original queued order, no selection by observed benefit','pending_policy':'null; all_six mean withheld until all six paired values exist; available means always carry completed_pairs','edit_related_metrics':['overall_semantic_consistency','phrase_semantic_consistency','semantic_fidelity','vtss'],'awq':'not included; separate frozen10 batch in progress','summary':summary,'cases':rows},indent=2))
