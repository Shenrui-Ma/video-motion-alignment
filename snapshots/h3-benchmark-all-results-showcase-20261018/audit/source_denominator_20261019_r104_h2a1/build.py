from pathlib import Path
import json,hashlib,collections,re,time
ROOT=Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018')
OUT=Path(__file__).parent
# Explicit classification of existing review text. No new visual assessment is claimed.
# ordinary acceptance, alternative acceptance, observed timing effect
F='''flex_r50_chest_auto FAIL - ZERO
flex_r49_crouch_native FAIL - NA
flex_r49_fitness_native COMPLETE_OBSERVED - NA
flex_r49_one_leg_native PARTIAL - NA
flex_r49_rotate_native COMPLETE_OBSERVED - NA
flex_r65_fitness_fixed UNKNOWN - NEUTRAL
flex_r65_one_leg_fixed UNKNOWN - NEUTRAL
flex_r66_human2animal_1__movie_man_11 FAIL - NOT_COMPARABLE
flex_r66_human2animal_1__game_man_4 FAIL - NOT_COMPARABLE
flex_r66_fitness__game_man_4 PARTIAL - NEUTRAL
flex_r66_one_leg__movie_man_11 PARTIAL - NEUTRAL
flex_r66_human2animal_3__movie_man_11 UNKNOWN - NEUTRAL
flex_r66_human2animal_3__game_man_4 FAIL - NOT_COMPARABLE
flex_r66_human2animal_2__movie_man_11 FAIL - NOT_COMPARABLE
flex_r66_human2animal_2__game_man_4 FAIL - NOT_COMPARABLE
flex_r72_fitness_prompt_control COMPLETE_OBSERVED COMPLETE_OBSERVED NA
flex_r72_one_leg__movie_man_9_native UNKNOWN - NA
flex_r74_chest__game_man_5_native UNKNOWN - NA
flex_r85_one_leg__movie_man_9_fixed FAIL - NOT_COMPARABLE
flex_r85_crouch__movie_man_5_fixed PARTIAL - NEUTRAL
flex_r85_rotate__game_girl_1_fixed PARTIAL - NEUTRAL
flex_r98_human2animal_1__game_man_4_task_repair FAIL PARTIAL NA
flex_r101_human2animal_1__game_man_4_fixed PARTIAL - NEUTRAL
flex_r90_one_leg__movie_man_9_prompt_control FAIL PARTIAL NA
flex_r104_fitness__game_man_4_fixed COMPLETE_OBSERVED - NEUTRAL
flex_r105_human2animal_2__movie_man_11_fixed PARTIAL - NEUTRAL
flex_r105_crouch__movie_man_4_native PARTIAL - NA
flex_r104_human2animal_1__movie_man_11_fixed PARTIAL - NEUTRAL'''
I='''r73_short_0252 COMPLETE_OBSERVED - LOCAL_TIMING_IMPROVEMENT
r55_short_0210 FAIL - ZERO
r55_short_0230 FAIL - ZERO
r55_short_0263 FAIL - ZERO
r55_short_0352 FAIL - ZERO
r55_short_0370 UNKNOWN - ZERO
r63_short_0210 FAIL - NOT_COMPARABLE
r64_short_0092 FAIL - NOT_COMPARABLE
r64_short_0114 FAIL - NOT_COMPARABLE
r64_short_0126 FAIL - NOT_COMPARABLE
r64_short_0392 UNKNOWN - NOT_COMPARABLE
r69_short_0230 FAIL - NOT_COMPARABLE
r69_short_0263 FAIL - NOT_COMPARABLE
r69_short_0352 FAIL - NOT_COMPARABLE
r69_short_0370 COMPLETE_OBSERVED - NEUTRAL
r71_short_0210 FAIL COMPLETE_OBSERVED NA
r73_short_0035 COMPLETE_OBSERVED - NEUTRAL
r73_short_0065 COMPLETE_OBSERVED - NEUTRAL
r73_short_0135 COMPLETE_OBSERVED - NEUTRAL
r73_short_0344 COMPLETE_OBSERVED - NEUTRAL
r78_short_0370 COMPLETE_OBSERVED COMPLETE_OBSERVED NA
r80_short_0230 COMPLETE_OBSERVED - NA
r80_short_0352 COMPLETE_OBSERVED - NA
r89_short_0085 COMPLETE_OBSERVED - NEUTRAL
r89_short_0131 COMPLETE_OBSERVED - NEUTRAL
r89_short_0268 COMPLETE_OBSERVED - NEUTRAL
r89_short_0274 COMPLETE_OBSERVED - NEUTRAL
r89_short_0343 COMPLETE_OBSERVED - NEUTRAL
r96_long_0047 PARTIAL - NA
r89_short_0358 COMPLETE_OBSERVED - LOCAL_TIMING_IMPROVEMENT
r96_long_0123 COMPLETE_OBSERVED - NA
r96_long_0167 COMPLETE_OBSERVED - NA
r96_long_0173 COMPLETE_OBSERVED - NEUTRAL
r89_short_0178 COMPLETE_OBSERVED - NEUTRAL
r97_short_0358_extended COMPLETE_OBSERVED - NEUTRAL_EXTENSION
r99_short_0210 COMPLETE_OBSERVED - NEUTRAL
r100_short_0114 PARTIAL - NEUTRAL
r99_short_0230 COMPLETE_OBSERVED - NEUTRAL
r99_short_0352 COMPLETE_OBSERVED - EXTRA_GESTURE_SUPPRESSED
r102_short_0263 COMPLETE_OBSERVED - NEUTRAL
r102_short_0092 PARTIAL - NA
r109_short_0114_promptcontrol PARTIAL FAIL NA
r107_long_0174 COMPLETE_OBSERVED - MIXED_LOCAL_CHANGE
r102_short_0126 COMPLETE_OBSERVED - NA
r110_short_0114_promptcontrol FAIL PARTIAL NA
r108_short_0392 COMPLETE_OBSERVED - NEUTRAL
r111_long_0174_spatial COMPLETE_OBSERVED - REGRESSION_EVENTS_NOT_COMPARABLE
r106_short_0252_sampler_control COMPLETE_OBSERVED COMPLETE_OBSERVED NA'''
lookup={}
for line in (F+'\n'+I).splitlines():
 k,n,a,t=line.split();lookup[k]=(n,None if a=='-' else a,t)
