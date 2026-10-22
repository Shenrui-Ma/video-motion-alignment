from pathlib import Path
import base64
import hashlib
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parent
REPORT=Path('/Users/researcher/DevProjects/video-motion-alignment/reports/视频编辑中动作时间对齐-研究进展v1.html')
BACKUP=ROOT/'before-dual-weak-comparison.html'
if not BACKUP.exists():
    subprocess.run(['/bin/cp','-c',str(REPORT),str(BACKUP)],check=True)
source=BACKUP.read_text()
evidence=json.loads((ROOT/'dual_vs_weak_evidence.json').read_text())
by_id={c['source_id']:c for c in evidence['cases']}
names={'short_0252':'机舱人物替换','short_0358':'饮酒男子加眼镜','05_real_megumi_v':'Sam 真人舞蹈'}
roles=['forward_early','forward_global_weak','bidirectional_early']
rows=[]
for key in names:
    case=by_id[key]
    assert case['matching_conditions']['verified']
    conditions={c['id']:c for c in case['conditions']}
    row='<tr><td>'+names[key]+'</td>'
    for role in roles:
        item=conditions[role]
        row+=f'<td>{item["time_error_frames"]:.2f}</td><td>{item["MF"]:.4f}</td>'
    rows.append(row+'</tr>')

new='''<div class="prose"><h3 id="dual-comparison">3.4　双向结构与全程弱引导对照</h3>
<p>在同一源视频、提示词与初始噪声下，比较三种已有配置：<b>单向第 1–9 步</b>取 α=1、β=0；<b>单向全程弱引导</b>取 α=0.25、β=0；<b>双向第 1–9 步</b>取 α=β=1。</p>
<div class="scroll"><table><thead><tr><th rowspan="2">任务</th><th colspan="2">单向第 1–9 步</th><th colspan="2">单向全程弱引导</th><th colspan="2">双向第 1–9 步</th></tr><tr><th>时差 ↓（帧）</th><th>MF ↑</th><th>时差 ↓（帧）</th><th>MF ↑</th><th>时差 ↓（帧）</th><th>MF ↑</th></tr></thead><tbody>__ROWS__</tbody></table></div>
<p>前两组统计三个动作的平均绝对时差，舞蹈组使用手臂动作序列时差。Sam 的早期引导作用于原定动作窗口，全程弱引导覆盖全片；前两组均覆盖全片。这张表比较各配置的最终效果。</p>
<p><b>动作对齐优先采用单向全程弱引导：</b>两组时差更小，一组持平。双向版本的 MF 在三组均较高。全程弱引导与双向引导都完成了三项编辑，并保持了饮酒样例的构图。</p>
<p>双向结构继续作为候选。下一项结构对照应统一为全程弱引导及相同视频覆盖范围，仅增加反向约束，检查它能否在保持动作对齐的同时改善运动保真度。</p></div>
'''.replace('__ROWS__',''.join(rows))

def uri(path,mime):
    return f'data:{mime};base64,'+base64.b64encode(path.read_bytes()).decode()

media=ROOT/'dual_vs_weak'
image=uri(media/'drink_five_versions_frame039.jpg','image/jpeg')
video=uri(media/'drink_five_versions.mp4','video/mp4')
new+=f'''<article class="result" id="dual-weak-drink"><div class="resulthead"><h3>外观编辑 — 给饮酒男子戴眼镜</h3><span>IVEBench · short_0358</span></div>
<div class="inputnote"><p><b>编辑指令：</b>Add a pair of glasses to the man.　<b>输入：</b>源视频与文本，无角色参考图。</p><p>五列依次为参考、普通编辑、单向第 1–9 步、单向全程弱引导、双向第 1–9 步；完整提示词与 3.3 节同一样例一致。</p></div>
<figure><img loading="lazy" src="{image}" alt="饮酒样例五版本同帧对比"><figcaption class="imagecaption">同帧对比：参考、普通编辑、单向早期引导、单向全程弱引导、双向早期引导。</figcaption></figure>
<video controls playsinline preload="none" src="{video}"></video><div class="controls"><button type="button" data-rate="1">1×</button><button type="button" data-rate="0.5">0.5×</button><button type="button" data-restart>从头播放</button></div>
<div class="imagecaption">视频上排：参考、普通编辑、单向第 1–9 步；下排：单向全程弱引导、双向第 1–9 步。两种下排配置都保住了构图；全程弱引导时差为 1.33 帧，双向为 2.00 帧。</div></article>
<div class="prose">'''

start=source.index('<div class="prose"><h3>3.4')
end=source.index('<p><b>其他结构对照。</b>',start)
updated=source[:start]+new+source[end:]
old='<p><b>双向时间 Attention 保留为结构改进方向。</b>三组早期引导实验保持或改善时序，并提高 MF；下一步测试其与全程弱引导的组合，重点检查构图与人物交互。</p>'
replacement='<p><b>双向时间 Attention 作为候选结构继续检查。</b>与单向全程弱引导相比，双向早期引导的三组 MF 较高，动作时差在两组更大、一组持平。后续统一采样区间、正向强度和视频覆盖范围，测试增加反向约束的收益。</p>'
assert updated.count(old)==1
updated=updated.replace(old,replacement)
abstract=lambda text:re.search(r'<section id="abstract"[\s\S]*?</section>',text).group(0)
assert abstract(updated)==abstract(source)
assert updated.count('<video ')==4
(ROOT/'updated-with-dual-weak.html').write_text(updated)
(ROOT/'DUAL_WEAK_UPDATE.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'staged_sha256':hashlib.sha256(updated.encode()).hexdigest(),'report':str(REPORT),'backup':str(BACKUP),'abstract_unchanged':True,'changed_sections':['3.4','conclusion: bidirectional paragraph'],'new_media':1},ensure_ascii=False,indent=2))
print(json.dumps({'staged':str(ROOT/'updated-with-dual-weak.html'),'size_MB':round(len(updated.encode())/1e6,2)},ensure_ascii=False))
