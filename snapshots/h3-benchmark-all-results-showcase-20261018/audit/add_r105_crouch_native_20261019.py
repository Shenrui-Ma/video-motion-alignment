from pathlib import Path
import copy,json,hashlib,time,re,collections
R=Path(__file__).resolve().parents[1];C=R.parent/'h3-flexiact-remaining-repair-metrics-r105-20261019'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source='crouch__movie_man_4';a=C/'incoming'/source;s=C/'showcase'/source
contract=C/'configs/contract.json';c=next(x for x in read(contract)['sources'] if x['source_id']==source)
pres=s/'PRESENTATION.json';pr=read(pres);gate=a/'NATIVE_RUNTIME_GATE.json';g=read(gate)
review=C/'audit/ROOT_NATIVE_REVIEW_crouch__movie_man_4.json';v=read(review)
assert sha(review)=='4d1631028b442079196717ef464f8fdbb6c2600dc9e2e7b7590df79f67d2e6a5'
assert g['passed'] and all(g['checks'].values()) and g['runs']['native']['routed_blocks']==0
assert v['coverage']['all_frames_visually_viewed'] and v['coverage']['count']==147 and v['decision']=='skip'
evidence=[contract,gate,a/'COLLECTION.json',pres,review,C/'audit/full_frame_review'/source/'native/MEDIA_BINDINGS.json',C/'audit/crouch_decision_review_reference.json',C/'prepared'/source/'native/MF_INPUTS.json']
media={'reference_image_path':str(C/c['portrait']['file']),'reference_video_path':str(C/c['source']['file']),'ordinary_video_path':str(a/'native.mp4'),'native_comparison_video_path':str(s/'source_native_full_valid.mp4')}
assert sha(media['ordinary_video_path'])==g['runs']['native']['video']['sha256'] and sha(media['native_comparison_video_path'])==pr['videos'][0]['sha256']
p=R/'inventory/flexiact.json';before=sha(p);assert before=='d66b84e15b6b9a4bbf150a3a73ceb8dce485f72669db4ae480a6b526586f34cd'
d=read(p);old=copy.deepcopy(d['items']);row=copy.deepcopy(next(x for x in old if x['id']=='flex_r49_crouch_native'))
summary='全部147有效帧审阅：目标赤膊男子、深蓝泳裤和海景替换成功，两次下蹲与起立顺序保留；人物放大，双脚与部分小腿被裁出。可见下蹲和起立阶段与参考区间重叠，未发现清楚的时序错误。本轮保留普通编辑结果并跳过引导，记为构图不完整。'
row.update(id='flex_r105_crouch__movie_man_4_native',source_id='crouch',reference_image_id='movie_man_4',variant='R105 · 提示词修复后普通编辑',title='两次下蹲起立 · movie_man_4',task=c['display_task'],display_task=c['display_task'],**media,preview_html=str(Path('/Users/researcher/Downloads')/f'H3_R105_{source}_普通编辑预览_20261019.html'),review_status='角色和蹲起完成，脚部被裁出；普通编辑',review_status_code='partial_framing_native_only',review_summary=summary,display_summary=summary,count_as_complete_task_success=False,clear_temporal_support=False,support_for_clear_whole_event_repair=False,identity_success={'native':True,'guided':None},motion_transfer='two_squats_retained_partial_framing',pair_group='官方原始配对',input_contract_path=str(contract),prompt=c['prompt'],prompt_version=c['prompt_version'],input_reference_image_sha256=c['portrait']['sha256'],input_reference_video_sha256=c['source']['sha256'],scene_requirement='目标图海景与天空',judgment_source='root完整审阅147有效帧，目标身份、场景、动作与裁剪分别验收。',event_review={'file':str(review),'sha256':sha(review)},parent_inventory_id='flex_r49_crouch_native',runtime={'native_job_wall_seconds':g['runs']['native']['job_wall_seconds']},evidence_paths=[str(x) for x in evidence],evidence_sha256={str(x):sha(x) for x in evidence},media_sha256={k:sha(x) for k,x in media.items()},method_label='普通编辑；任务审阅后跳过引导',comparison_kind='native_only',comparison_subtype='repaired_prompt_native_screen',column_labels=['1.参考视频','2.普通编辑'],guidance_activation='not_applicable',routed_block_calls=0,guidance_decision='skip',quantitative_metrics={'motion_fidelity':{'native':None,'guided':None,'delta':None,'higher_is_better':True,'status':'pending','protocol':'FlexiAct official MF; original49@8fps source and generated0,3,...144','source_files':[str(C/'prepared'/source/'native/MF_INPUTS.json')],'scope':'本轮实际普通编辑尚待官方MF；无引导输出。'}})
row.pop('scene_requirement_prompt_quote',None)
assert row['guided_video_path'] is None and row['alternative_video_path'] is None
assert not any(x['id']==row['id'] for x in old);d['items'].append(row);assert d['items'][:-1]==old
# Recompute snapshot counters from all preserved rows.
d['counts']=dict(collections.Counter(x['comparison_kind'] for x in d['items']));d['distinct_motion_sources']=len({x['source_id'] for x in d['items']})
d['previous_inventory_sha256']=before;d['updated_unix']=time.time();assert sha(p)==before
audit=R/'audit/r105_crouch_native_20261019';audit.mkdir(exist_ok=False);(audit/'PREVIOUS_INVENTORY.json').write_bytes(p.read_bytes());p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
html=Path(row['preview_html']);h=html.read_text();message='<section id="native-review"><h2>全片检查结果</h2><p>'+summary+'</p></section>';assert 'id="native-review"' not in h;new=h.replace('<figure>',message+'<figure>',1);assert new!=h
assert re.findall(r'data:[^\"\s>]+',h)==re.findall(r'data:[^\"\s>]+',new);html.write_text(new)
update={'file':str(html),'previous_sha256':hashlib.sha256(h.encode()).hexdigest(),'sha256':sha(html),'review':str(review),'embedded_assets_unchanged':True};(C/'audit/crouch_native_HTML_UPDATE.json').write_text(json.dumps(update,ensure_ascii=False,indent=2)+'\n')
receipt={'before_sha256':before,'after_sha256':sha(p),'id':row['id'],'row_count':len(d['items']),'counts':d['counts'],'review_sha256':sha(review),'html':update};(audit/'RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False))