rows=[]; bindings={}
for bench in ('flexiact','ivebench'):
 p=ROOT/'inventory'/f'{bench}.json';raw=p.read_bytes();j=json.loads(raw)
 bindings[bench]={'path':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'records':len(j['items'])}
 for x in j['items']:
  n,a,e=lookup.pop(x['id']);m=x.get('quantitative_metrics',{}).get('motion_fidelity',{});active=x.get('comparison_kind')=='guided_pair' and x.get('guidance_activation')=='active'
  evidence=[]
  for ep in x.get('evidence_paths',[]):
   if any(t in ep.upper() for t in ('REVIEW','PHYSICAL_RESULTS','VISUAL_EVENT','HUMAN_REVIEW')):
    evidence.append({'path':ep,'recorded_sha256':x.get('evidence_sha256',{}).get(ep)})
  ordinary_files={k:x.get(k) for k in ('ordinary_video_path','alternative_video_path') if x.get(k)}
  # sampler media keys differ; keep original declared columns and hashes available.
  row={'id':x['id'],'benchmark':x['benchmark'],'source_id':x['source_id'],'run_number':int(re.search(r'(?:^|_)r(\d+)',x['id'])[1]),'comparison_kind':x.get('comparison_kind'),'actual_guidance':x.get('guidance_activation'),'actual_routed_blocks':x.get('actual_routed_blocks'),'has_actual_intervention_pair':active,'ordinary_task_acceptance':n,'alternative_ordinary_task_acceptance':a,'timing_effect_from_review':e,'clear_whole_event_repair_established':False,'review_status':x.get('review_status'),'review_summary':x.get('review_summary'),'review_evidence':evidence,'review_coverage_note':x.get('task_acceptance_scope') or x.get('review_scope') or 'See preserved review text and linked review; coverage ranges from six sampled moments to all valid frames.','metric_status':m.get('status'),'mf_values':{k:v for k,v in m.items() if k in ('native','guided','alternative_native','euler','res_multistep')},'active_pair_mf_complete':active and isinstance(m.get('native'),(int,float)) and isinstance(m.get('guided'),(int,float)),'ordinary_media':ordinary_files,'media_sha256':x.get('media_sha256',{}),'column_labels':x.get('column_labels')}
  rows.append(row)
assert not lookup
by_source=collections.defaultdict(list)
for r in rows:by_source[(r['benchmark'],r['source_id'])].append(r)
sources=[]
for (b,s),rs in sorted(by_source.items()):
 last=max(r['run_number'] for r in rs);latest=[r for r in rs if r['run_number']==last]
 # For prompt control, the newer ordinary alternative is the latest native result.
 latest_status=sorted(set(r['alternative_ordinary_task_acceptance'] or r['ordinary_task_acceptance'] for r in latest))
 effect=collections.defaultdict(list)
 for r in rs:
  if r['has_actual_intervention_pair']:effect[r['timing_effect_from_review']].append(r['id'])
 sources.append({'benchmark':b,'source_id':s,'record_count':len(rs),'record_ids':[r['id'] for r in rs],'latest_run':last,'latest_ordinary_acceptance':latest_status[0] if len(latest_status)==1 else 'MIXED','latest_ordinary_acceptance_components':latest_status,'latest_record_ids':[r['id'] for r in latest],'ordinary_acceptance_observed_across_versions':sorted(set(v for r in rs for v in (r['ordinary_task_acceptance'],r['alternative_ordinary_task_acceptance']) if v)),'actual_intervention_pair_count':sum(r['has_actual_intervention_pair'] for r in rs),'actual_pair_effects':dict(effect),'clear_whole_event_repair_established':False,'active_pairs_missing_mf':[r['id'] for r in rs if r['has_actual_intervention_pair'] and not r['active_pair_mf_complete']]})
