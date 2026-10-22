from pathlib import Path
import json,hashlib,html,csv,collections
from write_review import D
R=Path(__file__).resolve().parents[1]
D.update({
'0116':('defer','human_attribute','持杯稳定','女子一直双手持杯，主要为镜头移动、轻微手腕变化。','纹身删除是明确局部任务，当前源缺少明显动作阶段。',''),
'0120':('defer','held_object','指向与握持稳定','女子持续举指，男子握遥控器放在膝上，主要是表情变化。','被删除的遥控器基本静止，当前动作检验价值低。',''),
'0358':('first','human_attribute','举瓶、喝酒、放下','左侧男子先举瓶示意，随后瓶口举到嘴边饮用，最后放低。','两名男子都可被官方the man指代；后续需明确眼镜加到左侧喝酒者。',''),
'0362':('secondary','held_object','低头、持书倾斜','女子持蓝封皮书，随头部和上身变化轻微倾斜书本。','六时刻无明显翻页，动作幅度小。',''),
'0068':('secondary','operated_object','雕刻针接近、离开、换点','雕刻针在玉坠表面移动并改变接触点。','只有手指和工具近景；官方放大玉坠会改变接触几何，适合检查事件顺序，绝对轨迹不应强制相同。',''),
'0132':('secondary','human_hands','伸拳、汇合、维持','多只拳头从画面边缘伸向中心并碰在一起。','仅手和前臂可见；官方放大手掌改变几何，接触时刻可保留。',''),
'0046':('secondary','human_hands','连续敲键、手腕位移','两手在键盘上交替敲键，后段手腕移位。','六时刻不足以标注单次按键，原片保留；官方缩小手和电脑改变几何。',''),
'0096':('secondary','human_geometry','书写指向、抱臂','中间女子举笔在透明板上书写，右侧男子由放手转为抱臂。','官方缩小三人会改变几何；适合阶段顺序检验，空间位置直接误差有任务混杂。',''),
'0175':('defer','subject_removal','抬臂、俯身、起身','中间红帽人物双臂快速上抬并俯身，周围人也做手势。','官方恰好要求删除动作最清楚的红帽人物，不能要求保留他的动作；当前不选。',''),
'0233':('secondary','nearby_subject_removal','端锅、转身、移锅','母亲抱着婴儿，伸手端起锅，转身并把锅移向灶台，旁边儿童有手部动作。','官方删除旁边幼童，主要动作发生在保留的母亲；属于局部删除下的动作保持扩展，优先级低于换人换衣。',''),
'0182':('secondary','nearby_object_removal','放入包裹、压下、折箱盖','双手将包裹放入纸箱，按平后折起箱盖。','官方删除桌面标签，主要动作发生在保留手部；原source描述opening box，实际是装箱/合箱，须单列描述错误。',''),
'0264':('secondary','nearby_object_removal','舀汤、倾倒、撤勺','汤勺从画面上方进入并倾倒汤汁，随后撤离。','删除碗内肉片，动作主体汤勺/手保留；不直接编辑运动主体，作为次级局部编辑控制。',''),
})
plans=[json.load(open(R/'metadata/REVIEW_PLAN.json')),json.load(open(R/'metadata/EXTENSION_REVIEW_PLAN.json'))]
raw={x['src_video_name'][:-4]:x for p in plans for x in p['sources']};tb={x['source_id']:x for x in json.load(open(R/'audit/SOURCE_TIMEBASE.json'))}
dl={x['source_id']:x for p in ['DOWNLOAD_RECEIPTS.json','EXTENSION_DOWNLOAD_RECEIPTS.json'] for x in json.load(open(R/'audit'/p))}
rows=[]
for k,v in D.items():
 sid='short_'+k;rows.append({'source_id':sid,'priority':v[0],'scope':v[1],'visible_phases':v[2],'observation':v[3],'limitations':v[4],'known_development':v[5],'official_task':raw[sid],'source_file':dl[sid]['file'],'source_sha256':dl[sid]['sha256'],'source_bytes':dl[sid]['bytes'],'timebase':tb[sid]})
