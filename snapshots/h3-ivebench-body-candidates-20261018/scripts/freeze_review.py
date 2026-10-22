from pathlib import Path
import base64
import csv
import hashlib
import html
import json
import time

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')

# Every observation below refers only to the original official six fixed frames.
decisions={
 'short_0131':{'status':'PRIORITY','rank':1,'stratum':'clothing_color','observation':'右侧工人抬手指点、迈步并转身伸向箱子；左侧工人维持扶箱姿态，末段也改变指点方向。','reason':'动作变化清楚，两个全身主体基本可见，官方任务仅改外衣颜色。','limitations':'片段仅1.8秒；多人对应需明确。元数据写搬箱，固定画面实际以指点、迈步和转身为主。外衣实拍偏深蓝灰，保留官方 black down jackets 原指令。'},
 'short_0178':{'status':'PRIORITY','rank':2,'stratum':'clothing_color','observation':'双手在腹部上下移动并改变支撑位置；上侧手来回抚摸，下侧手托腹。','reason':'手部位置持续改变，衣色编辑可保留该动作。','limitations':'肩膀与头部不在画面，手臂姿态观察器可能不可测；应单独按手部/轨迹评价。'},
 'short_0090':{'status':'PRIORITY','rank':3,'stratum':'global_style','observation':'攀岩者手向上探、收回重新触岩、再向上伸直；身体与脚的位置也变化。','reason':'不同于已有对话/舞蹈原片，具有清楚的上肢阶段变化；官方动漫风格转换应保存动作。','limitations':'岩壁会部分遮挡手；全局风格编辑与人物身份编辑分组报告。'},
 'short_0055':{'status':'PRIORITY','rank':4,'stratum':'global_style','observation':'一手握杯，另一手将叉子下压入蛋糕，再向外侧切开/拨动；镜头同时逐渐上移。','reason':'手与工具的接触和方向变化可辨；官方油画风格编辑应保存动作。','limitations':'肩肘不完整且存在镜头运动；应检查手/叉轨迹，全身pose不适合作为唯一评价。'},
 'short_0321':{'status':'PRIORITY','rank':5,'stratum':'prop_addition','observation':'男子从略前倾变为后靠、转头；末段将桌面上的手抬起向外做手势。','reason':'上肢可见且有清楚抬手阶段；官方加花束无需改变人物动作。','limitations':'只有约2秒，主要只有一次抬手事件；花束可能遮挡手，编辑成功和遮挡需单独记录。'},
 'short_0268':{'status':'RESERVE','rank':6,'stratum':'identity','observation':'右侧成年女性在约0.8秒短暂抬手，再放下并转头说话；左侧人物也转头。','reason':'短暂手势可观察，可作为身份替换补充。','limitations':'官方 one of the women 未指定替换哪位；实际左侧人物看起来年纪较小。多人指代和手的短时出框使评价更复杂，不改写官方指令。'},
 'short_0343':{'status':'RESERVE','rank':7,'stratum':'identity','observation':'人物先低头，后将手机举到胸前操作；镜子中可同时看到另一视角。','reason':'存在明确拿起手机的阶段，身份编辑应保留动作。','limitations':'只有一次主要举手机事件，动作密度较低；镜像与前景人体对应需要人工确认。'},
 'short_0085':{'status':'RESERVE','rank':8,'stratum':'hair_color','observation':'人物笑着转头，同时将杯子从胸前逐渐放低到画面下边缘。','reason':'可作为低动作量的外观编辑对照。','limitations':'只有一次放杯动作，肩肘不完整，后半手离开画面；不列为动作密集案例。'},
 'short_0220':{'status':'EXCLUDE','observation':'坐着说话、轻微表情及头部变化，双手始终不在六个画面内。','reason':'不满足手臂可见及多阶段动作的筛选目标。'},
 'short_0309':{'status':'EXCLUDE','observation':'脸与肩部近景，主要是眨眼和表情变化，手臂不在画面。','reason':'不适合当前上肢动作保持问题。'},
 'short_0395':{'status':'EXCLUDE','observation':'校服人物的脸与肩部近景，表情变化为主，手臂不在画面。','reason':'不适合当前上肢动作保持问题。'},
}
mapping={row['order_name']:row for row in csv.DictReader((ROOT/'metadata/ivebenchdb_name_mapping.csv').open())}
allrows=[]
for scope in (ROOT,ROOT/'supplement_style_or_props'):
 plan=read(scope/'PREFILTER_FREEZE.json');receipts={r['source_id']:r for r in read(scope/'audit/DOWNLOAD_RECEIPTS.json')};times={r['source_id']:r for r in read(scope/'SOURCE_TIMEBASE.json')}
 for row in plan['candidates']:
  sid=row['source_id'];receipt=receipts[sid];image=scope/'source_review'/(sid+'.jpg')
  assert sha(receipt['file'])==receipt['sha256']
  allrows.append({**row,'source_file':receipt,'timebase':times[sid],'official_origin':mapping[sid],
    'source_review':decisions[sid],'six_frame_image':{'file':str(image),'sha256':sha(image)},'generated_outputs_consulted':0})
