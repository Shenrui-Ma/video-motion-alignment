"""Build a portable, evidence-linked interim report from completed local artifacts."""
from pathlib import Path
import base64
import hashlib
import html
import json
import time

HERE = Path(__file__).resolve().parent
OUT = Path('/Users/researcher/Downloads/H3_自动窗口与干预验证_20261017.html')
R33 = Path('/Users/researcher/DevProjects/h3-timing-window-location-r33-20261017/analysis/postrun/captured/batch/final/r33_s05_index4_bins23to27')
R27 = Path('/Users/researcher/DevProjects/h3-timing-auto-controller-r27-20261017/analysis/postrun_recovery_v2/captured/r27_s05_bad1311_auto/final')
ANCHOR = Path('/Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/analysis/source_anchor_selection_execution/results/source05/SOURCE_SELECTION.json')
ANCHOR_TARGET = ANCHOR.parents[2] / 'audit/TARGET_RESULT_SUMMARY.json'
R34 = Path('/Users/researcher/DevProjects/h3-timing-fixed-early-global-r34-20261017/analysis/postrun_v3/captured/r34_source40372_seed2026101701_global_full_index4')
R35 = Path('/Users/researcher/DevProjects/h3-timing-auto-bedside-r35-20261017/analysis/postrun/captured/r35_s07_seed2026101311_auto/final')
assets = []


