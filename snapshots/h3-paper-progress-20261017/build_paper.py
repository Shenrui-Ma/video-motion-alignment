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
R41_POST = BASE / 'h3-timing-manual-source51310-r41-20261017/analysis/postrun'
R41_MEDIA = R41_POST / 'captured/r41_source51310_seed2026101701_manual56to127_6to14/analysis/media/source_native_auto_manual'
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
    # Every asset is bound to a completed presentation's verified file inventory.
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
            f'</div><figcaption>{caption}</figcaption>' + (f'<details><summary>查看关键帧截图</summary><div class="frame"><img alt="{escape(title)}关键帧对照" src="{embed(poster, "image/png")}"></div></details>' if poster else '') + '</figure>')


old_manifest = read(OLD_PRESENTATION / 'MANIFEST.json', '既有展示素材清单')
old_assets = {x['path']: x for x in old_manifest['assets']}
paired_assets = read(R41_POST / 'independent_review/MEDIA_BINDINGS.json', '球场四列展示：完成归档后的素材绑定')
old_assets.update({x['path']: x for x in paired_assets['media'].values()})
paired = read(R41_POST / 'independent_review/COMPACT_RESULTS.json', '球场51310：普通、自动、人工三组完成结果')
read(R41_POST.parent / 'ROOT_PAIRED_FIXED_VIEW_REVIEW.json', '球场预定第72/96帧：静态检查范围')
fixed33 = read(R33 / 'FIXED_WINDOWS.json', '旧动作片段与异位干预：固定区间指标')['results']
fixed34 = read(R34 / 'analysis/compare/FIXED_WINDOWS.json', '40372：自动与固定全片指标')['results']
fixed35 = read(R35 / 'FIXED_WINDOWS.json', '床边舞蹈：固定区间指标')['results']
summary35 = read(R35 / 'FINAL_SUMMARY.json', '床边舞蹈：完整归档与计时')
matched = read(R39 / 'analysis/postrun/independent_review/COMPACT_RESULTS.json', '40372：相同四次干预的全片对照')
normal = read(R27 / 'analysis/postrun_normal_final_v3/captured/r27_s05_normal1313_auto/final/FINAL_SUMMARY.json', '正常样例：限定完成范围')
manual = read(R41 / 'COMPACT.json', '球场51310：人工选择参照的已完成指标')
persistence = read(R26 / 'analysis/persistence_ablation_replay/RESULTS.json', '移除跨步持续要求：仅决策重放')
bind_text(R26 / 'literature/CURRENT_ONLINE_MECHANISM_OVERLAP_20261017.txt', '当前实现与原始论文核验')
bind_text(R26 / 'literature/attention_motion_addendum_20261017.txt', 'Attention运动控制补充核验')
fresh_normal = read(BASE / 'h3-timing-source28289-native-r42-20261017/analysis/postrun/captured/batch/final/r42_source_28289_seed2026101701_native/SUMMARY.json', '新增绿背景手势：普通编辑完整评价')
assert fresh_normal['scan_summary']['baseline_counts'] == {'delayed_candidate':0,'advanced_candidate':0,'aligned':179,'unknown':7}
bind_text(HERE / 'audit/dynamic_guidance_primary_check.txt', '动态引导近邻：TempoControl与IB原文复核')
normal_pulse = read(HERE / 'audit/normal_fixed_pulse_check.json', '正常样例：固定单次全片引导的共同支持误差')
for conf, result in normal_pulse.items():
    actual = read(Path(result['source']), '正常样例固定引导：共同支持原始结果 ' + conf)
    assert sha(Path(result['source'])) == result['sha256']
    item = next(x for x in actual['rows'] if x['region'] == 'full_0_140' and x['feature'] == 'arm_direction')
    assert {k:x['same_frame_error_on_common_support'] for k,x in item['runs'].items()} == result['errors']
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
assert paired['completed'] is True
def paired_lag(key, feature):
    return [next(r for r in paired['fixed_windows'][key][c]
                 if r['window'] == [64,95] and r['feature'] == feature)['reliable_lag_frames']
            for c in ['0.3','0.5']]
