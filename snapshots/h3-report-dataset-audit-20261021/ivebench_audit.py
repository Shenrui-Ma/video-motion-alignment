import json,csv,hashlib,collections
from pathlib import Path
ROOT=Path('/Users/researcher/DevProjects/h3-report-dataset-audit-20261021')
SRC=Path('/Users/researcher/DevProjects/h3-ivebench-next-candidates-20261018/metadata')
rows=[]
for split in ('short','long'):
 for x in json.loads((SRC/f'ivebenchdb_prompt_{split}.json').read_text()):
  rows.append(dict(x,split=split,key=Path(x['src_video_name']).stem))
M={}
def add(status,split,lines):
 for line in lines.strip().splitlines():
  n,reason=line.split('|',1); key=f'{split}_{int(n):04d}'; assert key not in M,key; M[key]={'status':status,'reason_zh':reason}
add('core_human','short','''
35|手部打字；改变键盘灯光颜色，保留手指动作。
44|女子行走；替换手持水瓶，保留行走与持物动作。
65|厨师搅拌沙拉；替换操作台上的砧板，保留备餐动作。
114|人物运球；替换为霓虹篮球，保留人物与球的运动。
120|人物指向电视；移除另一人物手中遥控器，保留人物动作。
131|工人装卸箱子；改变外套颜色，保留装卸动作。
161|人物操作搅拌机；替换正在处理的水果，保留操作动作。
210|女子演讲并打手势；替换为男子。
220|男子交谈；替换为人形圣诞精灵。
230|女子准备食物；头巾和围裙改色。
252|男子示范氧气面罩；替换为年长女子。
263|女子读书；替换为女孩，具体可测动作需查看原视频。
268|两名女子交谈；替换其中一人为男孩。
309|女子交谈；上衣由白改黑。
330|男子交谈；移除外层西装，保留人物动作。
344|手抚摸行李箱；行李箱由黑改红。
352|男子用手势交谈；替换为现代着装女子。
353|医务人员进行手术；手术服改色。
358|男子饮酒；添加眼镜。
362|女子读书、男子交谈；所读书本改色，具体可测动作需查看原视频。
370|男子从杯中饮用；衣服改色。
395|男子交谈；校服由黑改白。
''')
add('core_human','long','''
31|手切甜椒；替换砧板材质，保留切菜动作。
34|手切黄瓜；在食材下添加砧板，保留切菜动作。
35|DJ操作唱机；移除头戴耳机，保留表演动作。
39|女子办公和读书；书本改蓝色。
40|人物使用手机；手持手机换成书本，需视觉确认交互动作与物体兼容。
47|男子对麦克风讲话；替换为女子。
59|男子擦眼睛；手中添加白手帕。
60|男子吸烟；移除香烟，保留手部轨迹。
81|手将鸡翅蘸酱；更换酱料颜色和类型。
91|手用打字机；给右小指添加金戒指。
123|揉面并将面团放进容器；面团改色。
143|人物用雪块搭冰屋；雪块替换冰块。
161|男女交谈；男子替换为儿童。
162|两人行走；移除其中一人手中冰淇淋。
163|人物交接文件；蓝色西装改黑色。
166|人形超级英雄参与讨论；替换为蓝色服装超人。
167|人形动画角色使用工具和互动；衣服改色。
174|男女挽手行走；女子服装改色。
''')
add('core_nonhuman','short','''
39|海鸥啄食；替换为鹈鹕。
40|柠檬掉入水中；柠檬改红色。
115|树叶随水漂浮；叶片改白色。
135|人体手部绘画替换机械臂；保留轨迹，目标属于非人体机械结构。
166|犬在采摘者身旁移动；犬替换猫。
177|老虎打哈欠；替换为狮子。
235|水獭在水中梳理；毛色改绿。
242|奇幻生物漂浮；替换为友善的精灵生物。
299|天鹅游泳；替换为火烈鸟。
''')
add('core_nonhuman','long','''
62|巧克力融化滴落；黑巧克力改为白色。
63|车辆穿过路口；汽车替换自行车，保留路径与时间。
122|金刚鹦鹉梳理羽毛；替换为巨嘴鸟。
''')
add('pending_human','short','''
84|男子持枪指向头部；角色替换允许保留运动，但源描述只有持物和表情，动作变化需查原片。
85|女子持杯微笑；改变头发颜色，源描述未交代动态过程。
116|女子持杯；移除纹身，源描述未交代动态过程。
122|战士站立；服装改色，源描述未交代动态过程。
167|男子等车；外套改色，明确运动来自列车，人物运动需查原片。
178|孕妇双手托腹；上衣改色，是否发生手部动作需查原片。
185|替换躺地角色为泰迪熊；原描述中舞蹈属于其他角色，待替换角色运动未说明。
274|宇航员站在水中；替换外星人，原主体运动未说明。
308|战士站立；替换巫师，原主体运动未说明。
318|女子望向窗外；替换年长女子，动态过程未说明。
343|女子看手机；替换医生，是否有明确操作动作需查原片。
394|男子站立望向一侧；替换女子，动态过程未说明。
''')
add('pending_human','long','''
151|学生专注于课堂；移除眼镜，具体动作未说明。
173|女孩开盒子，女子旁观；被替换的旁观者是否有可测动作需查原片。
181|男子躺在床上；头发改色，动态过程未说明。
''')
add('pending_nonhuman','short','''
28|将停在人物身旁的SUV替换骆驼；原车辆运动未说明。
69|蔬菜展示与撒盐；被替换的洋葱自身运动未说明。
121|排列的水果；苹果换猕猴桃，运动未说明。
139|高科技座椅改色；椅子和体验者的具体运动未说明。
300|咖啡豆特写改色；运动未说明。
''')
add('motion_semantics_conflict','short','''
21|双板滑雪者换成单板滑雪者，运动技术和肢体关系随任务改变；不纳入严格保留动作测试。
43|将快艇激起的浪花改为平静水面，编辑直接改变原运动现象。
''')
add('motion_semantics_conflict','long','''
88|将正在饮用的杯子替换书本，原饮用动作与目标物体用途冲突。
''')
add('geometry_human','short','''
46|手部打字；缩放手和电脑，需空间归一化后评估时序。
68|手雕刻玉石；放大玉石，需控制手物接触和尺度。
96|人物写白板；缩小人物，需空间归一化。
129|女子行走；改变人物画面位置，需空间配准。
132|多只手聚拢；放大手部，需空间归一化。
163|人物指向电脑；改变人物相对位置，需空间配准与交互检查。
184|人物操作手机；移位手机，需检查手物关系。
271|学生讨论；移位持本学生，需空间配准。
319|人物交谈；改变另一人物位置，需空间配准。
320|女子交谈；缩小人物，需空间归一化。
354|人物解释并打手势；放大人物，需空间归一化。
365|女子对麦克风讲话；人物移位，需空间配准。
367|人物互动；放大人物，需空间归一化。
372|男子交谈；缩小人物，需空间归一化。
396|女子交谈；指令是放大女子，官方标签却为camera_angle_editing，按实际指令归为缩放。
''')
add('geometry_human','long','''
27|人物攀岩；改变人物画面位置，需空间配准。
57|男子打电话；缩小眼镜，保留动作。
95|女子涂口红；缩小人物，需空间归一化。
116|男子俯卧撑；人物移位，需空间配准。
118|人物骑摩托；放大骑手与摩托，需空间归一化。
157|女子交谈；缩小人物，需空间归一化。
172|人物交谈；女子移位，需空间配准。
188|男女交谈；放大两人，需空间归一化。
190|男女交谈；女子移位，需空间配准。
191|男子打手势；人物移位，需空间配准。
''')
add('geometry_nonhuman','short','''
189|机械臂运动；放大机械臂，需空间归一化。
''')
add('geometry_human','short','''
243|人形女巫乘扫帚飞行；改变人物位置，需空间配准。
''')
add('geometry_nonhuman','long','''
20|帆船航行；放大船只，需空间归一化。
30|变色龙眼睛缓慢移动；缩放头部，指令前后关于显著程度矛盾，需核查。
70|蜘蛛缠绕猎物；放大蜘蛛，需空间归一化。
125|企鹅行走；缩小企鹅，需空间归一化。
''')
add('geometry_pending','short','''
41|人物持相机；整体移位，人物动态过程未说明。
108|眼睛特写；放大眼睛，动态过程未说明。
173|老人沉思；放大人物，动态过程未说明。
241|人形幽灵坐着持地图；缩放，主体动态过程未说明。
267|人物持树叶；缩放，动态过程未说明。
283|男子站立沉思；缩放，动态过程未说明。
284|女孩坐着仰望；移位，动态过程未说明。
''')
add('geometry_pending','long','''
65|双手交握；改变深度位置，动态过程未说明。
80|烤肠在火上；放大烤肠，烤肠自身运动未说明。
139|人物盘坐，烟雾弹爆炸；移位人物，人物运动未说明。
''')
add('geometry_interaction_conflict','short','''
346|人物正用腿上笔记本电脑；把电脑移至床头柜，会改变原手物接触关系。
''')
add('effect_human','short','''
130|人物摆放姜饼屋；添加烟雾装饰，需检查遮挡影响。
164|神职人员行走；添加圣光。
257|手锉宝石；工具添加火焰特效。
324|男子使用手机；手机添加闪电。
''')
add('effect_nonhuman','long','''
44|猫环顾并跳下；添加闪电特效。
49|人形机器人踏上箱子；添加火焰特效。
''')
add('effect_pending','short','''
325|人物佩戴面具；面具添加闪电，原主体动态过程未说明。
357|人物站立；添加能量盾，原主体动态过程未说明。
368|男子沉思；添加火焰，原主体动态过程未说明。
''')
add('effect_pending','long','''
170|老人持杯沉思；杯子添加烟雾，原主体动态过程未说明。
178|男子说话；笔记本电脑添加护盾，编辑目标为静态配件。
''')
add('natural_dynamics_extension','short','''
15|海浪拍岸改色；自然场景动力学，不纳入可分辨人物/动物/物体主体的核心统计。
51|火焰燃烧改色；自然现象运动，不纳入实体主体核心统计。
253|熔岩流动改色；自然场景动力学，不纳入实体主体核心统计。
''')
# Specific replacements and removals with an explicitly background/supporting target.
# Remaining subject additions/removals are retained in the audit, outside the current core subject-editing scope.
for r in rows:
 key=r['key']; c=r['category']; sub=r['subcategory']; e=r['edit_prompt']
 if key in M: r.update(M[key])
 elif c in ('style_editing','style editing'):
  r.update(status='global_style_or_weather',reason_zh='全局风格或天气编辑，单列为扩展任务；本次主体编辑核心计数排除。')
 elif c=='subject_motion_editing':
  r.update(status='explicit_motion_change',reason_zh='编辑指令明确要求改变动作或运动状态，不以保持原动作时间为目标。')
 elif c in ('camera_motion_editing','camera_angle_editing'):
  r.update(status='camera_change',reason_zh='改变相机运动或视角，属于当前主体运动保留测试以外任务。')
 elif c=='quantity_modification':
  r.update(status='quantity_change',reason_zh='增加/减少主体或物体数量，需要重新建立主体对应，单列扩展任务。')
 elif c=='effect_editing':
  st='background_only' if key=='short_0186' else 'event_or_transition_change'
  r.update(status=st,reason_zh='仅改变背景特效。' if st=='background_only' else '事件特效或转场改变原视频事件/连续性，排除严格动作时间保持测试。')
 elif c=='subject_editing':
  if sub=='add new subject':r.update(status='unrelated_subject_addition',reason_zh='新增场景物件或额外主体，未编辑原运动主体或其佩戴/交互对象。')
  elif sub=='remove existing subject':
   actor_keys={'short_0047','short_0128','short_0175','short_0193','short_0209','short_0233','short_0278','short_0307','short_0315','short_0345','short_0351','short_0364','short_0375','long_0087'}
   r.update(status='remove_subject' if key in actor_keys else 'background_only',reason_zh='删除已有运动主体/互动参与者，目标对应关系发生变化。' if key in actor_keys else '删除背景或场景陈设，未编辑原运动主体。')
  else:r.update(status='background_only',reason_zh='替换背景、家具或静态场景陈设，未直接编辑运动主体或其手持/操作对象。')
 elif c=='attribute_editing':
  st='global_style_or_weather' if key in {'long_0018','long_0029'} else 'background_only'
  r.update(status=st,reason_zh='整幅画面色调改变，单列全局外观扩展。' if st=='global_style_or_weather' else '仅改变背景、静态场景陈设或环境颜色，不纳入核心主体编辑统计。')
 else:raise ValueError((key,c))
 if r['status'] in ('core_human','core_nonhuman'):
  speech_only={'short_0220','short_0268','short_0309','short_0330','short_0395','long_0047','long_0161','long_0166'}
  unspecified_activity={'short_0161','short_0230','short_0252','short_0263','short_0353','short_0362','long_0035','long_0039','long_0040','long_0167'}
  r['source_motion_evidence']='speech_without_explicit_limb_action' if key in speech_only else 'activity_without_detailed_movement' if key in unspecified_activity else 'explicit_limb_or_object_motion'
 else: r['source_motion_evidence']='not_counted_in_core'
 r['human_candidate']=r['status']=='core_human'
 r['subject_candidate']=r['status'] in ('core_human','core_nonhuman')
 r['review_basis']='official_source_and_edit_text'
 r['video_visual_review_for_this_audit']=False
 r['generated_result_used_for_selection']=False
