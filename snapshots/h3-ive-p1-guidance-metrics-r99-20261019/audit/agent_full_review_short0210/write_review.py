from pathlib import Path
import json,hashlib,time
R=Path(__file__).resolve().parent
b=json.loads((R/'MEDIA_BINDINGS.json').read_text())
assert b['coverage']==list(range(87)) and sum((x['frames'] for x in b['pages']),[])==list(range(87))
rows=[
([0,17],'手掌从较高位置缓慢回收，头部从侧向转向镜头附近。','普通编辑与引导均保持对应手势进程；手指形状和面部表情有细节差异。'),
([18,39],'空手向外展开，掌面上翻并停留；持遥控器一手靠近躯干。','两版均按源片阶段展开和停留，未见明确少做一次手势。'),
([40,53],'空手向躯干回收并下降，两手逐渐靠近腰腹附近。','两版回收、下降阶段与源片对应，引导版与普通版很接近。'),
([54,71],'两手在较低位置保持，小幅面部和手部运动。','均保持该停留阶段；人物和舞台连续。'),
([72,86],'头部向另一侧转动，两手再次向外展开。','两版保留转头与展手顺序；未观察到可稳健界定的时序改善。')]
record={'schema':'r99-short0210-independent-full-frame-visual-review-v1','source_id':'short_0210','review_status':'任务完成，未见明确时序收益','reviewer':'r59_execution_preparation','created_unix':time.time(),'recommendation':'首组可继续后续匹配引导实验；本例计入中性结果','reviewed_frames':list(range(87)),'reviewed_time_seconds':[0,86/24],'frame_interval_seconds':1/24,'contact_pages_actually_viewed':b['pages'],'input_bindings':b['inputs'],'pair_gate_sha256':b['gate_sha256'],'collection_sha256':b['collection_sha256'],'basic_edit':{'ordinary':'男性替换成立；短发男性形象在全部有效帧保持。','guided':'男性替换成立，未见明显源女性身份回流。','scene_camera':'蓝色舞台幕布、白衣黑领结、手持遥控器、身体位置及镜头构图在两版保留。','structural_artifacts':'未见明显重复肢体、场景重生或引导新增的大范围重影；手部细节与原片并非逐像素一致。'},'motion_intervals':[{'frames_inclusive':a,'times_inclusive_seconds':[a[0]/24,a[1]/24],'source':s,'comparison':c} for a,s,c in rows],'temporal_result':'普通P1已大致保留主要手势的物理时间阶段；固定6..14引导与普通编辑近似，逐帧审阅未发现明确收益。','precision_limits':['审阅基于每一有效帧的同时间三栏图，单格从1280×720等比缩至480×270；不以此认定手指细节完全一致。','上述区间是完整动作段的描述，不作为精确事件边界GT或毫秒级测量。','源视频帧87..89为padding，排除评估；无重定时、补帧或插帧。','本复核未计算官方MF，不从肉眼结论推导量化分数。'],'method':{'ordinary_NFE':20,'ordinary_routes':0,'guided_NFE':20,'guided_routes':450,'guided_indices':list(range(6,15))},'scientific_classification':'neutral_already_close_in_timing'}
(R/'REVIEW.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
lines=['R99 short_0210 全有效帧独立复核','', '结论：两版男性替换和原舞台/镜头保留成立，可继续后续匹配实验。普通P1本已大致保留手势时间，固定时序引导未显示明确肉眼收益。本例记录为中性。','', '实际查看：frames0..86，共87帧，0.000..3.583秒，24fps；10页连续逐帧图全部看过。各图左源片、中普通P1、右固定steps6..14引导。','']
for a,s,c in rows:lines.append(f'{a[0]:03d}–{a[1]:03d} ({a[0]/24:.3f}–{a[1]/24:.3f}s)：{s} {c}')
lines+=['','男性短发、脸部和身体形象在两版贯穿全段；蓝色幕布、衣服领结、遥控器及原镜头构图连续。未见明显身份回流、重复肢体或新场景替代。面部表情、手指形状等局部细节存在差别。','阶段区间是描述性审核，不是精确事件GT；未给出毫秒差值。该次审核未运行MF。正式门、原媒体SHA、每页实际帧范围见MEDIA_BINDINGS.json与REVIEW.json。']
(R/'REPORT.txt').write_text('\n'.join(lines)+'\n')
print(hashlib.sha256((R/'REVIEW.json').read_bytes()).hexdigest())
