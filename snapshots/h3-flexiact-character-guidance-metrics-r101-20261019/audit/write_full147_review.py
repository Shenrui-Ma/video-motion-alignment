from pathlib import Path
import hashlib,json,time

R=Path(__file__).resolve().parents[1]
O=R/'audit/full147_review'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
b=read(O/'MEDIA_BINDINGS.json');g=read(R/'incoming/PAIR_RUNTIME_GATE.json')
assert b['coverage']==list(range(147)) and len(b['pages'])==25
for p in b['pages']:assert sha(p['file'])==p['sha256']
assert sha(R/'incoming/PAIR_RUNTIME_GATE.json')==b['gate_sha256']
assert g['passed'] and all(g['checks'].values())
j={
 'schema':'r101-full-valid-frame-visual-review-v1','source_id':g['source_id'],
 'reviewed_unix':time.time(),'reviewer':'Codex recover_r99_r101',
 'review_method':'Visual inspection of every row in 25 actual three-column contact sheets, all147 generated valid frames; source motion has49 unique8fps samples.',
 'coverage':list(range(147)),'pages_reviewed':[p['file'] for p in b['pages']],
 'binding':{'file':str(O/'MEDIA_BINDINGS.json'),'sha256':sha(O/'MEDIA_BINDINGS.json')},
 'gate':{'file':str(R/'incoming/PAIR_RUNTIME_GATE.json'),'sha256':sha(R/'incoming/PAIR_RUNTIME_GATE.json')},
 'event_plan':{'file':str(R/'audit/ROOT_EVENT_PLAN.json'),'sha256':sha(R/'audit/ROOT_EVENT_PLAN.json')},
 'edit_acceptance':{
  'native_identity':'PASS','guided_identity':'PASS','native_background':'PASS','guided_background':'PASS',
  'description':'两版均持续呈现目标图的短黑发动漫男子、绿斗篷、棕夹克及装备，背景保持白色。',
  'overall_motion_transfer':'PARTIAL',
  'remaining':'两版把源侧面视角改成三分之四视角，膝盖和胸口位置不同；末段屈肘降胸与参考伸臂拱背不一致。'
 },
 'events':[
  {'event':'低伏支撑阶段','source_review_frames':[36,57],'native_review_frames':[36,53],'guided_review_frames':[36,53],
   'finding':'三列都有低伏阶段。两个编辑结果接近，guide略改变头部角度。','timing_benefit':'NOT_RESOLVED'},
  {'event':'从低伏阶段抬头抬胸','source_transition_interval':[60,72],'native_transition_interval':[50,60],'guided_transition_interval':[50,60],
   'finding':'参考约60帧后头胸逐渐离地，66–72帧更清楚。两版约50–60帧已逐渐抬起，仍有提前趋势；引导版没有使此转折明显接近参考。',
   'interval_definition':'渐进转折的视觉不确定区间；侧视与三分之四视角及身体比例不同，禁止当成精确lag。','timing_benefit':'NO_CLEAR_GAIN'},
  {'event':'高位支撑之后低头','source_transition_interval':[105,117],'native_transition_interval':[96,108],'guided_transition_interval':[96,108],
   'finding':'两版都较早开始低头，变化相近。参考与生成的姿态、俯仰和头部裁切使精确事件点不确定。','timing_benefit':'NO_CLEAR_GAIN','exact_lag':'UNKNOWN'},
  {'event':'末段低头拱背','source_review_frames':[126,146],'native_review_frames':[126,146],'guided_review_frames':[126,146],
   'finding':'参考保持手臂较直并拱背，两版继续明显屈肘、胸口下沉；该动作形态差异在引导版中仍存在。','timing_benefit':'NOT_RESOLVED','pose_fidelity':'PARTIAL'}
 ],
 'quality':{
  'hands_ground_contact':'两版手掌在全部有效帧保持撑地；接触点的精确三维位置未量化。',
  'head_clipping':'两版约75–95帧头顶出画，邻近帧存在少量顶部裁切。',
  'limb_duplication':'在审阅的有效帧中未见明显重复手臂；细小手指形变未逐像素标注。'
 },
 'conclusion':'角色与目标背景在两版中均成功；固定6–14步引导与普通编辑动作接近，提前转折和末段姿态差异仍存在，本例没有明确时序改善。',
 'support_class':'TASK_IDENTITY_PASS_MOTION_PARTIAL_NO_CLEAR_TIMING_GAIN',
 'clear_temporal_support':False,'automatic_method_test':False,'count_as_complete_task_success':False,
 'method':{'type':'fixed temporal routing','sampler_steps_zero_based':[6,14],'alpha':1,'routed_blocks':450,'NFE':20},
 'runtime':{'job_wall_seconds':g['runs']['forced']['job_wall_seconds'],'capture_seconds':g['runs']['forced']['capture_seconds'],'service_released':True},
 'official_FlexiAct_MF':'Pending independent matching guided tracking; source and native have prior verified scores.',
 'source_motion_time_precision_seconds':0.125,'browser_playback_review':False
}
(O/'REVIEW.json').write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
(O/'REPORT.txt').write_text(j['conclusion']+'\n\n'+'\n'.join(x['event']+'：'+x['finding'] for x in j['events'])+'\n\n147有效帧已逐行看完；原视频49帧/8fps，事件区间按0.125秒原始精度解释。\n')
print(json.dumps({'review':str(O/'REVIEW.json'),'sha256':sha(O/'REVIEW.json')},ensure_ascii=False))
