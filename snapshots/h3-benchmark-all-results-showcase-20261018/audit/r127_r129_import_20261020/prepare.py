from pathlib import Path
import json,hashlib,copy,time
B=Path('/Users/researcher/DevProjects');R=B/'h3-benchmark-all-results-showcase-20261018';A=Path(__file__).parent
H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
x=json.loads((R/'inventory/ivebench.json').read_text());by={r['id']:r for r in x['items']}
def media(row,pres):
 a=json.loads(pres.read_text())
 for key,v in zip(['reference_video_path','ordinary_video_path','guided_video_path' if row['comparison_kind']=='guided_pair' else 'alternative_video_path'],a['inputs']):
  assert H(v['file'])==v['sha256'];row[key]=v['file']
 row['comparison_video_path']=str(pres.parent/a['videos'][0]['file']);assert H(row['comparison_video_path'])==a['videos'][0]['sha256']
 row['media_sha256']={k:H(row[k]) for k in ['reference_video_path','ordinary_video_path','guided_video_path','alternative_video_path','comparison_video_path'] if row.get(k)}
 return a

def prompt_binding(graph,hist,protocol):
 g=json.loads(graph.read_text());s=g['5']['inputs']['prompt'];assert json.loads(hist.read_text())['prompt'][2]['5']['inputs']['prompt']==s
 return {'text':s,'prompt_sha256':hashlib.sha256(s.encode()).hexdigest(),'protocol':protocol,'exact_official_edit_prompt':False,'graph_bindings':[{'graph':str(graph),'graph_sha256':H(graph),'node_id':'5','field':'inputs.prompt'}],'actual_history':str(hist),'actual_history_sha256':H(hist),'scope':'实际提交图与 Comfy history 文本逐字相同。'}

r=copy.deepcopy(by['r123_long_0034_full_context']);c=B/'h3-ive-prompt-envelope-metrics-r123-20261020/variants/long0122_full_context';src='long_0122';inc=c/'incoming_pairs'/src;show=c/'showcase_pairs'/src;review=c/'audit/full_frame_review'/src/'paired/INDEPENDENT_REVIEW.json';b=json.loads(review.read_text());assert H(review)=='fa0bab56f82353d9864474026ba50c5c15147cf428bd8a12f330dacfdc78e87e';assert b['reviewed_frame_count']==106 and b['reviewed_frame_range']==[0,105] and len(b['reviewed_pages'])==22
summary='巨嘴鸟替换和原场景在两版中成立。初始抬头、转左两项动作在普通版和引导版中均缺失，恢复0/2；后半回喙梳羽阶段保持接近同步。'
r.update(id='r127_long_0122_full_context',source_id=src,variant='R127 · 完整Context-IR · 同提示词时序引导',title='梳羽动作 · 金刚鹦鹉替换为巨嘴鸟',display_task='梳羽动作 · 金刚鹦鹉替换为巨嘴鸟',review_status=summary,review_summary=summary,display_summary=summary,review_status_code='TARGET_EDIT_PASS_LOCAL_ACTION_MISSING',guidance_effect='NO_REPAIR_BENEFIT',key_same_frame_indices=[16,30,75],judgment_source='continue_r111_r103 完整106有效帧三列审阅；root复核。',full_frame_review_path=str(review),execution_seconds=b['efficiency'])
a=media(r,show/'PRESENTATION.json');r.update(task=a['original_task']['edit_prompt'],source_clip=a['source_clip'],original_task=a['original_task'])
r['event_review']={'file':str(review),'sha256':H(review),'events':b['events'],'recovered_missing_events':0,'tested_missing_events':2,'scope':'全部106有效帧；缺失转折时刻为null，后段按头颈回转阶段评价。'}
evid=[show/'PRESENTATION.json',review,review.parent/'FRAME_LEDGER.json',inc/'PAIR_RUNTIME_GATE.json',inc/'COLLECTION.json',c/'prepared'/src/'paired/MF_INPUTS.json',c/'audit/actual_release/HANDOFF.json']
r['actual_prompt_by_column']={};ss=[]
for arm,column in [('native','ordinary'),('forced','guided')]:
 graph=inc/(arm+'_graph.json');hist=inc/(arm+'_history.json');q=prompt_binding(graph,hist,a['prompt_version']);ss.append(q['text']);r['actual_prompt_by_column'][column]=q
 assert json.loads((inc/(arm+'_router.json')).read_text())['routed_calls']==(450 if arm=='forced' else 0)
 evid.extend([graph,hist,inc/(arm+'_job.json'),inc/(arm+'_router.json')])
