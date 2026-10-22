#!/usr/bin/env python3
"""Extract evidence-bound sampler timing; reads local evidence, never launches inference."""
import hashlib,json,re,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent
PROJECTS=Path('/Users/researcher/DevProjects')
CASES=['short_0252','short_0358','long_0039','long_0059','short_0085','short_0274']
METHODS=['native','early','fixed','late','split','global_weak']
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def seconds(t):
    ans=0
    for part in t.split(':'): ans=ans*60+int(part)
    return ans
remote={}
for p in HERE.glob('remote_*.json'):
    doc=read(p)
    for root in doc['roots']:
        root['host']=doc['host'];root['local_evidence']=str(p)
        text=root.get('log_text','')
        blocks=re.split(r'(?m)^.*?got prompt\s*$',text)[1:]
        jobs=sorted(root['job_records'],key=lambda j:j['submitted_unix'])
        assert len(blocks)==len(jobs),(root['remote_root'],len(blocks),len(jobs))
        root['bound_jobs']={}
        for index,(job,block) in enumerate(zip(jobs,blocks)):
            assert job['status']=='success' and 'Prompt executed in' in block
            progress=re.findall(r'(\d+)/(\d+) \[([\d:]+)<[^,\]]*,\s*([\d.]+)s/it\]',block)
            complete=[x for x in progress if x[0]==x[1] and int(x[0])>0]
            assert complete,job['name']
            last=complete[-1]
            root['bound_jobs'][job['name']]={'job':job,'sampler_elapsed_seconds':seconds(last[2]),'mean_step_seconds':float(last[3]),'steps':int(last[1]),'block_index_zero_based':index,'closing_progress_text':f'{last[0]}/{last[1]} [{last[2]}<00:00, {last[3]}s/it]'}
        remote[root['remote_root']]=root
records=[]
for case_id in CASES:
    root=PROJECTS/('h3-guidance-schedule-eval-r149-20261020' if case_id in CASES[:2] else 'h3-guidance-schedule-eval-r150-20261021')
    manifest=read(root/'EVALUATION_MANIFEST.json');case=next(c for c in manifest['cases'] if c['source_id']==case_id)
    for method in METHODS:
        rec={'case_id':case_id,'method':method,'geometry':case['geometry'],'prompt_sha256':case['prompt_sha256'],'seed':case['seed'],'includes_x0_cpu_capture':True,'includes_audit_io':True,'per_step_vae_decode':False,'mean_step_seconds':None,'per_step_seconds':None,'sampler_wall_seconds':None,'sampler_elapsed_seconds_rounded':None,'recorder_envelope_wall_seconds':None}
        if method in ('native','fixed'):
            gatefile=Path(case['historical_pair_gate']['file']);gate=read(gatefile);runtime=gate['runtime_profile'];run=gate['runs']['native' if method=='native' else 'forced'];runid=run['run_id'];rr=remote[runtime['remote_root']];binding=rr['bound_jobs'][runid];job=binding['job'];hist=case['historical_runs'][method]
            assert job['graph_sha256']==hist['graph']['sha256']
            assert binding['steps']==run['Euler_updates']==20
            sm=rr['sampling_manifests'][runid];summary=sm['summary']
            rec.update(run_id=runid,host=runtime['host'],gpu_index=runtime.get('expected_gpu_index'),gpu_uuid=runtime.get('gpu_uuid'),steps=run['Euler_updates'],NFE=run.get('NFE'),graph_sha256=hist['graph']['sha256'],job_wall_seconds=run.get('job_wall_seconds'),sampler_elapsed_seconds_rounded=binding['sampler_elapsed_seconds'],mean_step_seconds=binding['mean_step_seconds'],recorder_envelope_wall_seconds=summary['finished_unix']-summary['created_unix'],capture_seconds=run.get('capture_seconds'),measurement_basis='tqdm_final_sampler_loop',measurement_resolution={'sampler_elapsed_seconds':1,'mean_step_seconds':0.01},scope='Euler sampling loop including every-step CPU x0 capture and audit writes; tqdm final closing average. Recorder envelope is a separate wall-clock timestamp difference including initial/final manifest writes, final tensor capture and endpoint check.',evidence={'gate':str(gatefile),'gate_sha256':sha(gatefile),'remote_log':rr['log_path'],'remote_log_sha256':rr['log_sha256'],'local_remote_evidence':rr['local_evidence'],'job':job,'log_block_index_zero_based':binding['block_index_zero_based'],'closing_progress_text':binding['closing_progress_text'],'binding_method':'chronological submitted jobs matched to got-prompt blocks; equal counts, all successful, graph SHA256 matched','recorder_manifest':{'file':sm['file'],'sha256':sm['sha256']}})
            rec['configured_router_inputs']={k:v for k,v in hist['router_node_50']['inputs'].items() if k in ('mode','alpha','radius','time_offset','start_frame','end_frame','block_start','block_end','step_start','step_end')}
            rec['missing_reason']='Historical runs have no monotonic sampler wrapper or per-callback timing; exact sampler_wall_seconds and individual per_step_seconds are null.'
        else:
            gatefile=root/'actual'/case_id/method/'GATE.json';gate=read(gatefile);runtime=read(root/'runtime'/case_id/f'{method}.json');t=gate['sampler_timing'];intervals=[x['callback_interval_seconds'] for x in t['callback_steps']]
            assert gate['passed'] and t['passed'] and len(intervals)==gate['Euler_updates']==20
            assert abs(sum(intervals)+t['after_last_callback_seconds']-t['sampler_wall_seconds'])<1e-4
            rec.update(run_id=gate['run_id'],host=runtime['host'],gpu_index=runtime.get('gpu_index'),gpu_uuid=runtime.get('gpu_uuid'),steps=gate['Euler_updates'],NFE=gate.get('NFE'),graph_sha256=runtime['graph']['sha256'],job_wall_seconds=gate.get('job_wall_seconds'),sampler_wall_seconds=t['sampler_wall_seconds'],mean_step_seconds=statistics.mean(intervals),per_step_seconds=intervals,after_last_callback_seconds=t['after_last_callback_seconds'],measurement_basis='monotonic_passive_recorder_wrapper',measurement_resolution={'sampler_elapsed_seconds':None,'mean_step_seconds':None},scope=t['scope'],actual_routed_steps_zero_based=gate.get('actual_routed_steps_zero_based'),alpha=gate.get('alpha'),evidence={'gate':str(gatefile),'gate_sha256':sha(gatefile),'runtime':str(root/'runtime'/case_id/f'{method}.json'),'timing_sha256':next((v for k,v in gate['binding_artifacts'].items() if k.endswith('/timing.json')),None)})
            assert runtime['historical_prompt_sha256']==case['prompt_sha256']
        records.append(rec)
