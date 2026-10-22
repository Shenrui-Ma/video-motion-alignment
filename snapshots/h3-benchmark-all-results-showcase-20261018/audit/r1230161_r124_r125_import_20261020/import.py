from pathlib import Path
import json,hashlib,copy,time,os
B=Path('/Users/researcher/DevProjects');R=B/'h3-benchmark-all-results-showcase-20261018';A=Path(__file__).parent
H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=R/'inventory/ivebench.json';old=H(p);assert old=='e8c0e0832c4178be8860e111d7ccd24d992063305ff84497b493f7cf2bb9220d'
x=json.loads(p.read_text());(A/'ivebench_before.json').write_bytes(p.read_bytes());template=next(v for v in x['items'] if v['id']=='r123_short_0358_full_context')
specs=[
 dict(id='r123_long_0161_full_context',source='long_0161',consumer='h3-ive-prompt-envelope-metrics-r123-20261020/variants/long0161_full_context',paired=True,review='INDEPENDENT_REVIEW.json',reviewsha='23a4d5bf349b3d92fb374317b2ae7deb4667e16f2a271e5465b15ff859970101',release=None,title='公园后仰动作 · 男子替换为儿童',summary='两版均完成儿童替换并保留双人公园场景。参考视频的手撑地与后仰在普通编辑和引导版中均缺失；本例的固定时序引导未恢复这两个动作。',code='PASS_CORE_EDIT',alignment=False,keys=[39,48,69],reviewer='continue_r111_r103完整106有效帧三列审阅；root复核。',effect='NO_REPAIR_BENEFIT'),
 dict(id='r124_long_0163_full_context',source='long_0163',consumer='h3-ive-full-context-metrics-r124-20261020',paired=False,review='REVIEW.json',reviewsha='9127ac6e9821a6d85faccb1605e34266fb2104d3ca1db46e0112a36885dc64ea',release='h3-timing-ive-full-context-r124-20261020/audit/root_full_context_attempt1',title='办公室递文件 · 浅蓝正装改黑',summary='出现黑色外套，但原坐姿看文件被改成背面站立拿文件、坐下递纸；桌面、电脑与镜头也发生重建。基础编辑失败，保留普通编辑结果。',code='FAIL_COMPOSITION_AND_ACTION_RECONSTRUCTION',alignment=False,keys=[6,72,140],reviewer='continue_r90_r104完整144有效帧两列审阅。',effect='NOT_RUN'),
 dict(id='r125_long_0031_full_context',source='long_0031',consumer='h3-ive-board-edit-metrics-r125-20261020',paired=False,review='REVIEW.json',reviewsha='14264c61580ba1944cef39dcab14415f562e1e9709d7f0c87bd7cd29c83f9526',release='h3-timing-ive-board-edit-r125-20261020/audit/root_board_edit_attempt1',title='切甜椒 · 木砧板替换为大理石',summary='大理石砧板替换完成，原手部、刀具、甜椒与构图保留。切片倒下、转动甜椒和刀刃复位的时段均与参考重叠；保留已同步的普通编辑样本。',code='PASS_CORE_EDIT',alignment=True,keys=[69,89,97],reviewer='continue_r90_r104完整106有效帧两列审阅。',effect='NOT_RUN')]