summary={}
for b in sorted(set(r['benchmark'] for r in rows)):
 rs=[r for r in rows if r['benchmark']==b];ss=[s for s in sources if s['benchmark']==b];active=[r for r in rs if r['has_actual_intervention_pair']]
 summary[b]={'source_count':len(ss),'record_count':len(rs),'records_by_kind':dict(collections.Counter(r['comparison_kind'] for r in rs)),'sources_with_any_actual_intervention_pair':sum(s['actual_intervention_pair_count']>0 for s in ss),'actual_intervention_pair_versions':len(active),'zero_intervention_pair_versions':sum(r['actual_guidance']=='zero' for r in rs),'latest_ordinary_acceptance_by_source':dict(collections.Counter(s['latest_ordinary_acceptance'] for s in ss)),'actual_pair_timing_effects_by_version':dict(collections.Counter(r['timing_effect_from_review'] for r in active)),'actual_pair_effects_unique_sources_overlapping':{e:len({r['source_id'] for r in active if r['timing_effect_from_review']==e}) for e in sorted(set(r['timing_effect_from_review'] for r in active))},'actual_pair_versions_with_complete_mf':sum(r['active_pair_mf_complete'] for r in active),'actual_pair_versions_missing_mf':sum(not r['active_pair_mf_complete'] for r in active),'record_ids_with_unknown_ordinary_acceptance':[r['id'] for r in rs if r['ordinary_task_acceptance']=='UNKNOWN'],'clear_whole_event_repair_sources':0}
result={'schema':'source-denominator-audit-v1','created_unix':time.time(),'inventory_bindings':bindings,'scope':'Existing inventory review evidence only. This audit makes no new video review, metric run, or benchmark accuracy estimate.','definitions':{'independent_source':'benchmark + original source_id; target characters, prompts, seeds and guidance variants remain versions of the same source.','record':'one inventory comparison entry; an entry may contain two or more edit outputs and may reuse historical media. Record counts are not unique inference counts.','COMPLETE_OBSERVED':'Existing review describes requested subject/appearance and scene/action class as completed within its stated coverage. This is not exhaustive task perfection or precise timing success.','PARTIAL':'Existing review records partial identity/scene/action/framing retention or a missing visible component.','UNKNOWN':'No explicit basic-task acceptance in available review, or archived media without visual acceptance.','latest':'Highest run number per source. For prompt controls use newer ordinary alternative; ties retain all statuses. Historical failures remain in per-version evidence.','timing_effects':'Local improvement, extra gesture suppression and mixed movement changes are separate from complete event alignment. Neutral judgments can be limited to visible body parts or sampled frames.','mf':'Numeric official MF is availability only; no score threshold determines basic-task pass or timing benefit.','overlap':'Per-effect source counts overlap because a source may have neutral, positive and failed versions.'},'summary':summary,'sources':sources,'records':rows}
(OUT/'SUMMARY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['现有证据分母：按原始视频去重','',f"快照合计：{len(rows)} 条实验展示记录，{len(sources)} 个原始视频来源。记录数包含提示词、角色、采样器及引导变体；同一成片也可能被不同对照复用。",'']
for b,z in summary.items():
 lines.extend([b,f"来源 {z['source_count']} 个；记录 {z['record_count']} 条；实际激活引导的配对 {z['actual_intervention_pair_versions']} 个版本，涉及 {z['sources_with_any_actual_intervention_pair']} 个来源；零干预配对 {z['zero_intervention_pair_versions']} 个版本。",f"每来源最新普通编辑验收：{z['latest_ordinary_acceptance_by_source']}。",f"实际配对的既有时序结论（版本数）：{z['actual_pair_timing_effects_by_version']}。",f"已有实际配对官方 MF {z['actual_pair_versions_with_complete_mf']} 个版本；缺失 {z['actual_pair_versions_missing_mf']} 个版本。",''])
lines.extend(['局部支持与边界：','IVEBench short_0252 的三个面罩阶段有对齐改善，short_0358 的部分喝酒阶段更接近参考。这两个来源有局部时序改善证据。short_0358 末端到达仍延后。','long_0174 固定引导提前了局部伸臂，同时头手组合仍未恢复；后续空间版本出现构图/内容退化。short_0352 抑制了新增手势，属于动作内容保持证据。','现有记录没有建立整条事件序列全面修复，也没有建立自动方法在十个独立来源上有效。','FlexiAct 的新 fitness 配对完成角色、背景和可见动作，两版时序接近；新盘腿前屈配对仍存在手触地延后。','', '解释：COMPLETE_OBSERVED 只指现有审阅覆盖内的任务完成；六时刻和全帧审阅的覆盖差异保留在 JSON。UNKNOWN 与 PARTIAL 均保留。该审计未新增视觉判断。','', '快照：']+[f"{b}: {x['sha256']}" for b,x in bindings.items()])
(OUT/'SUMMARY.txt').write_text('\n'.join(lines)+'\n')
print(json.dumps({'summary':summary,'json_sha256':hashlib.sha256((OUT/'SUMMARY.json').read_bytes()).hexdigest(),'text_sha256':hashlib.sha256((OUT/'SUMMARY.txt').read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
