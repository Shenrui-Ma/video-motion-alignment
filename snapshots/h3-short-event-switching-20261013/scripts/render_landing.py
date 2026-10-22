"""Make the local experiment landing page from archived evidence, not predictions."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
validation = json.loads((ROOT / 'analysis/archive_validation.json').read_text())
summary = validation['summary']
complete = (ROOT / 'analysis/final_conclusions.json').exists()
conclusions = json.loads((ROOT / 'analysis/final_conclusions.json').read_text()) if complete else {}
rows = []
names = {'06_anime_eye_insert': '动画：换成参考图人物',
         '05_real_megumi_v': '真人 Megumi：黑裙改红',
         '07_real_ary_v': '真人 Ary：白上衣改蓝'}
for key, title in names.items():
    links = ' '.join(f'<a href="review/index.html#{key}_s{s}">种子 {s} 对照</a>' for s in (1, 2))
    rows.append(f'<tr><td>{html.escape(title)}</td><td>{links}</td></tr>')
headline = conclusions.get('headline_zh', '实验进行中；这里展示已归档结果，尚未作整轮结论。')
report_link = '<a href="REPORT.txt">完整实验报告</a>' if (ROOT / 'REPORT.txt').exists() else ''
body = f'''<!doctype html><html lang="zh"><meta charset="utf-8">
<title>H3：连续动作切换中的短事件</title>
<style>body{{font:17px/1.65 system-ui,sans-serif;max-width:1100px;margin:auto;padding:32px;color:#17324b;background:#f7f9fc}}h1{{font-size:30px}}article{{background:white;padding:24px;border:1px solid #dbe4ee;border-radius:12px;margin:22px 0}}a{{color:#1465aa;margin-right:18px}}img,video{{max-width:100%}}td,th{{padding:14px;text-align:left;border-bottom:1px solid #e0e7ef}}table{{border-collapse:collapse;width:100%}}small{{color:#566b7c}}.lead{{font-size:21px}}code{{overflow-wrap:anywhere}}</style>
<h1>H3：连续动作切换中的短事件</h1>
<p class="lead">{html.escape(headline)}</p>
<article><b>已验证归档：{summary['fully_archived_formal_runs']} / {summary['planned_primary']} 条正式结果；{summary['valid_pairs']} / 6 个配对。</b>
<p>{report_link}<a href="review/index.html">全部视频、慢放与逐帧检查</a><a href="analysis/experiment_ledger.csv">运行记录 CSV</a></p>
<p>A：外观编辑并要求保留全部动作。B：在 A 上明确强调目标短动作、时间及前后次序。每组两个种子，A/B 实际初始噪声配对。页面与比较视频不自动判定科研成功。</p></article>
<article><h2>先看完整动作，再看局部</h2><table><tr><th>素材与任务</th><th>原片 / A / B 同步对照</th></tr>{''.join(rows)}</table>
<p>每段 141 帧、24 FPS、5.875 秒。0.25× 视频仅延长同一批帧的显示时间，不插帧。所有源视频与模型原始输出单独保留。</p>
<img src="analysis/source_event_map.png" alt="三段素材的完整短事件、核心姿态和语义采样位置">
<p>动画第一次短暂眼旁动作与后面较长的 V 手势分别检查。出现过相似手势不等于时间、时长和次序全部保留。</p></article>
<article><h2>证据和边界</h2><p>这是 3 段录像、同一种编舞、两种编辑任务的初筛。不能由此比较真人与动画域的难度，也不能估计一般失败率或定位架构因果。</p>
<p><a href="inputs/source_manifest.json">源素材、网址、目标与提示词</a><a href="configs/preregistered_plan.json">生成前固定的设计</a></p>
<p><a href="analysis/vae_gate_independent.json">实际输入 / VAE 回解检查</a><a href="analysis/archive_validation.json">配对与归档校验</a><a href="analysis/interpretation_cautions.json">结论解释边界</a></p>
<p><a href="configs/runtime_actual_provenance.json">运行环境证据</a><a href="analysis/int8_gpu_validation.json">INT8 运行时修复验证</a></p>
<small>推理内核的行分块修复属于工程兼容处理，不是本轮提出的科研方法。视觉结论来自可见条件标签的 AI 检查，需结合完整视频人工复核。</small></article></html>'''
(ROOT / 'START_HERE.html').write_text(body)
print(ROOT / 'START_HERE.html')
