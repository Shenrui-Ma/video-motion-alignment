from pathlib import Path
import copy,collections,hashlib,json,re,time
R=Path(__file__).resolve().parents[1];C=R.parent/'h3-flexiact-remaining-repair-metrics-r104-20261019';K='crouch__movie_man_5'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=R/'inventory/flexiact.json';before=sha(p)
assert before=='b4d7871f28ba32aaaeea7e4a26d35da2b269fa15af8d02b6c75412daf3ba51bc'
d=read(p);prior=copy.deepcopy(d['items']);old=next(x for x in prior if x['id']=='flex_r105_crouch__movie_man_4_native')
row=json.loads(json.dumps(old).replace('r105','r104').replace('R105','R104').replace('movie_man_4','movie_man_5'))
c=next(x for x in read(C/'configs/contract.json')['sources'] if x['source_id']==K);a=C/'incoming'/K;s=C/'showcase'/K;g=read(a/'NATIVE_RUNTIME_GATE.json');pr=read(s/'PRESENTATION.json');review=C/'audit/full_frame_review'/K/'native/REVIEW.json';v=read(review)
assert g['passed'] and all(g['checks'].values()) and g['runs']['native']['routed_blocks']==0
assert v['reviewed_all_valid_frames'] and v['reviewed_frames']==list(range(147)) and v['decision']=='skip'
assert sha(review)=='a9548555dda5f652ead6de910a34cbdfd7dbc2236d51f27e840e0d8f67c2efa8'
media={'reference_image_path':str(C/c['portrait']['file']),'reference_video_path':str(C/c['source']['file']),'ordinary_video_path':str(a/'native.mp4'),'native_comparison_video_path':str(s/'source_native_full_valid.mp4')}
assert sha(media['ordinary_video_path'])==g['runs']['native']['video']['sha256'];assert sha(media['native_comparison_video_path'])==pr['videos'][0]['sha256']
ev=[C/'configs/contract.json',a/'NATIVE_RUNTIME_GATE.json',a/'COLLECTION.json',s/'PRESENTATION.json',review,review.parent/'MEDIA_BINDINGS.json',C/'audit/CROUCH_SOURCE_PHASE_BRACKETS_PRE_INFERENCE.json',C/'prepared'/K/'native/MF_INPUTS.json',C/'audit/actual_full_release/VERIFIED.json']
summary='完整147帧检查：炭灰西装男子替换成功，两次深蹲、中间站立和末段起身保留，侧面构图及头、手、脚均可见。各动作阶段与参考视频重叠，当前未见清楚延后。白色背景已生成，脚下仍保留源视频木栈道，环境编辑部分完成。本轮保留普通编辑。'
html=Path('/Users/researcher/Downloads')/f'H3_R104_{K}_普通编辑预览_20261019.html'
row.update(id='flex_r104_crouch__movie_man_5_native',source_id='crouch',reference_image_id='movie_man_5',title='两次深蹲与起身 · movie_man_5',task=c['display_task'],display_task=c['display_task'],**media,preview_html=str(html),review_status='角色与两次深蹲完成，动作时序接近；木栈道残留',review_summary=summary,display_summary=summary,identity_success={'native':True,'guided':None},motion_transfer='two_squat_repetitions_preserved_partial_environment',pair_group='官方原始配对',prompt=c['prompt'],prompt_version=c['prompt_version'],input_contract_path=str(C/'configs/contract.json'),input_reference_image_sha256=c['portrait']['sha256'],input_reference_video_sha256=c['source']['sha256'],scene_requirement='目标图白色影棚；当前残留原视频木栈道',judgment_source='continue_r90_r104逐帧审阅全147有效帧与目标图；源阶段计划在该输出前记录。',event_review={'file':str(review),'sha256':sha(review)},parent_inventory_id='flex_r85_crouch__movie_man_5',runtime={'native_job_wall_seconds':g['runs']['native']['job_wall_seconds']},evidence_paths=[str(x) for x in ev],evidence_sha256={str(x):sha(x) for x in ev},media_sha256={k:sha(v) for k,v in media.items()})
row['quantitative_metrics']['motion_fidelity'].update(status='NOT_RUN',native=None,guided=None,delta=None,source_files=[str(C/'prepared'/K/'native/MF_INPUTS.json')])
assert not any(x['id']==row['id'] for x in prior);d['items'].append(row);assert d['items'][:-1]==prior
d.update(previous_inventory_sha256=before,updated_unix=time.time(),counts=dict(collections.Counter(x['comparison_kind'] for x in d['items'])),distinct_motion_sources=len({x['source_id'] for x in d['items']}))
b=R/'audit/r104_crouch_native_20261019';b.mkdir(exist_ok=False);(b/'PREVIOUS_INVENTORY.json').write_bytes(p.read_bytes());assert sha(p)==before;p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
t=html.read_text();assets=re.findall(r'data:[^"\s>]+',t);assert 'id="native-review"' not in t
t=t.replace('<figure>','<section id="native-review"><h2>全片检查结果</h2><p>'+summary+'</p><p>本例采用官方原始视频与角色图配对。官方 Motion Fidelity 尚未评分。</p></section><figure>',1);assert re.findall(r'data:[^"\s>]+',t)==assets;html.write_text(t)
v={'before_sha256':before,'after_sha256':sha(p),'rows':len(d['items']),'id':row['id'],'review_sha256':sha(review),'html':str(html),'html_sha256':sha(html),'embedded_assets_unchanged':True};(b/'RECEIPT.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');print(json.dumps(v,ensure_ascii=False))
