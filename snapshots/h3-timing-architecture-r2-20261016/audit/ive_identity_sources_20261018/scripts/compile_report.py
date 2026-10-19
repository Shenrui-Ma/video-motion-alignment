from pathlib import Path
from fractions import Fraction
import csv
import hashlib
import html
import json

R = Path(__file__).resolve().parents[1]
load = lambda n: json.loads((R / 'metadata' / f'{n}.json').read_text())
plan = load('REVIEW_PLAN')
files = {x['source_id']: x for x in load('SOURCE_RECEIPTS')}
timebase = {x['source_id']: x for x in load('TIMEBASE')}
official = {Path(x['src_video_name']).stem: x for x in plan['source_rows']}
observations = {
 'short_0084': {
  'recommendation': '候补：单次手臂事件',
  'status': 'single_arm_event_candidate',
  'action': '电影片段中，男子最初把手枪抵在太阳穴处，约1.5秒后把手枪从太阳穴处放下，约2.7秒持枪手退出画面下缘。',
  'intervals': ['约0–1.5秒保持头侧姿态', '约1.5–2.7秒手从头侧降至胸前及画外', '约2.7–3.13秒手已在画外'],
  'visible': '脸、上半身和一只手清楚；肘和下半身不完整。原片是持枪的非血腥电影画面。',
  'feasibility': '男换女的官方任务本身允许保留把手枪从太阳穴处放下的路径。可比较离开头侧、降至肩/胸前的时刻。只有一次下降，没有连续拿取或多次切换，不能充作密集多阶段样例。',
  'suggested': True,
 },
 'short_0177': {
  'recommendation': '动物身份替换扩展候选',
  'status': 'animal_event_candidate',
  'action': '老虎张嘴打哈欠，下颌开合幅度清楚，末段闭嘴并降低头部。',
  'intervals': ['约0–0.6秒已张嘴并继续展开', '约0.6–1.7秒大幅张嘴', '约1.8–2.2秒闭嘴并低头', '约2.2–2.48秒闭嘴保持'],
  'visible': '侧面头颈和前躯清楚，嘴部边界可见；人体手臂观察器不适用。',
  'feasibility': '虎换狮与保留张嘴闭嘴动作相容。可人工检查闭嘴时刻；嘴型与鬃毛变化影响几何指标，需独立非人体评估。这是单次动物动作，不能算人物身份替换。',
  'suggested': True,
 },
 'short_0394': {
  'recommendation': '低优先级头部事件候选',
  'status': 'head_event_conditional',
  'action': '人物最初低头，约0.9–1.5秒抬头看向侧前方，随后保持。',
  'intervals': ['约0–0.9秒低头', '约0.9–1.5秒抬头转向', '约1.5–2.09秒保持抬头'],
  'visible': '头肩可见，双手和大部分躯体在画外；光线暗。',
  'feasibility': '辫发男性替换成长卷发女性是明确身份编辑。抬头阶段能肉眼比较，但片长仅2.09秒、只有头部动作，无法检验手物接触或连续手臂动作。',
  'suggested': True,
 },
 'short_0220': {
  'recommendation': '本轮不推荐',
  'status': 'reject_low_motion',
  'action': '人物坐着说话，嘴部、眉眼和头部有轻微变化；手臂大体保持。',
  'intervals': ['约0–3.75秒说话和小幅点头，没有清楚举落或接触阶段'],
  'visible': '头部与上半身可见，手大多不在画面。',
  'feasibility': '圣诞精灵身份替换任务明确，但动作幅度不足以支持本次寻找明显时序偏移的目的。',
  'suggested': False,
 },
 'short_0308': {
  'recommendation': '本轮不推荐',
  'status': 'reject_low_motion',
  'action': '盔甲角色在火光背景前小幅转动头部，身体与手臂没有清楚阶段变化。',
  'intervals': ['约0–4秒轻微头部转向，火焰背景运动明显'],
  'visible': '头肩为主，手臂基本不可见。',
  'feasibility': '战士替换成巫师任务明确。背景动态容易主导整体运动指标，源人物动作不足，本轮不推荐。',
  'suggested': False,
 },
 'short_0318': {
  'recommendation': '本轮不推荐',
  'status': 'reject_low_motion',
  'action': '窗后人物轻微低头、眨眼和说话，未出现手臂或物体操作。',
  'intervals': ['约0–3.84秒眼神和头部小幅变化'],
  'visible': '头部被窗框分割，肩部部分可见，手在画外。',
  'feasibility': '年轻女子换成年长女子的指令明确，但动作较少，年龄外观变化比时序诊断更突出。',
  'suggested': False,
 },
 'short_0021': {
  'recommendation': '本轮不推荐',
  'status': 'reject_motion_semantics_and_scale',
  'action': '多名滑雪者连续向山下滑行；近处红裤人物很快远离，画面伴随移动拍摄。',
  'intervals': ['约0–1.3秒红裤滑雪者由近及远', '约1.3–4.92秒多名人物继续远处滑行'],
  'visible': '全身可见但大部分人物很小，多主体、运动相机，肢体细节不足。',
  'feasibility': '双板滑雪者改成单板滑雪者会合理改变站姿、腿部关系和动作；难把姿态差异直接归为意外时序错误。',
  'suggested': False,
 },
}