new=[]
for s in specs:
 assert not any(r['id']==s['id'] for r in x['items']);c=B/s['consumer'];src=s['source'];pair=s['paired'];phase='paired' if pair else 'native';inc=c/('incoming_pairs' if pair else 'incoming')/src;show=c/('showcase_pairs' if pair else 'showcase')/src
 pres=show/'PRESENTATION.json';a=json.loads(pres.read_text());review=c/'audit/full_frame_review'/src/phase/s['review'];assert H(review)==s['reviewsha'];b=json.loads(review.read_text())
 frames=b.get('reviewed_valid_frames',b.get('examined_frames'));assert frames==list(range(a['timeline']['valid_frames']))
 r=copy.deepcopy(template)
 r.update(id=s['id'],source_id=src,variant=f"{s['id'].split('_')[0].upper()} · 完整Context-IR · "+('同提示词时序引导' if pair else '普通编辑'),title=s['title'],task=a['original_task']['edit_prompt'],display_task=s['title'],pair_group='IVEBench素材片段探索',comparison_kind='guided_pair' if pair else 'native_only',column_labels=['1.参考视频','2.普通编辑']+(['3.时序引导'] if pair else []),guidance_activation='fixed_active' if pair else 'not_run',guidance_decision='guide' if pair else 'skip',guided_status='complete' if pair else 'not_run',actual_routed_blocks=450 if pair else 0,routed_block_calls=450 if pair else 0,method_label='固定6–14步时序引导' if pair else '完整Context-IR，普通编辑',valid_frames=a['timeline']['valid_frames'],generated_frames=a['timeline']['total_frames'],fps=24,source_clip=a['source_clip'],prompt_version=a['prompt_version'],original_task=a['original_task'],review_status=s['summary'],review_status_code=s['code'],review_summary=s['summary'],display_summary=s['summary'],count_as_complete_task_success=s['code']=='PASS_CORE_EDIT',clear_temporal_support=False,support_for_clear_whole_event_repair=False,action_alignment_bool=s['alignment'],action_alignment_by_method={'native':s['alignment'],'guided':False if pair else None},guidance_effect=s['effect'],key_same_frame_indices=s['keys'],judgment_source=s['reviewer'],full_frame_review_path=str(review),release_status='COMPLETE_EXACT_RELEASE' if pair else 'EXACT_RELEASED_NATIVE_ONLY')
 r.pop('execution_seconds',None);r['event_review']={'file':str(review),'sha256':H(review),'events':b['events'],'scope':'全部有效帧审阅；缺失或不可比事件时间保持null。'}
 r['guided_video_path']=None
 for key,v in zip(['reference_video_path','ordinary_video_path','guided_video_path'],a['inputs']):assert H(v['file'])==v['sha256'];r[key]=v['file']
 v=a['videos'][0];r['comparison_video_path']=str(show/v['file']);assert H(r['comparison_video_path'])==v['sha256']
 r['media_sha256']={k:H(r[k]) for k in ['reference_video_path','ordinary_video_path','guided_video_path','comparison_video_path'] if r.get(k)}
 evid=[pres,review,review.parent/'FRAME_LEDGER.json',inc/('PAIR_RUNTIME_GATE.json' if pair else 'NATIVE_RUNTIME_GATE.json'),inc/'COLLECTION.json',c/'prepared'/src/phase/'MF_INPUTS.json']
 r['actual_prompt_by_column']={};prompts=[]
 for arm,column in [('native','ordinary')]+([('forced','guided')] if pair else []):
  graph=inc/(arm+'_graph.json');history=inc/(arm+'_history.json');g=json.loads(graph.read_text());prompt=g['5']['inputs']['prompt'];prompts.append(prompt);router=json.loads((inc/(arm+'_router.json')).read_text());assert router['routed_calls']==(450 if arm=='forced' else 0)
  r['actual_prompt_by_column'][column]={'text':prompt,'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'protocol':a['prompt_version'],'exact_official_edit_prompt':False,'graph_bindings':[{'graph':str(graph),'graph_sha256':H(graph),'node_id':'5','field':'inputs.prompt'}],'actual_history':str(history),'actual_history_sha256':H(history),'scope':'已完成视频的实际提交图与Comfy history；consumer逐字核验。'}
  evid += [graph,history,inc/(arm+'_job.json'),inc/(arm+'_router.json')]
 assert len(set(prompts))==1;r['prompt']=prompts[0]
 for key in ['source_prompt','edit_prompt','target_prompt']:assert a['original_task'][key] in r['prompt']
 r['prompt_protocol']={'kind':'official_context_ir_with_benchmark_captions','label':'官方source/edit/target三字段适配完整Context-IR','actual_prompt':r['prompt'],'official_edit_prompt':a['original_task']['edit_prompt'],'official_edit_prompt_preserved_verbatim':True}
 r['quantitative_metrics']={'motion_fidelity':{'native':None,'guided':None,'delta':None,'status':'pending','higher_is_better':True,'protocol':'IVEBench official MF','valid_frames':r['valid_frames'],'evaluation_frames':r['valid_frames'],'evaluation_fps':24}}
 rel=B/s['release'] if s['release'] else c/'audit/actual_release'
 for name in ['ROOT_EXIT_RECEIPT.json','COMPLETE.json']:
  f=rel/name;v=json.loads(f.read_text());assert v['passed'];evid.append(f)
 if pair:
  hand=c/'audit/FORMAL_PAIR_HANDOFF.json';hv=json.loads(hand.read_text());assert hv['passed'];assert hv['inventory_id']==s['id'];evid.append(hand);r['execution_seconds']=b['efficiency']
 else:evid.append(c/'audit/NATIVE_DECISION_SUBMISSION.json')
 r['evidence_paths']=[str(e) for e in dict.fromkeys(evid)];r['evidence_sha256']={str(e):H(e) for e in evid};x['items'].append(r);new.append(r['id'])
a=x['items'];x['updated_unix']=time.time();x['counts'].update(items=len(a),unique_sources=len({r['source_id'] for r in a}),guided_pairs=sum(r.get('comparison_kind')=='guided_pair' for r in a),activated_fixed_pairs=sum(r.get('comparison_kind')=='guided_pair' and (r.get('actual_routed_blocks') or r.get('routed_block_calls') or 0)>0 for r in a),native_only=sum(r.get('comparison_kind')=='native_only' for r in a))
assert H(p)==old;t=p.with_suffix('.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(t,p)
v={'before_sha256':old,'after_sha256':H(p),'added':new,'ive_counts':x['counts'],'total_versions':len(a)+31,'created_unix':time.time()};(A/'RECEIPT.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');print(json.dumps(v,ensure_ascii=False,indent=2))
