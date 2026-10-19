from pathlib import Path
import json, hashlib, datetime
R=Path('/Users/researcher/DevProjects/h3-flexiact-character-repair-metrics-r98-20261019');A=R/'audit/agent_task_repair_review'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p):return {'file':str(p),'sha256':sha(p)}
def write(p,j):p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
c=read(R/'configs/contract.json');p=read(R/'showcase/PRESENTATION.json');g=read(R/'incoming/NATIVE_RUNTIME_GATE.json');ledger=read(A/'FRAME_LEDGER.json')
assert g['passed'] and all(g['checks'].values()) and g['routed_blocks']==0
assert ledger['all_physical_frame_indices']==list(range(147))
for item in ledger['media']+ledger['sheets']:
 assert sha(item['file'])==item['sha256'],item['file']
assert [n for x in ledger['sheets'] for n in x['physical_frame_indices']]==list(range(147))
for item in p['inputs']:assert sha(item['file'])==item['sha256']
assert sha(R/'showcase'/p['video']['file'])==p['video']['sha256']
review={
 'schema':'r98-native-task-repair-visual-review-v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'source_id':c['source_id'],'run_id':c['run_id'],'review_scope':'完整147有效帧的同帧参考/旧普通/新普通对照，30页逐帧图覆盖0..146；目标图单独核对。',
 'viewed_frame_indices':list(range(147)),'fps':24,'source_time_precision_seconds':0.125,'guidance_routed_calls':{'old_native':0,'new_native':0},
 'bindings':[bind(R/'configs/contract.json'),bind(A/'REVIEW_PLAN.json'),bind(A/'FRAME_LEDGER.json'),bind(R/'showcase/PRESENTATION.json'),bind(R/'incoming/NATIVE_RUNTIME_GATE.json'),bind(R/'incoming/COLLECTION.json'),bind(c['media']['target']['file'])],
 'source_and_output_files':p['inputs'],
 'task_acceptance':{
  'old_identity':'fail','old_scene':'fail','new_identity':'pass','new_scene':'pass',
  'new_motion_sequence':'partially_preserved','new_motion_shape_and_contacts':'partial','whole_task_exact_preservation':'partial',
  'identity_evidence':'新版全段保持短黑发动漫男性脸、绿披肩、棕色短夹克、浅色内衬/领饰、深裤浅色交叉束带、靴及腰侧装备；旧版源女性脸与长辫残留在新版消失。',
  'scene_evidence':'新版全段为纯白背景和带接触阴影的浅色地面，旧版室内墙面/地板消失。',
  'motion_evidence':'两版可辨认的低伏下降、向上撑起、随后低头拱背次序在新版保留。新版采用更偏正面三分之四视角，膝盖较持续收在躯干下，后半肘部重新弯曲；源视频的前后重心移动、挺胸伸背幅度和末段伸直手臂并未完整复刻。',
  'framing_quality':'撑起高位约75..95帧期间头顶接近或触及上边界，局部被裁切。未观察到新增的大范围重影或身体断裂。'
 },
 'events':[
  {'event':'低伏接近地面的阶段','source_frames':[36,57],'new_frames':[38,49],'assessment':'两者有重叠低位阶段；投影、肘角及最低点高度不同，未给单一lag。','lag_frames':None},
  {'event':'从低位明显抬头/抬胸','source_frames':[60,69],'new_frames':[50,58],'assessment':'新版较早离开低位；这是看过输出后的探索性视觉区间，动作幅度/视角变化影响转折边界。','lag_frames':None},
  {'event':'撑起后再次向下低头','source_frames':[105,117],'new_frames':[96,108],'assessment':'新版有较早下降迹象，但两个宽区间相交，未给精确时间修复数值。','lag_frames':None},
  {'event':'末段低头拱背','source_frames':[126,146],'new_frames':[126,146],'assessment':'源手臂较直，新版肘部再次弯曲、胸较低；属于支撑姿态/幅度差异，不能仅用时间平移解释。','lag_frames':None}
 ],
 'event_annotation_basis':'事件类型来自冻结源动作计划；具体输出边界在全段审片后探索性标注。帧区间表示人工可见边界，不是统计置信区间。原源8fps每帧重复3次，不能据24fps容器宣称源时间精度提高。',
 'timing_conclusion':'可见动作次序保留，若干转折有提前迹象；现成对照没有证明整体恒定延后，也没有测试时序引导的改善。姿态幅度和支撑形状差异需与phase分开。',
 'recommendation':{'action':'matched_guidance_comparison','reason':'目标身份及纯白场景已通过基础验收，可在同一新版提示/输入/主机条件下补固定引导，检验剩余phase和形状差异是否改善。保持本条普通编辑与未来匹配引导分开归档。','requires_further_identity_prompt_repair':False,'guidance_effect':None},
 'cross_host_limit':c['cross_host_limit'],'official_motion_fidelity':'pending; current R98 output has no bound official MF score.'
}
write(A/'REVIEW.json',review)
(A/'REPORT.txt').write_text('R98普通编辑修复：全147有效帧审阅完成。\n\n身份与场景：新版短黑发动漫男性脸、披肩/夹克/束带和腰侧装备连续可见，旧源人物脸及长辫残留消失；纯白背景实现。\n动作：低伏→撑起→低头拱背顺序保留。膝肘支撑、前后重心、挺胸幅度与源有差别；末段源伸臂拱背，新版肘部又弯曲。撑起高位头顶有裁切。\n时间：从低位抬头/抬胸的可见转折，源约60–69帧，新版约50–58帧；再次低头源约105–117帧，新版约96–108帧。后验探索性边界受投影和幅度变化影响，保留为可见区间，未报告精确lag。\n建议：基础身份和场景已完成，可以补同输入/同新版提示/同主机的固定引导对照，分别检验动作形状和phase。当前两版均为0次时序干预，尚无新版引导效果结论。\n限制：旧R66在.41，新R98在.9，软件环境不同，不能把差异全部归因于提示词；源8fps，展示24fps来自三次重复。新R98官方MF尚待计算。\n')
print(json.dumps({'review':bind(A/'REVIEW.json'),'report':bind(A/'REPORT.txt'),'all147_frames_evidence_verified':True},ensure_ascii=False))
