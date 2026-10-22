from pathlib import Path
from html import escape
import base64, hashlib, json, re

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'original-user-edited.html'
DEST = Path('/Users/researcher/DevProjects/video-motion-alignment/reports/视频编辑中动作时间对齐-研究进展v1.html')
source = SOURCE.read_text()
page = source

def replace_once(old, new):
    global page
    assert page.count(old) == 1, (old[:90], page.count(old))
    page = page.replace(old, new, 1)

def section(text, ident):
    return re.search(r'<section id="' + ident + r'"[^>]*>[\s\S]*?</section>', text).group(0)

old_abstract = section(source, 'abstract')
abstract = old_abstract.replace(
    '将目标视频 query 对源视频的注意力限制在对应的 VAE 时间 bin 内',
    '通过强度参数，将目标视频 query 对源视频的部分注意力重分配到对应的 VAE 时间 bin 内'
).replace(
    '目前大部分测试固定选择在7-15步引导（20步）。',
    '最新十组对照中，全程弱引导优于已测试的固定区间引导；同时进一步测试双向时间 Attention。'
)
replace_once(old_abstract, abstract)
replace_once('RESEARCH PROGRESS · 2026.10.20', 'RESEARCH PROGRESS · 2026.10.21')

# Keep the existing literature discussion, removing claims about the retired controller.
replace_once('，并根据预测动作偏差决定应用范围。', '。')
replace_once('，再根据预测动作时差选择干预窗口和采样步。', '。')
page, count = re.subn(r'<p><b>动态引导。</b>[\s\S]*?</p>', '', page)
assert count == 1

replace_once('补丁只修改输出视频 query 对参考视频 tokens 的加权特征。',
             '正向引导修改输出视频 query 对参考视频 tokens 的加权特征；双向变体还修改参考视频 query 对输出视频 tokens 的加权特征。')
replace_once('2.2　参考视频 Attention 的时间重分配', '2.2　参考视频时间对齐引导')
replace_once('当前成片对照取 α = 1；', '区间强引导取 α = 1，全程弱引导取 α = 0.25；')
replace_once('当前实验检验的机制是对应时间的参考特征约束，以及动作时差控制的干预选择。',
             '当前实验比较同时间参考约束的引导区间、强度，以及正向与双向结构。')
replace_once('固定开启干预：第 7–15 步，作用于全部有效视频时间。',
             '图中示例：第 7–15 步，作用于选定视频时间对应的 bins。')
page, count = re.subn(r'<text\b[^>]*>自动开启和停止干预：[\s\S]*?</text>',
                     '<text x="280" y="322" font-size="19" fill="#526277">当前优先配置：第 1–20 步，α=0.25，覆盖全部有效视频时间。</text>', page)
assert count == 1
replace_once('<p><b>预设采样区间的实验：</b>在 20 步去噪中的第 7–15 步启用本算子，覆盖全部 50 个 Block 和有效视频时间。普通编辑与干预编辑使用相同输入、提示词、初始噪声及采样器。每个步骤都执行一次完整模型前向，启用时增加内部参考 Attention 子计算。</p>',
             '<p>本方法在采样过程中直接应用。区间实验比较第 1–9、7–15、12–20、1–4＋16–20 步的 α=1 引导，以及第 1–20 步的 α=0.25 弱引导，均作用于全部 50 个 Block。强引导沿用各样例原定的视频时间窗口，全程弱引导覆盖全部有效视频时间。每组普通编辑与引导编辑使用相同输入、提示词、初始噪声及采样器。</p>')

