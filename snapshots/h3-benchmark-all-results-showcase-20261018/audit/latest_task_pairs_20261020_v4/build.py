from pathlib import Path
import json,hashlib,re,collections,time,ast
ROOT=Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018')
OUT=Path(__file__).parent
H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=ast.parse((ROOT/'audit/source_denominator_20261019_r104_complete/build.py').read_text())
constants={n.targets[0].id:ast.literal_eval(n.value) for n in old.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('F','I')}
classes={}
for line in (constants['F']+'\n'+constants['I']).splitlines():
 k,n,a,t=line.split();classes[k]={'ordinary':n,'alternative':None if a=='-' else a,'effect':t}
new='''flex_r116_human2animal_1__game_man_4_fixed PARTIAL NEUTRAL
r115_long_0174_fixed_one_bin COMPLETE_OBSERVED LOCAL_TIMING_IMPROVEMENT
r115_long_0174_matched_one_bin COMPLETE_OBSERVED NEUTRAL
r118_long_0047_fixed PARTIAL NEUTRAL
r113_short_0252_seed2026101702_fixed COMPLETE_OBSERVED LOCAL_TIMING_IMPROVEMENT
r113_short_0252_seed2026101703_fixed COMPLETE_OBSERVED EVENT_TIMING_IMPROVEMENT
r117_short_0114_framing_prompt FAIL NOT_RUN
r119_short_0114_official_prompt FAIL NOT_RUN
r114_long_0081_native COMPLETE_OBSERVED NOT_RUN
r121_short_0252_official_prompt FAIL NOT_RUN
r121_short_0358_official_prompt FAIL NOT_RUN
r120_long_0059_official_prompt FAIL NOT_RUN
r123_short_0358_prompt_envelope FAIL NOT_RUN
r123_short_0358_generic_retention PARTIAL NOT_RUN
r122_long_0039_generic_retention COMPLETE_OBSERVED LOCAL_TIMING_IMPROVEMENT
r123_short_0358_full_context COMPLETE_OBSERVED LOCAL_TIMING_IMPROVEMENT
r123_long_0161_full_context COMPLETE_OBSERVED NO_REPAIR_BENEFIT
r124_long_0163_full_context FAIL NOT_RUN
r125_long_0031_full_context COMPLETE_OBSERVED NOT_RUN'''
for line in new.splitlines():
 k,n,t=line.split();classes[k]={'ordinary':n,'alternative':None,'effect':t}
