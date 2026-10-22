from pathlib import Path
from fractions import Fraction
import hashlib, json, math, time

R=Path(__file__).resolve().parent
H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
J=lambda p:json.loads(Path(p).read_text())
draft=J(R/'INPUT_PLAN_DRAFT.json')
inventory=R.parent/'h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json'
used={x['source_id'] for x in J(inventory)['items']}
planned={'long_0059','long_0163','long_0081'}
notes={
 'short_0116':('DEFER_LOW_DISCRETE_MOTION','持杯近乎静止，未见明确手臂动作阶段。'),
 'short_0161':('DEFER_WEAK_HAND_EVENT','双手基本停留在搅拌机按钮和杯盖处；主要变化为食材搅动，编辑目标会改变该运动外观。'),
 'short_0362':('SELECT','书页在末段向下落，书和手部可见；动作阶段较少，保留这一限制。'),
 'short_0220':('DEFER_TALKING_HEAD','正面交谈，手部出画，缺少清楚的离散手部事件。'),
 'short_0309':('DEFER_TALKING_HEAD','主要是眨眼与头部轻转，手部出画。'),
 'short_0394':('DEFER_TALKING_HEAD','片段较短，主要是转头，手部出画。'),
 'short_0395':('DEFER_TALKING_HEAD','主要是头部与眼睛的小幅变化，手部出画。'),
 'short_0068':('RESERVE_GEOMETRY','工具持续加工吊坠，接触状态变化不明显；缩放目标会直接影响物体几何。'),
 'short_0167':('DEFER_BACKGROUND_MOTION','人物相对静止，主要运动来自背景列车。'),
 'short_0177':('RESERVE_ANIMAL','虎张嘴后闭嘴的阶段清楚，暂存动物动作候选。'),
 'short_0235':('RESERVE_ANIMAL','水獭手爪揉动和转头较多，毛发遮挡手爪，暂存动物动作候选。'),
 'short_0120':('DEFER_LOW_DISCRETE_MOTION','遥控器相对静止，指脸手势持续，阶段边界较弱。'),
}
events={
 'short_0362':[
  ('头部向下转动',[23,40]),('抬起的书页向下落至较低位置',[55,60]),
 ],
 'long_0031':[
  ('刀刃下行切入甜椒',[24,66]),('切片分离并倒向砧板',[71,81]),('刀刃抬起至甜椒上方',[95,104]),
 ],
 'long_0091':[
  ('持续敲键',[421,487]),('双手从键盘区域抬起',[487,497]),('双手移出画面',[516,525]),
 ],
 'long_0161':[
  ('男子双手离开腿部并移向身后',[28,43]),('躯干完成后仰',[47,62]),('男子转头看向女子',[62,71]),
 ],
}
limits={
 'short_0362':'书页落下和头部转动可测；此片只有少量事件，不能预先称为动作密集样本。',
 'long_0031':'以刀刃和甜椒切片为动作标志；本任务编辑接触表面材质，需确认手、刀、食材和构图保留。',
 'long_0091':'抬手及离开画面可测；逐键按压受景深和运动模糊影响。戒指是否位于右小指需成片验收，遮挡时记录无法判断。',
 'long_0161':'男子换为儿童会改变身体比例；保留动作顺序和发生时刻，女子和公园场景需保持。',
}
selected=[]
for row in draft['pairs']:
 sid=row['source_id'];assert sid not in used|planned
 assert H(row['source']['file'])==row['source']['sha256']
 assert H(row['metadata_evidence']['path'])==row['metadata_evidence']['sha256']
 assert row['edit_prompt']==row['official_task']['edit_prompt']
 assert H(row['source_review']['path'])==row['source_review']['sha256']
 clip=row['clip'];protocol=row['input_protocol'];start=clip['start_frame'];end=clip['end_frame_inclusive']
 duration=Fraction(clip['duration_rational']);assert protocol['effective_frame_count']==math.ceil(duration*24)
 assert protocol['h3_frame_count']==5+17*math.ceil((protocol['effective_frame_count']-5)/17)
 assert len(protocol['input_to_original_frame'])==protocol['h3_frame_count']
 assert all(start<=i<=end for i in protocol['input_to_original_frame'])
 assert protocol['input_to_original_frame']==sorted(protocol['input_to_original_frame'])
 assert protocol['h3_frame_count']==(73 if sid=='short_0362' else 107)
 pts=row['source']['actual_pts_s'];start_s=float(Fraction(clip['start_pts_rational']))
 event_rows=[]
 for name,(lo,hi) in events[sid]:
  assert start<=lo<=hi<=end
  event_rows.append({'name':name,'original_frame_bracket':[lo,hi],
    'original_pts_bracket_s':[pts[lo],pts[hi]],
    'excerpt_relative_bracket_s':[pts[lo]-start_s,pts[hi]-start_s],
    'precision':'coarse bracket from 24-frame source contact sheet; refine from complete source frames before event scoring'})
 selected.append({'source_id':sid,'official_edit_prompt':row['edit_prompt'],'source':row['source']['file'],
   'source_sha256':row['source']['sha256'],'reference_image_used':False,'clip':clip,
   'evaluation_scope':row['evaluation_scope'],'source_review':row['source_review'],
   'events':event_rows,'acceptance_caveat':limits[sid],
   'valid_frames':protocol['effective_frame_count'],'total_frames':protocol['h3_frame_count']})