rows = []
for sid, observation in observations.items():
    t = timebase[sid]
    end = Fraction(t['duration_ts']) * Fraction(t['time_base'])
    row = dict(source_id=sid, **observation, official=official[sid], source=files[sid],
        timebase={k:v for k,v in t.items() if k not in ('pts_s','pts_rational')},
        suggested_source_window={'start_pts_rational': t['pts_rational'][0], 'end_exclusive_pts_rational': str(end),
            'first_frame': 0, 'last_frame_inclusive': t['frames']-1, 'actual_clip_produced': False} if observation['suggested'] else None,
        generated_results_used=False, action_annotation_scope='Qualitative intervals from16 fixed whole-video frames; not exact event ground truth.')
    rows.append(row)

result = {
 'schema':'ive-identity-source-visual-review-v1',
 'scope':'待测源素材筛选。按原官方身份替换任务与源动作取舍，未看生成结果选样。',
 'downloaded_original_count':7,
 'downloaded_original_bytes':sum(x['bytes'] for x in files.values()),
 'main_finding':'没有找到新的、同时满足人物身份替换与连续多阶段大动作的强样例。short0084为电影中把手枪从太阳穴处放下的单次事件，当前列候补，short0394可作低优先级抬头候选；short0177可作动物开合动作扩展。其余4条本轮不推荐。',
 'source_independence':'已排除46个注册或已看ID，逐source_name/非空URL/平台原视频ID交叉600条。short0220与short0282、long0120同YouTube原视频但不同原片时间段。0308、0318、0394缺原URL，独立拍摄来源未知。',
 'not_downloaded':plan['not_downloaded'],
 'rows':rows,
}
(R/'metadata/VISUAL_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['IVEBench人物/主体身份替换：源内容复核', '', result['main_finding'], '',
 '7条完整官方视频共52,680,688字节，固定版本LFS SHA和大小逐一核验。long0122原视频295,647,038字节，按预算保留为未下载候选，未作视觉结论。',
 result['source_independence'],
 '所有取舍均基于源内容。尚未证明这些候选会产生编辑后时序偏移。没有新增生产者、实际裁片、依赖或GPU任务。',
 '动作时间范围是抽帧观察，不能当精确逐帧GT；建议窗口保留整个短片以覆盖动作前后。', '']
for x in rows:
    t=x['timebase'];o=x['official'];w=x['suggested_source_window']
    lines += [x['source_id']+' | '+x['recommendation'],
        '官方原指令：'+o['edit_prompt'], '官方源描述：'+o['source_prompt'], '官方目标描述：'+o['target_prompt'],
        f"源格式：{t['frames']}帧，{t['fps_rational']}fps，{t['duration_s']}秒，{t['width']}×{t['height']}",
        '实际源路径：'+x['source']['path'], 'SHA256：'+x['source']['sha256'],
        '原始来源：'+json.dumps(o['origin_mapping'],ensure_ascii=False),
        '与其他官方ID同源：'+json.dumps(o['related_originals'],ensure_ascii=False),
        '动作：'+x['action'], *x['intervals'], '可见性：'+x['visible'], '可行性：'+x['feasibility'],
        ('建议完整源窗口：['+w['start_pts_rational']+', '+w['end_exclusive_pts_rational']+')秒；原帧0…'+str(w['last_frame_inclusive'])) if w else '本轮不建议新增推理。', '']