assert len(records)==36 and len({(r['case_id'],r['method']) for r in records})==36

def aggregate(rows):
    def stat(key):
        vals=[r[key] for r in rows if r.get(key) is not None]
        return {'n':len(vals),'mean':statistics.mean(vals) if vals else None,'unit':'seconds'}
    return {'n':len(rows),'cases':[r['case_id'] for r in rows],'hosts':sorted({r['host'] for r in rows}),'measurement_bases':sorted({r['measurement_basis'] for r in rows}),'sampler_wall_seconds':stat('sampler_wall_seconds'),'sampler_elapsed_seconds_rounded':stat('sampler_elapsed_seconds_rounded'),'mean_step_seconds':stat('mean_step_seconds'),'job_wall_seconds':stat('job_wall_seconds')}
observed={m:aggregate([r for r in records if r['method']==m]) for m in METHODS}
subsets=[]
for label,methods in [('native_vs_fixed',['native','fixed']),('new_schedule_methods',['early','late','split','global_weak'])]:
    for match in ['host_and_measurement_basis','host_gpu_and_measurement_basis']:
        eligible=[]
        for cid in CASES:
            rows=[r for r in records if r['case_id']==cid and r['method'] in methods]
            keys=['host','measurement_basis']+(['gpu_uuid'] if match.startswith('host_gpu') else [])
            if all(len({r[k] for r in rows})==1 for k in keys):eligible.append(cid)
        subsets.append({'name':label,'matching':match,'n_cases':len(eligible),'cases':eligible,'methods':{m:aggregate([r for r in records if r['method']==m and r['case_id'] in eligible]) for m in methods}})
subsets.append({'name':'all_six_methods','matching':'host_and_measurement_basis','n_cases':0,'cases':[],'reason':'Historical native/fixed use tqdm loop timing; other schedules use full recorder timing. Three cases also change hosts across methods.'})
byhost={h:{m:aggregate([r for r in records if r['method']==m and r['host']==h]) for m in METHODS} for h in sorted({r['host'] for r in records})}
out={'schema':'h3-historical-sampling-timing-v1','scope':'Retained six cases from R149/R150; excludes four newly generated cases. CPU extraction only. All 36 trajectories have 20 Euler updates.','measurement_notes':['Reported averages use recorded sampling intervals, never end-to-end job time divided by steps.','Exact 24 recorder timers include x0 capture and audit I/O; individual callbacks include setup in the first interval and prior Euler update in later intervals.','Twelve historical tqdm timings report rounded loop total and final average; no exact individual step timing was recorded.','Recorder timestamp envelope is retained separately and does not replace sampler measurement.','Per-method all-case averages describe observed runs with mixed hardware; use matched subsets for method comparisons.','Historical prompt hashes are preserved; these six cases retain their historical prompts.'], 'records':records,'observed_per_method':observed,'matched_subsets':subsets,'per_host':byhost}
(HERE/'historical_six_cases_timing.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'records':len(records),'observed':observed,'matched':[{k:v for k,v in s.items() if k!='methods'} for s in subsets]},ensure_ascii=False,indent=2))
