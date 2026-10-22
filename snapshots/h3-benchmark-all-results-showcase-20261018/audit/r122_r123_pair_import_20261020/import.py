from pathlib import Path
import json,hashlib,copy,time,os
ROOT=Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018');OUT=Path(__file__).parent
H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=ROOT/'inventory/ivebench.json';raw=p.read_bytes();old=H(p);x=json.loads(raw);(OUT/'ivebench_before.json').write_bytes(raw)
assert old=='46b53fa56972004538ec76a2afba1dce0bd246808d167a4150446413476994c0'
r122=next(r for r in x['items'] if r['id']=='r122_long_0039_generic_retention');template=copy.deepcopy(r122)
def configure(r,base,source,review_name):
 c=Path('/Users/researcher/DevProjects')/base;sr=c/'showcase_pairs'/source;inc=c/'incoming_pairs'/source
 presentation=sr/'PRESENTATION.json';a=json.loads(presentation.read_text());review=c/'audit/full_frame_review'/source/'paired'/review_name;b=json.loads(review.read_text())
 for key,v in zip(['reference_video_path','ordinary_video_path','guided_video_path'],a['inputs']):
  assert H(v['file'])==v['sha256'];r[key]=v['file']
 v=a['videos'][0];r['comparison_video_path']=str(sr/v['file']);assert H(r['comparison_video_path'])==v['sha256']
 r.update(comparison_kind='guided_pair',column_labels=['1.参考视频','2.普通编辑','3.时序引导'],guidance_activation='fixed_active',guided_status='complete',guidance_decision='guide',actual_routed_blocks=450,routed_block_calls=450,method_label='固定6–14步时序引导',valid_frames=a['timeline']['valid_frames'],generated_frames=a['timeline']['total_frames'],fps=24,source_clip=a['source_clip'],original_task=a['original_task'],prompt_version=a['prompt_version'],review_status_code='PASS_CORE_EDIT',count_as_complete_task_success=True,support_for_clear_whole_event_repair=False,action_alignment_bool=False,action_alignment_by_method={'native':False,'guided':False},release_status='COMPLETE_EXACT_RELEASE')
 r['full_frame_review_path']=str(review);r['event_review']={'file':str(review),'sha256':H(review),'events':b['events'],'scope':'同帧事件区间逐帧审阅；局部提前与残余延迟分别记录。'}
 r['media_sha256']={k:H(r[k]) for k in ['reference_video_path','ordinary_video_path','guided_video_path','comparison_video_path']}
 r['actual_prompt_by_column']={};prompts=[]
 evid=[presentation,review,inc/'PAIR_RUNTIME_GATE.json',inc/'COLLECTION.json',review.parent/'FRAME_LEDGER.json',c/'prepared'/source/'paired/MF_INPUTS.json']
 for arm,column in [('native','ordinary'),('forced','guided')]:
  graph=inc/(arm+'_graph.json');history=inc/(arm+'_history.json');g=json.loads(graph.read_text());text=g['5']['inputs']['prompt'];prompts.append(text);router=json.loads((inc/(arm+'_router.json')).read_text());assert router['routed_calls']==(0 if arm=='native' else 450)
  r['actual_prompt_by_column'][column]={'text':text,'prompt_sha256':hashlib.sha256(text.encode()).hexdigest(),'protocol':a['prompt_version'],'exact_official_edit_prompt':False,'graph_bindings':[{'graph':str(graph),'graph_sha256':H(graph),'node_id':'5','field':'inputs.prompt'}],'actual_history':str(history),'actual_history_sha256':H(history),'scope':'对应已完成视频的实际提交图及Comfy history；consumer严格逐字核验。'}
  evid += [graph,history,inc/(arm+'_job.json'),inc/(arm+'_router.json')]
 assert prompts[0]==prompts[1];r['prompt']=prompts[0]
 r['prompt_protocol']['actual_prompt']=prompts[0];r['prompt_protocol']['official_edit_prompt']=a['original_task']['edit_prompt'];r['prompt_protocol']['official_edit_prompt_preserved_verbatim']=a['original_task']['edit_prompt'] in prompts[0]
 r['quantitative_metrics']={'motion_fidelity':{'native':None,'guided':None,'delta':None,'status':'pending','higher_is_better':True,'protocol':'IVEBench official MF','valid_frames':r['valid_frames'],'evaluation_frames':r['valid_frames'],'evaluation_fps':24}}
 r['evidence_paths']=list(dict.fromkeys(r.get('evidence_paths',[])+[str(v) for v in evid]));r['evidence_sha256']={str(v):H(v) for v in r['evidence_paths']}
 return c,b