assert paired_lag('Native', 'left_arm_direction') == [15,15]
assert paired_lag('Auto', 'left_arm_direction') == [3,3]
assert paired_lag('Manual', 'left_arm_direction') == [-1,-1]
assert paired_lag('Auto', 'arm_direction') == [None,None]
paired_error_rows = []
for c in ['0.3','0.5']:
    for region, label in [('primary_64_95','第64–95帧'),('full_0_140','完整141帧')]:
        r = next(x for x in paired['common_support']['Native__Auto__Manual'][c]
                 if x['region'] == region and x['feature'] == 'arm_direction')
        enough = r['status'] == 'usable_exploratory'
        paired_error_rows.append(row([label, c, f"{100*r['common_valid_fraction']:.1f}%"] +
            [f"{r['errors'][k]:.3f}" if enough else 'UNKNOWN' for k in ['Native','Auto','Manual']]))

experiment_rows = ''.join([
    row(['动作片段05', '50–65', lag_text(lag_pair(fixed33,'N',[50,65])), lag_text(lag_pair(fixed33,'Auto',[50,65])), lag_text(lag_pair(fixed33,'F',[50,65])), '1 / 21']),
    row(['棚内舞蹈40372', '40–55', lag_text(lag_pair(fixed34,'Native',[40,55])), lag_text(lag_pair(fixed34,'Auto',[40,55])), '全片固定：0 / 0', '4 / 24']),
    row(['床边舞蹈07', '54–69', lag_text(lag_pair(fixed35,'native',[54,69])), lag_text(lag_pair(fixed35,'auto',[54,69])), lag_text(lag_pair(fixed35,'fixed_full',[54,69])), '3 / 23']),
    row(['球场51310（左臂）', '64–95', lag_text(paired_lag('Native','left_arm_direction')), lag_text(paired_lag('Auto','left_arm_direction')), lag_text(paired_lag('Manual','left_arm_direction')), '4 / 24']),
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
 'schema':'h3-paper-progress-evidence-v1','date':'2026-10-17','status':'reviewed_development_progress',
 'scope':'selected completed development cases; not a blind benchmark or full novelty proof',
 'scientific_claims':{
  'case05':{'ordinary_lag':lag_pair(fixed33,'N',[50,65]),'auto_lag':lag_pair(fixed33,'Auto',[50,65]),'window':[50,65]},
  'case40372':{'ordinary_lag':lag_pair(fixed34,'Native',[40,55]),'auto_lag':lag_pair(fixed34,'Auto',[40,55]),'window':[40,55]},
  'case07':{'ordinary_lag':lag_pair(fixed35,'native',[54,69]),'auto_lag':lag_pair(fixed35,'auto',[54,69]),'window':[54,69]},
  'normal':{'Full_count':0,'final_AV_latent_exact':True,'all_141_RGB_equal':False,'RGB_difference_origin':'undetermined'},
  'case51310':{'left_arm_lag':{k:paired_lag(k,'left_arm_direction') for k in ['Native','Auto','Manual']},'auto_bilateral_lag':[None,None], 'primary_common_h0.5':'insufficient_common_support', 'status':'complete', 'scope':'development example; manual better on primary span, full-video pose error descriptively close'},
 },'sources':sources,
 'references':[
  {'name':'DIAL','version':'2609.11507v1','url':'https://arxiv.org/html/2609.11507v1'},
  {'name':'MotionEcho','version':'2506.19348v2','url':'https://arxiv.org/html/2506.19348v2'},
  {'name':'FlowMotion','version':'2603.06289v2','url':'https://arxiv.org/html/2603.06289v2'},
  {'name':'FlowDirector','version':'2506.05046v2','url':'https://arxiv.org/html/2506.05046v2'},
  {'name':'Motion by Queries','version':'2412.07750v3','url':'https://arxiv.org/html/2412.07750v3'}, {'name':'Motion4Motion','version':'2607.11644v1','url':'https://arxiv.org/html/2607.11644v1'}, {'name':'STR-Match','version':'2506.22868v1','url':'https://arxiv.org/html/2506.22868v1'}, {'name':'TempoControl','version':'2510.02226v1','url':'https://arxiv.org/html/2510.02226v1'}, {'name':'Information Bottleneck CFG','version':'2610.13369v1','url':'https://arxiv.org/html/2610.13369v1'}],
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
<h1>基于动作时间偏差的视频编辑自动引导<small>MiniMax H3 的方法设计与阶段实验</small></h1>
<div class="byline">研究进展 · 2026 年 10 月<br>Training-free 推理方法 · 图像与视频已内嵌</div></header>
<section class="abstract" id="abstract"><h2>摘要</h2><p>视频角色替换有时会保留动作内容，却改变动作发生的时间。我们在 MiniMax H3 的去噪过程中估计当前预测与参考视频的动作时间差，自动选择需要引导的视频区间与去噪步，并在 DiT Attention 内重新分配参考时间信息。三个开发样例中，所检查动作段的时间差由约 +13、+13、+15 帧降至 +2、−1、−1 帧，与已有人工选择结果接近。新增球场样例的左臂延后由 15 帧降到 3 帧，人工版为 −1 帧；自动版的全片同帧姿态误差接近人工版。一个正常样例全程保持零干预。消融显示，全片引导和改变干预位置也能改善时序，局部选择的额外作用仍需验证。当前工作已实现自动选时机的推理流程，正在扩大样例并检验各组件的独立贡献。</p><div class="keywords"><strong>关键词：</strong>视频编辑；动作时序；Diffusion Transformer；Training-free</div></section>
<nav class="toc" aria-label="文章目录"><a href="#related">1 相关工作</a><a href="#method">2 方法</a><a href="#experiments">3 实验</a><a href="#ablation">4 消融</a><a href="#limits">5 讨论与限制</a><a href="#conclusion">6 结论</a></nav>

<section id="related"><h2>1　问题与相关工作</h2>
<p>本文研究<strong>角色编辑中的动作时序保持</strong>：更换人物后，抬手、转身等动作仍应在参考视频对应时刻发生。评价同时关注时间差、同帧姿态误差与可见性，以区分时间错位、动作形变和测量失败。</p>
<div class="table-wrap"><table><thead><tr><th>工作</th><th>输入与控制方式</th><th>时机 / 训练要求</th><th>与当前实现的关系</th></tr></thead><tbody>
<tr><td><a href="https://arxiv.org/html/2609.11507v1">DIAL</a> [1]</td><td>用内生主体注意力图，为视频 query 读取参考主体 key 增加偏置。</td><td>Phase I 作用于最后 80% 的去噪过程，免训练；Phase II 另有 DPO 训练。</td><td>参考读取增强已有先例。当前约束参考组总注意力权重，改变组内的时间分布。</td></tr>
<tr><td><a href="https://arxiv.org/html/2506.19348v2">MotionEcho</a> [2]</td><td>运动误差与历史统计触发教师轨迹修正，达到条件后停止。</td><td>应用时免训练；使用预训练教师及蒸馏学生。</td><td>按误差启停已有先例。当前重算同一个模型，控制的是参考时间读取。</td></tr>
<tr><td><a href="https://arxiv.org/html/2603.06289v2">FlowMotion</a> [3]</td><td>预测 clean latent 与跨帧差分提供运动约束，优化 latent 并调整速度方向。</td><td>官方实现使用固定早期引导区间；无需额外教师或新权重训练。</td><td>免教师、端点运动引导已有先例。当前使用 RGB 姿态判别和离散的注意力干预选择。</td></tr>
<tr><td><a href="https://arxiv.org/html/2506.05046v2">FlowDirector</a> [4]</td><td>编辑流、空间掩码与方向分解；V2 进一步使用去时间均值的端点运动能量。</td><td>免训练、免反演。核验时官方代码公开 V1，V2 论文与代码范围分开。</td><td>端点运动残差与流修正已有先例。当前控制信号有物理帧单位，并允许 UNKNOWN。</td></tr>
<tr><td><a href="https://arxiv.org/html/2510.02226v1">TempoControl</a> [8]</td><td>将词语的时序 Attention 与指定时间掩码匹配，通过梯度更新 latent。</td><td>免训练；相关性达到阈值后结束当前去噪步内的优化。</td><td>时间目标与阈值停止已有先例。当前从参考动作估计帧级偏差，并选择参考视频读取区间。</td></tr>
<tr><td><a href="https://arxiv.org/html/2610.13369v1">Information Bottleneck CFG</a> [9]</td><td>条件与无条件 score 的平方范数差，估计条件引导收益。</td><td>首次越过阈值后，为余下采样开启 CFG；免训练。</td><td>数据依赖的启动时机已有先例。当前使用局部动作观测，并逐步决定启停。</td></tr>
</tbody></table></div>
<p><a href="https://arxiv.org/html/2412.07750v3">Motion by Queries</a> [5] 也使用对应帧 K/V 共享及当前预测掩码。当前方案的研究重点是：<strong>用具有物理时间单位、能够识别测量不足的动作偏差，自动决定参考读取的作用区间与启停</strong>。动态引导和注意力重分配各有先例，方法贡献将通过组件消融与同任务比较进一步界定。</p>
<p>另外，<a href="https://arxiv.org/html/2607.11644v1">Motion4Motion</a> [6] 按运动轨迹重写附加 K 的 RoPE，并拼接目标锚点 K/V；<a href="https://arxiv.org/html/2506.22868v1">STR-Match</a> [7] 以时空 Attention 关联匹配驱动 latent 优化。它们也是进一步设计位置编码或内部 Attention 观测量时需要比较的工作。</p>
</section>

<section id="method"><h2>2　方法</h2>
<h3>2.1　区分两条时间轴</h3><p>物理帧 <em>f</em> 表示动作在视频中的时刻；去噪索引 <em>n</em> 表示推理进度。本轮设置为 141 帧、24 fps、20 次更新。例如，“在去噪索引 4 引导视频第 44–59 帧”包含两个独立选择。视频帧到 latent 时间槽按 H3 的实际时间压缩映射换算。</p>
<figure>''' + method + '''<figcaption>图 1　方法结构。上：在 RoPE 之后、输出投影之前修改 Attention 输出。下：每个去噪步先测量当前预测，按动作偏差决定是否重算时序引导预测，再更新采样状态。修改范围限定所选时间槽内的 query，后续网络传播可影响其他时刻。</figcaption></figure>
<h3>2.2　自动定位动作偏差与选择引导时机</h3><p>先提取参考视频姿态。每个去噪步，将模型的 clean 预测经 VAE 解码，使用冻结的 DWPose 估计姿态。随后遍历长 16 / 32 帧、间隔 4 帧的区间，比较左右手臂的方向变化，共得到 186 个重叠描述。当前实现以手臂时序作为动作偏差的观测量。</p>
<p>每个区间在 ±24 帧内寻找动作匹配。两种姿态置信阈值（0.3 / 0.5）均测得超过 2 帧的延后、估计差不超过 2 帧，并通过有效帧覆盖率与误差收益筛选后，形成候选区间。将重叠候选合并，每组保留证据最强的一项；当相邻去噪步持续发现同一部位的偏差时启动引导。候选数量由当前视频与预测状态决定。</p>
<p>当前控制器响应<strong>持续延后</strong>。延后证据消失或测量不足时，下一步使用原模型预测；“已对齐”与“无法判断（UNKNOWN）”分别记录。提前、遮挡和其他形变保留在评价中，供后续扩展控制策略。</p>
<h3>2.3　保持参考总权重，重新分配时间读取</h3><p>对每个 query 与 Attention head，令 <em>m</em><sub>ref</sub> 为参考视频 key 的总注意力权重，<em>O</em><sub>ref</sub> 为参考组内部归一化的加权输出，<em>O</em><sub>same_ref</sub> 为对应时间槽内归一化的加权输出。对选定视频区间的画布 query，在 RoPE 之后、输出投影 W<sub>O</sub> 之前计算：</p>
<div class="equation"><span class="eqno">(1)</span>O′ = O + α m<sub>ref</sub> (O<sub>same_ref</sub> − O<sub>ref</sub>)</div>
<p>当前取 α = 1、时间半径为 0，在全部 50 层中修改所选时间槽的所有空间 query。式（1）在理想实数下保持参考视频的总权重，将组内读取集中到对应时间槽；代码以 FP32 构造修正。它与带归一化补偿的 logit 重加权等价，研究重点在其动作偏差控制规则及实际效果。</p>
<h3>2.4　同输入重算，采样只更新一次</h3><p>关闭引导时采用原模型预测 <em>y</em><sub>N</sub>；开启时，以相同 <em>x</em><sub>n</sub>、σ<sub>n</sub>、条件和随机状态计算时序引导预测 <em>y</em><sub>G</sub>。选定 <em>y</em><sub>n</sub> 后执行一次 Euler 更新：</p>
<div class="equation"><span class="eqno">(2)</span>x<sub>n+1</sub> = (1 − β<sub>n</sub>) x<sub>n</sub> + β<sub>n</sub> y<sub>n</sub>,　β<sub>n</sub> = 1 − σ<sub>n+1</sub> / σ<sub>n</sub></div>
<p>共 K 步开启时，需要 20 + K 次模型预测（NFE）和 20 次 Euler 更新。引导结果进入下一采样状态，下一步再测量其动作偏差。推理耗时另行记录 VAE 解码与姿态计算开销。</p>
</section>

<section id="experiments"><h2>3　已完成实验</h2><h3>3.1　设置与结果口径</h3><p>实验采用 MiniMax H3 角色替换，1312 × 736、141 帧、24 fps，20 步 Euler、CFG = 1。组内固定源片、角色、种子、模型和推理配置，检查首次干预前的预测是否一致。当前试验使用既定加速实现，关闭 Turbo LoRA。</p>
<p>下表报告所选动作段内<strong>手臂方向拟合的时间差</strong>，依次对应置信阈值 0.3 / 0.5。正值表示延后，负值表示提前；24 帧为 1 秒。以下为已见开发样例，重叠区间的统计按同一视频内的描述解释。</p>
<div class="table-wrap"><table><thead><tr><th>视频</th><th>评价帧段</th><th>普通编辑</th><th>自动选择</th><th>人工 / 固定参照</th><th>自动引导次数 / NFE</th></tr></thead><tbody>''' + experiment_rows + '''</tbody></table></div>
<p class="note">表 1　单位：帧。前三行测量两侧手臂方向，球场行测量左臂；该片段自动版的两侧手臂合并时间差为 UNKNOWN。UNKNOWN 表示测量不足。05 与床边片段的人工参照使用人工指定的视频范围及固定去噪区间；40372 的固定参照作用于全片。</p>
<p>前三个动作段的时序均得到改善，自动选择的效果接近已有人工或固定参照。球场片段的左臂延后减少，人工版在该动作段仍更接近参考。视频中仍有手形、动作幅度和身体形状差异；床边视频后段仍拟合提前约 3–5 帧。</p>
'''
body += media(R33/'media/full_comparison.mp4',2,'动作片段05：完整逐帧对照','从左到右：参考、普通编辑、固定连续引导、自动选择、较晚区间引导。各列显示同一物理时刻；可切换 0.5× 播放观察动作差异。',R33/'media/frame055_comparison.png')
body += media(R34/'analysis/media/all_methods/fixed_clip_comparison.mp4',3,'棚内舞蹈40372：动作片段对照','从左到右：参考、普通编辑、固定连续引导、自动选择、固定单次全片引导。视频为动作片段，量化同时覆盖完整 141 帧。',R34/'analysis/media/all_methods/frame070_comparison.png')
body += media(OLD_PRESENTATION/'assets_r35/full_comparison.mp4',4,'床边舞蹈：自动选择与人工选择','从左到右：参考、普通编辑、人工选择、自动选择。展示完整 141 帧。')
body += '''<h3>3.2　正常样例与执行成本</h3><p>同源片、不同种子的正常样例，20 步均保持零干预，最终音视频 latent 与普通编辑精确相同。解码后的 RGB 存在细微差异（MAE 0.8624 / 255，PSNR 44.94 dB），来源待查。新增绿背景手势视频的普通编辑整体对齐，正用来检验自动方法对正常样例的保护。</p>
<p>床边自动版执行 23 NFE、20 次更新，总任务约 ''' + f'{summary35["efficiency"]["job_wall_seconds"]/60:.1f}' + ''' 分钟，其中观察器记录约 ''' + f'{summary35["efficiency"]["observer_wall_seconds"]/60:.1f}' + ''' 分钟，包含在总耗时中。全程解码和姿态测量的成本较高，后续将研究更轻量的观测量。</p>
<h3>3.3　新增球场片段：自动选择与人工参照</h3><p>人工参照作用于视频第 56–127 帧、去噪索引 6–14。自动版在索引 4、11、12、13 启动，分别选择第 68–83、56–71、64–79、64–79 帧。第 64–95 帧内，左臂时间差由 +15 降至 +3 帧，人工版为 −1 帧；自动版两侧手臂合并的时间差仍为 UNKNOWN。</p><p>三种结果在共同可见的骨骼位置上计算同帧方向误差，越小越好。该动作段人工版更接近参考；完整视频中自动版与人工版误差接近。置信阈值 0.5 下，该动作段的共同可见率为 78.9%，低于预设 80% 要求，保留 UNKNOWN。</p>
'''
body += '<div class="table-wrap"><table><thead><tr><th>评价范围</th><th>置信阈值</th><th>共同可见率</th><th>普通编辑</th><th>自动选择</th><th>人工选择</th></tr></thead><tbody>' + ''.join(paired_error_rows) + '</tbody></table></div>'
body += media(R41_MEDIA/'comparison_141frames.mp4',5,'球场片段：自动选择与人工参照','从左到右：参考、普通编辑、自动选择、人工选择。完整 141 帧；第 72 帧人工版站姿更接近参考，第 96 帧两种引导均较普通编辑接近。',R41_MEDIA/'frame072.png')
body += '<details><summary>查看同组第 96 帧</summary><div class="frame"><img alt="球场四组第96帧对照" src="' + embed(R41_MEDIA/'frame096.png','image/png') + '"></div></details>'
body += '<p class="note">球场自动版使用 24 NFE，总任务约 105.6 分钟，其中解码和姿态观察约 48.5 分钟；人工版使用 29 NFE，约 39.5 分钟。两者记录了实际执行成本，完整视频的动作质量还需结合连续播放判断。</p>'
body += '''</section><section id="ablation"><h2>4　消融与机制检查</h2><h3>4.1　改变作用区间与引导次数</h3><div class="table-wrap"><table><thead><tr><th>视频</th><th>实际干预安排</th><th>相同评价段时间差</th><th>NFE</th></tr></thead><tbody>''' + ablation_rows + '''</tbody></table></div>
<p>05 中，将同一次引导移到较晚区间，较早动作的时间差仍降至约 +1 帧。40372 中，保持自动版的四个去噪索引、将范围扩至全片，也得到约 0 帧。这提示局部 Attention 改动会沿后续层和采样轨迹传播，局部定位的额外收益需要进一步分离。</p>
<p>四次全片引导使用已完成自动轨迹的时刻，属于事后消融。它匹配次数与 NFE，同时增加受影响的 query 数量和修正量；后续需控制这些因素，比较局部作用的质量与成本收益。</p>
<p>在已知正常样例上，索引 4 的一次全片引导也保留了接近的整体时序；全片同帧方向误差从 0.169 变为 0.171（阈值 0.3），从 0.152 变为 0.154（阈值 0.5）。这个结果支持继续比较简单固定策略，并检验自动选择在更多正常样例上的实际收益。</p>
<h3>4.2　相邻去噪步的持续证据</h3><p>在四条已存轨迹、共 80 份观察结果上重放决策，移除相邻去噪步的持续要求，其他条件保持一致：</p>
<div class="table-wrap"><table><thead><tr><th>记录轨迹</th><th>实际引导次数</th><th>移除持续要求后的决定次数</th><th>新增开启的去噪索引</th></tr></thead><tbody>''' + persistence_rows + '''</tbody></table></div>
<p class="note">表 3　离线重放显示，持续要求减少了触发次数。生成效果需重新推理验证；正常样例两种规则均为零次。</p>
</section>
<section id="limits"><h2>5　贡献候选与待验证部分</h2><p><strong>当前进展：</strong>自动扫描动作偏差、决定引导范围和启停的流程已运行完成；四个开发样例的所检动作段得到改善，球场样例保留左臂残余延后及两侧手臂 UNKNOWN；正常样例保持零干预。生成结果、控制记录与条件数据已归档。</p>
<p><strong>适用范围：</strong>当前采用固定开发阈值，主要测量手臂延后；遮挡、姿态识别误差与形变可能影响判断。停止记录需区分已对齐与测量不足，用户主动修改动作的豁免机制尚待实现。扩大评估时需同时覆盖成功编辑、错误编辑、不同角色与视频来源。</p>
<p><strong>创新验证：</strong>动作偏差驱动的自动决策是当前候选贡献。后续将用组件消融确定各设计的收益，并在相同编辑任务、预算和质量口径下比较近邻方法。当前阶段已完成文献与实现核对，统一重跑比较仍在计划中。</p>
</section>
<section id="conclusion"><h2>6　结论</h2><p>当前实验表明，自动选择引导时间与视频区间可以缓解所检查片段的动作延后。部分动作段接近人工选择，新增球场样例在全片同帧误差上接近人工结果，局部仍有差距。接下来将检验更多样例中的可重复性、正常视频保持与完整成片质量，同时分离局部作用和持续检测的贡献。</p></section>

<section id="references"><h2>参考文献与复核范围</h2><ol class="refs">
<li><a href="https://arxiv.org/html/2609.11507v1">Harnessing Intrinsic Subject-Aware Attention for Controllable Multi-Subject Video Generation</a>. DIAL，arXiv:2609.11507v1，§3.3 / Algorithm 1；Phase II 训练范围见 §3.4。</li>
<li><a href="https://arxiv.org/html/2506.19348v2">When Distillation Breaks Motion Control: Restoring Generative Trajectories for Fast Video Generators</a>. MotionEcho，arXiv:2506.19348v2，§3.3–3.5。</li>
<li><a href="https://arxiv.org/html/2603.06289v2">FlowMotion: Training-Free Flow Guidance for Video Motion Transfer</a>. arXiv:2603.06289v2；<a href="https://github.com/HKUST-LongGroup/FlowMotion">官方代码</a>，核验提交 f5b4dcf。</li>
<li><a href="https://arxiv.org/html/2506.05046v2">FlowDirector: Training-Free Flow Steering for Precise Text-to-Video Editing</a>. arXiv:2506.05046v2；<a href="https://github.com/Westlake-AGI-Lab/FlowDirector">官方仓库</a> V1 代码核验提交 cecd56e。V2 论文结论与 V1 实现不混用。</li>
<li><a href="https://arxiv.org/html/2412.07750v3">Motion by Queries</a>. arXiv:2412.07750v3，Appendix B.10，对应帧 K/V 共享与当前预测掩码。</li>
<li><a href="https://arxiv.org/html/2607.11644v1">Motion4Motion: Motion Transfer Across Subjects at Inference</a>. SIGGRAPH 2026，arXiv:2607.11644v1，§3.2–3.3，Algorithm 1。</li>
<li><a href="https://arxiv.org/html/2506.22868v1">STR-Match: Matching SpatioTemporal Relevance Score for Training-Free Video Editing</a>. arXiv:2506.22868v1，§4.1–4.2。</li>
<li><a href="https://arxiv.org/html/2510.02226v1">TempoControl: Temporal Attention Guidance for Text-to-Video Models</a>. arXiv:2510.02226v1，§4，Algorithm 1；官方代码核验提交 ac28c44。</li>
<li><a href="https://arxiv.org/html/2610.13369v1">Opening the Black Box of Classifier-Free Guidance via Information Bottleneck</a>. arXiv:2610.13369v1，§4，Eq. 26–27，Algorithm 1。</li>
</ol><p class="small">文献核验截至2026年10月17日。正文中方法对比依据所列版本，不代表穷尽检索或同环境性能排名。论文链接需要联网；本页视频、截图与方法图已完整内嵌。</p></section>
'''
evidence['assets'] = assets
evidence['selected_source_count'] = len(sources)
body += '<details><summary>展开本稿证据索引与 SHA-256</summary><p class="small">下列本地路径用于作者复核，不参与页面加载。收件人只需当前 HTML；所有展示素材已经嵌入。证据 JSON 也以 application/json 保存在本文件内。</p><ol class="evidence-list">'
for record in sources:
    body += '<li><strong>' + escape(record['label']) + '</strong><br>' + escape(record['path']) + '<br>SHA-256: ' + record['sha256'] + '</li>'
body += '</ol></details><footer class="footer">研究进展稿 · 图像、SVG 与 MP4 均已内嵌；复制本 HTML 即可分享。建议使用现代浏览器打开。</footer></article>'
body += '<script type="application/json" id="evidence-json">' + json.dumps(evidence, ensure_ascii=False).replace('<','\\u003c') + '</script>'
body += '''<script>document.querySelectorAll('[data-rate]').forEach(button=>button.addEventListener('click',()=>{const video=button.closest('figure').querySelector('video');video.playbackRate=Number(button.dataset.rate);}));</script></body></html>'''
OUT.write_text(body)
(HERE/'paper.html').write_text(body)
(HERE/'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n')
manifest = {'schema':'h3-paper-progress-build-v1','html':str(OUT),'html_sha256':sha(OUT),'html_bytes':OUT.stat().st_size,'builder_sha256':sha(Path(__file__)),'method_svg_sha256':sha(HERE/'assets/method.svg'),'evidence_sha256':sha(HERE/'evidence.json'),'assets':assets,'source_files':sources,'browser_layout_verified':False,'browser_playback_verified':False,'status':'content_and_embedded_assets_reviewed_browser_unassessed'}
(HERE/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:manifest[k] for k in ['html','html_sha256','html_bytes','status']},ensure_ascii=False))