start = page.index('<h3>2.3')
end = page.index('<h3>2.4', start)
dual_svg = (ROOT / 'dual_attention.svg').read_text()
dual = '''<div class="prose"><h3>2.3　双向时间 Attention</h3>
<p>正向引导约束<strong>生成 query → 参考视频 K/V</strong>。双向变体进一步约束<strong>参考 query → 生成视频 K/V</strong>：两组 query 分别从对方视频的同时间 bin 提取特征，并在 Attention 输出投影前更新各自的 head 输出。</p>
<p>在同一个 DiT Block 中，两向计算共用原始 Q、K、V 和 Joint Attention 输出。参考 tokens 的 hidden states 经输出投影、残差与 FFN 更新后，进入后续 Block；后续层的生成 query 再读取这些参考特征。每个采样步仍从固定的参考 latent 构建条件序列。</p></div>
<figure class="fig">__FIGURE__<figcaption>图 5．双向时间 Attention：同时修正生成与参考两组 query 的 Attention 输出，更新后的参考 hidden states 传入后续 DiT Block。</figcaption></figure>
<div class="prose"><p>记生成视频 token 集合为 T、参考视频集合为 R。沿用 2.2 节的组内归一化 Value 加权和，正向与反向修正分别为：</p>
<div class="eq"><span class="row">O′<sub>T</sub> = O<sub>T</sub> + α m<sub>R</sub>(μ<sub>R,same</sub> − μ<sub>R,all</sub>)</span><span class="row">O′<sub>R</sub> = O<sub>R</sub> + β m<sub>T</sub>(μ<sub>T,same</sub> − μ<sub>T,all</sub>)</span><small>m<sub>R</sub>、m<sub>T</sub> 为当前 query 在原 Joint Attention 中分给对方视频组的概率总和；same 表示同时间 bin，all 表示对方视频全部 tokens。</small></div>
<p>α 控制正向引导，β 控制反向引导。β=0 对应已有正向方法；α=0、β=1 用于单独检查反向作用。已完成的三组结构实验在第 1–9 步取 α=β=1，结果见 3.4 节。</p></div>
'''.replace('__FIGURE__', dual_svg)
page = page[:start] + '</div>' + dual + '<div class="prose">' + page[end:]

# Update the conclusions of the existing structural trials without rewriting their derivations.
replace_once('当前额外收益尚未稳定，主要成片证据仍来自 2.2 节算子。',
             '三条空间对应变体中，部分动作提前，同时出现路径或内容变化，后段延后仍存在；该轮配置已停止，继续使用 2.2 节的时间对齐引导。')
replace_once('在书封改色样例中，复用普通编辑的输入、提示词与实际初始噪声后，五个动作的发生区间均回到参考范围，但书封保持原色，编辑失败。对应成片见 3.5 节。',
             '该结构对照在书封改色样例中改善了动作时间，但保留了原书封颜色，编辑失败。')
replace_once('这一配置尚未改善该样例的时序；完整对照见实验部分。',
             '随后将相位变换与同时间 bin 约束组合，在五组已有有效样例上复测；四组没有额外时序收益，Sam 舞蹈由晚 1 帧变为晚 12 帧，当前相位配置已停止。')

# Reuse existing media bytes from the completed seven-version comparison page.
schedule_path = DEST.parent / 'R150_十组引导区间对照_单文件.html'
schedule_html = schedule_path.read_text()
data = json.loads(re.search(r'<script id="data" type="application/json">([\s\S]*?)</script>', schedule_html).group(1))
cases = {c['id']:c for c in data['cases']}
ranking = json.loads(Path('/Users/researcher/DevProjects/h3-guidance-schedule-eval-r150-20261021/audit/DISPLAY_RANKING.json').read_text())
old_experiments = section(source, 'experiments')
data_intro = re.search(r'<div class="prose">[\s\S]*?</div>', old_experiments).group(0)
labels = {'global_weak':('全程弱引导','1–20','0.25'), 'early':('早期引导','1–9','1'), 'split':('前后分段引导','1–4＋16–20','1'), 'fixed':('原固定区间引导','7–15','1'), 'late':('后期引导','12–20','1')}
rows = '<tr><td>普通编辑</td><td>—</td><td>0</td><td>11.40</td><td>10/10</td></tr>'
assert all(c['control_verdicts']['native']=='PASS_CORE_EDIT' for c in data['cases'])
for r in ranking['rows']:
    label,steps,alpha=labels[r['role']]
    rows+=f'<tr><td>{label}</td><td>{steps}</td><td>{alpha}</td><td><b>{r["mean_absolute_frames"]:.2f}</b></td><td>{r["edit_passed"]}/{r["edit_total"]}</td></tr>'