c,b=configure(r122,'h3-ive-generic-retention-metrics-r122-20261020','long_0039','REVIEW.json')
r122.update(variant='R122 · 原句加通用保留要求 · 时序引导配对',review_status='抬书提前，触书仍晚；最初伸手过程拉长',review_summary=b['conclusion'],display_summary=b['conclusion'],guidance_effect='LOCAL_TIMING_IMPROVEMENT',clear_temporal_support=True,key_same_frame_indices=[18,81,90],judgment_source='continue_r90_r104完整106有效帧三列审阅；root抽查并复核阶段持续时间。')
r122['event_review']['phase_durations_frames']=b['phase_durations_frames']
for name in ['ROOT_EXIT_RECEIPT.json','COMPLETE.json']:
 e=Path('/Users/researcher/DevProjects/h3-timing-ive-generic-retention-r122-20261020/audit/root_generic_retention_attempt1')/name;r122['evidence_paths'].append(str(e));r122['evidence_sha256'][str(e)]=H(e)
new=copy.deepcopy(template);new.update(id='r123_short_0358_full_context',source_id='short_0358',variant='R123 · 完整Context-IR · 同提示词时序引导',title='饮酒动作 · 给饮酒者加眼镜',task='Add a pair of glasses to the man.',display_task='给画面左侧饮酒男子加眼镜，保留双人场景和饮酒动作。',pair_group='IVEBench官方短视频任务',evidence_paths=[],evidence_sha256={})
c,b=configure(new,'h3-ive-prompt-envelope-metrics-r123-20261020/variants/full_context','short_0358','INDEPENDENT_REVIEW.json')
summary='两版均给左侧饮酒男子加眼镜，右侧男子、餐馆与饮酒动作保留。引导后酒瓶到嘴约提前3帧、离嘴约提前1–2帧，事件区间部分重叠，后半段仍延后。'
new.update(review_status='基础编辑完成；饮酒局部小幅提前，残余延迟保留',review_summary=summary,display_summary=summary,guidance_effect='SMALL_LOCAL_TIMING_IMPROVEMENT',clear_temporal_support=False,key_same_frame_indices=[45,85],judgment_source='continue_r111_r103完整105有效帧三列审阅；root抽查。',execution_seconds=b['execution_seconds'])
new['prompt_protocol'].update(kind='official_context_ir_with_benchmark_captions',label='官方source/edit/target三字段适配完整Context-IR；指定饮酒者消歧单独记录')
for name in ['ROOT_EXIT_RECEIPT.json','COMPLETE.json']:
 e=c/'audit/actual_release'/name;new['evidence_paths'].append(str(e));new['evidence_sha256'][str(e)]=H(e)
assert not any(r['id']==new['id'] for r in x['items']);x['items'].append(new)
a=x['items'];x['updated_unix']=time.time();x['counts'].update(items=len(a),unique_sources=len({r['source_id'] for r in a}),guided_pairs=sum(r.get('comparison_kind')=='guided_pair' for r in a),activated_fixed_pairs=sum(r.get('comparison_kind')=='guided_pair' and (r.get('actual_routed_blocks') or r.get('routed_block_calls') or 0)>0 for r in a),native_only=sum(r.get('comparison_kind')=='native_only' for r in a))
assert H(p)==old
out=json.dumps(x,ensure_ascii=False,indent=2)+'\n';tmp=p.with_suffix('.tmp');tmp.write_text(out);os.replace(tmp,p)
receipt={'before_sha256':old,'after_sha256':H(p),'changed':['r122_long_0039_generic_retention',new['id']],'ive_counts':x['counts'],'total_versions_with_flex':len(a)+31,'created_unix':time.time()};(OUT/'RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False,indent=2))