prior=read(ROOT/'PREFILTER_FREEZE.json')['excluded_previously_generated_or_queued']
duplicate_checks=[]
for row in allrows:
 origin=row['official_origin'];same=[]
 for sid in prior:
  other=mapping[sid]
  if origin['source_name']==other['source_name'] or (origin['url'] and origin['url']==other['url']):same.append({'prior_id':sid,'origin':other})
 duplicate_checks.append({'source_id':row['source_id'],'same_origin_as_prior':same})
manifest={'schema':'ivebench-body-source-review-v1','status':'CANDIDATES_ONLY_ROOT_SOURCE_REVIEW_PENDING','created_unix':time.time(),
 'scope':'Official sources only; no H3 outputs for any of these IDs inspected or generated in this selection.',
 'primary_recommendation':['short_0131','short_0178','short_0090','short_0055','short_0321'],
 'reserve_candidates':['short_0268','short_0343','short_0085'],
 'excluded':['short_0220','short_0309','short_0395'],
 'source_motion_review':'Six uniformly spaced original frames; full original videos supplied for root review. Motion density is a qualitative observation, not a measured metric.',
 'originals_are_full_official_clips':True,'generated_output_count':0,'inference_started':False,
 'prefilter_bindings':[{'file':str(scope/'PREFILTER_FREEZE.json'),'sha256':sha(scope/'PREFILTER_FREEZE.json')} for scope in (ROOT,ROOT/'supplement_style_or_props')],
 'metadata_provenance_duplicate_checks':duplicate_checks,'rows':allrows}
save(ROOT/'CANDIDATES_MANIFEST.json',manifest)
save(ROOT/'SELECTION_REVIEW_FREEZE.json',{'manifest_sha256':sha(ROOT/'CANDIDATES_MANIFEST.json'),'candidate_count':8,'excluded_count':3,'no_generation_queue_created':True})
ordered=sorted(allrows,key=lambda r:r['source_review'].get('rank',100))
sections=[]
for row in ordered:
 sid=row['source_id'];review=row['source_review'];task=row['official_task']
 video=base64.b64encode(Path(row['source_file']['file']).read_bytes()).decode();jpg=base64.b64encode(Path(row['six_frame_image']['file']).read_bytes()).decode()
 note='；'.join(review[k] for k in ('observation','reason','limitations') if k in review)
 status={'PRIORITY':'优先候选','RESERVE':'备选 / 低动作量','EXCLUDE':'排除'}[review['status']]
 sections.append(f'<section><h2>{sid} · {status}</h2><p>{html.escape(task["edit_prompt"])}</p><p>{html.escape(note)}</p><video controls preload="metadata" src="data:video/mp4;base64,{video}"></video><img alt="六个固定原片时刻" src="data:image/jpeg;base64,{jpg}"></section>')
document='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IVEBench 人体动作候选源</title><style>body{background:#111;color:#eee;font:18px/1.6 system-ui;margin:24px auto;max-width:1500px;padding:0 20px}section{margin:44px 0}video{width:75%;display:block;background:black}img{width:100%;display:block;margin-top:15px}p{color:#ccc}</style><h1>IVEBench 人体动作候选源</h1><p>8条候选、3条排除。仅按官方原视频筛选，尚未做模型推理。优先5条包含衣色2条、风格2条、道具1条；人物身份替换作为备选。每条均保留官方原始指令与完整原片。六时刻为全片均匀采样，完整视频供复核动作密度。</p>'+''.join(sections)+'</html>'
(ROOT/'index.html').write_text(document)
report=['8条候选供原片复核：','优先：0131 转身指点改衣色；0178 双手抚腹改衣色；0090 攀岩转动漫；0055 叉蛋糕转油画；0321 抬手对话加花束。','备选：0268 短暂抬手身份替换（指代模糊）；0343 举手机身份替换；0085 放杯改发色（低运动量）。','排除：0220/0309/0395 手臂在画面外。','严格衣色/身份编辑中，当前新源没有足够多高密度动作；8条不是8条动作密集视频。后续应按任务类型与动作量分组。','0065等现有14条生成/排队源已排除；原片、metadata、下载SHA、原PTS与六时刻图全部保留。','未准备模型输入、未修改提示词、未启动推理。','Manifest SHA: '+sha(ROOT/'CANDIDATES_MANIFEST.json')]
(ROOT/'REPORT.txt').write_text('\n'.join(report)+'\n')
save(ROOT/'audit/VALIDATION.json',{'passed':True,'files_sha_verified':len(allrows),'candidate_count':8,'excluded_count':3,'total_source_bytes':sum(row['source_file']['bytes'] for row in allrows),'html_sha256':sha(ROOT/'index.html'),'manifest_sha256':sha(ROOT/'CANDIDATES_MANIFEST.json'),'prior_source_origin_collisions':[r for r in duplicate_checks if r['same_origin_as_prior']]})
print(json.dumps(read(ROOT/'audit/VALIDATION.json'),indent=2))