screen=J(R/'CANDIDATES.json')
decisions=[]
for row in screen['candidates']:
 sid=row['source_id'];decision,reason=notes[sid]
 decisions.append({'source_id':sid,'decision':decision,'reason':reason,
  'source_path':row['source_path'],'source_sha256':row['source_sha256'],
  'duration_s':row['estimated_duration_s'],'official_edit_prompt':row['metadata']['edit_prompt'],
  'contact_path':row['contact_path'],'contact_sha256':row['contact_sha256'],
  'viewed_frame_indices':row['viewed_frame_indices']})
output={'schema':'r122-source-only-selection-v1','created_unix':time.time(),
 'status':'SOURCE_PLAN_ONLY_PROMPT_FORMAT_PENDING','new_GPU_tasks_started':0,
 'inventory_binding':{'file':str(inventory),'sha256':H(inventory)},
 'current_pending_sources':sorted(planned),'initial_short_screen':decisions,'selected':selected,
 'selection_basis':'Only original video content, official edit target, visibility and distinct action phases. No generated results from these four sources exist in the inventory.',
 'sampling_protocol':'Use original frame timestamps; nearest source frame to each 24fps target timestamp, earlier frame on ties; pad last source frame to 17k+5. Compare only effective frames.',
 'previous_6s_plan':{'file':str(R/'INPUT_PLAN_DRAFT_6s.json'),'sha256':H(R/'INPUT_PLAN_DRAFT_6s.json')},
 'current_input_plan':{'file':str(R/'INPUT_PLAN_DRAFT.json'),'sha256':H(R/'INPUT_PLAN_DRAFT.json')},
 'proposed_execution':{'run_number':'R122','prompt_status':'Keep exact benchmark edit_prompt in metadata; defer actual H3 input prompt until official task-marker and reference-format review completes.',
  'numeric_reuse':'Reuse sealed R120 attention operator, fixed denoising steps6..14, seed, sampler, sigmas, quantization and geometry after parent review; only source inputs, frame counts and task binding change.',
  'review_sequence':['Run ordinary editing for each admitted source.', 'Inspect all effective source and output frames for requested edit, preserved actors/scene and action comparability.', 'If the task is comparable and a visible timing discrepancy exists, run same-prompt fixed temporal guidance.', 'Archive ordinary-only failures and already-aligned cases with the actual reason. Preserve all tested sources in the denominator.', 'Review paired outputs on identical physical timestamps and run official MF on the valid domain.'],
  'GPU_admission':'No batch or GPU job created by this selection plan.'}}
for name,obj in [('SOURCE_SELECTION_REVIEW.json',output),('SOURCE_SELECTION_VERIFIED.json',{'input_plan_sha256':H(R/'INPUT_PLAN_DRAFT.json'),'all4_unseen':True,'official_prompts_exact':True,'media_and_metadata_hashes_verified':True,'frame_mapping_checks':True,'expected_total_frames':[73,107,107,107]})]:
 (R/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'review':str(R/'SOURCE_SELECTION_REVIEW.json'),'sha256':H(R/'SOURCE_SELECTION_REVIEW.json'),'input_plan_sha256':H(R/'INPUT_PLAN_DRAFT.json')},ensure_ascii=False))
