from pathlib import Path
import json,hashlib,html,csv,math
R=Path(__file__).resolve().parents[1]
# Source-only visual observations. All source times were chosen uniformly before inspection.
D={
'0131':('first','human_clothing','手势、转身、伸臂','两工人交谈；右侧工人先抬手到脸附近，随后转身并伸出双臂；左侧工人持续指向车内纸箱。','衣着实际为深色马甲与蓝袖；官方称black down jackets，原文保留，后续需明确改色区域。','R76 preregistered source'),
'0044':('secondary','held_object','步行、身体起伏','女子携瑜伽垫与水瓶行进，头和躯干随步伐起伏；持瓶手在六时刻中较稳定。','连续步行适合运动保持对照，短手势切换较少，腿部部分出画。',''),
'0353':('secondary','human_clothing','低头、抬头、再低头、转头','前景医生先低头，抬起头部后再俯身低头，最后转向右侧。','以头颈阶段为主，双手多数在画面外，手臂时序可测性较弱。',''),
'0268':('first','human_identity','抬掌、放下、前倾','右侧成人先抬起手掌，随后放低，再明显前倾；左侧人物转向她。','官方one of women未明确目标，左侧实际像儿童；建议后续明确绑定右侧成人，记录这一消歧。',''),
'0309':('defer','human_clothing','轻微头眼变化','女子主要改变眼神和轻微头部角度，六时刻没有可见手臂阶段切换。','原任务清楚，但当前动作检验价值低。',''),
'0220':('defer','human_identity','讲话与轻微头部变化','男子坐姿基本稳定，主要嘴部、表情与轻微头部运动。','六时刻未见可辨认的抬放手或躯干阶段。',''),
'0343':('first','human_identity','拿起手机、双手操作','镜前女子最初手部低于镜中胸口；后段手机和双手明显抬起到胸前并操作。','镜像与人物是同一主体；官方doctor属身份/职业改动，后续需保留原人物与镜中动作对应。',''),
'0394':('defer','human_identity','抬头与目光变化','男子先低头，后抬头看向一侧，肩膀变化有限。','头部单次变化，手臂不可见；不优先投入动作时序实验。',''),
'0395':('defer','human_clothing','眼神与表情变化','学生近景主要表情变化，身体姿态基本稳定。','六时刻未见非平凡手臂/躯体动作。',''),
'0085':('secondary','human_attribute','放低杯子、转头','女子开始双手持杯靠近胸口，随后逐步放低至画面下沿，并向一侧转头。','手臂仅局部可见；目标为头发改色。官方target额外描述暖色饱和度，须把edit_prompt限定为头发。',''),
'0167':('defer','human_clothing','主体站立、背景列车行驶','男子基本站定，后段列车进入画面。','主要运动来自背景车辆，不满足主体动作阶段优先条件。',''),
'0178':('secondary','human_clothing','手掌上下交替滑动','两手在腹部上方与下方交替滑移，起始双手相近，后分开再靠近。','仅腹部和手臂局部可见；白衬衫是敞开的，保留其实际遮挡关系。','R76 preregistered source'),
'0274':('first','human_identity','前倾、站直、转头','宇航员起始前倾，随后明显抬起躯干站直，再转向一侧。','后半主要头部变化，水下腿部不可见；alien替换应保留人形动作和原水面。',''),
'0021':('defer','human_identity','滑行与转向','多人持雪杖滑行下坡，前景滑雪者逐渐远离。','官方改为snowboarders，会主动要求器材和身体姿势变化，难把所有姿态变化当成非预期错位。',''),
'0185':('defer','animated_identity','周围角色抬手跳跃','中间站立角色有抬手和跳跃；被编辑的地面角色多数蜷伏不动。','官方目标是躺地角色，不能把其他角色的活跃动作当成该编辑主体动作。',''),
'0308':('defer','human_identity','轻微头部转动','铠甲武士近景中轻微低头/转头，背景火焰明显运动。','手臂不可见，主要图像变化是火焰。',''),
'0318':('defer','human_identity','低头、抬眼','窗后女子轻微低头与抬眼。','窗框遮挡身体；动作阶段幅度较小。',''),
'0122':('defer','human_clothing','主体略变姿态、镜头绕行','黑衣人物在尸堆上站立，明显变化来自镜头靠近绕行、烟雾和特效。','主体手臂/躯干阶段不清晰，镜头变化可能主导运动测量。',''),
'0161':('secondary','operated_object','旋钮操作、搅拌开始','男子一手按住杯盖、一手在旋钮，果块在后段开始明显翻动和碎化。','人物手臂变化小；果块从静止到搅动可作物体事件，苹果替换本身也可能改变碎化外观。',''),
'0039':('extension','animal_identity','啄地、抬头','海鸥起始低头啄湿沙，随后抬头并站立。','直接动物主体替换；人体姿态观察器不适用，需另列物种/事件评价。',''),
'0177':('extension','animal_identity','张嘴、最大张口、合嘴','老虎侧身卧着，嘴逐步大张，后段合嘴并降低头部。','直接动物主体替换；主体阶段清晰，但不能混算人体动作姿态指标。',''),
'0235':('extension','animal_attribute','前爪梳理、抬头、转头','海獭前爪位于头胸之间，低头梳理并交替抬头转向。','直接动物主体改色；毛色实际头浅身深，需明确官方white sea otter的整个主体。',''),
'0299':('defer','animal_identity','平稳游动','多只天鹅和鸭子在河面游动，部分低头，主要为缓慢位移。','目标多、遮挡多、阶段切换少，不优先。',''),
'0040':('extension','moving_object','入水、下沉、回浮','柠檬和青柠从画面上方入水，伴随气泡下沉，后段部分果实回浮。','移动物体改色，阶段清楚；原片首帧近乎空画面，任务检验需看全片。',''),
'0114':('first','held_object','左右运球、换手、跨步','篮球运动员左右手运球，球在两侧交替，身体伴随侧移与跨步。','前段头部出画；直接动作物体替换适配，但已有开发实验。','R64 previous development source'),
}
if __name__=='__main__':
 (R/'audit/INITIAL_25_VISUAL_REVIEW.json').write_text(json.dumps({'schema':'r82-initial-source-visual-review-v1','reviewed_source_count':len(D),'review_basis':'Six uniform actual source frames per full clip; phase descriptions are coarse screening, not exact event annotations. No generated output was consulted.','rows':[{'source_id':'short_'+k,'priority':v[0],'scope':v[1],'visible_phases':v[2],'observation':v[3],'limitations':v[4],'known_development':v[5]} for k,v in D.items()]},ensure_ascii=False,indent=2)+'\n')
