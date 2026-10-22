from pathlib import Path
import datetime, hashlib, json, os, time

BASE = Path('/Users/researcher/DevProjects')
P = BASE/'h3-benchmark-all-results-showcase-20261018'
H = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
J = lambda p: json.loads(Path(p).read_text())
inventory = P/'inventory/ivebench.json'
before = H(inventory)
assert before == '9b518433d2094fcd4673ff689a992c84284755154da7975b670bae2094b57fef'
data = J(inventory)
specs = [
    dict(run=120, source='long_0059', consumer='h3-ive-official-prompt-metrics-r120-20261019',
         id='r120_long_0059_official_prompt', variant='R120 · benchmark原文普通编辑',
         title='擦眼动作 · 添加白手帕', display_task='为正在擦眼的男子手中添加白色手帕。',
         review='REVIEW.json', review_sha='c63697795f53bdea6ad77c403c2a17f7e2aa2831726ab1848c3ac74c6a0f3dec',
         status='FAIL_SCENE_VIEW_AND_ACTION',
         summary='白手帕出现，但原室内正面擦眼视频变为户外西装男子行走和转头；全部144有效帧的擦眼动作序列不可比，已跳过引导。',
         frames=[30,70,98,140], protocol='official_edit_prompt', label='benchmark原文',
         release=BASE/'h3-timing-ive-official-prompt-r120-20261019/audit/native_failed_queue_close_20261020/EXACT_RELEASE.json',
         release_sha='5e99749e61d307dff7bb9f9b8aacd1181be5752b950a9c4a6fc149c271852755',
         reviewer='continue_r90_r104完整144有效帧审阅；root抽查001/015/028页并同意skip。'),
    dict(run=123, source='short_0358', consumer='h3-ive-prompt-envelope-metrics-r123-20261020',
         id='r123_short_0358_prompt_envelope', variant='R123 · 原文加任务与参考标记',
         title='餐厅饮酒 · 给男人加眼镜', display_task='为餐厅中饮酒的男子添加一副眼镜。',
         review='INDEPENDENT_REVIEW.json', review_sha=None,
         status='FAIL_PEOPLE_FRAMING_AND_ACTION',
         summary='眼镜出现，但两名对坐男子变为并排近景中的男女；瓶子全程直立桌面，饮酒改成抬手碰眼镜，已跳过引导。',
         frames=[0,38,65,82], protocol='official_edit_prompt_with_task_reference_envelope', label='原文加任务与参考标记',
         release=BASE/'h3-ive-prompt-envelope-metrics-r123-20261020/audit/actual_release/ROOT_EXIT_RECEIPT.json',
         release_sha='a1f7042b6cbbf3d4650067e41c57254cb7d28023dc0fd10c7af9094031dc7f0c',
         reviewer='continue_r111_r103完整105有效帧独立审阅及实际skip决定。')
]
added = []
for s in specs:
    C = BASE/s['consumer']; source=s['source']
    presentation_path=C/'showcase'/source/'PRESENTATION.json'
    presentation=J(presentation_path)
    review_path=C/'audit/full_frame_review'/source/'native'/s['review']; review=J(review_path)
    n=presentation['timeline']['valid_frames']; total=presentation['timeline']['total_frames']
    assert review.get('examined_frames',review.get('reviewed_frames'))==list(range(n))
    if s['review_sha']: assert H(review_path)==s['review_sha']
    decision_path=C/'audit/root_decisions'/source/'ROOT_DECISION.json'
    decision=J(decision_path)['decision']; assert decision['choice']=='skip'
    graph=C/'incoming'/source/'native_graph.json'; history=C/'incoming'/source/'native_history.json'
    actual=J(graph)['5']['inputs']['prompt']; official=presentation['original_task']['edit_prompt']
    assert official in actual
    if s['run']==120: assert actual==official
    else: assert actual!=official and '[video editing]' in actual and 'retention_analysis' not in actual
    release=s['release']; assert H(release)==s['release_sha'] and J(release)['passed']
    row=dict(id=s['id'],benchmark='IVEBench',source_id=source,variant=s['variant'],title=s['title'],
             task=official,display_task=s['display_task'],reference_image_used=False,reference_image_path=None,
             reference_video_path=str(C/'inputs'/f'{source}_video.mp4'),
             ordinary_video_path=str(C/'incoming'/source/'native.mp4'),
             comparison_video_path=str(C/'showcase'/source/'source_native_full_valid.mp4'),
             guided_video_path=None,alternative_video_path=None,comparison_kind='native_only',
             column_labels=['1.参考视频','2.普通编辑'],guidance_activation='not_run',guidance_decision='skip',
             actual_routed_blocks=0,routed_block_calls=0,method_label=s['label']+'，普通编辑',
             pair_group='IVEBench素材片段探索' if s['run']==120 else '官方原任务',
             valid_frames=n,generated_frames=total,fps=24,seed=2026101701,
             prompt=actual,prompt_version=s['protocol'],original_task=presentation['original_task'],
             review_status='基础任务改变，已跳过引导',review_status_code=s['status'],
             review_summary=s['summary'],display_summary=s['summary'],
             count_as_complete_task_success=False,clear_temporal_support=False,
             support_for_clear_whole_event_repair=False,action_alignment_bool=None,
             action_alignment_by_method={'native':None,'guided':None},guidance_effect='NOT_RUN',
             key_same_frame_indices=s['frames'],judgment_source=s['reviewer'],
             event_review={'file':str(review_path),'sha256':H(review_path),'events':review['events'],
                           'scope':'基础人物、场景或动作序列改变；原动作事件在编辑成片中不可比较。'},
             full_frame_review_path=str(review_path),release_status='EXACT_RELEASED_NATIVE_ONLY')
    if s['run']==120:
        row['source_clip']=presentation['source_clip']
        row['queue_disposition']={'long_0059':'Native complete; guided skip','long_0163':'never submitted','long_0081':'never submitted'}
    evidence=[presentation_path,review_path,decision_path,C/'incoming'/source/'NATIVE_RUNTIME_GATE.json',
              C/'incoming'/source/'COLLECTION.json',graph,history,C/'incoming'/source/'native_job.json',release]
    row['evidence_paths']=[str(p) for p in evidence]
    row['evidence_sha256']={str(p):H(p) for p in evidence}
    row['media_sha256']={k:H(row[k]) for k in ['reference_video_path','ordinary_video_path','comparison_video_path']}
    assert row['media_sha256']['ordinary_video_path']==decision['binding']['video_sha256']
    assert row['media_sha256']['comparison_video_path']==presentation['videos'][0]['sha256']
    for i in presentation['inputs']: assert H(i['file'])==i['sha256']
    row['quantitative_metrics']={'motion_fidelity':dict(native=None,guided=None,delta=None,status='pending_native_only',
        higher_is_better=True,protocol='IVEBench official MF',valid_frames=n,evaluation_frames=n,evaluation_fps=24)}
    row['prompt_protocol']=dict(kind=s['protocol'],label=s['label'],official_edit_prompt=official,actual_prompt=actual,
                               verbatim=actual==official,official_edit_prompt_preserved_verbatim=True)
    row['actual_prompt_by_column']={'ordinary':dict(text=actual,prompt_sha256=hashlib.sha256(actual.encode()).hexdigest(),
        protocol=s['protocol'],exact_official_edit_prompt=actual==official,
        graph_bindings=[dict(graph=str(graph),graph_sha256=H(graph),node_id='5',field='inputs.prompt')],
        actual_history=str(history),actual_history_sha256=H(history),
        scope='Actual ordinary video; guided skipped after full task review.')}
    row['producer_release']=dict(file=str(release),sha256=H(release),GPU_released=True)
    assert not any(x['id']==row['id'] for x in data['items'])
    added.append(row)
data['items'].extend(added)
data['counts'].update(items=len(data['items']),unique_sources=len({x['source_id'] for x in data['items']}),
                      native_only=data['counts']['native_only']+len(added),
                      native_only_skipped_after_review=data['counts']['native_only_skipped_after_review']+len(added))
data.update(updated_unix=time.time(),snapshot_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),previous_inventory_sha256=before)
out=P/'audit/r120_r123_native_import_20261020';out.mkdir(exist_ok=False)
(out/'ADDED_ROWS.json').write_text(json.dumps(added,ensure_ascii=False,indent=2)+'\n')
tmp=inventory.with_suffix('.json.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
assert H(inventory)==before
os.replace(tmp,inventory)
receipt={'before':before,'after':H(inventory),'inventory':str(inventory),'added_ids':[r['id'] for r in added],'counts':data['counts'],'new_scores':False}
(out/'RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(receipt,ensure_ascii=False))