# R97's stored headline compares extended vs fixed; the requested denominator compares guided vs ordinary.
classes['r97_short_0358_extended']['effect']='LOCAL_TIMING_IMPROVEMENT'
# Existing writing contact boundary remains unknown; retain its no-clear-gain observation separately.
classes['r73_short_0135']['effect']='UNKNOWN'
notes={
 'r97_short_0358_extended':'相对普通编辑，早期降瓶与接触嘴部阶段有局部改善；相对原固定6–14步版，延长到6–19步未建立额外收益。',
 'r115_long_0174_fixed_one_bin':'该Value transport算子仅提前进入遮挡；后续出现、转身和末端伸臂仍未修复。',
 'r115_long_0174_matched_one_bin':'匹配后的Value transport与普通编辑阶段接近。与固定一步输运同轮，两个变体均保留。',
 'r123_short_0358_full_context':'同一source新prompt复验；到嘴提前约3帧、离嘴约1–2帧，区间重叠且明显迟到保留。',
 'r122_long_0039_generic_retention':'新独立源；抬书提前，触书仍晚；离键盘到触书过程参考/普通12–17帧，引导25–30帧。局部改善。',
 'r114_long_0081_native':'普通版基础任务成立且阶段接近；引导18步中断，未生成完整引导成片。',
 'r73_short_0135':'机械臂任务成立，逐帧运笔检查未见清楚收益；可靠接触时刻未知，本审计将事件时序判断单列UNKNOWN。',
 'r99_short_0352':'抑制普通编辑额外增加的指点手势，属于动作内容保持；原有动作时刻的改善未建立。',
 'flex_r65_fitness_fixed':'只测可见手臂相关性时差；基础人物/背景验收未明确，列UNKNOWN。',
 'flex_r65_one_leg_fixed':'只测可见手臂相关性时差；基础人物/背景验收未明确，列UNKNOWN。',
}
rows=[];bindings={};groups=collections.defaultdict(list)
for bench in ('flexiact','ivebench'):
 p=ROOT/'inventory'/f'{bench}.json';raw=p.read_bytes();j=json.loads(raw);sha=hashlib.sha256(raw).hexdigest();(OUT/(bench+'_snapshot.json')).write_bytes(raw)
 bindings[bench]={'path':str(p),'sha256':sha,'snapshot':str(OUT/(bench+'_snapshot.json')),'versions':len(j['items'])}
 for r in j['items']:
  assert r['id'] in classes,r['id']
  im=r.get('reference_image_path'); imsha=H(im) if im else None
  key=(bench,r['source_id'],imsha if bench=='flexiact' else None)
  c=classes[r['id']];active=r.get('comparison_kind')=='guided_pair' and (r.get('guidance_activation') in ('active','positive','fixed_active') or (r.get('actual_routed_blocks') or r.get('routed_block_calls') or 0)>0)
  ps=list(r.get('evidence_paths',[]));er=r.get('event_review') or {}
  if er.get('file'):ps.append(er['file'])
  if r.get('full_frame_review_path'):ps.append(r['full_frame_review_path'])
  eps=[]
  for ep in dict.fromkeys(ps):
   if any(q in ep.upper() for q in ['REVIEW','CONCLUSION','PHYSICAL','VISUAL_EVENT','HUMAN_REVIEW']):
    expected=(r.get('evidence_sha256') or {}).get(ep) or (er.get('sha256') if ep==er.get('file') else None)
    exists=Path(ep).is_file();actual=H(ep) if exists else None
    eps.append({'path':ep,'current_sha256':actual,'inventory_sha256':expected,'exists':exists,'hash_matches_if_recorded':actual==expected if expected else None})
  row={'id':r['id'],'benchmark':bench,'source_id':r['source_id'],'target_image_sha256':imsha,'target_image_path':im,'title':r.get('title'),'run':int(re.search(r'(?:^|_)r(\d+)',r['id'])[1]),'kind':r.get('comparison_kind'),'actual_pair':active,'pair_group':r.get('pair_group'),'method_label':r.get('method_label'),'ordinary_acceptance':c['ordinary'],'alternative_acceptance':c['alternative'],'paired_guided_acceptance':c['ordinary'] if active else None,'timing_effect':c['effect'],'existing_review_summary':r.get('review_summary'),'existing_review_status':r.get('review_status'),'notes':notes.get(r['id']),'review_evidence':eps,'media_sha256':r.get('media_sha256'),'quantitative_metrics':r.get('quantitative_metrics',{}),'alignment_by_method':r.get('action_alignment_by_method')}
  rows.append(row);groups[key].append(row)
assert len(rows)==97

def aggregate_effect(rs):
 vals={r['timing_effect'] for r in rs}
 if vals <= {'LOCAL_TIMING_IMPROVEMENT','EVENT_TIMING_IMPROVEMENT'}:return 'IMPROVED'
 if len(vals)>1:return 'MIXED_BY_VARIANT'
 v=next(iter(vals))
 return {'EXTRA_GESTURE_SUPPRESSED':'OTHER_ACTION_CONTENT_BENEFIT','ZERO':'NO_ACTUAL_INTERVENTION'}.get(v,v)