assert len(set(ss))==1;r['prompt']=ss[0];r['prompt_protocol'].update(actual_prompt=ss[0],official_edit_prompt=r['task']);assert all(a['original_task'][k] in ss[0] for k in ['source_prompt','edit_prompt','target_prompt'])
r['quantitative_metrics']={'motion_fidelity':{'native':None,'guided':None,'delta':None,'status':'pending','higher_is_better':True,'protocol':'IVEBench official MF','valid_frames':106,'evaluation_frames':106,'evaluation_fps':24}}
for n in ['ROOT_EXIT_RECEIPT.json','COMPLETE.json']:
 f=c/'audit/actual_release'/n;assert json.loads(f.read_text())['passed'];evid.append(f)
r['evidence_paths']=[str(e) for e in evid];r['evidence_sha256']={str(e):H(e) for e in evid}
rows=[r]

r=copy.deepcopy(by['r122_long_0039_generic_retention']);c=B/'h3-ive-aligned-media-clock-metrics-r129-20261020';inc=c/'incoming';review=c/'audit/full106_review/REVIEW.json';b=json.loads(review.read_text());assert H(review)=='dfa984974a43f7b5dac4d1e42930963dadd2cf2c99cd52a41eac300508b051b8';assert b['examined_frames']==list(range(106)) and b['all_valid_frames_inspected']
summary='RoPE时间原点对齐后，手与书的五个事件接近参考；书封仍为橙棕色，改蓝任务失败。该配置保留过多源内容，时序接近不计作有效编辑修复。'
r.update(id='r129_long_0039_aligned_clock',variant='R129 · RoPE时间坐标对齐对照',title='读书动作 · 书封改蓝 · RoPE对照',display_task='读书动作 · 书封改蓝',comparison_kind='positional_control',column_labels=['1.参考视频','2.普通编辑','3.RoPE时间坐标对齐'],guidance_activation='not_applicable',guidance_decision='positional_control',guided_status='not_generated',actual_routed_blocks=0,routed_block_calls=0,method_label='全采样步输出音视频RoPE原点对齐',guided_video_path=None,review_status=summary,review_summary=summary,display_summary=summary,review_status_code='TASK_FAIL_COPY_SOURCE',count_as_complete_task_success=False,clear_temporal_support=False,support_for_clear_whole_event_repair=False,action_alignment_bool=True,action_alignment_by_method=b['action_alignment_bool'],guidance_effect='TASK_FAIL_COPY_SOURCE',key_same_frame_indices=b['key_comparison_frames'],judgment_source='continue_metrics完整106有效帧审阅；root独立抽帧复核。',full_frame_review_path=str(review),release_status='COMPLETE_EXACT_RELEASE')
a=media(r,c/'showcase/source_native_aligned/PRESENTATION.json');r['task_acceptance_by_method']=b['task_acceptance'];r['event_review']={'file':str(review),'sha256':H(review),'events':b['events'],'all_adjacent_phases':b['all_adjacent_phases'],'scope':'全部106有效帧；事件接近伴随编辑目标失败。'}
r['actual_prompt_by_column']={'ordinary':copy.deepcopy(by['r122_long_0039_generic_retention']['actual_prompt_by_column']['ordinary']),'aligned':prompt_binding(inc/'graph.json',inc/'history.json',r['prompt_version'])};assert r['actual_prompt_by_column']['aligned']['text']==r['prompt'];assert json.loads((inc/'router.json').read_text())['routed_calls']==0
r['quantitative_metrics']={'motion_fidelity':{'native':by['r122_long_0039_generic_retention']['quantitative_metrics']['motion_fidelity']['native'],'aligned':None,'guided':None,'delta_aligned_minus_native':None,'status':'pending_aligned','higher_is_better':True,'protocol':'IVEBench official MF','valid_frames':106,'evaluation_frames':106,'evaluation_fps':24,'native_reuse_from_id':'r122_long_0039_generic_retention'}}
r['additional_comparisons']=[{'roles':['source','fixed','aligned'],'presentation_path':str(c/'showcase/source_fixed_aligned/PRESENTATION.json'),'sha256':H(c/'showcase/source_fixed_aligned/PRESENTATION.json'),'scope':'已有固定时序引导与RoPE坐标对照；aligned的router调用数为0。'}]
evid=[review]+[Path(v['file']) for v in b['evidence'].values()]+[inc/n for n in ['graph.json','history.json','job.json','router.json','alignment.json','COMPLETE.json']]
for v in r['actual_prompt_by_column']['ordinary']['graph_bindings']:evid.append(Path(v['graph']))
evid.append(Path(r['actual_prompt_by_column']['ordinary']['actual_history']));evid=list(dict.fromkeys(evid));r['evidence_paths']=[str(e) for e in evid];r['evidence_sha256']={str(e):H(e) for e in evid};rows.append(r)
(A/'DRAFT_ROWS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'draft':str(A/'DRAFT_ROWS.json'),'sha256':H(A/'DRAFT_ROWS.json'),'count':len(rows),'inventory_unchanged_sha256':H(R/'inventory/ivebench.json')},ensure_ascii=False))
