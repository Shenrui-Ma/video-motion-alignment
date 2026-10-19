import csv
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
read = lambda name: json.loads((ROOT / 'metadata' / (name + '.json')).read_text())
plan = read('REVIEW_PLAN')
sources = {r['source_id']: r for r in read('SOURCE_RECEIPTS')}
times = {r['source_id']: r for r in read('TIMEBASE')}
windows = {r['source_id']: r for r in read('SUGGESTED_WINDOWS')}
origins = {r['source_id']: r for r in read('ORIGIN_RELATIONSHIPS')['rows']}

# These source-only visual notes are qualitative intervals from the saved sheets,
# not frame-accurate action ground truth or model-output-derived selections.
notes = {
 'long_0039': ('priority', '优先',
  '前景女子把手从键盘移向橙色书，触碰书封，再拿起并打开。改书封颜色与保留这段动作直接兼容。',
  ['约0.5–1.3秒：手离开键盘并伸向书。', '约1.3–2.9秒：手触书并调整抓握。', '约2.9–3.9秒：书抬起并打开，随后保持阅读。'],
  '前景人物上半身、操作手与书清楚；背景有数位同事，须明确绑定前景书与人物。',
  '只改运动中物体颜色，动作语义保留；背景人物不能混入主动作评估。', '目前最适合新增的一条。'),
 'long_0035': ('conditional', '候补：手部操作',
  '双手拿起耳机并移出画面，随后手回到唱盘；两个可辨认阶段之间存在较长画外间隔。',
  ['约5.0–6.6秒：抓住耳机并抬起，随后手与耳机离开画面。', '约6.6–10.1秒：双手主要在画外，动作不可判。', '约10.2–11.0秒：手回到设备并接触唱盘。'],
  '主要可见腰部与双手，头部和肩肘不在画面；不适合现有人体双臂观察器。',
  '官方任务删除被操作的耳机；可以检验剩余手部路径与返回唱盘时刻，但抓握接触语义会随物体删除改变。',
  '可作手物操作扩展，动作在画外期间标为不可观测。'),
 'long_0060': ('conditional', '候补：逆光接触',
  '手带香烟靠近嘴部，停留后离开；逆光下手与脸边界可辨，肩肘细节很暗。',
  ['约12.4–13.7秒：手向嘴靠近。', '约13.7–17.3秒：手在嘴附近停留。', '约17.3–18.4秒：手开始离开嘴。'],
  '人物侧面上半身可见，强逆光形成剪影；手到嘴距离可人工判断，姿态自动测量可靠性待测。',
  '官方删除香烟，保留身体路径可以评估；烟雾和被删除物体本身不宜作时间误差依据。',
  '动作转折少，优先级低于书本案例。'),
 'short_0185': ('conditional', '候补：未编辑人物动作',
  '中间站立角色多次抬落手臂，末段拿到音响；官方要替换的是前景趴地角色，该角色大部分时间静止。',
  ['约0–3.0秒：中间角色多次抬落手臂，旁人也有小幅摆动。', '约3.2–3.8秒：中间角色抬手接住/拿到音响。', '约3.9–4.17秒：卡通特效与表情变化。'],
  '多角色动画；站立角色手臂可见，被替换的趴地角色手臂大多不可见。',
  '可评估局部替换后其余角色动作是否保留；不能作为被替换主体自身运动继承的直接证据。',
  '保留为原场景中未编辑动作保持的扩展任务。'),
 'long_0088': ('reject', '本轮不推荐',
  '举杯、嘴边停留、放下杯子的阶段清楚，但官方任务把杯子替换成书。',
  ['约2–4秒：举杯至嘴。', '约4–10.7秒：嘴边停留。', '约11–12.7秒：杯子降低。'],
  '女子上半身与杯子可见。',
  '杯子换书会改变饮用动作的合理性，动作变化难直接解释成不受控时序错误。',
  '主要拒绝原因是任务与保留饮用动作存在语义冲突。'),
 'short_0039': ('reject', '本轮不推荐',
  '海鸥从低头位置抬头，随后主要站立和小幅转头；没有连续多次动作切换。',
  ['约0–0.8秒：低头后抬头。', '约0.8–2.8秒：主要站立。'],
  '全身鸟类可见，现有人体观察器不适用。',
  '海鸥换鹈鹕伴随明显头喙形状变化，应另设计非人体评估。',
  '动作密度不足，暂不作为当前扩展。'),
 'short_0235': ('reject', '本轮不推荐',
  '海獭漂浮并小幅梳理毛发，手爪与脸附近运动较细，水体带来整体漂移。',
  ['约0–3.7秒：细小梳理和转头，缺少清楚的大幅阶段变化。'],
  '手爪部分被毛发遮挡，非人体。',
  '可以作动物毛色编辑，但难用于当前明确手臂阶段与时序评价。',
  '动作幅度和可见性不足；且与short_0217/long_0046属于同一YouTube原视频。'),
 'short_0362': ('reject', '本轮不推荐',
  '人物低头阅读，蓝色书封和手的位置基本保持，未见清楚翻页或举落阶段。',
  ['约0–2.68秒：头部轻微变化，书与手大体静止。'],
  '两位人物上半身可见，视频分辨率较低。',
  '改书封颜色任务清楚，但源动作不足以检验明显时序偏移。',
  '动作过少；官方映射缺少URL，独立原视频身份仅能按source_name登记。'),
}