experiments = '<section id="experiments">' + data_intro + '''
<div class="prose"><h3>3.2　引导区间与强度</h3>
<p>本轮比较 <b>10 项已完成基础编辑的任务，来自 9 条独立参考视频</b>：6 项使用 IVEBench，4 项使用已有舞蹈素材。对每项任务固定提示词、输入、初始噪声与 20 步采样，只改变引导配置。强引导在 7 项任务覆盖全片、3 项舞蹈任务覆盖已有动作窗口；全程弱引导在全部 10 项覆盖全片。新增 45 条区间对照视频，沿用已有普通编辑与第 7–15 步结果。</p>
<p>平均时间误差统计其中 7 项动作延后的任务：先计算每项任务的绝对时间偏移，再对任务等权平均。六项使用动作转折标注区间的中点差，一项舞蹈沿用手臂动作序列时差。另两项用于检查原本同步的动作保持，一项用于检查短动作恢复。<b>编辑完成率统计全部 10 项任务。</b></p>
<div class="scroll"><table><thead><tr><th>设置</th><th>引导采样步</th><th>α</th><th>平均绝对时差 ↓（帧）</th><th>编辑完成</th></tr></thead><tbody>__ROWS__</tbody></table></div>
<p><b>全程弱引导配置的平均时差最低，并完成全部十项编辑。</b>固定区间中，第 1–9 步效果最好；早期和前后分段强引导各有一项构图发生改变。当前优先使用 α=0.25 的全程引导。</p>
<h3>3.3　代表性区间对照</h3>
<p>下列三组来自 IVEBench，输入均为源视频与编辑文本，无角色参考图。组内完整提示词一致。视频第一行为参考，第二行为普通编辑、1–9 步、7–15 步，第三行为 12–20 步、前后分段、全程弱引导。</p></div>
'''.replace('__ROWS__',rows)
selected = ['short_0252','long_0039','short_0358']
commands = {'short_0252':'Replace the man with an elderly woman','long_0039':'Adjust the color of book to blue','short_0358':'Add a pair of glasses to the man.'}
media_manifest=[]
for key in selected:
    c=cases[key];overview=c['overview'];frame=overview['default_frame'];poster=next(f['url'] for f in overview['frames'] if f['frame']==frame)
    prompt_note = '参考定义、原编辑句与通用保留要求' if key!='short_0358' else '历史 Context-IR 输入适配，包含目标人物和保留内容描述'
    experiments+=f'''<article class="result" id="schedule-{key}"><div class="resulthead"><h3>{escape(c['title'])}</h3><span>IVEBench · {key}</span></div>
<div class="inputnote"><p><b>编辑指令：</b>{escape(commands[key])}</p><details><summary>完整提示词：{prompt_note}</summary><pre>{escape(c['prompt'])}</pre></details></div>
<figure><img loading="lazy" src="{poster}" alt="{escape(c['title'])}七版本同帧对照"><figcaption class="imagecaption">同帧截图：参考、普通编辑、1–9 步、7–15 步、12–20 步、前后分段、全程弱引导。</figcaption></figure>
<video controls playsinline preload="none" src="{overview['video']}"></video><div class="controls"><button type="button" data-rate="1">1×</button><button type="button" data-rate="0.5">0.5×</button><button type="button" data-restart>从头播放</button></div>
<div class="imagecaption">{escape(c['display_summary'])}平均绝对时差：普通编辑 {c['mean_absolute_offset']['native']:.2f} 帧，全程弱引导 {c['mean_absolute_offset']['global_weak']:.2f} 帧。</div></article>'''
    media_manifest.append({'id':key,'frame':frame,'video_sha256':hashlib.sha256(base64.b64decode(overview['video'].split(',',1)[1])).hexdigest(),'image_sha256':hashlib.sha256(base64.b64decode(poster.split(',',1)[1])).hexdigest()})

experiments+='''<div class="prose"><h3>3.4　双向结构与评价结果</h3>
<p>双向时间 Attention 在三组已有任务上增加了仅反向与双向版本，共 6 条视频。与正向版本统一在第 1–9 步启用，正向取 α=1、β=0，双向取 α=β=1。</p>
<div class="scroll"><table><thead><tr><th>任务</th><th>正向时差 ↓（帧）</th><th>双向时差 ↓（帧）</th><th>正向 MF ↑</th><th>双向 MF ↑</th></tr></thead><tbody>
<tr><td>机舱人物替换</td><td>1.00</td><td>0.33</td><td>0.8059</td><td>0.8274</td></tr>
<tr><td>饮酒男子加眼镜</td><td>3.00</td><td>2.00</td><td>0.8121</td><td>0.9143</td></tr>
<tr><td>Sam 真人舞蹈</td><td>0</td><td>0</td><td>0.8527</td><td>0.8567</td></tr>
</tbody></table></div>
<p>前两组统计三个动作的平均绝对时差，舞蹈组使用手臂序列时差。双向版本完成三项编辑，时间对齐接近或优于正向版本，三组 MF 均提高；饮酒样例同时恢复了正向强引导改变的构图与旁人姿态。该样例的全程弱引导时差为 1.33 帧，早期双向为 2.00 帧；弱引导与双向结构的组合列为下一步实验。</p>
<p><b>其他结构对照。</b>空间 Value 对应的三条变体未持续改善时序，部分改变路径与内容。参考分支相位与已有引导的五组组合中，四组没有额外时序收益，一组延后增加；当前空间与相位配置均已停止。</p>
<p><b>评价指标。</b>FlexiAct 与 IVEBench 各沿用其官方 Motion Fidelity；本轮 IVEBench 与自有舞蹈的区间、双向对照统一使用 IVEBench MF。MF 汇总跟踪轨迹的一致性，动作时间另外记录。机舱固定引导曾使动作更对齐而全图 MF 下降；同一组轨迹的区域分解显示，目标人物改善被背景与邻座区域的下降抵消。因此同时报告编辑完成度、动作时间和 MF。</p>
</div></section>'''
replace_once(section(page,'experiments'),experiments)