tasks=[]
for key,rs in sorted(groups.items(),key=lambda x:tuple(str(v) for v in x[0])):
 active=[r for r in rs if r['actual_pair']];last=max(r['run'] for r in rs);latest=[r for r in rs if r['run']==last]
 # R123 input-format trials were sequential; full_context is the last completed attempt.
 if any(r['id']=='r123_short_0358_full_context' for r in latest): latest=[r for r in latest if r['id']=='r123_short_0358_full_context']
 selected=[r for r in active if r['run']==max(x['run'] for x in active)] if active else[]
 cs={r['ordinary_acceptance'] for r in selected};lc={r['alternative_acceptance'] or r['ordinary_acceptance'] for r in latest}
 tasks.append({'task_key':list(key),'benchmark':key[0],'source_id':key[1],'target_image_sha256':key[2],'version_count':len(rs),'all_version_ids':[r['id'] for r in rs],
 'latest_attempt_ids':[r['id'] for r in latest],'latest_attempt_acceptance':next(iter(lc)) if len(lc)==1 else'MIXED','latest_attempt_records':latest,
 'latest_actual_pair_ids':[r['id'] for r in selected],'latest_actual_pair_records':selected,'pair_task_acceptance':next(iter(cs)) if len(cs)==1 else('MIXED' if cs else'NO_ACTUAL_PAIR'),
 'pair_timing_effect':aggregate_effect(selected) if selected else'NO_ACTUAL_PAIR','newer_attempt_than_pair':bool(selected and last>selected[0]['run']),
 'strict_task_pass_pair':bool(selected and cs=={'COMPLETE_OBSERVED'})})
summary={}
for bench in ['flexiact','ivebench']:
 ts=[t for t in tasks if t['benchmark']==bench];pairs=[t for t in ts if t['latest_actual_pair_ids']];strict=[t for t in pairs if t['strict_task_pass_pair']]
 summary[bench]={'unique_sources':len({t['source_id'] for t in ts}),'independent_task_combinations':len(ts),'versions':sum(t['version_count'] for t in ts),'tasks_with_actual_pair':len(pairs),'tasks_without_actual_pair':len(ts)-len(pairs),'latest_selected_pair_versions_including_ties':sum(len(t['latest_actual_pair_ids']) for t in pairs),'pair_task_acceptance':dict(collections.Counter(t['pair_task_acceptance'] for t in pairs)),'pair_timing_effects_all_acceptance_levels':dict(collections.Counter(t['pair_timing_effect'] for t in pairs)),'strict_task_pass_pair_timing':dict(collections.Counter(t['pair_timing_effect'] for t in strict)),'latest_attempt_acceptance':dict(collections.Counter(t['latest_attempt_acceptance'] for t in ts)),'task_ids_with_improvement':[t['source_id'] for t in pairs if t['pair_timing_effect']=='IMPROVED'],'tasks_with_variant_dependent_local_improvement':[t['source_id'] for t in pairs if t['pair_timing_effect']=='MIXED_BY_VARIANT'],'tasks_with_no_reliable_event_timing':[t['source_id'] for t in pairs if t['pair_timing_effect']=='UNKNOWN']}
