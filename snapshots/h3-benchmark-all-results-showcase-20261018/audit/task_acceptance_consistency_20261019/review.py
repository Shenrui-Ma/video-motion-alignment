from pathlib import Path
import json,hashlib,datetime
A=Path(__file__).parent;R=A.parents[1];B=R.parent

def bind(p):return {'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(p):return json.loads(p.read_text())
inv=[R/'inventory/flexiact.json',R/'inventory/ivebench.json'];items=[x for f in inv for x in read(f)['items']]
# Explicit adjudication from existing text only. Axes: edit, scene, action content, timing retained, guidance timing benefit.
# P/F/U do not constitute new video judgments. Unknown includes incomplete task acceptance and inapplicable guidance.
M={
'flex_r50_chest_auto':('FU UUF'.replace(' ',''),'身份替换明确失败；自动0次，逐帧等同Native。'),
'flex_r49_crouch_native':('UUFUU','既有六帧指明下蹲/手臂/构图变化，身份和场景未单独验收。'),
'flex_r49_fitness_native':('PUPUU','铠甲女性出现，大动作阶段保留；前段慢仅早期六帧描述。'),
'flex_r49_one_leg_native':('PPUUU','西装人物和目标汽车场景出现，下肢画外；动作完整性待确认。'),
'flex_r49_rotate_native':('PUPUU','铠甲人物与全身构图大体保持；未建立时差不等于全段同步验收。'),
'flex_r65_fitness_fixed':('UUUUU','当前引用结论是MF和姿态相关性数值；缺完整身份/场景验收，不能由MF推断。'),
'flex_r65_one_leg_fixed':('UUUUU','当前引用结论是姿态相关性数值和部分下肢出画，不能代替视觉任务验收。'),
'flex_r66_human2animal_1__movie_man_11':('FUFF F'.replace(' ',''),'长辫残留且撑起/低伏阶段与参考相反，基础身份和动作任务失败。'),
'flex_r66_human2animal_1__game_man_4':('FFPUF','已纠正：脸/长辫身份混合、目标白背景失败；大阶段接近，无清楚时序修复。'),
'flex_r66_fitness__game_man_4':('PFPPF','同目标补查确认短黑发/动漫面孔/服装替换，白背景却变山地。时序本来接近。'),
'flex_r66_one_leg__movie_man_11':('PPP PF'.replace(' ',''),'金发西装人物和树木路灯场景出现，举臂抬膝阶段接近；裁切限制细节。'),
'flex_r66_human2animal_3__movie_man_11':('UUPUF','既有六时刻只确认向倒立进展和几何差异，未独立验收目标身份或背景。'),
'flex_r66_human2animal_3__game_man_4':('FUFF F'.replace(' ',''),'目标角色不明显，动作倒序。'),
'flex_r66_human2animal_2__movie_man_11':('PPFUF','目标外观场景主导，但盘腿前屈改为俯撑/跪姿。'),
'flex_r66_human2animal_2__game_man_4':('FUPFF','角色未换，前屈延后；局部手势差不构成成功修复。'),
'flex_r72_fitness_prompt_control':('PPPUU','两Native机器人/黑背景及动作顺序成立，提示版本时序接近；没有时序引导。'),
'flex_r72_one_leg__movie_man_9_native':('UUUUU','清单仅记录写出成功，不代表视觉任务通过。'),
'flex_r74_chest__game_man_5_native':('UUUUU','清单仅记录写出成功，不代表视觉任务通过。'),
'flex_r85_one_leg__movie_man_9_fixed':('PPFFF','身份场景成功，但额外插入胸前合掌路径且举臂明显延后，不能只当恒定相位差。'),
'flex_r85_crouch__movie_man_5_fixed':('UFPPF','Native仅部分身份替换；fixed短发更接近，细脸不确定。两版白背景要求失败，时序近。'),
'flex_r85_rotate__game_girl_1_fixed':('PUPPF','主要目标女性铠甲外观和转身序列成立；灰/青背景部分匹配，不能报完整场景通过。'),
'r73_short_0252':('PPPFP','任务成立；局部抓面罩/举带阶段改善候选，全片时序准确仍未证实。'),
'r55_short_0210':('PFFUF','R54六帧：男性出现，站立演讲变异室坐姿，源手动作缺席；R55逐帧相同。'),
'r55_short_0230':('UUFUF','R54六帧：头巾出画、围裙多色，倾倒变搅拌；R55逐帧相同。'),
'r55_short_0263':('PFFUF','R54六帧：女孩出现，但坐姿阅读变站立/走动，书椅不见；R55逐帧相同。'),
'r55_short_0352':('UUFUF','R54六帧：女人出现，现代服装要求不明确；源指点缺席并新增字幕；R55逐帧相同。'),
'r55_short_0370':('PUPUF','R54六帧：白衣和持杯下放大阶段保留，稀疏图不能定可靠时差；R55逐帧相同。'),
'r63_short_0210':('UFFUF','原蓝幕站姿手势和场景改变，具体身份只据当前摘要不能判。'),
'r64_short_0092':('FFFUF','目标植物删除未完成，动作被手机特写替代。'),
'r64_short_0114':('UUFUF','球外观部分变化，手运球成脚边球/站立持球。'),
'r64_short_0126':('PUFUF','猫添加完成，原伸展动作变摸猫特写。'),
'r64_short_0392':('FUPUF','壁炉目标修改未清楚实现，手势大阶段保持。'),
'r69_short_0230':('UUFUF','构图近景使头巾改色无法确认，倾倒动作变碗勺特写。'),
'r69_short_0263':('PFFUF','女孩出现，吊椅和书以及阅读动作消失。'),
'r69_short_0352':('UUFUF','女人出现但衣着要求不符，原抬手动作未保持。'),
'r69_short_0370':('PUPUF','六时刻白衣和杯/头动作保持；不足以把全片同步判通过。'),
'r71_short_0210':('UUUUU','P0/P1提示对照必须分臂：P0场景动作失败，P1主要任务保持；不合并成一个引导结论。'),
'r73_short_0035':('PPPPF','70帧灯改红，手入镜/下降/打字阶段接近，未见引导收益。'),
'r73_short_0065':('PUPUF','六时刻大理石砧板与翻拌保持，未见引导收益；全段时间验收未知。'),
'r73_short_0135':('PPPUF','机械臂替换和运笔保持；接触边界不确定，不能以无清楚收益宣称时间准确。'),
'r73_short_0344':('PPP UF'.replace(' ',''),'六时刻红箱/手和场景保持；稀疏阶段不足以确认完整时间准确。'),
'r78_short_0370':('PPPUU','两Native提示诊断任务大阶段保持，没有引导。'),
'r80_short_0230':('PPPUU','六时刻头巾围裙蓝色/厨房/操作保持，引导未生成。'),
'r80_short_0352':('PPPUU','六时刻人物和场景/抬手保持，引导未生成。'),
'r89_short_0085':('PPPPF','全66帧红发和场景/杯下放/转头笑容接近，无收益。'),
'r89_short_0131':('PUPPF','43帧改白及抬手转身基本同相，场景独立验收摘要未明确。'),
'r89_short_0268':('PPPPF','97帧男孩替换、厨房保留，动作阶段接近。'),
'r89_short_0274':('PPPPF','全72帧外星人和水面/漂浮物/镜头，动作阶段保持，无收益。'),
'r89_short_0343':('PUPPF','61帧医生外观与手机动作阶段接近，场景独立验收摘要未明确。'),
'r96_long_0047':('PPPPU','全97帧女子和采访场景手势同步；未授权衣色变化另记，无引导。'),
'r89_short_0358':('PPPFU','全105帧加眼镜和饮酒保持；早段稍提前，末段延后仍在，整体改善不能判通过。'),
'r96_long_0123':('PPPPU','全144帧改红及操作序列同步；面团形状纹理变化另记，无引导。')}
assert set(M)=={x['id'] for x in items},(set(M)-{x['id'] for x in items},{x['id'] for x in items}-set(M))
axes=['edit_or_identity_completed','requested_scene_preserved','action_sequence_preserved','timing_visually_retained','guidance_temporal_improvement'];tr={'P':'pass','F':'fail','U':'unknown'}
extra=B/'h3-timing-ivebench-native-r54-20261017/analysis/postrun/mf_execution/fixed_native_review/ROOT_VISUAL_REVIEW.json'
rows=[]
for x in items:
 code,reason=M[x['id']];assert len(code)==5,(x['id'],code)
 eps=[Path(p) for p in x.get('evidence_paths',[]) if Path(p).is_file()]
 if x['id'].startswith('r55_'):eps.append(extra)
 if x['id']=='flex_r66_fitness__game_man_4':eps.append(R/'audit/flexiact_inventory/r66_human1_game4_task_recheck/SAME_TARGET_FITNESS_RECHECK.json')
 rows.append({'id':x['id'],'benchmark':x['benchmark'],'current_label':x['review_status'],'current_summary':x['review_summary'],'comparison_kind':x['comparison_kind'],'classification':dict(zip(axes,[tr[k] for k in code])),'reason':reason,'basis':'existing_review_text_only_no_new_video_inspection','evidence':[bind(p) for p in eps]})
priorities=[
{'rank':1,'ids':['r55_short_0210','r55_short_0230','r55_short_0263','r55_short_0352'],'issue':'当前卡片仅写自动0次，隐藏了R54对应输出已经记录的任务/动作失败。','recommended_wording':'自动0次；原动作/场景保持失败（按各例原六帧事实），任务颜色无法确认的记UNKNOWN。','evidence':bind(extra),'caution':'只继承各自R54视觉证据及精确输出相同证明；不把fresh R69结果移植到R55。'},
{'rank':2,'ids':['flex_r85_crouch__movie_man_5_fixed'],'issue':'无明显改善标签仅谈时间；原review明确Native身份只部分替换、两版目标白背景失败。','recommended_wording':'部分任务失败；固定版短发改善，时序原本接近。','caution':'fixed短发较像目标不能推成精细脸身份全通过。'},
{'rank':3,'ids':['flex_r66_fitness__game_man_4'],'issue':'身份确有成功证据，但目标图白背景明确变山地。','recommended_wording':'身份替换完成、场景要求失败；动作已近同步，引导无清楚时序收益。','caution':'这是场景要求失败，不应误改成身份失败。'},
{'rank':4,'ids':['flex_r85_one_leg__movie_man_9_fixed'],'issue':'明确新增胸前合掌路径，时序差和动作内容/路径错误并存。','recommended_wording':'身份/场景完成；动作路径及时间保持失败，引导未修复。','caution':'不能把源侧举到顶与生成胸前合掌后举手的差数当整个动作恒定延时。'},
{'rank':5,'ids':['flex_r66_human2animal_3__movie_man_11'],'issue':'现有报告仅论倒立阶段与几何/构图，缺目标身份和场景的显式验收。','recommended_wording':'任务身份/场景待确认；已审时刻未见清楚时序收益。','caution':'UNKNOWN，不能按相邻GameMan4失败外推本例失败。'}]
out={'schema':'task-acceptance-consistency-review-v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'input_inventories':[bind(p) for p in inv],'n_items':len(rows),'scope':'Read-only synthesis of existing review prose/evidence; no new models, GPU, video reinspection or changes to producer/inventories. Repeated identities/methods are not independent sources.','status_definitions':{'pass':'Existing visual evidence explicitly supports this axis at its recorded review coverage, not an unconditional full-video guarantee.','fail':'Existing visual evidence explicitly documents violation of this axis.','unknown':'Missing/ambiguous evidence, partial success, mixed arms or inapplicable intervention; never converted to pass.','guidance_temporal_improvement':'pass only where an improvement is explicitly observed, including clearly labelled local candidate. Zero activation has fail for benefit, not evidence of successful synchronization.'},'rows':rows,'priority_corrections':priorities,'already_corrected':['flex_r66_human2animal_1__game_man_4'],'additional_caveats':['R65 MF/pose values alone do not establish identity/scene success or exact visual lag.','R72 one_leg and R74 chest archived Native writing success is not task acceptance.','R71 and R78 are prompt-control variants; their third column is a different Native, not temporal guidance.','R89 glasses0358 has partial early gains with later delay; summarize both, not whole-video success.']}
(A/'REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
lines=['本次按已有审阅文字核对52项（Flex21，IVE31），没有新增视频审阅。每项分别登记编辑/身份、场景、动作内容、时间保持、引导收益；没有明确依据的字段留UNKNOWN。','优先纠正的5组：']
for p in priorities:lines.append(str(p['rank'])+'. '+','.join(p['ids'])+'：'+p['issue']+' 建议：'+p['recommended_wording'])
lines.extend(['当前没有证据把fitness/game_man_4归为身份替换失败；其失败项是实际prompt要求的白背景。','R55零触发是运行事实，与任务验收是不同维度；R54既有源相同的六帧失败证据可以通过已证明RGB/PTS相同关系继承。','全部精确证据路径和SHA已写REVIEW.json，未修改其他人清单。'])
(A/'REPORT.txt').write_text('\n'.join(lines)+'\n');print(bind(A/'REVIEW.json'))
