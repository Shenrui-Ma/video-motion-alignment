from pathlib import Path
import json,hashlib,time
O=Path(__file__).parent;R=Path('/Users/researcher/DevProjects');old=R/'h3-timing-ive-event-candidates-r93-20261018'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
inputs={x['source_id']:x for n in ('SOURCE_INPUTS.json','SOURCE_INPUTS_MORE.json') for x in json.loads((O/n).read_text())}
ip={x['source_id']:x for x in json.loads((old/'design/INPUT_PLAN.json').read_text())['pairs']}
ep={x['source_id']:x for x in json.loads((old/'design/REFERENCE_EVENT_REVIEW_PLAN.json').read_text())['items']}
specs=[
('long_0081','将乳白色酱汁替换为辣红酱。','R93_PREPARED_REUSE',None,'戴手套的手将已沾酱鸡翅从小碗附近提起，悬停并转动。','首帧已沾酱，不标注蘸入开始；手指部分被食物遮挡，测食物轮廓和腕部。'),
('long_0059','在男子手中加一块白手帕。','R93_PREPARED_REUSE',None,'男子抬手接近眼角、擦拭、放下手。','手帕会遮住接触点，比较手/布整体到达眼部和离开脸部，避免要求原手指接触外形。'),
('long_0163','将浅蓝色上衣改为黑色。','R93_PREPARED_REUSE',None,'前景男子低头看文件，再抬头并把文件递回。','官方称 suit，源片可见衬衫领带；保留官方原文。笔记本遮住中段手部，量化抬头与最后递纸，接收文件动作在该片段之前。'),
('long_0031','将木砧板替换为大理石砧板。','NEW_PLAN_ONLY',[0,150],'刀向下切入黄椒、首块侧片分离落到砧板、手转动黄椒并抬刀准备下一刀。','首帧刀已靠在椒顶；不标注从无接触到接触的开始。首片分离与刀回升可测；板面换材质时需保留食物数量、接触关系与镜头。'),
('long_0091','在右手小指上添加金戒指。','NEW_PLAN_ONLY',[0,150],'双手从画外进入打字机键盘，清晰一侧手指按下、抬起并持续交替敲击。','前景手浅景深，单个按键接触常遮挡；先评入画与清晰手指抬落阶段，不给全部击键标精确时刻。右手小指戒指属于较难验收，优先级第五。')]
selected=[]
for rank,(s,tr,status,clip,action,risk) in enumerate(specs,1):
 x=inputs[s];entry={'rank':rank,'source_id':s,'official_task':x['official_task'],'task_translation':tr,'reference_image_used':False,'reference_image_basis':'Official IVE task record supplies source video and text edit request; no target reference image field.','source_file':{'path':x['path'],'sha256':x['sha256'],'frames':x['frames'],'fps':x['fps'],'full_duration_s':x['duration']},'source_visual_review':{'whole_source_contact':x['contact'],'whole_source_contact_sha256':sha(x['contact']),'viewed_original_indices':x['review_indices'],'observed_actions':action,'visibility_limits':risk},'preparation_status':status,'generated_results_consulted':0,'started_gpu':False}
 if s in ip:
  p=ip[s];assert p['source']['sha256']==x['sha256']
  entry['selected_clip']=p['clip'];entry['prepared_input_protocol']=p['input_protocol'];entry['evaluation_scope']=p['evaluation_scope'];entry['source_event_plan']=ep[s];entry['reuse_existing_project']=str(old)
 else:
  entry['selected_clip']={'start_frame':clip[0],'end_frame_exclusive':clip[1],'start_s':0,'end_exclusive_s':6,'original_fps':'25/1','selection_basis':'Source-only inspection before generation; first six seconds contain multiple visible transitions.'}
  entry['evaluation_scope']='IVEBench source-derived six-second exploratory clip; not official full-video benchmark score'
  entry['proposed_conversion']={'target_fps':24,'target_times':'0+j/24 for j=0,...,143','nearest_original_frame':'Choose nearest original PTS among frames0..149; tie goes to earlier frame. Preserve exact original-to-target map.','valid_frames':144,'legal_h3_total_frames':158,'padding':'Repeat last valid frame for legal H3 length; exclude terminal padding in metrics and review.','geometry':'Use existing R93 geometry policy if later authorized; no media preprocessing applied now.'}
  entry['source_visual_review']['window_review_indices']=list(range(0,150,5))+[149]
  entry['source_visual_review']['window_contacts']=[{'path':str(O/f'{s}_window_{i:02d}.jpg'),'sha256':sha(O/f'{s}_window_{i:02d}.jpg')} for i in (0,12,24)]
  entry['source_event_plan']={'precision':'Coarse source-only brackets at 5-original-frame review spacing; refine source boundaries before comparing any generated outputs.','original_frame_brackets':({'first_piece_separates':[65,80],'knife_resets_up_and_pepper_turns':[85,105],'next_cut_begins':[110,140]} if s=='long_0031' else {'hands_enter_keyboard':[5,15],'focused_finger_first_down_phase':[15,25],'focused_finger_lift_phase':[25,40]})}
 selected.append(entry)
