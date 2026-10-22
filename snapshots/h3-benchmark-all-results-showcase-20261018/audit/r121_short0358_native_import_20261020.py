from pathlib import Path
import copy, datetime, hashlib, json, os, time

P = Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018')
C = Path('/Users/researcher/DevProjects/h3-ive-official-positive-recheck-metrics-r121-20261020')
H = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
J = lambda p: json.loads(Path(p).read_text())
inventory = P/'inventory/ivebench.json'
before = H(inventory)
assert before == 'f33dbcb8b8daf8254121a3d3c534f2c33f3882b276c2fe55fd37ddc81f0c2fdb'
data = J(inventory)
row = copy.deepcopy(J(P/'audit/r121_short0252_native_import_20261020/ADDED_ROW.json'))
row = json.loads(json.dumps(row).replace('short_0252', 'short_0358'))
presentation = J(C/'showcase/short_0358/PRESENTATION.json')
review_path = C/'audit/full_frame_review/short_0358/native/INDEPENDENT_REVIEW.json'
review = J(review_path)
assert H(review_path) == '43e1502ea0efaf05aea558fbc11d673941f53a20e2333c26f769efae5ce2eaec'
assert review['examined_frames'] == list(range(105))
decision = J(C/'audit/root_decisions/short_0358/ROOT_DECISION.json')
assert decision['decision']['choice'] == 'skip'
prompt = presentation['original_task']['edit_prompt']
assert prompt == 'Add a pair of glasses to the man.'
graph = C/'incoming/short_0358/native_graph.json'
history = C/'incoming/short_0358/native_history.json'
assert J(graph)['5']['inputs']['prompt'] == prompt
row.update(title='餐厅饮酒 · 给男人加眼镜', task=prompt,
           display_task='为餐厅中饮酒的男子添加一副眼镜。', valid_frames=105,
           prompt=prompt, original_task=presentation['original_task'],
           review_status='构图和饮酒动作改变，已跳过引导',
           review_status_code='FAIL_SCENE_FRAMING_AND_ACTION',
           review_summary='全部105帧中，原双人餐厅宽景变为单人正面近景，邻座男子消失；饮酒动作变为拿起并戴上眼镜，酒瓶全程直立在桌面。眼镜约80–84帧戴到眼前。本轮保留普通编辑并跳过引导。',
           display_summary='双人餐厅宽景变为单人近景，饮酒动作变成戴眼镜；已跳过引导。',
           key_same_frame_indices=[0,38,82],
           judgment_source='continue_r111_r103完整105有效帧审阅及实际skip决定。',
           release_status='BOTH_NATIVE_COMPLETE_EXACT_RELEASE_PENDING_BINDING')
row['event_review'].update(file=str(review_path), sha256=H(review_path), events=review['events'],
                         scope='基础场景和动作序列改变；三个饮酒事件在新视频中均不可比。')
row['evidence_sha256'] = {p:H(p) for p in row['evidence_paths']}
row['media_sha256'] = {key:H(row[key]) for key in row['media_sha256']}
for i in presentation['inputs']:
    assert H(i['file']) == i['sha256']
assert row['media_sha256']['ordinary_video_path'] == decision['decision']['binding']['video_sha256']
assert row['media_sha256']['comparison_video_path'] == presentation['videos'][0]['sha256']
row['quantitative_metrics']['motion_fidelity'].update(valid_frames=105,evaluation_frames=105)
row['prompt_protocol'].update(official_edit_prompt=prompt, actual_prompt=prompt)
column=row['actual_prompt_by_column']['ordinary']
column.update(text=prompt,prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),actual_history_sha256=H(history))
column['graph_bindings'][0]['graph_sha256']=H(graph)
assert all(x['id'] != row['id'] for x in data['items'])
data['items'].append(row)
data['counts'].update(items=len(data['items']),unique_sources=len({x['source_id'] for x in data['items']}),
                      native_only=data['counts']['native_only']+1,
                      native_only_skipped_after_review=data['counts']['native_only_skipped_after_review']+1)
data.update(updated_unix=time.time(),snapshot_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),previous_inventory_sha256=before)
out=P/'audit/r121_short0358_native_import_20261020';out.mkdir(exist_ok=False)
(out/'ADDED_ROW.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
tmp=inventory.with_suffix('.json.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
assert H(inventory)==before
os.replace(tmp,inventory)
receipt={'before':before,'after':H(inventory),'inventory':str(inventory),'added_id':row['id'],'counts':data['counts'],'independent_review_sha256':H(review_path),'new_scores':False}
(out/'RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(receipt,ensure_ascii=False))