def embed(path, mime):
    raw = path.read_bytes()
    assets.append({'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'mime': mime})
    return 'data:' + mime + ';base64,' + base64.b64encode(raw).decode()


def video(path, title, explanation):
    return f'<section><h3>{html.escape(title)}</h3><p>{html.escape(explanation)}</p><video controls playsinline preload="metadata" src="{embed(path, "video/mp4")}"></video><p><button onclick="this.closest(\'section\').querySelector(\'video\').playbackRate=.5">0.5×</button> <button onclick="this.closest(\'section\').querySelector(\'video\').playbackRate=1">1×</button></p></section>'


fixed = json.loads((R33/'FIXED_WINDOWS.json').read_text())['results']
names = {'N': '普通编辑', 'F': '固定连续引导', 'Auto': '自动窗口与时机', 'Displaced': '较晚窗口单次引导'}
rows = []
for key, values in fixed.items():
    lag = [next(x['reliable_lag_frames'] for x in values[c]['diagnostics'] if x['window'] == [50, 65] and x['feature'] == 'arm_direction') for c in ['0.3', '0.5']]
    rows.append(f'<tr><td>{names[key]}</td><td>{lag[0]} / {lag[1]} 帧</td><td>' + {'N':'0','F':'9','Auto':'1','Displaced':'1'}[key] + '</td></tr>')
source = json.loads(ANCHOR.read_text())
target = json.loads(ANCHOR_TARGET.read_text())
selection_names = {'source_margin': '源动作可辨性', 'random_SHA256_20261017': '固定随机', 'even': '均匀选择', 'visibility': '可见性优先', 'motion': '运动幅度优先'}
selection_rows = []
for key, label in selection_names.items():
    bad = target['runs']['r27_s05_bad1311_auto']['methods'][key]
    normal = target['runs']['r27_s05_normal1313_auto']['methods'][key]
    coverage = bad['relative_full279']['delayed']
    selection_rows.append(f'<tr><td>{label}</td><td>{coverage["intersection_slots"]} / {coverage["full_scan_slots_denominator"]}</td><td>{bad["descriptor_counts"]["UNKNOWN"]} / {bad["descriptor_denominator"]}</td><td>{normal["descriptor_counts"]["UNKNOWN"]} / {normal["descriptor_denominator"]}</td></tr>')
by_id = {r['id']: r for r in source['candidates']}
anchor_rows = []
for row in source['selection']['source_margin']['rows']:
    detail = by_id[row['id']]
    anchor_rows.append(f'<tr><td>{row["start"]}–{row["end"]}</td><td>{html.escape(row["feature"])}</td><td>{detail["Q"]:.3f}</td><td>{detail["unknown_rivals"]}</td></tr>')

body = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>H3 自动窗口与干预验证 · 阶段记录</title>
<style>:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#090c10;color:#e9edf4;font:16px/1.75 system-ui,-apple-system,"PingFang SC",sans-serif}main{max-width:1240px;margin:auto;padding:40px 24px 80px}h1{font-size:32px;line-height:1.3}h2{font-size:24px;margin-top:46px}h3{font-size:20px}p{max-width:1040px}section,.card{background:#111820;border:1px solid #2b3542;border-radius:12px;padding:22px;margin:20px 0}video,img{width:100%;display:block;background:#000;border-radius:6px}table{border-collapse:collapse;width:100%;margin:18px 0}th,td{border-bottom:1px solid #34404d;text-align:left;padding:10px}th{color:#a6caed}a{color:#8cc6ff}button{border:1px solid #53647a;background:#182738;color:#fff;padding:7px 16px;border-radius:6px;cursor:pointer}.muted{color:#aab6c4}.equation{overflow:auto;font:15px/1.8 ui-monospace,monospace;white-space:pre-wrap;background:#090e14;padding:18px;border-radius:8px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}.chip{display:inline-block;padding:3px 10px;border:1px solid #4a6c87;border-radius:16px;color:#acd6f7}svg{max-width:100%;height:auto}.note{border-left:3px solid #e4b871;padding-left:16px}@media(max-width:600px){main{padding:24px 12px}h1{font-size:25px}section{padding:13px}td,th{font-size:13px;padding:7px}}</style>
<main><span class="chip">研究进行中 · 2026-10-17</span><h1>自动选择观察窗口，按当前动作偏差干预</h1>
<p>已完成的三个视频中，自动方法分别把主窗口的拟合时间差从 13 帧降到 2 帧、从 13 帧降到 −1 帧、从 15 帧降到 −1 帧。固定引导也能改善这些样例。当前工作重点是跨视频自动定位与开关、正常样例保持，以及人工参照与自动版的效果差异。</p>
<p class="note">本轮目标是让自动版相对普通编辑改善动作时间错位，并在多个独立视频上达到接近逐例人工选窗的效果，省去人工标注。人工版提供效果参照，固定全片引导提供机制参照。当前数据用于逐例比较；独立的方法贡献、跨视频稳定收益与整体视觉质量仍在验证。页面中的姿态拟合值用于诊断，人物身份、重影和动作语义需要结合视频判断。</p>
<h2>当前实现作用在哪里</h2><div class="card">
<svg viewBox="0 0 1100 245" role="img" aria-label="参考视频提供动作特征；每步原始预测经解码和姿态测量；控制器选择是否在DiT的画布query到参考视频key的读取上干预，再进行Euler更新">
<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0 0L7 3L0 6" fill="#8eb8da"/></marker></defs>
<g fill="#172838" stroke="#66849b"><rect x="10" y="20" width="220" height="65" rx="9"/><rect x="280" y="20" width="235" height="65" rx="9"/><rect x="565" y="20" width="235" height="65" rx="9"/><rect x="850" y="20" width="240" height="65" rx="9"/><rect x="280" y="155" width="235" height="65" rx="9"/><rect x="565" y="155" width="235" height="65" rx="9"/></g>
<g fill="#eef5fc" text-anchor="middle" font-family="system-ui" font-size="17"><text x="120" y="47">参考视频</text><text x="120" y="70">物理时间 τ / 动作特征</text><text x="397" y="47">当前状态 xₖ 的原始预测</text><text x="397" y="70">每个去噪步得到 clean 估计</text><text x="682" y="47">VAE 解码 / 姿态测量</text><text x="682" y="70">局部时间差 + 可判性</text><text x="970" y="47">自动控制器</text><text x="970" y="70">选择窗口 / ON / OFF</text><text x="397" y="183">Euler 更新 xₖ₊₁</text><text x="397" y="207">记录实际 NFE 与效率</text><text x="682" y="183">DiT 参考时间读取</text><text x="682" y="207">画布 query → 参考 K/V</text></g>
<g fill="none" stroke="#8eb8da" stroke-width="2" marker-end="url(#arrow)"><path d="M230 52H280"/><path d="M515 52H565"/><path d="M800 52H850"/><path d="M970 85V187H800"/><path d="M565 187H515"/><path d="M397 155V85"/></g></svg>
<p>自动版在每个去噪步先观察原始模型的当前预测。满足共同可见性、两种姿态置信阈值的一致性和相邻去噪步的持续性条件后，才计算额外参考引导分支。当前控制器覆盖完整视频的186个重叠窗口描述子，并针对持续延后触发引导。提前候选也会记录，当前在线版尚未用它们触发引导；后段提前是后续需要处理的现象。</p>
<div class="equation">O′ = O + m_ref · (P_same − P_ref) V_ref
xₖ₊₁ = (1 − βₖ)xₖ + βₖ yₖ,    βₖ = 1 − σₖ₊₁ / σₖ</div>
<p>m_ref 为原注意力分配给参考视频的总质量。P_same 在对应参考时间内重新分配这部分读取。选定的画布 query 行经过该算子，其余层继续传播；因此局部施加的改动可以影响其他物理时间。该算子沿用已研究的条件读取思路，新增控制策略的价值要通过对照证明。</p></div>
<h2>已完成的窗口位置对照</h2><p>同一参考视频、角色、种子与推理设置。主诊断窗口为 50–65 帧；表中两列时间差分别对应姿态置信阈值 0.3 / 0.5，24 fps。</p><table><thead><tr><th>方法</th><th>主动作拟合延后</th><th>施加引导的去噪步数</th></tr></thead><tbody>''' + ''.join(rows) + '''</tbody></table>
<p>自动方法在去噪索引 4 选择了 44–59 帧附近的窗口；较晚窗口对照同样仅在索引 4 干预，使用 23–27 号 latent 时间槽，约对应 77–93 帧。两个方案各干预 5 个槽，实际均为 21 NFE / 20 次 Euler 更新。其扰动范数并未匹配，位置效应与扰动强度仍需区分。</p>
<p>本个例中，较晚窗口也修复了较早动作的时间指标。因此“必须选中发生偏差的那一小段才能修复”的必要性还需要新的证据。三个固定帧的有限检查未发现明显形态差异；完整连续质量评价仍待完成。</p>
'''
body += video(R33/'media/full_comparison.mp4', '完整视频：原片、普通编辑、固定连续引导、自动引导、较晚窗口引导', '各列使用相同物理帧号并排展示。可通过下方按钮统一切换播放速度。')
body += video(R33/'media/fixed_clip_comparison.mp4', '预先指定的短动作段', '短片展示主动作附近的时序差异；完整视频用于观察动作衔接和其他时间段。')
body += '<details><summary>查看固定帧 55、86、105</summary>'
for frame in [55, 86, 105]:
    body += f'<p>Frame {frame}</p><img alt="固定帧 {frame} 五列对照" src="{embed(R33/"media"/f"frame{frame:03d}_comparison.png", "image/png")}">'
body += '</details>'
fresh = json.loads((R34/'analysis/compare/WHOLE_SCAN_SUMMARY.json').read_text())
fresh_names = {'Native': '普通编辑', 'GlobalFull6to14': '固定连续引导 6–14', 'Auto': '自动局部引导', 'EarlyGlobalPulse': '固定第 4 步全片引导一次'}
fresh_fixed = json.loads((R34/'analysis/compare/FIXED_WINDOWS.json').read_text())['results']
fresh_common = json.loads((R34/'analysis/compare/COMMON_Native__GlobalFull6to14__Auto__EarlyGlobalPulse_0.3.json').read_text())
fresh_full = next(x for x in fresh_common['rows'] if x['region'] == 'full_0_140' and x['feature'] == 'arm_direction')
fresh_rows = []
for key, name in fresh_names.items():
    lag = next(x['reliable_lag_frames'] for x in fresh_fixed[key]['0.3']['diagnostics'] if x['window'] == [40,55] and x['feature'] == 'arm_direction')
    counts = fresh[key]['baseline_counts']
    error = fresh_full['runs'][key]['same_frame_error_on_common_support']
    fresh_rows.append(f'<tr><td>{name}</td><td>{lag:+d} 帧</td><td>{counts["delayed_candidate"]} / {counts["advanced_candidate"]} / {counts["aligned"]} / {counts["unknown"]}</td><td>{error:.4f}</td></tr>')
body += '<h2>新参考视频 40372：自动版与固定引导</h2><p>主检查片段为 40–55 帧。正值表示拟合延后，负值表示拟合提前。全片扫描含 186 个重叠描述子；这些记录不作为独立样本计数。表中误差使用四种结果共同可见的骨骼，姿态置信阈值为 0.3，覆盖率为 98.76%。</p><table><thead><tr><th>方案</th><th>主片段双臂时间差</th><th>全扫：延后 / 提前 / 对齐 / 未知</th><th>全片同帧方向误差</th></tr></thead><tbody>' + ''.join(fresh_rows) + '</tbody></table>'
body += '<p>自动版改善了主片段，左臂仍约延后 3 帧；固定单次引导的左臂约延后 7 帧。自动版和固定单次引导的全片误差接近，固定连续引导更低。自动版的提前描述子增多，需检验是否出现过度修正。接下来重点验证自动选窗在更多样例上能否达到接近人工参照的效果，并记录正常样例保持、未知状态和视觉质量。</p><p>自动版使用 24 NFE / 20 次更新，固定单次为 21 NFE / 20 次更新，固定连续引导为 20 NFE / 20 次更新；额外观察、解码和姿态计算时间另有完整记录。新增机制对照重放自动版实际触发的 [2, 4, 5, 6] 步，将干预范围扩大到全片：主双臂时间差为0帧，自动版为−1帧；两者共同支持上的全片方向误差分别为0.1555和0.1667（置信阈值0.5，覆盖84.40%）。该对照沿用了自动版已经测得的触发时机，作用是检查物理窗口范围。两者调用数相同，扰动幅度与查询数量不同。局部范围的必要性仍需证据。</p>'
body += video(R34/'analysis/media/all_methods/fixed_clip_comparison.mp4', '新片段：原片、普通编辑、固定连续引导、自动版、固定单次引导', '相同物理帧号。有限固定帧检查显示三种引导均改善部分上身姿态；连续画质与精确身份保持仍需单独评估。')
body += '<details><summary>查看第 70 / 105 帧的五列对照</summary>'
for frame in [70,105]:
    body += f'<p>Frame {frame}</p><img alt="新片段固定帧 {frame}" src="{embed(R34/"analysis/media/all_methods"/f"frame{frame:03d}_comparison.png", "image/png")}">'
body += '</details>'
bedside = json.loads((R35/'FIXED_WINDOWS.json').read_text())['results']
bedside_rows = []
for key, label in [('native', '普通编辑'), ('fixed_full', '固定人工窗口'), ('auto', '自动窗口与时机')]:
    cells = []
    for window in [[54,69], [75,88], [98,111]]:
        values = [next(x['reliable_lag_frames'] for x in bedside[key][c]['diagnostics'] if x['window'] == window and x['feature'] == 'arm_direction') for c in ['0.3', '0.5']]
        cells.append(' / '.join('UNKNOWN' if value is None else f'{value:+d}' for value in values))
    bedside_rows.append('<tr><td>' + label + '</td>' + ''.join('<td>' + cell + '</td>' for cell in cells) + '</tr>')
body += '<h2>床边舞蹈：自动版接近固定人工窗口的结果</h2><p>人工版预设物理帧54–69、去噪索引6–14。自动版实际在去噪索引8、9、10干预物理帧60–75，其余17步使用原始预测。两个物理窗口重叠10帧，IoU约0.455；自动版较人工版晚2步开始、早4步结束。两版主片段均约提前1帧，普通编辑在可判支持上约延后15帧。表中为双臂方向的拟合帧差，依次列出姿态置信阈值0.3 / 0.5。</p><table><thead><tr><th>方案</th><th>54–69帧</th><th>75–88帧</th><th>98–111帧</th></tr></thead><tbody>' + ''.join(bedside_rows) + '</tbody></table>'
body += '<p>全片共同可见支持为90.60%，同帧方向误差由普通编辑0.4514降到自动版0.3769，固定人工版为0.3476。自动版后段仍拟合提前3–5帧，固定人工版约提前2–4帧。固定第63、81帧的观察显示抬腿与抬手时机更接近参考，同时保留手臂高度与动作幅度差异；连续细节质量仍需结合成片检查。</p><p>自动版实际23次网络预测、20次Euler更新，总任务约95.9分钟，其中观察器记录约42.7分钟。各计时范围可能重叠。此历史人工版采用单分支固定引导，网络调用成本与自动版的原始预测加引导分支不同；后续51310配对采用同一双分支实现。</p>'
body += video(HERE/'assets_r35/full_comparison.mp4', '床边舞蹈完整对照', '从左到右：参考视频、普通编辑、固定人工窗口引导、自动时序引导。141帧，24fps，保留同帧顺序。')
body += video(HERE/'assets_r35/short_comparison.mp4', '床边舞蹈预定短动作片段', '主动作段与完整片结合观察。底部中文说明已写入视频画布。')
manual_preview = Path('/Users/researcher/DevProjects/h3-timing-manual-source51310-r41-20261017/analysis/early_manual_preview')
body += '<h2>新球场片段：人工参照已完成</h2><p>角色替换使用Sam，物理窗口56–127帧、去噪索引6–14，共29次预测。主评价段64–95帧的双臂拟合时间差，在两种姿态阈值下均由普通编辑延后15帧降为提前1帧。阈值0.3下，全片共同可见骨槽占97.87%，同帧方向误差为普通编辑0.2847、人工版0.1699；阈值0.5下为83.51%、0.2541、0.1433。两个阈值的支持集合不同，数值分别解读。</p><p>固定第72、96帧可见人工版的抬手、支撑腿与交叉步更接近参考，手形和手臂幅度仍有差异。自动版正在生成，完成后加入同一组对照。</p>'
body += video(manual_preview/'media/comparison_141frames.mp4', '角色替换：参考、普通编辑、人工窗口引导', '完整141帧，24fps，三列共享源视频的时间轴。此组用于建立有效的人工参照；自动版随后配对。')
body += '<figure><img alt="预声明第72帧三列对照" src="' + embed(manual_preview/'media/frame072.png', 'image/png') + '"><figcaption>第72帧：普通编辑仍处于抬膝和双手高举姿态，人工版更接近参考的手靠近脸、另一手扶髋姿态。</figcaption></figure>'
body += '''<h2>源视频预扫描候选</h2><p>新原型先计算源动作窗口的可见性及其相对其他时段的可辨程度，按固定贪心规则选择最多 3 个互不重叠窗口。得分 Q 衡量视图扰动下的相对余量，生成失败风险还要由目标轨迹检验。</p><table><thead><tr><th>参考帧</th><th>特征</th><th>Q</th><th>未知竞争时段数</th></tr></thead><tbody>''' + ''.join(anchor_rows) + '''</tbody></table>
<p>本次选取 72 个物理帧、176 个去重骨槽。随机、均匀、可见性优先和动作幅度优先四个对照使用相同窗口数量与长度／特征预算。源扫描约 9.92 秒；两份已存姿态视图的预处理约 155.80 秒，另计。两条历史轨迹的全部 40 个端点评分已完成。</p>
<table><thead><tr><th>选窗规则</th><th>异常轨迹：覆盖的延后证据骨槽</th><th>异常轨迹 UNKNOWN</th><th>正常轨迹 UNKNOWN</th></tr></thead><tbody>''' + ''.join(selection_rows) + '''</tbody></table>
<p>五种选窗规则均漏掉了异常轨迹上的合格延后证据。完整 279 描述子扫描在去噪索引 3／4 找到 13 条重叠证据，主要集中在左臂；这些重叠记录属于同一视频，按端点、物理帧和骨骼去重后共有 176 个证据骨槽。表中 UNKNOWN 的分母为每条轨迹 20 步 × 3 个描述子。</p>
<p>这轮结果显示，源视频中的可辨性更高，尚不能保证窗口能捕获编辑中的偏离。后续需要检验动作部位覆盖、窗口长度导致的局部信号稀释，以及当前生成状态能提供的补充信息。正常轨迹的全扫也没有发现合格延后；它提供正常对照。预扫描评分使用已保存端点，额外视频生成次数为 0。</p>
<p>279 个候选中有 257 个 Q &gt; 0。当前视频选满了上限 3 个窗口，因此自适应选择更少窗口的实际收益仍待检验。新增 24 帧长度使候选数从历史 186 增到 279；两组结果会分别保留。</p>
<h2>自动开关与证据边界</h2><div class="grid"><div class="card"><h3>正常样例</h3><p>自动版全部关闭引导，20 个端点复核通过，最终视频与音频 latent 均精确相等。141 帧最终 RGB 均有像素差异，平均绝对差为 0.8624 / 255，PSNR 为 44.94 dB；差异来源尚未确定。正常成片的姿态扫描为 0 延后、1 提前、165 对齐、20 未知。另加一次早期全片引导后为 0、1、166、19，时序表现接近。</p></div><div class="card"><h3>参考视频 40372</h3><p>自动版与固定单次引导的 GPU、最终指标及媒体归档均已完成。实际自动触发索引为 2、4、5、6，期间重新启动一次。按同样四个索引进行全片引导的对照已完成数值评价，主时间差为0帧。固定5帧的匿名检查显示两版粗姿态接近，连续画质仍待评估。</p></div><div class="card"><h3>床边舞蹈与新素材</h3><p>床边舞蹈的生成、20端点复核、最终指标与媒体归档已完成，主动作约15→−1帧。新素材51310的普通编辑在预定64–95帧窗口拟合延后15帧，人工版已完成生成，自动版正在运行。它与此前球场素材属于相似拍摄场景。另一条素材43210的186项扫描有169项UNKNOWN，固定帧可见动作差异，时间与幅度变化仍需区分。</p></div></div>
<h2>可变数量选窗：离线诊断结果</h2><p>第一版分段原型按左右臂搜索相位一致的区间，再用段数代价选择窗口。全部 63 个预登记端点评分已完成。实际源视图校准得到 λ = 0，因此正复杂度惩罚消失；正常开发轨迹仍在 14 / 20 个端点出现合格候选。异常开发轨迹的候选出现在更晚端点，也未复现既有早期信号。</p>
<p>随后冻结的配准候选先消去每根骨骼在局部区间内的常量角度差，再检查能够解释观测的时间偏移集合。它在 31 个合成控制上完成核验，并对相同的 63 个既有端点完成评分。下表记录通过全部门限并由动态规划选出的区间；这些端点来自少数视频的重复去噪状态。</p>
<table><thead><tr><th>数据</th><th>端点数</th><th>选中区间</th><th>检测描述</th></tr></thead><tbody>
<tr><td>原延后样例</td><td>20</td><td>0</td><td>遗漏已有诊断信号</td></tr>
<tr><td>原正常样例</td><td>20</td><td>0</td><td>结合可见支持解释，K=0包含证据不足</td></tr>
<tr><td>参考视频40372</td><td>20</td><td>3</td><td>索引4、5、6连续检出右臂延后；区间约74–101帧</td></tr>
<tr><td>正常样例加固定引导的最终帧序列</td><td>1</td><td>0</td><td>保留为正常保护对照</td></tr>
<tr><td>床边舞蹈普通编辑的最终帧序列</td><td>1</td><td>1</td><td>87–116帧右臂拟合提前5帧</td></tr>
<tr><td>床边舞蹈固定引导的最终帧序列</td><td>1</td><td>1</td><td>104–116帧右臂拟合提前4帧</td></tr>
</tbody></table>
<p>这版共同可见骨槽为 9,976 / 35,532；完整 ±24 帧搜索会缩小视频两端与遮挡附近的支持范围。它压低了正常轨迹上的候选，同时漏掉一组已知延后信号，当前作为离线观察器继续改进。63 项 CPU 评分合计 27.01 秒，视频解码与姿态提取时间另计。</p>
<p>第二版改为判断干预方向：可接受相位集合D整体超出±2帧、且方向一致时提出候选，保留整个D。43项合成中出现了动作切换附近的反向候选。第三版保留第二版的候选分数与证据，只增加跨窗口顺序约束。</p>
<div class="equation">窗口 I=[aᵢ,bᵢ]，目标时间包络 [aᵢ+min Dᵢ, bᵢ+max Dᵢ]
I → J 可同时选择：bᵢ &lt; aⱼ 且 bᵢ+max Dᵢ &lt; aⱼ+min Dⱼ
每条手臂独立选择总证据值最大的有序链，允许 K=0。</div>
<p>第三版在原43项合成控制中的38项预登记必测门全部通过，第二版为32/38。7个局部时移阳性中的11个附加反向窗口被移除，14个臂／动作平台覆盖均为100%。遮挡诊断仍留下一个孤立反向窗口：缺少相邻候选时，顺序约束无法排除它，安全性检查保留为失败。宽相位集合也可能排斥实际可行的相邻窗口。第三版已完成相同63条真实开发端点与189项产物核验：第二、三版均选出6个窗口，所有选择一致。真实数据每个端点至多选一窗，顺序约束本轮没有改变结果。原异常轨迹20个端点均未检出窗口；共同支持为9,976 / 35,532个骨槽，96.11%的候选因支持不足保留为UNKNOWN。三版计算及归档共82.50秒，视频解码和姿态提取另计。下一候选将检查全时移共同支持造成的检测覆盖损失。<a href="https://proceedings.neurips.cc/paper_files/paper/2009/hash/2ca65f58e35d9ad45bf7f3ae5cfd08f1-Abstract.html">时空联合配准和单调对齐</a>、常量旋转拟合及集合式控制均有先例，贡献需要落在可靠判别和实际生成改善上。</p>
<h2>自动版与人工版的配对验证</h2><p>新增视频51310的自动版与人工版已在 .9 两张卡上运行，使用相同角色、种子、模型、采样配方和同时间参考读出算子。人工版的物理窗口为56–127帧，去噪索引为6–14；该设置在自动版成片出现前登记。自动版使用实际推理中观测到的信号决定窗口与开关。最终比较以预先登记的64–95帧、其余固定窗口、全片共同可见支持及画质为依据。</p><p>自动版相对普通编辑的改善是主目标；与人工版的逐例差异用于判断效果是否接近。两者的主时间差相差不超过2帧时，可在本轮作描述性的“接近”记录，同时列出幅度、可见性与画质差异。小样本阶段保留逐例结果。匹配四次引导的全片对照已完成97项下载产物校验。它与自动版共享事后取得的干预索引，主时间差为0帧；左臂匹配存在多解，需保留为UNKNOWN。新绿背景手势与耳机舞蹈素材已完成源检查，分别准备Musk和Sam角色替换的普通编辑。</p>
<p>单个开发例关闭引导的第一步触发于可见性不足，之后的预测才显示小时间差。“停止”记录需要注明原因：对齐、信号不足或其他门限。当前系统把不可判状态保留为 UNKNOWN。</p>
<h2>与已有方法的关系</h2><table><thead><tr><th>已有工作</th><th>已存在的思路</th><th>本轮要验证的区别</th></tr></thead><tbody>
<tr><td><a href="https://arxiv.org/html/2609.11507v1">DIAL</a></td><td>推理时增强指定参考内容的注意力读取</td><td>自动观察位置与实际动作偏差驱动的开关；验证省去逐例选窗后的效果保持及失败边界</td></tr>
<tr><td><a href="https://arxiv.org/html/2506.19348v2">MotionEcho</a></td><td>按运动误差动态调用／停止额外指导</td><td>当前方法读取同一编辑模型的原始预测；MotionEcho通过预训练教师的细步轨迹校正蒸馏学生。两者应用阶段均可免训练</td></tr>
<tr><td><a href="https://arxiv.org/html/2506.07177v2">Frame Guidance</a></td><td>少量帧上的引导可传播到全视频</td><td>检测位置与执行位置的关系及必要性对照</td></tr>
<tr><td><a href="https://arxiv.org/html/2601.23231v1">MPC-Flow</a></td><td>分阶段优化控制并根据新状态重新规划</td><td>未来跨窗口响应设计须给出具体结构、可辨性与实验证据</td></tr></tbody></table>
<p class="muted">本页为阶段记录。基于现有论文的数学部件、自动化工程与独立方法贡献分别陈述。效率按每项实验实际记录，尚未进行效率优化结论。所有视频和图片已嵌入本文件，复制 HTML 即可携带这些展示素材；论文链接联网打开。</p>
</main></html>'''
OUT.write_text(body)
manifest = {'built_unix': time.time(), 'html': str(OUT), 'html_sha256': hashlib.sha256(OUT.read_bytes()).hexdigest(), 'assets': assets, 'source_selection_sha256': hashlib.sha256(ANCHOR.read_bytes()).hexdigest(), 'target_selection_summary_sha256': hashlib.sha256(ANCHOR_TARGET.read_bytes()).hexdigest(), 'status': 'interim research record', 'browser_playback_verified': False}
(HERE/'MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'html': str(OUT), 'bytes': OUT.stat().st_size, 'assets': len(assets)}, ensure_ascii=False))
