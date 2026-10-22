from pathlib import Path
import json,hashlib,time,copy
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bound(p):return {'file':str(p),'sha256':sha(p)}
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
T=read(R/'audit/EVENT_REVIEW_TEMPLATE.json');P=R/'audit/full106_exploratory_review';L=read(P/'FRAME_LEDGER.json')
events=copy.deepcopy(T['events'])
for e in events:e['reference_origin']={'status':'VISIBLE_DELAYED','frames':e['R122_native']['frames'].copy(),'observation':'Full-frame inspection: no resolvable event-boundary shift relative to Native within these visible annotation intervals.'}
phases=[]
for a,b in zip(events,events[1:]):
 d={'from_event':a['id'],'to_event':b['id']}
 for role in ['source','R122_native','R122_fixed','reference_origin']:
  x,y=a[role]['frames'],b[role]['frames'];d[role]={'duration_frames_range':[y[0]-x[1],y[1]-x[0]],'midpoint_duration_frames':(sum(y)-sum(x))/2}
 phases.append(d)
means={role:sum(abs(p[role]['midpoint_duration_frames']-p['source']['midpoint_duration_frames'])for p in phases)/4 for role in ['R122_native','R122_fixed','reference_origin']}
flags=dict(input_pairing='historical_cross_host_pixel_mismatch',paired_input_exact=False,strict_gate_pass=False,exploratory=True)
review=dict(schema='r132-exploratory-full106-review-v1',source_id='long_0039',inventory_id='r132_long_0039_reference_origin',comparison_kind='reference_origin_control',actual_role='reference_origin',fps=24,valid_frames=106,all_frames_inspected=True,inspected_frame_indices=list(range(106)),inspected_pages=[bound(P/f'{i:03d}.jpg')for i in range(1,23)],frame_ledger=bound(P/'FRAME_LEDGER.json'),event_plan=bound(R/'audit/EVENT_REVIEW_TEMPLATE.json'),collection=bound(R/'incoming_exploratory/COLLECTION.json'),original_failed_gate=bound(R/'incoming_exploratory/REFERENCE_ORIGIN_RUNTIME_GATE.json'),actual_release=bound(R/'incoming_exploratory/ROOT_EXIT_RECEIPT.json'),**flags,
 task={'status':'PASS_CORE_EDIT','blue_book_preserved':True,'scene_person_camera_preserved':True,'action_sequence_preserved':True,'observations':['蓝色封面从平放到举起、展开均保持；没有R129棕色书封复制源片的失败。','人物、电脑、桌面和背景人群保留，五个可见动作阶段存在。']},
 temporal_conclusion='NO_CLEAR_BENEFIT_VS_NATIVE_AND_NO_EVENT_ALIGNMENT_GAIN_OVER_R122_FIXED',alignment={'native':False,'R122_fixed':False,'reference_origin':False},events=events,all_adjacent_phases=phases,phase_midpoint_mean_absolute_duration_error_frames=means,
 summary='参考分支相位引导保留蓝书编辑，但五事件区间均与普通编辑重叠；离键盘、立书、离支撑和展开仍比旧R122固定引导更晚。四阶段持续时间接近普通编辑，并不构成事件时刻恢复。',
 cautions=['历史输入像素跨主机不完全一致，原严格gate失败保留；这里只是实际成片探索性描述，不作精确同条件因果或主方法正例。','事件区间是可见标注范围，非置信区间；源、Native、R122fixed区间来自冻结历史标注，此次完整检查source/Native/reference_origin。','相邻阶段使用同一组事件端点；阶段中点误差不等于事件绝对时差，减少阶段误差不能替代事件对齐。'],created_unix=time.time())
save(P/'REVIEW.json',review)
pres=read(R/'showcase_exploratory/source_native_reference_origin/PRESENTATION.json')
manifest=dict(schema='r132-exploratory-official-mf-input-v1',**flags,valid_frames=106,total_frames=107,evaluation_fps=24,evaluation_indices=list(range(106)),crop_xywh=[16,8,1280,720],full_videos=dict(zip(pres['columns'],pres['inputs'])),collection=bound(R/'incoming_exploratory/COLLECTION.json'),actual_runtime_gate=bound(R/'incoming_exploratory/REFERENCE_ORIGIN_RUNTIME_GATE.json'),actual_release=bound(R/'incoming_exploratory/ROOT_EXIT_RECEIPT.json'),review=bound(P/'REVIEW.json'),metric_scope='Official video score of actual generated frames; does not turn failed historical inference-input equality into a passed pairing gate.')
save(R/'prepared_exploratory/MF_INPUTS.json',manifest)
print(json.dumps({'review':bound(P/'REVIEW.json'),'mf_inputs':bound(R/'prepared_exploratory/MF_INPUTS.json'),'phase_errors':means}))