obj={'schema':'latest-task-pair-review-audit-v1','created_unix':time.time(),'scope':'对现有97条记录的既有审阅进行只读归纳；未新增视频审阅、推理或指标计算。','inventory_bindings':bindings,
 'definitions':{'source':'benchmark+原始source_id；共有40条独立源视频。','task':'IVE按source；Flex按source+目标参考图内容SHA。共有49任务组合，同源不同角色不是独立源视频。','latest_pair':'每任务取最高R编号的实际非零干预配对。相同R内多个seed/方法全部保留。基础失败亦保留在分母，再按验收分层。','latest_attempt':'另列最高R的普通/引导/提示词尝试；R123同编号输入格式依实际完成顺序取full_context，全部早期版本保留。较新Native-only结果不与旧guided拼成假配对。','COMPLETE_OBSERVED':'既有审阅覆盖内主体/外观编辑、场景与动作类别已成立。','PARTIAL':'已有视角、构图、幅度、背景或额外外观差异，独立列出。','UNKNOWN':'现有审阅未明确验证该项或不能可靠测量；不转换为失败或成功。','NEUTRAL':'现有覆盖内未观察到清楚额外时序收益，不代表经过等价性检验；部分为固定六时刻或可见手臂。','IMPROVED':'相对同prompt/seed普通编辑有既有局部事件时刻改善；完整修复范围以每条事件表为准。','MIXED_BY_VARIANT':'同轮变体效果不同，保留所有变体，未挑较好变体代替整个任务。','NOT_COMPARABLE':'基础任务/动作内容失败，无法将变化解释为同一动作时序修复。','OTHER_ACTION_CONTENT_BENEFIT':'减少新增动作与改善原动作的时刻分别登记。','NO_REPAIR_BENEFIT':'基础编辑成立，但被省略的目标动作在两版均缺失；保留null事件时刻。','metrics':'MF只附原分数，不以MF阈值决定任务成立或时序收益。'},
 'summary':summary,'tasks':tasks,
 'recommendations':[{'priority':1,'category':'IVE单人手与物体的离散操作，主体或外观编辑','reason':'氧气面罩和饮酒有局部时序支持；可用接近、接触、移开等可见事件标注。R124递文件发生构图和动作重建；R125砧板替换成功且已同步，均保留Native-only。'}, {'priority':2,'category':'同一源已选定的全部种子与普通版已接近的样例','reason':'保留改善、中性、失败三类；同源多个种子用于复验，不增加独立来源数。'}, {'priority':3,'category':'Flex角色迁移','reason':'13个实际配对任务中只有1个在既有覆盖内完整成立，6个部分成立、3个失败、3个验收未知；先使身份、视角和动作内容可比，再解释时序。'}, {'priority':4,'category':'双人遮挡与Value transport探索','reason':'long_0174固定输运局部转折提前，匹配输运近中性；继续单列结构变体，避免与固定same-bin干预的收益合并。'}]}
(OUT/'SUMMARY.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
lines=['现有97版本：按独立任务选择最新实际配对','', '任务组合49个，独立源视频40条；同源角色、提示词、种子和方法版本单独留档。','']
for b,s in summary.items():
 lines += [b, f"任务{s['independent_task_combinations']}个，源视频{s['unique_sources']}条，版本{s['versions']}条；有实际干预配对{s['tasks_with_actual_pair']}个任务。",f"配对任务验收：{s['pair_task_acceptance']}",f"配对时序结论（含各验收层级）：{s['pair_timing_effects_all_acceptance_levels']}",f"任务完整成立后的时序结论：{s['strict_task_pass_pair_timing']}",f"每任务最新尝试验收（含Native-only）：{s['latest_attempt_acceptance']}",'']
lines+=['逐任务：benchmark | source | targetSHA前8位 | 最新实际pair | 任务验收 | 时序结果 | 最新尝试','']
for t in tasks:
 lines.append(' | '.join([t['benchmark'],t['source_id'],(t['target_image_sha256'] or '-')[:8],','.join(t['latest_actual_pair_ids']) or'-',t['pair_task_acceptance'],t['pair_timing_effect'],','.join(t['latest_attempt_ids'])]))
lines+=['','关键解释：','1. short_0252、short_0358、long_0039为三个有局部时序改善的独立来源。R113新seed和R123新prompt只增加复验版本。long_0039初始伸手过程拉长，整段修复未建立。','2. long_0174新Value transport固定变体仅局部转折提前，匹配变体近中性；归MIXED_BY_VARIANT。','3. short_0352减少新增指点手势，归动作内容收益；short_0135接触时刻UNKNOWN。','4. NEUTRAL表示既有审阅范围内未见清楚收益，基础任务部分成功和未知均单列；完整任务成立不等于每个事件对齐。','5. 当前统计按最高R的实际配对，保留较新Native-only的单独验收。旧失败配对不被较新普通版替换。','', '优先继续：IVE单人手部离散操作与主体/外观修改，按源动作可见性预选；保留全部预选样本、失败和中性结果。']
(OUT/'SUMMARY.txt').write_text('\n'.join(lines)+'\n')
print(json.dumps({'summary':summary,'summary_path':str(OUT/'SUMMARY.json'),'sha256':H(OUT/'SUMMARY.json')},ensure_ascii=False,indent=2))
