from pathlib import Path
import json,hashlib,copy
B=Path('/Users/researcher/DevProjects');R=B/'h3-benchmark-all-results-showcase-20261018';A=Path(__file__).parent
C=B/'h3-ive-handkerchief-full-context-metrics-r126-20261020';P=B/'h3-timing-ive-handkerchief-full-context-r126-20261020';S='long_0059';inc=C/'incoming_pairs'/S
H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
by={r['id']:r for r in read(R/'inventory/ivebench.json')['items']};row=copy.deepcopy(by['r123_short_0358_full_context'])
review=C/'audit/full_frame_review'/S/'paired/REVIEW.json';rv=read(review);assert H(review)=='abda2deee395679e2b2943f5c3335eff7c50402740e73e6be04062ce684ddce1';assert rv['examined_frames']==list(range(144)) and rv['all_valid_frames_inspected']
pres=C/'showcase_pairs'/S/'PRESENTATION.json';v=read(pres);assert H(pres)=='c148387a6f6b011ed79dbbb540f9de9e036540a804922580b01104ba1fe7a367'
for k,x in zip(['reference_video_path','ordinary_video_path','guided_video_path'],v['inputs']):assert H(x['file'])==x['sha256'];row[k]=x['file']
row['comparison_video_path']=str(pres.parent/v['videos'][0]['file']);assert H(row['comparison_video_path'])==v['videos'][0]['sha256']
text='两版均成功添加白手帕，保留人物、场景和擦眼动作。抬手与触眼接近参考，撤手均约晚16帧；固定时序引导未缩短这段延后。'
row.update(id='r126_long_0059_full_context',source_id=S,variant='R126 · 完整Context-IR · 同提示词时序引导',title='擦眼动作 · 手中添加白手帕',display_task='擦眼动作 · 手中添加白手帕',task=v['original_task']['edit_prompt'],pair_group=v['evaluation_scope'],valid_frames=144,generated_frames=158,source_clip=v['source_clip'],prompt_version=v['prompt_version'],original_task=v['original_task'],review_status=text,review_summary=text,display_summary=text,review_status_code='PASS_CORE_EDIT',count_as_complete_task_success=True,clear_temporal_support=False,support_for_clear_whole_event_repair=False,action_alignment_bool=False,action_alignment_by_method={'native':False,'guided':False},guidance_effect='NO_CLEAR_BENEFIT',key_same_frame_indices=[107,120],judgment_source='continue_r90_r104完整144有效帧三列审阅；root复核8页。',full_frame_review_path=str(review))
row['task_acceptance_by_method']={'native':rv['task_acceptance']['native'],'guided':rv['task_acceptance']['forced']}
row['event_review']={'file':str(review),'sha256':H(review),'events':rv['events'],'phase_durations_frames':rv['phase_duration'],'additional_observations':rv['additional_observations'],'scope':'全部144有效帧，三项既有事件与探索性手部出画阶段分别记录。'}
row['quantitative_metrics']={'motion_fidelity':{'native':None,'guided':None,'delta':None,'status':'pending','higher_is_better':True,'protocol':'IVEBench official MF','valid_frames':144,'evaluation_frames':144,'evaluation_fps':24}}
evid=[pres,review,review.parent/'FRAME_LEDGER.json',review.parent/'ROOT_SPOT_REVIEW.json',inc/'PAIR_RUNTIME_GATE.json',inc/'COLLECTION.json',C/'prepared'/S/'paired/MF_INPUTS.json',C/'audit/actual_release/HANDOFF.json',P/'audit/ACTUAL_PAIR_SUBMISSION.json',P/'audit/ACTUAL_EFFICIENCY_LOG_EXCERPT.json']
row['actual_prompt_by_column']={};prompts=[]
for arm,column in [('native','ordinary'),('forced','guided')]:
 g=inc/(arm+'_graph.json');hist=inc/(arm+'_history.json');job=inc/(arm+'_job.json');router=inc/(arm+'_router.json');prompt=read(g)['5']['inputs']['prompt'];assert read(hist)['prompt'][2]['5']['inputs']['prompt']==prompt;prompts.append(prompt)
 assert read(router)['routed_calls']==(450 if arm=='forced' else 0)
 row['actual_prompt_by_column'][column]={'text':prompt,'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'protocol':v['prompt_version'],'exact_official_edit_prompt':False,'graph_bindings':[{'graph':str(g),'graph_sha256':H(g),'node_id':'5','field':'inputs.prompt'}],'actual_history':str(hist),'actual_history_sha256':H(hist),'scope':'实际提交图与Comfy history文本逐字相同；原benchmark source/edit/target三字段完整保留。'}
 evid.extend([g,hist,job,router])
assert len(set(prompts))==1;assert all(v['original_task'][f] in prompts[0] for f in ['source_prompt','edit_prompt','target_prompt']);row['prompt']=prompts[0];row['prompt_protocol'].update(actual_prompt=prompts[0],official_edit_prompt=row['task'])
for name in ['ROOT_EXIT_RECEIPT.json','COMPLETE.json']:
 f=C/'audit/actual_release'/name;assert read(f)['passed'];evid.append(f)
eff=read(P/'audit/ACTUAL_EFFICIENCY_LOG_EXCERPT.json');row['execution_seconds']={'native_sampling':eff['native_sampling_seconds'],'guided_sampling':eff['guided_sampling_seconds'],'native_comfy_job':eff['native_comfy_job_seconds'],'guided_comfy_job':eff['guided_comfy_job_seconds'],'sampling_steps':20,'scope':'Actual ComfyUI log elapsed; shared GPU conditions retained.'}
row['evidence_paths']=[str(f) for f in evid];row['evidence_sha256']={str(f):H(f) for f in evid};row['media_sha256']={k:H(row[k]) for k in ['reference_video_path','ordinary_video_path','guided_video_path','comparison_video_path']}
(A/'DRAFT_ROW.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n');out={'draft':str(A/'DRAFT_ROW.json'),'sha256':H(A/'DRAFT_ROW.json'),'inventory_unchanged':H(R/'inventory/ivebench.json'),'actual_pair_and_review_verified':True,'official_mf':'pending'};(A/'PREPARED.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