rows = []
for source_id in ['long_0039','long_0035','long_0060','short_0185','long_0088','short_0039','short_0235','short_0362']:
    source = next(r for r in plan['source_rows'] if r['src_video_name'] == source_id + '.mp4')
    status, label, reason, phases, visible, task, conclusion = notes[source_id]
    rows.append(dict(source_id=source_id, status=status, status_label=label,
        official_edit_prompt=source['edit_prompt'], official_source_prompt=source['source_prompt'],
        official_target_prompt=source['target_prompt'], source_receipt=sources[source_id],
        origin=origins[source_id], timebase={k:v for k,v in times[source_id].items() if k not in ['pts_s','pts_rational','frame_pts']},
        suggested_window=windows.get(source_id), action_observation=reason,
        approximate_action_intervals=phases, body_visibility=visible,
        task_fidelity_issue=task, recommendation=conclusion,
        observation_basis='Full-span fixed16-frame sheet; where available source-only fixed24-frame proposed-window sheet. Approximate intervals, not precise event GT.',
        generated_outputs_used=False))

review = dict(schema='ive-more-subject-source-review-v1', scope='待测原片筛选；源内容定向选取，尚未运行生成。',
    counts=dict(downloaded=8, priority=1, conditional=3, rejected=4),
    independent_origin_limits='Exact source_name/nonempty URL/canonical platform ID checked against the registered exclusions and all600. Separate IDs are not independent filming events. Missing URL remains unknown.',
    selection_limit='这8条中仅1条适合直接优先扩展，3条各有用途限制；未凑足5条同等适合样本。此结论仅针对实际检查的8条，未宣称剩余600条全无合适样例。',
    rows=rows)
(ROOT/'metadata/VISUAL_REVIEW.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')

lines=['IVEBench新增原片：源内容筛选，尚未生成', '', review['selection_limit'],
 '优先：long_0039。候补：long_0035、long_0060、short_0185。其余4条本轮不推荐。',
 '8份官方完整视频均已保留；没有制作裁片、没有修改推理或创建生产者。',
 '建议窗口采用原始有理PTS与半开区间；阶段描述来自抽帧查看，不能当逐帧精确标注。',
 '所有原指令保持原文。官方LFS SHA和大小、实际源SHA、全帧PTS、固定抽帧序号分别见metadata文件。',
 '去重：与R73/R80/R89/R88及之前12条没有相同已知原视频；short_0235与另外的short_0217、long_0046共用YouTube原片，不能重复计独立源；short_0362缺URL。', '']
for r in rows:
    t=r['timebase']; w=r['suggested_window']
    lines += [f"{r['source_id']} | {r['status_label']} | {t['fps_rational']} fps | {t['frames']}帧 | {t['duration_s']}秒",
        '官方指令：'+r['official_edit_prompt'],
        '源：'+r['source_receipt']['path'], 'SHA256：'+r['source_receipt']['sha256'],
        '来源：'+str(r['origin']['origin_mapping']),
        '动作：'+r['action_observation'], *r['approximate_action_intervals'],
        '可见性：'+r['body_visibility'], '任务边界：'+r['task_fidelity_issue'],
        ('建议窗口：['+w['start_pts_rational']+', '+w['end_exclusive_rational']+')秒；原帧'+str(w['start_frame'])+'…'+str(w['end_frame_inclusive'])) if w else '本轮不建议制作推理窗口。',
        r['recommendation'], '']
