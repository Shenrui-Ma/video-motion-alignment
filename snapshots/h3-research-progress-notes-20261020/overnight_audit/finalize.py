from pathlib import Path
import json,hashlib,datetime,collections,re
B=Path('/Users/researcher/DevProjects');O=B/'h3-research-progress-notes-20261020/overnight_audit';tz=datetime.timezone(datetime.timedelta(hours=8));utc=datetime.timezone.utc
scan=json.loads((O/'HISTORY_SCAN.json').read_text());start=datetime.datetime.fromisoformat(scan['cutoff_sleep_utc'].replace('Z','+00:00')).timestamp();wake=datetime.datetime.fromisoformat(scan['cutoff_wake_utc'].replace('Z','+00:00')).timestamp()
def bind(p):
 p=Path(p);return {'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def stamp(t):return {'unix':t,'utc':datetime.datetime.fromtimestamp(t,utc).isoformat(),'cst':datetime.datetime.fromtimestamp(t,tz).isoformat()}
invfiles=[B/'h3-benchmark-all-results-showcase-20261018/inventory'/n for n in ['ivebench.json','flexiact.json']];inventories=[json.loads(p.read_text()) for p in invfiles];items=[r for d in inventories for r in d['items']]
r132=B/'h3-ive-reference-origin-metrics-r132-20261020/incoming_exploratory';hist=json.loads((r132/'binding_01.json').read_text());job=json.loads((r132/'binding_02.json').read_text());gate=json.loads((r132/'REFERENCE_ORIGIN_RUNTIME_GATE.json').read_text());t=next(v['timestamp']/1000 for k,v in hist['status']['messages'] if k=='execution_success')
assert bind(r132/'binding_01.json')['sha256']==gate['runs']['reference_origin']['history_sha256']
scan['successful'].append({'run_id':job['name'],'source_id':'long_0039','prompt_id':hist['prompt'][1],'completed_unix':t,'period':'sleep','success':True,'outputs':hist['outputs'],'history_file':str(r132/'binding_01.json'),'history_sha256':bind(r132/'binding_01.json')['sha256'],'job_file':str(r132/'binding_02.json')})
allruns=[]
for x in sorted(scan['successful'],key=lambda x:x['completed_unix']):
 if x['period']=='before_sleep':continue
 run=x['run_id'];role=next((r for r in ['reference_origin','visible_only','aligned','forced','fixed','native'] if run.endswith('_'+r)),x.get('method'))
 h=Path(x['history_file']);prefix=str(h).split('/incoming')[0]
 matching=[r for r in items if r.get('source_id')==x['source_id'] and any(str(r.get(k) or '').startswith(prefix+'/') for k in ['ordinary_video_path','guided_video_path','alternative_video_path'])]
 if len(matching)>1:
  matching=[r for r in matching if ('matched' in run)==('matched' in r['id'])] or matching
 item=matching[0] if matching else {}
 names=[]
 def outputs(v):
  if isinstance(v,dict):
   if isinstance(v.get('filename'),str) and v['filename'].endswith('.mp4') and v.get('type')!='input':names.append(v['filename'])
   for q in v.values():outputs(q)
  elif isinstance(v,list):
   for q in v:outputs(q)
 outputs(x['outputs'])
 row={'run_id':run,'generation_identity':{'prompt_id':x['prompt_id'],'variant_path':prefix},'benchmark':item.get('benchmark','IVEBench'),'source_id':x['source_id'],'inventory_id':item.get('id'),'method_role':role,'method_type':{'native':'ordinary_edit','forced':'fixed_same_bin_guidance','fixed':'fixed_same_bin_guidance','aligned':'global_aligned_RoPE_control','reference_origin':'reference_branch_origin_control','visible_only':'automatic_visible_only_resumed'}.get(role,role),'prompt_version':item.get('prompt_version'),'task':item.get('task'),'period':x['period'],'completion':stamp(x['completed_unix']),'completion_evidence':{'event':'Comfy execution_success timestamp','history_file':x['history_file'],'history_sha256':x['history_sha256'],'job':bind(x['job_file']) if x.get('job_file') else None},'actual_output_names':sorted(set(names)),'render_success':True,'scientific_pairing_note':'Strict historical input-pixel equality gate failed; exploratory actual output, not a strict same-input success.' if role=='reference_origin' else None,'task_review_status':item.get('review_status'),'task_success_not_implied_by_render_success':True}
 allruns.append(row)
assert len({r['generation_identity']['prompt_id'] for r in allruns})==len(allruns)
night=[r for r in allruns if r['period']=='sleep'];after=[r for r in allruns if r['period']=='after_wake']
snapshot=B/'h3-benchmark-all-results-showcase-20261018/audit/progress_protocol_snapshot_20261020_v3.json';s=json.loads(snapshot.read_text());baseline=s['counts']['IVEBench'];oldsources=set(baseline['short_source_ids']+baseline['derived_long_source_ids']);oldsources.add('long_0081') # actual completed before sleep, only later imported
newsources=sorted({r['source_id'] for r in night}-oldsources)
fixed=[r for r in night if r['method_type']=='fixed_same_bin_guidance'];pairproof=[]
for g in fixed:
 natives=[n for n in night if n['source_id']==g['source_id'] and n['method_role']=='native' and n['generation_identity']['variant_path']==g['generation_identity']['variant_path']]
 assert len(natives)==1,(g['run_id'],len(natives));pairproof.append({'source_id':g['source_id'],'ordinary_run_id':natives[0]['run_id'],'guided_run_id':g['run_id'],'variant_path':g['generation_identity']['variant_path']})
fail_specs=[('R132 attempt1','h3-timing-ive-reference-origin-r132-20261020/audit/host41_reference_origin_attempt1/FAILURE.json','node-ready check rejected startup; no inference submitted',0,False),('R133 attempt1','h3-timing-oxygen-online-r133-20261020/audit/actual_formal/failed_attempt1/FAILURE.json','decoder GPU unavailable; observer timeout at index9; no final generated video',13,True),('R138 attempt1','h3-timing-oxygen-online-resume-r138-20261020/audit/attempt1_failure/FAILURE.json','cross-generation conditioning UUID check rejected before first DiT; zero new model predictions',0,False)]
failures=[]
for name,rel,reason,nfe,partial in fail_specs:
 p=B/rel;d=json.loads(p.read_text());t=d['unix'];assert start<=t<wake
 failures.append({'attempt':name,'failure_timestamp':stamp(t),'reason':reason,'actual_model_predictions':nfe,'partial_denoising':partial,'final_video_generated':False,'evidence':bind(p)})
pre=B/'h3-timing-ive-three-source-r114-20261019/audit/actual_user_stop_20261020/FAILURE.json';pt=json.loads(pre.read_text())['unix'];assert pt<start
summary={'sleep_generated_outputs':len(night),'sleep_independent_source_videos':len({r['source_id'] for r in night}),'sleep_new_source_videos':len(newsources),'sleep_new_source_ids':newsources,'sleep_method_counts':dict(collections.Counter(r['method_type'] for r in night)),'sleep_complete_fixed_pairs':len(pairproof),'sleep_FlexiAct_generated_outputs':0,'sleep_nonrendering_failed_attempts':len(failures),'sleep_rendered_but_strict_pairing_failed_outputs':1,'after_wake_generated_outputs':len(after),'after_wake_independent_source_videos':len({r['source_id'] for r in after}),'after_wake_new_source_ids':sorted({r['source_id'] for r in after}-oldsources-{r['source_id'] for r in night}),'current_inventory_version_records':sum(len(d['items']) for d in inventories),'current_inventory_split':{'IVEBench':len(inventories[0]['items']),'FlexiAct':len(inventories[1]['items'])}}
assert summary['sleep_generated_outputs']==30 and summary['sleep_complete_fixed_pairs']==6
result={'schema':'overnight-actual-generation-completion-audit-v1','interval':{'sleep_start':stamp(start),'wake_request':stamp(wake),'rule':'sleep_start <= actual execution_success < wake_request; after_wake >= wake_request'},'units':{'generated_output':'One unique Comfy prompt_id producing a new final edited MP4; historical reused video not counted again. Same run_id in different prompt variants is distinguished by prompt_id/variant root.','independent_source':'Unique benchmark source_id; seeds/prompt variants/methods do not add sources.','success':'Rendering completed, not necessarily edit-task success. R132 strict pairing failure is separate.'},'summary':summary,'fixed_pairs_completed_during_sleep':pairproof,'successful_outputs':allruns,'failed_attempts_without_final_video':failures,'excluded_before_sleep':{'R114_guided_interruption':{'failure':stamp(pt),'evidence':bind(pre)},'R114_completed_Native':'2026-10-20T00:11:45.278+08:00; imported later, not an overnight new output'},'exclusions':['MF tracking/scoring','CPU package preparation/diagnostics/replay','cached-x0 decoder-only precheck','reused historical Native/fixed media','R141b currently sampling and R142 CPU package; no completed output yet'], 'inventory_bindings':[bind(p) for p in invfiles],'pre_sleep_snapshot':bind(snapshot),'historical_source_baseline_note':'v3 contains26 IVE source IDs; additionally long0081 Native had already completed before sleep and was imported later. The14 new sources are absent from both.','scan_coverage':{'roots':scan['roots_scanned'],'history_files':scan['history_files_scanned'],'extra_named_binding_history':str(r132/'binding_01.json')},'no_network':True,'no_GPU':True}
(O/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['# 睡眠期间实际生成核算','',f"区间：2026-10-20 01:00:56.042—11:08:58.061 CST。按 Comfy execution_success 完成时间，睡眠期间 **30 个实际新成片、16 条独立来源，其中14条新来源**；FlexiAct 新生成0。",'', '方法：21普通编辑、6固定引导、1全局RoPE对照、1参考分支对照、1自动闭环成片。6次固定引导均与本区间新Native构成完整配对。R132成片完成但严格输入配对门失败，单列探索性输出；成片数不等于任务成功数。','', '醒后已有完成：R140 Native，11:29:38.916 CST，1成片/1新来源；R141b采样与R142准备不计。','', '另有3次无最终成片尝试：R132启动检查失败（0预测）、R133观察器超时（13次模型预测，最终由R138续跑）、R138首次恢复UUID检查失败（0预测）。R114引导中断在00:59:31.927，早于睡眠起点，排除。','', '| CST完成时间 | run ID | 方法 | 来源 |','|---|---|---|---|']
for r in night:lines.append(f"| {r['completion']['cst'][11:23]} | {r['run_id']} | {r['method_role']} | {r['source_id']} |")
lines+=['','所有30条均有本地实际 execution_success 历史及SHA；详见 RESULT.json。R123同run ID的三个饮酒提示变体按不同prompt ID/目录独立计数。库存记录可能绑定2个输出或复用旧输出，因此112条库存记录不能作为本夜推理次数。','', '所有写入仅本audit目录，无网络/GPU/轮询。']
(O/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps({'summary':summary,'result':bind(O/'RESULT.json'),'report':bind(O/'REPORT.md')},ensure_ascii=False))