assert len(rows)==37 and set(raw)==set(tb)==set(dl)=={x['source_id'] for x in rows}
selected=['0131','0268','0343','0274','0178','0085','0358','0114','0044','0132','0046','0096','0068','0161','0362','0233','0182','0264']
assert len(selected)==18
out={'schema':'r82-source-review-complete-v1','official_revision':plans[0]['official_dataset_revision'],'reviewed_count':37,'candidate_review_order':['short_'+i for i in selected],'first_six_root_approved':['short_'+i for i in selected[:6]],'candidate_scope_note':'18 source candidates include 6 root-approved identity/clothing/hair cases, 2 further clear human/object phase cases, and 10 secondary cases. Secondary cases have weak motion, hand-only visibility, official geometry edits or edits to nearby objects; they do not establish 18 equally strong action-phase tests. Direct animal/object extensions are listed separately.','all_outcomes_retained':True,'generated_results_consulted':False,'GPU_used':False,'rows':rows}
(R/'audit/SOURCE_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
labels={'first':'优先动作源','secondary':'次选：需按限制解释','extension':'动物/物体扩展','defer':'暂缓'}
revieworder=['short_'+i for i in selected]+[x['source_id'] for x in rows if x['source_id'] not in ['short_'+i for i in selected]]
byid={x['source_id']:x for x in rows};cards=[]
for sid in revieworder:
 x=byid[sid];s=x['timebase'];t=x['official_task'];cards.append(f'<article id="{sid}" data-grade="{x["priority"]}"><h2>{sid} · {labels[x["priority"]]}</h2><p class="task">{html.escape(t["edit_prompt"])}</p><p><b>{html.escape(x["visible_phases"])}</b>。{html.escape(x["observation"])}</p><p class="note">{html.escape(x["limitations"])} {html.escape(x["known_development"])}</p><p class="small">完整原片 {s["decoded_frames"]} 帧，{s["fps_rational"]} fps，末帧 PTS {s["last_pts_s"]:.3f}s；六幅图沿全片均匀取样。</p><img loading="lazy" src="source_review/{sid}.jpg"><details><summary>播放完整原片</summary><video controls preload="none" src="sources/{sid}.mp4"></video><p>源描述：{html.escape(t["source_prompt"])}</p><p>目标描述：{html.escape(t["target_prompt"])}</p></details></article>')
(R/'index.html').write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><title>IVEBench 主体编辑候选原片审查</title><style>body{background:#101114;color:#eee;font:17px/1.6 sans-serif;margin:28px auto;max-width:1450px;padding:0 20px}article{padding:25px 0 40px;border-top:1px solid #555}img{width:100%}video{width:80%;max-height:720px}.task{color:#aee4f4}.note{color:#e5c990}.small{color:#aaa;font-size:14px}summary,button{cursor:pointer}button{padding:8px 15px;margin:5px}</style><h1>IVEBench 主体编辑候选原片审查</h1><p>核对37条官方短片，保留全部原片、原始任务和筛查结果。前6条已由研究负责人选作下一批：0131、0268、0343、0274、0178、0085。另列12条候选及其限制。六幅图用于粗粒度动作筛查，原片在下方播放。</p><p>候选依据原片动作与任务适配性确定，尚未得到这些新实验的效果结论。动物、物体和几何编辑分别标注，现有人体指标的适用范围需单独判断。</p><p><button onclick="show(\'all\')">全部37条</button><button onclick="show(\'first\')">优先</button><button onclick="show(\'secondary\')">次选</button><button onclick="show(\'extension\')">扩展</button><button onclick="show(\'defer\')">暂缓</button></p>'+''.join(cards)+'<script>function show(v){document.querySelectorAll("article").forEach(e=>e.hidden=v!=="all"&&e.dataset.grade!==v)}</script></html>')
with (R/'audit/CANDIDATE_TABLE.tsv').open('w') as f:
 w=csv.writer(f,delimiter='\t');w.writerow(['source','priority','scope','official_edit','phases','limitations'])
 for sid in revieworder:
  x=byid[sid];w.writerow([sid,x['priority'],x['scope'],x['official_task']['edit_prompt'],x['visible_phases'],x['limitations']])
report='''R82 原片审查完成\n\n37条来自冻结的400条short官方清单，另200条long未纳入。本轮保存所有37条原片与官方任务，来源逐一校验HF固定revision的LFS SHA和大小；原片总计406660612字节。6幅图按完整源帧数均匀选择，使用实际PTS，不依据编辑结果选时刻。\n\n先准备已批准6条：0131（手势转身伸臂）、0268（抬掌放下前倾，右侧成人）、0343（抬手机）、0274（前倾站直）、0178（腹部双手滑移，仅局部手臂）、0085（杯子放低）。0131/0178属于R76先前登记来源。\n\n新增0358最值得下批检查：左侧男子举啤酒瓶、饮用、放下，官方为给男子加眼镜；需明确左侧人物。0114左右运球阶段清晰，但属于R64开发源。\n\n候选清单共18条，其中上述8条动作较明确；其余10条包括连续步行、手部近景、官方几何编辑、保留动作主体但删除旁侧物体。每条限制见SOURCE_REVIEW.json/网页，不能将18条等同于18条强动作切换样例。另4条直接动物/物体阶段清晰（0039/0177/0235/0040），可作跨主体扩展，现有人体姿态指标不适用。\n\n官方600任务中有大量背景/风格/镜头任务；换人换衣子集也有许多仅表情轻摆头素材。已将这些低价值素材保留并标记暂缓。优先质量而非把静态片凑为动作密集。\n\n所有本轮判断是源侧可用性筛查。六帧未定义精确事件真值，也不能保证未取样区间无短动作。未运行H3、未测方法收益。\n'''
(R/'REPORT.txt').write_text(report)
files=[]
for p in sorted(R.rglob('*')):
 if p.is_file() and '__pycache__' not in p.parts and p.name!='SOURCE_PACKAGE_MANIFEST.json':files.append({'path':str(p.relative_to(R)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
(R/'SOURCE_PACKAGE_MANIFEST.json').write_text(json.dumps({'schema':'r82-source-package-v1','files':files,'source_count':37,'source_bytes':sum(x['source_bytes'] for x in rows),'gpu_used':False},indent=2)+'\n')
print({'reviewed':len(rows),'candidate_count':len(selected),'priority_counts':dict(collections.Counter(x['priority'] for x in rows)),'source_bytes':sum(x['source_bytes'] for x in rows),'manifest_files':len(files)})
