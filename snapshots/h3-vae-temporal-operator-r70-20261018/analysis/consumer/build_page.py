import base64
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
MEDIA=ROOT/'visual_attempt1'

def data(name,mime):
    return 'data:'+mime+';base64,'+base64.b64encode((MEDIA/name).read_bytes()).decode()

sections=[]
for key,title,description in [
    ('identity','1. VAE 再编码重建','相同视频再经过一次 VAE encode→decode，作为重建误差参照。'),
    ('shift3','2. 固定提前 125 ms','每个输出时刻选择晚 3 个 RGB 帧的内容。三列使用同一时间映射。'),
    ('offline_mapping','3. 已冻结的非均匀时间映射','将 final Native 的事后拟合映射应用于 index6 的 x0，只测试时间重排算子。')]:
    sections.append('<section><h2>'+title+'</h2><p>'+description+'</p><video controls playsinline preload="metadata" src="'+data(key+'_comparison.mp4','video/mp4')+'"></video><details><summary>固定六时刻：0、0.5、1、1.5、2、2.5 秒</summary><img src="'+data(key+'_six_times.png','image/png')+'" alt="'+title+'固定六时刻对照"></details></section>')
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>H3 VAE 时间重排算子诊断</title><style>
body{margin:0;background:#f5f5f2;color:#181818;font:17px/1.75 system-ui,-apple-system,sans-serif}main{max-width:1500px;margin:auto;padding:40px 24px}h1{font-size:32px;margin:0 0 12px}h2{font-size:23px;margin:0 0 10px}p{max-width:1050px;margin:10px 0}section{background:white;padding:24px;margin:24px 0;border:1px solid #ddd}video,img{display:block;width:100%;height:auto;background:black}video{margin:18px 0}details{margin-top:16px}summary{cursor:pointer;padding:8px 0}table{border-collapse:collapse;width:100%;max-width:1050px}th,td{padding:9px 13px;border-bottom:1px solid #ddd;text-align:left}small{color:#555}code{background:#eee;padding:2px 5px}a{color:#2354a2}</style><main>
<h1>H3 VAE 时间重排算子诊断</h1><p>直接对 latent 的时间轴做线性插值，在本例产生了手臂叠影、轮廓模糊及亮度变化。先在 RGB 中完成相同重排，再经原 VAE 编码、解码，更接近目标画面。</p><p><small>R70 · 2026-10-18 · fitness Native index6 x0 · 158 帧 / 24 fps · 3 encode + 6 decode · 0 DiT</small></p>
<section><h2>比较的三条路径</h2><p>令 <code>x=D(z)</code>。目标画面是 <code>Rφ(x)</code>；比较 <code>D(Lφ(z))</code> 与 <code>D(E(Rφ(x)))</code>。RGB 和 latent 均采用线性插值，latent 使用 H3 的非均匀输出 bin 中心坐标。所有路径输入的 z、VAE 和归一化流程一致。</p>
<p>以下数值是相对目标画面的平均绝对 RGB 误差，像素范围为 0–1。只统计各路径共同有效的原视频区域。</p><table><thead><tr><th>时间映射</th><th>有效帧数</th><th>RGB 重排后再编码</th><th>latent 直接重排</th></tr></thead><tbody><tr><td>identity</td><td>147</td><td>0.009279</td><td>—</td></tr><tr><td>固定 +3 RGB 帧</td><td>144</td><td>0.009917</td><td>0.019741</td></tr><tr><td>已冻结的离线映射</td><td>147</td><td>0.009794</td><td>0.019419</td></tr></tbody></table><p>latent 路径的误差约为 RGB 路径的两倍；截图可见局部结构变化。此处衡量的是重排算子和重建差异，动作时间改善需要另行评测。离线映射使用了 final Native 信息。</p></section>
'''+''.join(sections)+'''<section><h2>观察与适用范围</h2><p>离线映射在 1.0、1.5 秒的 latent 路径中出现明显双臂叠影。固定提前 125 ms 也出现臂甲模糊，以及 17 帧块邻接位置的面部和胸甲亮度变化。identity 再编码主要呈现较轻的重建差异。</p><p>本轮完成 8 条视频的 SHA、完整帧数和坐标核验，全部采用原 VAE 路径，未触发 OOM fallback。基础 D(z) 与此前 index6 解码的 float RGB 逐字节一致。实际总耗时 12 分 57 秒，显存峰值 reserved 为 7.90 GiB。</p><p>上述证据支持继续检验 RGB 重排再编码这个执行路径。后续去噪能否保留重排后的动作、在线选取时间映射的方式，尚未由本轮测试回答。</p></section></main></html>'''
(ROOT/'index.html').write_text(page)
assert page.count('<video ')==3 and page.count('data:video/mp4;base64,')==3 and page.count('<img ')==3
print(ROOT/'index.html',len(page))