reject={'short_0116':'持杯基本静止，无清楚多个手部阶段。','short_0161':'明显变化主要在杯内食物搅拌，手在按钮和杯盖上变化很小。','short_0182':'装箱动作清楚，但编辑桌旁散落标签与主体动作耦合低，作为后备。','long_0035':'前段拿走耳机与移除耳机任务发生直接语义冲突，且视频较长。','short_0362':'翻页与头部变化可见但阶段较少，作为后备。','short_0395':'主要头脸表情变化，手部不在画面内。','short_0120':'遥控器目标基本静止，女子指点动作变化较少。','short_0220':'主要谈话表情，手部动作少。','short_0309':'主要谈话表情与轻微头部运动。','short_0235':'海獭梳理可测，但现阶段优先人手操作，保留动物泛化候选。'}
res={'schema':'source-only-five-candidates-v1','created_unix':time.time(),'status':'PLAN_ONLY_NO_QUEUE_MUTATION','selection_scope':'Previously downloaded official IVE sources; no generated result used. All five source IDs absent from current IVE inventory.','selected':selected,'other_inspected_candidates':reject,'inventory_binding':{'path':str(R/'h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json'),'sha256':sha(R/'h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json')},'metadata_binding':{'path':str(R/'h3-ivebench-next-candidates-20261018/metadata/ivebenchdb_prompt_long.json'),'sha256':sha(R/'h3-ivebench-next-candidates-20261018/metadata/ivebenchdb_prompt_long.json')},'existing_r93_bindings':{str(p):sha(p) for p in [old/'configs/runtime.json',old/'design/INPUT_PLAN.json',old/'design/REFERENCE_EVENT_REVIEW_PLAN.json']},'r93_actual_remote_status':{'observed_unix':1792403898,'host':'H3_SERVER_A','path':'/data5/researcher/h3_runs/timing_ive_event_candidates_r93_20261018','root_exists':True,'log_files':[],'output_mp4_count':0},'new_candidate_run_evidence':'No matching generated outputs or graph configs found locally for long0031/long0091; candidate evidence limited to known project inventory and files. R93 three pre-existing graph configs have not launched.'}
(O/'FIVE_SOURCE_PLAN.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n')
lines=['五条待运行来源：源视频选材计划','']
for x in selected:
 c=x['selected_clip'];start=c.get('start_pts_rational',c.get('start_s'));end=c.get('end_exclusive_rational',c.get('end_exclusive_s'))
 lines.extend([f"{x['rank']}. {x['source_id']}：{x['task_translation']}",x['official_task']['edit_prompt'],f"原片 {x['source_file']['full_duration_s']:.3f}s；选段 [{start}, {end}) 秒；{x['preparation_status']}；无参考图。",x['source_visual_review']['observed_actions'],x['source_visual_review']['visibility_limits'],f"源文件：{x['source_file']['path']}",f"SHA256：{x['source_file']['sha256']}",''])
lines.extend(['R93 三条沿用其封存准备。新两条仅提出连续 0–6 秒片段，尚未生成新输入、模型图或 GPU 任务。四条六秒片段作为来源片段实验报告；long0081 使用完整官方视频。事件边界当前为源片审阅粗区间。'])
(O/'FIVE_SOURCE_PLAN.txt').write_text('\n'.join(lines)+'\n')
print(str(O/'FIVE_SOURCE_PLAN.json'));print(sha(O/'FIVE_SOURCE_PLAN.json'))