conclusion='''<section id="discussion"><div class="prose"><h2>4　结论与后续工作</h2>
<p><b>当前优先方案是参考视频时间对齐引导，覆盖全程去噪并取 α=0.25。</b>在七项延后任务中，平均绝对时差由普通编辑的 11.40 帧降至 0.33 帧，十项任务均完成基础编辑。固定区间中，第 1–9 步优于原先沿用的第 7–15 步。</p>
<p><b>双向时间 Attention 保留为结构改进方向。</b>三组早期引导实验保持或改善时序，并提高 MF；下一步测试其与全程弱引导的组合，重点检查构图与人物交互。</p>
<p><b>后续测试。</b>优先选择 IVEBench 的主体替换、外观与交互物体编辑，保持官方编辑指令，并固定必要的 H3 输入适配。继续在基础编辑成功且动作延后明显的任务上做同条件配对，同时保留原本同步的样本。每次方法修改先复测已确认有效的案例，联合记录编辑完成、动作时刻、动作持续时间和 MF。</p>
</div></section>'''
replace_once(section(page,'discussion'),conclusion)
page=re.sub(r'<details><summary>实验版本与证据范围</summary>[\s\S]*?</details>',
            '<details><summary>实验版本与证据范围</summary><p>区间对照：R149／R150，10 项任务、9 条独立源视频，新增 45 条视频；双向结构：R151，三项任务新增 6 条视频；相位组合复测：R148，五组。视频、截图与对应评分均取自已有完成记录。</p></details>',page)
page=page.replace('记录日期：2026-10-20；实验持续推进。','更新日期：2026-10-21。')

# Scope each SVG's marker identifiers to avoid collisions among the existing figures.
figure_index = 0
def scope_svg(match):
    global figure_index
    figure_index += 1
    svg = match.group(0)
    for ident in re.findall(r'\bid="([^"]+)"', svg):
        replacement = f'reportfig{figure_index}-{ident}'
        svg = svg.replace(f'id="{ident}"', f'id="{replacement}"')
        svg = svg.replace(f'url(#{ident})', f'url(#{replacement})')
        svg = svg.replace(f'href="#{ident}"', f'href="#{replacement}"')
        svg = svg.replace(f'aria-labelledby="{ident}"', f'aria-labelledby="{replacement}"')
    return svg
page = re.sub(r'<svg\b[\s\S]*?</svg>', scope_svg, page)

# The report uses its existing native video controls and local speed buttons.
replace_once('</style></head>', '.result video{max-height:78vh;object-fit:contain}.dual-figure{overflow-x:auto}\n</style></head>')

content_only = re.sub(r'data:[^"\s<>]+', '[EMBEDDED MEDIA]', page)
assert all(word not in content_only for word in ('DWPose','R86','逐步控制','自动')), 'obsolete controller wording remains'
assert page.count('<video ')==3
assert len(re.findall(r'<article class="result"',page))==3
(ROOT/'updated-report.html').write_text(page)
(ROOT/'abstract-before.html').write_text(old_abstract)
(ROOT/'abstract-after.html').write_text(abstract)
(ROOT/'MEDIA.json').write_text(json.dumps(media_manifest,ensure_ascii=False,indent=2))
print(json.dumps({'staged':str(ROOT/'updated-report.html'),'size_MB':round(len(page.encode())/1e6,2),'videos':3,'abstract_replacements':2},ensure_ascii=False))