(R/'REPORT.txt').write_text('\n'.join(lines)+'\n')
with (R/'CANDIDATES.tsv').open('w',newline='') as f:
    w=csv.writer(f,delimiter='\t');w.writerow(['id','status','original_edit','source_sha256','fps','duration_seconds','recommended_window','finding'])
    for x in rows:w.writerow([x['source_id'],x['status'],x['official']['edit_prompt'],x['source']['sha256'],x['timebase']['fps_rational'],x['timebase']['duration_s'],json.dumps(x['suggested_source_window']),x['feasibility']])

e=html.escape
parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>IVEBench身份替换原片筛选</title><style>body{max-width:1500px;margin:30px auto;padding:0 22px;font:17px/1.6 system-ui;background:#101319;color:#edf0f4}h1{font-size:28px}h2{margin-top:48px}a{color:#9fc9ff}img{width:100%;height:auto}video{width:min(100%,960px);display:block}section{border-top:1px solid #46505e;margin-top:30px}blockquote{margin:0;padding:14px;background:#232a35}small{color:#bac2cf}</style><h1>IVEBench身份替换原片筛选</h1>', '<p>'+e(result['main_finding'])+'</p>', '<p>'+e(result['source_independence'])+'</p>', '<p>全部为待测原片。52.7MB完整源视频，7份官方LFS核验通过。动作范围来自固定抽帧观察。</p>']
for x in rows:
    sid=x['source_id'];t=x['timebase'];w=x['suggested_source_window']
    parts += [f'<section><h2>{e(sid)} · {e(x["recommendation"])}</h2>',
      '<blockquote>'+e(x['official']['edit_prompt'])+'</blockquote>',
      '<p>'+e(x['action'])+'</p><p>'+e(x['feasibility'])+'</p>',
      f'<small>{t["frames"]}帧 · {t["fps_rational"]}fps · {t["duration_s"]}秒 · <a href="sources/{sid}.mp4">原片</a> · <a href="{e(x["source"]["url"])}">官方固定版本</a></small>',
      f'<video controls preload="none" src="sources/{sid}.mp4"></video>',
      '<p>'+e(x['visible'])+'</p>',f'<img loading="lazy" src="contact_sheets/{sid}.jpg"></section>']
parts += ['<p><a href="REPORT.txt">详细记录</a> · <a href="metadata/VISUAL_REVIEW.json">结构化观察</a> · <a href="metadata/REVIEW_PLAN.json">候选与排除登记</a></p></html>']
(R/'index.html').write_text('\n'.join(parts))

checks=[]
for x in rows:
    a=x['source'];p=Path(a['path']);h=hashlib.sha256(p.read_bytes()).hexdigest()
    assert h==a['sha256']==a['official_lfs']['oid']
    assert p.stat().st_size==a['bytes']==a['official_lfs']['size']
    t=x['timebase'];assert hashlib.sha256(Path(t['contact_sheet']).read_bytes()).hexdigest()==t['contact_sheet_sha256']
    assert t['sheet_indices'][0]==0 and t['sheet_indices'][-1]==t['frames']-1
    assert x['official']['edit_prompt']==official[x['source_id']]['edit_prompt']
    checks.append({'id':x['source_id'],'original_lfs_sha_and_size_exact':True,'whole_video_contactsheet_hash_exact':True,'source_sha256':h})
assert len(checks)==7 and result['downloaded_original_bytes']<150_000_000
(R/'VALIDATION.json').write_text(json.dumps({'passed':True,'checks':checks,'scope':'Source files and review artifacts only. No GPU, generated-output selection or producer.', 'artifact_sha256':{str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.rglob('*') if p.is_file() and p.name!='VALIDATION.json' and '__pycache__' not in str(p)}},indent=2)+'\n')
print('PASS 7 official originals,52680688 bytes, fullspan sheets and source-only report.')
