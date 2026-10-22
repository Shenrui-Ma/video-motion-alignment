"""Build the portable Chinese research draft from existing, completed evidence.

No inference, decoding, pose extraction, external assets, or network requests.
All numeric claims are bound to existing JSON and all media to SHA-256.
"""
from pathlib import Path
from html import escape
import base64
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
BASE = Path('/Users/researcher/DevProjects')
OUT = Path('/Users/researcher/Downloads/H3_动作时序研究_论文式进展_20261017.html')
R2 = BASE / 'h3-timing-architecture-r2-20261016'
R26 = BASE / 'h3-timing-auto-motion-r26-20261017'
R27 = BASE / 'h3-timing-auto-controller-r27-20261017'
R33 = BASE / 'h3-timing-window-location-r33-20261017/analysis/postrun/captured/batch/final/r33_s05_index4_bins23to27'
R34 = BASE / 'h3-timing-fixed-early-global-r34-20261017/analysis/postrun_v3/captured/r34_source40372_seed2026101701_global_full_index4'
R35 = BASE / 'h3-timing-auto-bedside-r35-20261017/analysis/postrun/captured/r35_s07_seed2026101311_auto/final'
R39 = BASE / 'h3-timing-matched-global-r39-20261017'
R41 = BASE / 'h3-timing-manual-source51310-r41-20261017/analysis/early_manual_preview'
OLD_PRESENTATION = R2 / 'presentation/automatic_20261017'
sources = []
assets = []


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p, label):
    sources.append({'label': label, 'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)})
    return json.loads(p.read_text())


def bind_text(p, label):
    sources.append({'label': label, 'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)})
    return p.read_text()


def embed(p, mime):
    raw = p.read_bytes()
    record = {'path': str(p), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'mime': mime}
    # Reuse only byte-identical assets from the previously verified presentation.
    old = old_assets[str(p)]
    assert old['sha256'] == record['sha256'] and old['bytes'] == len(raw), p
    assets.append(record)
    return f'data:{mime};base64,' + base64.b64encode(raw).decode()


def lag_pair(fixed, key, window, manual=False):
    values = []
    for conf in ['0.3', '0.5']:
        rows = fixed[key][conf] if manual else fixed[key][conf]['diagnostics']
        row = next(r for r in rows if r['window'] == window and r['feature'] == 'arm_direction')
        values.append(row['reliable_lag_frames'])
    return values


def lag_text(values):
    return ' / '.join('UNKNOWN' if v is None else f'{v:+d}' for v in values)


def row(values):
    return '<tr>' + ''.join('<td>' + escape(str(v)) + '</td>' for v in values) + '</tr>'


def media(path, number, title, caption, poster=None):
    poster_attr = f' poster="{embed(poster, "image/png")}"' if poster else ''
    return (f'<figure class="media"><div class="figure-heading">图 {number}　{escape(title)}</div>'
            f'<video controls playsinline preload="metadata"{poster_attr} src="{embed(path, "video/mp4")}">'
            '此浏览器不支持 MP4 播放。</video><div class="controls" aria-label="播放速度">'
            '<button type="button" data-rate="0.5">0.5×</button><button type="button" data-rate="1">1×</button>'
            f'</div><figcaption>{caption}</figcaption></figure>')


old_manifest = read(OLD_PRESENTATION / 'MANIFEST.json', '既有展示素材清单')
old_assets = {x['path']: x for x in old_manifest['assets']}
fixed33 = read(R33 / 'FIXED_WINDOWS.json', '旧动作片段与异位干预：固定区间指标')['results']
fixed34 = read(R34 / 'analysis/compare/FIXED_WINDOWS.json', '40372：自动与固定全片指标')['results']
fixed35 = read(R35 / 'FIXED_WINDOWS.json', '床边舞蹈：固定区间指标')['results']
summary35 = read(R35 / 'FINAL_SUMMARY.json', '床边舞蹈：完整归档与计时')
matched = read(R39 / 'analysis/postrun/independent_review/COMPACT_RESULTS.json', '40372：相同四次干预的全片对照')
normal = read(R27 / 'analysis/postrun_normal_final_v3/captured/r27_s05_normal1313_auto/final/FINAL_SUMMARY.json', '正常样例：限定完成范围')
manual = read(R41 / 'COMPACT.json', '球场51310：人工选择参照的已完成指标')
persistence = read(R26 / 'analysis/persistence_ablation_replay/RESULTS.json', '移除跨步持续要求：仅决策重放')
bind_text(R26 / 'literature/CURRENT_ONLINE_MECHANISM_OVERLAP_20261017.txt', '当前实现与原始论文核验')
method = bind_text(HERE / 'assets/method.svg', '可编辑方法架构图')

assert lag_pair(fixed33, 'N', [50,65]) == [13,13]
assert lag_pair(fixed33, 'Auto', [50,65]) == [2,2]
assert lag_pair(fixed34, 'Auto', [40,55]) == [-1,-1]
assert lag_pair(fixed35, 'native', [54,69]) == [15,None]
assert lag_pair(fixed35, 'auto', [54,69]) == [-1,-1]
assert normal['active_indices'] == [] and normal['final_AV_latent_exact'] is True
assert normal['all_OFF_141RGB_equal'] is False
assert persistence['all_original_reproduction_passed'] is True
assert lag_pair(manual['fixed'], 'Manual', [64,95], manual=True) == [-1,-1]

experiment_rows = ''.join([
    row(['动作片段05', '50–65', lag_text(lag_pair(fixed33,'N',[50,65])), lag_text(lag_pair(fixed33,'Auto',[50,65])), lag_text(lag_pair(fixed33,'F',[50,65])), '1 / 21']),
    row(['棚内舞蹈40372', '40–55', lag_text(lag_pair(fixed34,'Native',[40,55])), lag_text(lag_pair(fixed34,'Auto',[40,55])), '全片固定：0 / 0', '4 / 24']),
    row(['床边舞蹈07', '54–69', lag_text(lag_pair(fixed35,'native',[54,69])), lag_text(lag_pair(fixed35,'auto',[54,69])), lag_text(lag_pair(fixed35,'fixed_full',[54,69])), '3 / 23']),
])
ablation_rows = ''.join([
    row(['动作片段05', '自动选择约44–59帧；去噪索引4', lag_text(lag_pair(fixed33,'Auto',[50,65])), '21']),
    row(['动作片段05', '改为约77–93帧；去噪索引仍为4', lag_text(lag_pair(fixed33,'Displaced',[50,65])), '21']),
    row(['棚内舞蹈40372', '自动选择；去噪索引2、4、5、6', lag_text(lag_pair(fixed34,'Auto',[40,55])), '24']),
    row(['棚内舞蹈40372', '相同四个索引；范围改为全片', lag_text(lag_pair(matched['fixed'],'MatchedGlobal',[40,55],manual=True)), '24']),
    row(['棚内舞蹈40372', '仅去噪索引4；范围为全片', lag_text(lag_pair(fixed34,'EarlyGlobalPulse',[40,55])), '21']),
])
persistence_rows = ''.join(row([
    {'R27_bad':'动作片段05','R27_normal':'正常样例05','R32':'棚内舞蹈40372','R35':'床边舞蹈07'}.get(r['label'],r['label']),
    r['actual_Full_count'],r['no_persistence_fixed_tape_Full_count'],
    '、'.join(str(x) for x in r['added_ON_indices']) or '无'
]) for r in persistence['cases'])
evidence = {
 'schema':'h3-paper-progress-evidence-v1','date':'2026-10-17','status':'draft_for_science_and_layout_review',
 'scope':'selected completed development cases; not a blind benchmark or full novelty proof',
 'scientific_claims':{
  'case05':{'ordinary_lag':lag_pair(fixed33,'N',[50,65]),'auto_lag':lag_pair(fixed33,'Auto',[50,65]),'window':[50,65]},
  'case40372':{'ordinary_lag':lag_pair(fixed34,'Native',[40,55]),'auto_lag':lag_pair(fixed34,'Auto',[40,55]),'window':[40,55]},
  'case07':{'ordinary_lag':lag_pair(fixed35,'native',[54,69]),'auto_lag':lag_pair(fixed35,'auto',[54,69]),'window':[54,69]},
  'normal':{'Full_count':0,'final_AV_latent_exact':True,'all_141_RGB_equal':False,'RGB_difference_origin':'undetermined'},
  'manual51310':{'ordinary_lag':lag_pair(manual['fixed'],'Native',[64,95],True),'manual_lag':lag_pair(manual['fixed'],'Manual',[64,95],True),'automatic_result':'pending_not_included'},
 },'sources':sources,
 'references':[
  {'name':'DIAL','version':'2609.11507v1','url':'https://arxiv.org/html/2609.11507v1'},
  {'name':'MotionEcho','version':'2506.19348v2','url':'https://arxiv.org/html/2506.19348v2'},
  {'name':'FlowMotion','version':'2603.06289v2','url':'https://arxiv.org/html/2603.06289v2'},
  {'name':'FlowDirector','version':'2506.05046v2','url':'https://arxiv.org/html/2506.05046v2'},
  {'name':'Motion by Queries','version':'2412.07750v3','url':'https://arxiv.org/html/2412.07750v3'}],
 'new_model_invocations':0,'new_pose_invocations':0,
}

body = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="MiniMax H3 动作时间错位研究的阶段论文稿。包含方法图、已完成实验、机制消融和可离线播放的视频。">
<title>H3 动作时序研究｜论文式进展</title>
<style>
:root{color-scheme:light;--ink:#20252b;--muted:#59626d;--line:#ccd2d9;--blue:#245c81;--pale:#f4f7fa}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#eceef1;color:var(--ink);font:17px/1.85 "Songti SC","Noto Serif CJK SC","STSong",SimSun,serif}
article{max-width:1060px;margin:32px auto 64px;background:#fff;padding:58px 76px 54px;box-shadow:0 2px 22px #1b273211}
.running{display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);padding-bottom:9px;color:var(--muted);font:12px/1.5 system-ui,sans-serif;letter-spacing:.08em}
h1{font-size:36px;line-height:1.4;text-align:center;letter-spacing:.03em;margin:35px 0 12px;font-weight:700}h1 small{display:block;font-size:23px;margin-top:10px;letter-spacing:0;font-weight:500}
.byline{text-align:center;color:var(--muted);font:14px/1.7 system-ui,"PingFang SC",sans-serif;margin:18px 0 28px}
.abstract{max-width:800px;margin:24px auto 25px;padding:0 18px}.abstract h2{text-align:center;font-size:19px;border:0;margin:0 0 9px}.abstract p{font-size:16px;line-height:1.85;margin:0;text-align:justify}
.keywords{font-size:14px;color:var(--muted);margin:14px 0 0}.toc{display:flex;flex-wrap:wrap;justify-content:center;gap:9px 21px;margin:28px 0 38px;border-block:1px solid var(--line);padding:11px 0;font:13px/1.6 system-ui,"PingFang SC",sans-serif}.toc a{color:#374c60;text-decoration:none}
h2{font-size:24px;line-height:1.45;margin:42px 0 17px;border-bottom:1px solid var(--line);padding-bottom:8px}h3{font-size:19px;line-height:1.5;margin:25px 0 9px}p{margin:12px 0;text-align:justify}strong{font-weight:700}a{color:var(--blue);text-underline-offset:3px}.small{font-size:14px;color:var(--muted)}
.scope{border-left:3px solid #6a8297;background:var(--pale);padding:12px 17px;margin:20px 0;font-size:15px}.equation{font-family:Georgia,"Times New Roman",serif;text-align:center;font-size:23px;line-height:1.7;padding:15px 12px;margin:18px 0;background:#f7f8f9;overflow-x:auto;white-space:nowrap}.eqno{float:right;font:13px/2.9 system-ui,sans-serif;color:var(--muted)}
figure{margin:24px 0 29px}figure svg{display:block;width:100%;height:auto}figcaption{font-size:14px;line-height:1.7;color:#45515d;margin:9px 0 0;text-align:justify}.figure-heading{font-size:16px;font-weight:650;margin:0 0 10px}.media{border:1px solid #d7dde2;padding:15px;background:#fff}.media video,.media img{width:100%;height:auto;display:block;background:#000}.controls{display:flex;justify-content:flex-end;gap:7px;margin-top:9px}button{font:12px/1.5 system-ui,sans-serif;border:1px solid #b6c1ca;background:#fff;color:#273f53;border-radius:3px;padding:4px 11px;cursor:pointer}button:hover,button:focus-visible{background:#e7eff5;outline:1px solid #2b6289}
.table-wrap{overflow-x:auto;margin:18px 0}table{width:100%;border-collapse:collapse;font:14px/1.65 "PingFang SC","Microsoft YaHei",sans-serif;border-top:2px solid #515d69;border-bottom:2px solid #515d69}th,td{padding:10px 9px;vertical-align:top;text-align:left;border-bottom:1px solid #dbe0e5}th{font-weight:650;color:#243d52;background:#f5f7f9}tbody tr:last-child td{border-bottom:0}.note{font-size:13px;line-height:1.7;color:#53606d;margin-top:8px}
details{margin:16px 0;border-top:1px solid #dce1e5;padding-top:10px}summary{cursor:pointer;color:#285a7a;font:14px/1.7 system-ui,"PingFang SC",sans-serif}.frame{margin-top:14px}.frame img{width:100%;display:block;background:#000}.refs{font:13px/1.8 system-ui,"PingFang SC",sans-serif;padding-left:22px}.refs li{margin:9px 0}.evidence-list{font:12px/1.6 ui-monospace,monospace;overflow-wrap:anywhere}.evidence-list li{margin:9px 0}.footer{border-top:1px solid var(--line);margin-top:32px;padding-top:15px;font-size:12px;color:var(--muted)}.tag{font:11px/1.5 system-ui,"PingFang SC",sans-serif;display:inline-block;border:1px solid #aebcca;border-radius:2px;padding:2px 6px;vertical-align:middle;margin-left:5px;color:#405b70}
@media(max-width:760px){body{background:#fff}article{margin:0;padding:24px 20px 42px;box-shadow:none}h1{font-size:27px}h1 small{font-size:19px}.abstract{padding:0}h2{font-size:22px}.media{padding:9px}table{font-size:12px;min-width:620px}p{font-size:16px}.running{font-size:10px}.equation{font-size:19px}.toc{gap:8px 15px}}
@media print{body{background:white;font-size:11pt}article{margin:0;padding:0;max-width:none;box-shadow:none}h1{font-size:24pt}h2{font-size:16pt;break-after:avoid}h3{break-after:avoid}.toc,.controls{display:none}figure,table,.scope{break-inside:avoid}a{color:inherit;text-decoration:none}video{min-height:140px}.media{padding:7px}.abstract p{font-size:10.5pt}details{display:block}summary{color:inherit}.footer{font-size:9pt}@page{size:A4;margin:19mm 18mm}
</style></head><body><article>
<header><div class="running"><span>MINIMAX H3 · 动作时序研究</span><span>阶段论文稿 · 2026 年 10 月 17 日</span></div>
<h1>按动作时间偏差自动选择视频编辑干预<small>MiniMax H3 上的推理控制、实证结果与创新边界</small></h1>
<div class="byline">研究进展与可复核实验记录<br>开发样例 · 无新增模型训练 · 文中素材可离线播放</div></header>
<section class="abstract" id="abstract"><h2>摘要</h2><p>角色替换后，视频可能保留了动作内容，却在不同时间完成动作。我们研究一种推理控制流程：每个去噪步先读取当前普通预测，通过完整 VAE 解码与姿态测量估计动作时间差，再自动选择需要干预的视频区间；证据持续存在时，在相同输入上重算一次参考时间读取，最后只做一次采样更新。三个已完成开发样例中，选定动作段的时间差分别由约 +13、+13、+15 帧降至 +2、−1、−1 帧；床边样例的普通编辑在较高姿态阈值下不可判。正常样例未触发干预，最终音视频 latent 精确保持，但成片像素并不完全相同。异位区间与全片干预也能改善结果，提示局部选择的独立作用仍需检验。当前证据支持继续验证自动化实用性，尚不足以确认完整的架构创新或普遍的质量收益。</p><div class="keywords"><strong>关键词：</strong>视频编辑；动作时间差；Diffusion Transformer；无需新增训练；可拒判的推理控制</div></section>
<nav class="toc" aria-label="文章目录"><a href="#related">1 相关工作</a><a href="#method">2 方法</a><a href="#experiments">3 实验</a><a href="#ablation">4 消融</a><a href="#limits">5 讨论与限制</a><a href="#conclusion">6 结论</a></nav>

<section id="related"><h2>1　问题与相关工作</h2>
<p>本文关注的是<strong>动作发生时间的保持</strong>：更换人物后，抬手、转身等动作应在参考视频对应时刻发生。动作幅度变小、身体形状改变、遮挡和姿态识别失败也会造成表观差异，因此一个时间平移量不能解释全部编辑错误。我们将时间差作为可拒判的诊断量，并同时保留完整视频、同帧姿态误差和可见支持。</p>
<div class="table-wrap"><table><thead><tr><th>工作</th><th>输入与控制方式</th><th>时机 / 训练要求</th><th>与当前实现的关系</th></tr></thead><tbody>
<tr><td><a href="https://arxiv.org/html/2609.11507v1">DIAL</a> [1]</td><td>用内生主体注意力图，为视频 query 读取参考主体 key 增加偏置。</td><td>Phase I 作用于最后 80% 的去噪过程，免训练；Phase II 另有 DPO 训练。</td><td>参考读取增强已有先例。当前约束参考组总注意力质量，改变组内的时间分布。</td></tr>
<tr><td><a href="https://arxiv.org/html/2506.19348v2">MotionEcho</a> [2]</td><td>运动误差与历史统计触发教师轨迹修正，达到条件后停止。</td><td>应用时免训练；使用预训练教师及蒸馏学生。</td><td>按误差启停已有先例。当前重算同一个模型，控制的是参考时间读取。</td></tr>
<tr><td><a href="https://arxiv.org/html/2603.06289v2">FlowMotion</a> [3]</td><td>预测 clean latent 与跨帧差分提供运动约束，优化 latent 并调整速度方向。</td><td>官方实现使用固定早期引导区间；无需额外教师或新权重训练。</td><td>免教师、端点运动引导已有先例。当前使用 RGB 姿态判别和离散的注意力干预选择。</td></tr>
<tr><td><a href="https://arxiv.org/html/2506.05046v2">FlowDirector</a> [4]</td><td>编辑流、空间掩码与方向分解；V2 进一步使用去时间均值的端点运动能量。</td><td>免训练、免反演。核验时官方代码公开 V1，V2 论文与代码范围分开。</td><td>端点运动残差与流修正已有先例。当前控制信号有物理帧单位，并允许 UNKNOWN。</td></tr>
</tbody></table></div>
<p>上述差异是实现和约束的区别。动态开关、局部注意力、端点运动测量、无需新训练，都不能单独作为首次提出的贡献。<a href="https://arxiv.org/html/2412.07750v3">Motion by Queries</a> [5] 还包含对应帧 K/V 共享及基于当前预测的掩码。我们的贡献候选需要由<strong>自动定位与启停能否在多例中保持有效、接近人工选择</strong>来支撑，并通过组件对照解释收益。</p>
</section>

<section id="method"><h2>2　方法</h2>
<h3>2.1　区分两条时间轴</h3><p>物理帧 <em>f</em> 描述影片中的动作时刻：本轮视频有 141 帧、24 fps，索引为 0–140。去噪索引 <em>n</em> 描述推理进度：20 次更新，索引为 0–19。例如，“去噪索引 4 干预物理帧 44–59”包含两个独立选择。H3 的 latent 时间槽与 RGB 帧采用模型现有映射，不能将一个 latent 槽直接理解成精确独立的四帧。</p>
<figure>''' + method + '''<figcaption>图 1　当前实现。每个去噪步先观察本次未引导的预测；ON 时在同一输入状态重算 Full。下一步的普通预测已经受到之前干预的影响。图中的局部时间读取只限定本层所改 query，后续传播仍可能影响全片。</figcaption></figure>
<h3>2.2　用动作差异提出区间，并保留拒判</h3><p>源视频姿态预先提取。每一步的普通 clean 预测经 VAE 解码后，用冻结的 DWPose 测量姿态。观察器遍历长度为 16 / 32 帧、步长为 4 帧并包含尾部区间的组合，分别读取两只手臂及单侧手臂的方向，共形成 186 个重叠描述。它目前覆盖手臂时序，尚未实现任意动作语义或全身各部位的自动诊断。</p>
<p>每个候选在 ±24 帧内寻找匹配，两种姿态置信阈值（0.3 / 0.5）都需给出可靠的延后量，且两者相差不超过 2 帧。与 ±2 帧的同步容许范围比较，归一化误差收益须大于 0.5，并满足至少 8 帧、80% 有效支持及移位后残差门。重叠区间组成连通组，每组保留证据最强的代表；与前一去噪步的代表具有共同手臂、足够区间重叠，才允许启动。</p>
<p>当前只对<strong>持续延后</strong>触发干预。无法可靠测量、没有合格候选或持续性中断时关闭；可判的提前记录不触发相反方向修正。UNKNOWN 表示证据不足，不能计为已对齐或已修复。运行错误会中止并保留记录。</p>
<h3>2.3　在原参考总质量内重新分配时间读取</h3><p>对固定 query 与 attention head，令 <em>m</em><sub>ref</sub> 为原注意力分配给参考视频 key 的总质量，<em>O</em><sub>ref</sub> 为该组归一化后的加权输出，<em>O</em><sub>same_ref</sub> 为同一名义时间槽内的归一化输出。在 RoPE 之后、输出投影 W<sub>O</sub> 之前，对选中的画布 query 计算：</p>
<div class="equation"><span class="eqno">(1)</span>O′ = O + α m<sub>ref</sub> (O<sub>same_ref</sub> − O<sub>ref</sub>)</div>
<p>当前固定 α = 1、时间半径为 0，所选时间槽内的全部空间 query、全部 50 层使用该规则。理想实数公式保持参考组总质量，只改变组内时间分布；有限精度实现用 FP32 构造修正，并经过数值测试。该式仍可等价写成带归一化补偿的 token logit 重加权，因此残差形式本身不足以构成新注意力原语。质量守恒也不保证人物身份、背景或动作幅度不变。</p>
<h3>2.4　同输入重算，采样只更新一次</h3><p>若本步关闭，直接采用普通预测 <em>y</em><sub>N</sub>；若开启，在同一 <em>x</em><sub>n</sub>、σ<sub>n</sub>、条件与 RNG 下计算 <em>y</em><sub>F</sub>。选定 <em>y</em><sub>n</sub> 后，仅执行一次 Euler 更新：</p>
<div class="equation"><span class="eqno">(2)</span>x<sub>n+1</sub> = (1 − β<sub>n</sub>) x<sub>n</sub> + β<sub>n</sub> y<sub>n</sub>,　β<sub>n</sub> = 1 − σ<sub>n+1</sub> / σ<sub>n</sub></div>
<p>若共 K 步开启，则有 20 + K 次模型预测（NFE），始终为 20 次 Euler 更新。本步没有再评价 Full 后择优接受；下一步重新观察实际轨迹。VAE 解码、姿态计算、条件核验和保存成本分别记录，不从 NFE 推断总速度。</p>
</section>

<section id="experiments"><h2>3　已完成实验</h2><h3>3.1　设置与结果口径</h3><p>采用 MiniMax H3 角色编辑，1312 × 736、141 帧、24 fps，20 步 Euler、CFG = 1，无 Turbo LoRA。每组比较尽量固定源片、角色、种子、模型、条件和噪声，并核验首次干预前可用的实际预测。部分早期实验未保存完整处理后条件树，相关证据范围按原记录保留。</p>
<p>下表给出动作段内<strong>手臂方向拟合的时间差</strong>，依次为置信阈值 0.3 / 0.5。正值表示延后，负值表示提前；24 帧约为 1 秒。结果来自已见的开发样例，不是独立盲测统计；186 个重叠描述也不视为 186 个独立样本。</p>
<div class="table-wrap"><table><thead><tr><th>视频</th><th>评价帧段</th><th>普通编辑</th><th>自动选择</th><th>人工 / 固定参照</th><th>自动引导次数 / NFE</th></tr></thead><tbody>''' + experiment_rows + '''</tbody></table></div>
<p class="note">表 1　单位：帧。床边普通编辑在 0.5 阈值下不可判，不能写成两个阈值均为 +15。40372 的固定参照作用于全片，没有人工逐事件标注；其结果不能当作人工选择上限。动作片段05、床边片段的人工选择同时配有固定去噪区间。</p>
<p>自动版在三例中改善了这些动作段，效果接近已完成的人工或固定参照。它仍可能保留手形、动作幅度及身体形状差异；例如床边视频后段仍拟合提前约 3–5 帧。这个结论不等于完整视频质量已经得到保障。</p>
'''
body += media(R33/'media/full_comparison.mp4',2,'动作片段05：完整逐帧对照','从左到右：参考、普通编辑、固定连续引导、自动选择、较晚视频区间引导。各列共享物理时间轴；原验证素材中的底部说明保持不变。',R33/'media/frame055_comparison.png')
body += media(R34/'analysis/media/all_methods/fixed_clip_comparison.mp4',3,'棚内舞蹈40372：动作片段对照','参考、普通编辑、固定连续引导、自动选择、固定单次全片引导。这里展示已验证的短片段；量化评价同时保留完整141帧。',R34/'analysis/media/all_methods/frame070_comparison.png')
body += media(OLD_PRESENTATION/'assets_r35/full_comparison.mp4',4,'床边舞蹈：自动选择与人工选择','完整141帧。左至右为参考、普通编辑、人工选择、自动选择；黑色底边的中文说明已写入视频。')
body += '''<h3>3.2　正常样例与执行成本</h3><p>另一个相同源片、不同种子的正常样例，全程 20 步均未开启引导，最终音视频 latent 与普通编辑精确相同。但 141 帧 RGB 并不完全相同：MAE 为 0.8624 / 255，PSNR 为 44.94 dB，差异来源尚未确定。我们保留这个失败的像素等价门，不将 latent 相同扩大表述为成片逐像素相同。</p>
<p>全程观测的成本明显。床边自动版实际为 23 NFE、20 次更新，总任务约 ''' + f'{summary35["efficiency"]["job_wall_seconds"]/60:.1f}' + ''' 分钟，其中观察器记录约 ''' + f'{summary35["efficiency"]["observer_wall_seconds"]/60:.1f}' + ''' 分钟。计时范围可能重叠，不能直接相加；这轮没有做效率优化结论。旧固定引导采用单分支实现，其 NFE 与当前“普通预测后可选重算”的计数方式也应区分。</p>
<h3>3.3　新增球场片段：人工参照已完成，自动配对待验收</h3><p>在另一源片51310中，人工预先选择物理帧56–127，并沿用去噪索引6–14的固定区间。已完成结果显示，64–95帧内的方向时间差在两个阈值下均由 +15 降至 −1 帧。它是人工选择视频范围加固定去噪安排，并非人工优化后的最佳时机。自动版尚未完成本文所需的最终配对验收，此处保留待更新状态。</p>
'''
body += media(R41/'media/comparison_141frames.mp4',5,'新增球场片段：人工参照','参考、普通编辑、人工窗口引导。自动版未加入，避免把未验收结果提前作为对比。',R41/'media/frame072.png')
body += '''</section><section id="ablation"><h2>4　消融与机制检查</h2><h3>4.1　局部选择的必要性尚未成立</h3><div class="table-wrap"><table><thead><tr><th>视频</th><th>实际干预安排</th><th>相同评价段时间差</th><th>NFE</th></tr></thead><tbody>''' + ablation_rows + '''</tbody></table></div>
<p>动作片段05中，将同一次干预移到较晚的视频区间，仍将较早动作的时间差修复到约 +1 帧。40372 中，沿用自动版实际开启的四个去噪索引、把范围扩至全片，也得到约 0 帧。这些结果表明，局部 attention 改动可以通过后续层和采样轨迹传播；当前结果无法证明检测到的区间必须与施加位置严格相同。</p>
<p>相同四次引导的对照匹配了时刻、次数和 NFE，但扩大了 query 数量、参考贡献及修正范数，<strong>没有匹配扰动剂量</strong>。此外，四个索引取自已经运行的自动轨迹，是事后机制对照。它不构成与自动定位等价的独立自动规则，也不要求自动版必须胜过全片干预才能具有实用价值。</p>
<h3>4.2　跨步持续证据确实改变决定，效果仍待生成验证</h3><p>对四条已存轨迹的共80份观察结果，原策略的开关和区间逐项重现。仅移除相邻去噪步的持续要求，保留当前收益、置信门、UNKNOWN和连通分组，得到：</p>
<div class="table-wrap"><table><thead><tr><th>记录轨迹</th><th>实际 Full 次数</th><th>移除持续要求后的决定次数</th><th>新增开启的去噪索引</th></tr></thead><tbody>''' + persistence_rows + '''</tbody></table></div>
<p class="note">表 3　这是在原来实际状态上的离线决策重放，未生成替代轨迹。改变早期决定后，后续输入和观察本应改变，因此不能用此表推断新视频质量或实际速度。正常轨迹两种规则均为零次，尚不能证明持续要求对正常保护不可替代。</p>
</section>
<section id="limits"><h2>5　贡献候选与待验证部分</h2><p><strong>当前已经完成：</strong>同输入的可选重算与一次采样更新；无需逐例手填动作区间的全片观察；UNKNOWN和技术错误的区分；三个开发样例的时间差改善；正常样例的零干预和最终 latent 保持；若干否定过强机制解释的对照。源码、条件、噪声、端点与媒体均有对应归档。</p>
<p><strong>仍需验证：</strong>自动选择在更多角色、动作和场景中能否稳定接近人工选择；腿部及身体形状的副作用；姿态识别误差导致的触发和漏检；停止是否来自确实对齐或证据不足；用户主动要求修改动作时如何豁免；全程解码成本如何降低。当前高阈值门限、区间长度等属于冻结开发设置，尚无跨数据集校准结论。</p>
<p>方法贡献可落在“有物理帧单位、允许拒判的动作错误证据，如何可靠地驱动已知参考读取算子”上。要把它写成独立算法或架构贡献，还需要明确哪些约束与组件产生可复现增益，并在相同预算与质量口径下对比近邻方法。本文没有完成 DIAL、MotionEcho、FlowMotion 或 FlowDirector 的统一重跑比较，也没有宣称已避开所有先例。</p>
</section>
<section id="conclusion"><h2>6　结论</h2><p>已完成结果支持继续推进自动时序干预：在三组开发视频中，系统无需逐例标出动作区间即可显著减少所检查片段的时间差，并在一个正常例中保持零干预。与此同时，异位和全片对照同样有效，后段提前与形状差异仍然存在。下一步的判据是多例改善、接近人工选择的效果、正常例保持和完整视频质量；具体组件的独立创新需要这些对照共同支撑。</p></section>

<section id="references"><h2>参考文献与复核范围</h2><ol class="refs">
<li><a href="https://arxiv.org/html/2609.11507v1">Harnessing Intrinsic Subject-Aware Attention for Controllable Multi-Subject Video Generation</a>. DIAL，arXiv:2609.11507v1，§3.3 / Algorithm 1；Phase II 训练范围见 §3.4。</li>
<li><a href="https://arxiv.org/html/2506.19348v2">When Distillation Breaks Motion Control: Restoring Generative Trajectories for Fast Video Generators</a>. MotionEcho，arXiv:2506.19348v2，§3.3–3.5。</li>
<li><a href="https://arxiv.org/html/2603.06289v2">FlowMotion: Training-Free Flow Guidance for Video Motion Transfer</a>. arXiv:2603.06289v2；<a href="https://github.com/HKUST-LongGroup/FlowMotion">官方代码</a>，核验提交 f5b4dcf。</li>
<li><a href="https://arxiv.org/html/2506.05046v2">FlowDirector: Training-Free Flow Steering for Precise Text-to-Video Editing</a>. arXiv:2506.05046v2；<a href="https://github.com/Westlake-AGI-Lab/FlowDirector">官方仓库</a> V1 代码核验提交 cecd56e。V2 论文结论与 V1 实现不混用。</li>
<li><a href="https://arxiv.org/html/2412.07750v3">Motion by Queries</a>. arXiv:2412.07750v3，Appendix B.10，对应帧 K/V 共享与当前预测掩码。</li>
</ol><p class="small">文献核验截至2026年10月17日。正文中方法对比依据所列版本，不代表穷尽检索或同环境性能排名。论文链接需要联网；本页视频、截图与方法图已完整内嵌。</p></section>
'''
evidence['assets'] = assets
evidence['selected_source_count'] = len(sources)
body += '<details><summary>展开本稿证据索引与 SHA-256</summary><p class="small">下列本地路径用于作者复核，不参与页面加载。收件人只需当前 HTML；所有展示素材已经嵌入。证据 JSON 也以 application/json 保存在本文件内。</p><ol class="evidence-list">'
for record in sources:
    body += '<li><strong>' + escape(record['label']) + '</strong><br>' + escape(record['path']) + '<br>SHA-256: ' + record['sha256'] + '</li>'
body += '</ol></details><footer class="footer">研究进展稿 · 所有数据按原始归档解释 · 仅新增文档与呈现，不重跑生成、VAE或姿态模型。页面可单文件复制分享；请使用支持 MP4 的现代浏览器打开。</footer></article>'
body += '<script type="application/json" id="evidence-json">' + json.dumps(evidence, ensure_ascii=False).replace('<','\\u003c') + '</script>'
body += '''<script>document.querySelectorAll('[data-rate]').forEach(button=>button.addEventListener('click',()=>{const video=button.closest('figure').querySelector('video');video.playbackRate=Number(button.dataset.rate);}));</script></body></html>'''
OUT.write_text(body)
(HERE/'paper.html').write_text(body)
(HERE/'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n')
manifest = {'schema':'h3-paper-progress-build-v1','html':str(OUT),'html_sha256':sha(OUT),'html_bytes':OUT.stat().st_size,'builder_sha256':sha(Path(__file__)),'method_svg_sha256':sha(HERE/'assets/method.svg'),'evidence_sha256':sha(HERE/'evidence.json'),'assets':assets,'source_files':sources,'browser_layout_verified':False,'browser_playback_verified':False,'status':'draft_for_parent_review'}
(HERE/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:manifest[k] for k in ['html','html_sha256','html_bytes','status']},ensure_ascii=False))