(ROOT/'REPORT.txt').write_text('\n'.join(lines)+'\n')
with (ROOT/'CANDIDATES.tsv').open('w', newline='') as f:
    writer=csv.writer(f, delimiter='\t'); writer.writerow(['source_id','status','official_edit_prompt','fps','duration_seconds','source_path','sha256','reason'])
    for r in rows:
        writer.writerow([r['source_id'],r['status'],r['official_edit_prompt'],r['timebase']['fps_rational'],r['timebase']['duration_s'],r['source_receipt']['path'],r['source_receipt']['sha256'],r['recommendation']])

e=html.escape
parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>IVEBench新增原片筛选</title><style>body{max-width:1450px;margin:35px auto;padding:0 22px;font:17px/1.65 system-ui;background:#101318;color:#e8edf2}h1{font-size:27px}h2{margin-top:55px}a{color:#8ac5ff}img{width:100%;height:auto}video{width:min(100%,1000px);display:block}section{border-top:1px solid #4c5360;padding-top:12px}blockquote{background:#202631;padding:12px 20px;margin:10px 0}small{color:#abb4c1}code{overflow-wrap:anywhere}</style><h1>IVEBench新增原片筛选</h1><p>8条源内容复核：1条优先，3条候补，4条本轮不推荐。这里展示待测原片；生成与干预效果尚未测试。</p><p>已按source_name、非空URL及平台原视频ID去重。短片0235与short0217、long0046同源；0362缺原始URL。建议窗口按源视频动作选取，属于IVEBench素材片段探索。</p>']
for r in rows:
    sid=r['source_id']; t=r['timebase']; w=r['suggested_window']
    parts += [f'<section><h2>{e(sid)} · {e(r["status_label"])}</h2>',
        f'<blockquote>{e(r["official_edit_prompt"])}</blockquote>',
        f'<p>{e(r["action_observation"])} {e(r["task_fidelity_issue"])}</p>',
        '<p>'+e(r['body_visibility'])+'</p>',
        f'<small>完整原视频：{t["frames"]}帧，{t["fps_rational"]} fps，{t["duration_s"]}秒。<a href="sources/{sid}.mp4">打开原片</a> · <a href="{e(r["source_receipt"]["url"])}">官方固定版本</a></small>',
        f'<video controls preload="none" src="sources/{sid}.mp4"></video>',
        '<details><summary>全片固定16帧</summary>'+f'<img loading="lazy" src="contact_sheets/{sid}.jpg"></details>']
    if w:
        parts += [f'<p>建议源窗口 [{w["start_pts_rational"]}, {w["end_exclusive_rational"]}) 秒；原帧 {w["start_frame"]}…{w["end_frame_inclusive"]}。以下24帧用于查看源动作。</p>', f'<img loading="lazy" src="contact_sheets/{sid}_suggested_window.jpg">']
    parts += ['<p>'+e(r['recommendation'])+'</p></section>']
parts += ['<p><a href="REPORT.txt">完整说明</a> · <a href="metadata/VISUAL_REVIEW.json">结构化观察记录</a> · <a href="metadata/SOURCE_RECEIPTS.json">原片SHA/LFS</a> · <a href="metadata/TIMEBASE.json">原始时间轴</a></p></html>']
(ROOT/'index.html').write_text('\n'.join(parts))

# Re-read original files rather than accepting saved success booleans.
checks=[]
for r in rows:
    s=r['source_receipt']; path=Path(s['path']); actual=hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == s['sha256'] == s['official_lfs']['oid']
    assert path.stat().st_size == s['bytes'] == s['official_lfs']['size']
    t=r['timebase']; sheet=Path(t['contact_sheet'])
    assert hashlib.sha256(sheet.read_bytes()).hexdigest() == t['contact_sheet_sha256']
    assert len(t['sheet_indices'])==16 and t['sheet_indices'][0]==0 and t['sheet_indices'][-1]==t['frames']-1
    if r['suggested_window']:
        w=r['suggested_window']; assert hashlib.sha256(Path(w['sheet']).read_bytes()).hexdigest()==w['sheet_sha256']
    checks.append(dict(source_id=r['source_id'],sha256=actual,official_lfs_exact=True,size_exact=True,fullspan_sheet_hash_exact=True))
assert len(rows)==8 and len({r['source_id'] for r in rows})==8
receipt=dict(passed=True,checks=checks,downloaded_count=8,generated_output_used=False,originals_cropped=False,
    artifacts=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
        for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name!='VALIDATION.json' and '__pycache__' not in str(p)])
(ROOT/'VALIDATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print('PASS: 8 official original hashes and sizes; 8 fullspan and 4 dense source-only sheets; report written.')