assert all(k in {r['key'] for r in rows} for k in M)
assert len(rows)==len({r['src_video_name'] for r in rows})==600
mapping={x['order_name']:x for x in csv.DictReader((SRC/'ivebenchdb_name_mapping.csv').open())}
for r in rows:
 d=mapping[r['key']]; r['original_source_name']=d['source_name']; r['original_url']=d['url']

def count(rs):
 return {'tasks':len(rs),'source_clips':len({r['src_video_name'] for r in rs}),'original_source_names':len({r['original_source_name'] for r in rs}),'original_urls':len({r['original_url'] for r in rs})}
counts={s:count([r for r in rows if r['status']==s]) for s in sorted({r['status'] for r in rows})}
summary={
 'dataset':'IVEBench','audit_date':'2026-10-21','official_sources':['https://github.com/RyanChenYN/IVEBench','https://ryanchenyn.github.io/projects/IVEBench/','https://huggingface.co/datasets/Coraxor/IVEBench'],
 'metadata_coverage':{'short_tasks':400,'long_tasks':200,'all':count(rows),'source_task_relation':'one supplied instruction per unique source clip'},
 'core_human':count([r for r in rows if r['human_candidate']]),
 'core_subject_including_human':count([r for r in rows if r['subject_candidate']]),
 'core_candidates_by_split':{split:{'human':count([r for r in rows if r['split']==split and r['human_candidate']]),'subject_including_human':count([r for r in rows if r['split']==split and r['subject_candidate']])} for split in ('short','long')},
 'status_counts':counts,
 'rules_zh':[
  '统计单位为官方已给定的视频片段与编辑指令组合；600个片段各有一条指令，来自385个原始网址。',
  '核心范围为角色/动物/物体替换、主体与正在操作物体的颜色/材质改变、佩戴物或手持/操作物体增删；源描述包含动作活动，编辑保持其运动时间。',
  '人体口径包含半身、手部和人形动漫角色；包含交谈与表情动作，不要求全身可见；人手换机械臂归广义主体。',
  '广义主体包含人体、动物与具有运动的物体；人体计数是其子集。',
  '主体缩放/移位、装饰特效、全局风格和自然动力学另列；纯背景改动、增加无关主体、删除主体、改写动作、镜头变化不计入核心表。',
  '仅站立、坐着、持物、沉思等静态描述，且缺少明确动作活动的候选列待视觉确认。',
  '本轮依据全部600条官方元数据规则扫描；对主体/属性和装饰特效任务逐条语义审读，未将该统计描述为600段视频视觉审阅。',
  'reading和conversation按活动描述列为候选，具体动作可测性需原片确认；候选数量不是已完成推理或已证实改善数量。'
 ],
 'metadata_files':{p.name:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [SRC/'ivebenchdb_prompt_short.json',SRC/'ivebenchdb_prompt_long.json',SRC/'ivebenchdb_name_mapping.csv']},
 'counts_by_status':dict(collections.Counter(r['status'] for r in rows)),
 'manual_candidate_decisions':len(M),
 'core_motion_evidence_counts':dict(collections.Counter(r['source_motion_evidence'] for r in rows if r['subject_candidate'])),
 'core_motion_evidence_ids':{s:[r['key'] for r in rows if r['subject_candidate'] and r['source_motion_evidence']==s] for s in sorted({r['source_motion_evidence'] for r in rows if r['subject_candidate']})}
}
(ROOT/'ivebench_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(ROOT/'ivebench_audit_rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
fields=['key','split','category','subcategory','status','source_motion_evidence','human_candidate','subject_candidate','reason_zh','source_prompt','edit_prompt','target_prompt','original_source_name','original_url','review_basis','video_visual_review_for_this_audit','generated_result_used_for_selection']
with (ROOT/'ivebench_audit_rows.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
print(json.dumps(summary,ensure_ascii=False,indent=2))
