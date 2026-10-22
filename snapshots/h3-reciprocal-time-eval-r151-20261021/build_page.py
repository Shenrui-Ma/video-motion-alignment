"""Create a self-contained R151 research page from verified local evidence."""
import argparse
import base64
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def esc(value):
    return html.escape(str(value))


def asset(record):
    path = Path(record["file"])
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != record["sha256"]:
        raise ValueError(f"Changed media: {path}")
    mime = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".png": "image/png"}[path.suffix]
    return f"data:{mime};base64," + base64.b64encode(content).decode()


def build(final=False):
    manifest = read(ROOT / "EVALUATION_MANIFEST.json")
    findings_path = ROOT / "FINDINGS.json"
    findings = read(findings_path) if findings_path.exists() else {
        "summary": "三组已有普通编辑与正向引导对照已绑定；反向与双向引导正在实验。",
        "conclusion": "新增结果完成后，按动作时间与编辑质量评估双向约束的增量。",
    }
    if final and not findings.get("complete"):
        raise ValueError("Final page requires completed findings.")
    cards = []
    for case in manifest["cases"]:
        sid = case["source_id"]
        presentation_path = ROOT / "overview" / sid / "PRESENTATION.json"
        review_path = ROOT / "reviews" / f"{sid}.json"
        if final and (not presentation_path.exists() or not review_path.exists()):
            raise ValueError(f"Missing completed comparison: {sid}")
        media = '<p class="pending">新增视频正在生成。</p>'
        if presentation_path.exists():
            presentation = read(presentation_path)
            if presentation["roles"] != manifest["roles"] or not presentation["full_decode_passed"]:
                raise ValueError("Wrong comparison order or incomplete media verification.")
            shots = "".join(
                f'<figure><div class="wide"><img src="{asset(s)}" alt="同帧五条件对比"></div>'
                f'<figcaption>第 {s["frame"]} 帧 · {s["frame"]/case["geometry"]["fps"]:.3f} 秒</figcaption></figure>'
                for s in presentation["screenshots"]
            )
            video = asset(presentation["video"])
            media = (shots + f'<div class="wide"><video controls preload="metadata" src="{video}"></video></div>'
                     '<p class="caption">参考视频 · 普通编辑 · 仅正向引导 · 仅反向引导 · 双向引导</p>'
                     f'<a class="download" href="{video}" download="R151_{esc(sid)}_五条件.mp4">下载这组对比视频</a>')
        report = ""
        if review_path.exists():
            review = read(review_path)
            rows = "".join(
                "<tr>" + "".join(f"<td>{esc(row[k])}</td>" for k in (
                    "condition", "edit_quality", "timing", "MF", "sampling_seconds")) + "</tr>"
                for row in review["table"]
            )
            report = (f'<p class="finding">{esc(review["summary"])}</p>'
                      '<div class="table-scroll"><table><thead><tr><th>条件</th><th>编辑完成情况</th>'
                      '<th>动作时间</th><th>MF ↑</th><th>采样秒数</th></tr></thead>'
                      f'<tbody>{rows}</tbody></table></div>')
            weak_path = ROOT / "reviews" / sid / "EXISTING_WEAK_GUIDANCE.json"
            if weak_path.exists():
                weak = read(weak_path)
                evidence = weak["evidence"]
                if hashlib.sha256(Path(evidence["file"]).read_bytes()).hexdigest() != evidence["sha256"]:
                    raise ValueError("Existing schedule comparison changed.")
                report += (
                    '<p class="caption">同一素材的区间实验中，全局弱引导采用 α=0.25、'
                    '第 1–20 步及全片时间范围，完成眼镜编辑并保持构图，'
                    f'平均时间误差 {weak["mean_absolute_midpoint_error_frames"]:.1f} 帧，'
                    f'MF {weak["MF"]:.4f}。该结果用于比较完整引导配置；'
                    '上表四条件用于比较第 1–9 步内的正向、反向及组合。</p>')
        reference = "无参考图片"
        if case.get("reference_image"):
            reference = f'<img class="portrait" src="{asset(case["reference_image"])}" alt="身份参考图">'
        cards.append(
            f'<section class="case" id="{esc(sid)}"><h3>{esc(case["title"])}</h3>'
            f'<p class="caption">{esc(case["dataset"])} · {case["geometry"]["valid_frames"]} 有效帧 · 24 fps</p>'
            f'{media}{report}<details><summary>提示词与参考图片</summary><p>{reference}</p>'
            f'<pre>{esc(case["prompt"])}</pre></details></section>')

    document = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>双向时间引导：机制与三组对照 · R151</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f8;color:#17243a;font:17px/1.7 system-ui,-apple-system,sans-serif}
main{max-width:1280px;margin:32px auto;padding:42px;background:white;border:1px solid #dde3eb}
h1{font-size:34px;line-height:1.3;margin:0 0 16px}h2{font-size:25px;margin:38px 0 14px}h3{font-size:22px;margin:12px 0}
p{margin:12px 0}.lead{font-size:19px}.caption,figcaption{font-size:14px;color:#596b80}
.method{width:100%;height:auto}.formula{font:22px/1.9 Georgia,serif;background:#f5f8fc;padding:14px 20px;overflow:auto}
.case{border-top:1px solid #cad5e2;margin-top:32px;padding-top:24px}
.wide{overflow-x:auto;background:#000;border-radius:4px}.wide img,.wide video{display:block;width:100%;min-width:1920px}
figure{margin:18px 0}.finding{border-left:3px solid #287e72;padding-left:15px}.table-scroll{overflow:auto}
table{width:100%;border-collapse:collapse;font-size:15px}th,td{text-align:left;padding:10px 12px;border-bottom:1px solid #dce3ec}
th{background:#eef3f8}details{margin:16px 0;padding:12px;background:#f6f8fa}summary{cursor:pointer}
pre{white-space:pre-wrap;word-break:break-word;font:14px/1.6 ui-monospace,monospace}.portrait{max-width:160px;max-height:190px}
a{color:#215f9b}.download{font-size:15px}.pending{padding:24px;background:#f2f5f8}
@media(max-width:700px){main{margin:0;padding:22px}h1{font-size:28px}}
</style><main>
<h1>双向时间引导：机制与三组对照</h1>
<p class="caption">MiniMax H3 · Training-free · R151</p>
<p class="lead">__SUMMARY__</p>
<h2>1. 方法</h2>
<p>H3 将参考视频和生成视频的 token 放在单流 DiT 中联合计算 Attention。
原有引导作用于生成视频 query：保持它分给参考视频的注意力概率总和，
将这部分 V 加权结果替换为同一物理时间 bin 内的结果。
本轮增加相反方向的约束，让参考视频 query 也按对应时间读取生成视频。</p>
__FIGURE__
<p>两处改动均位于每个 DiT block 的 Attention head 输出，随后经过 out_proj、残差连接和 FFN。
箭头表示 query 读取另一视频 K/V 的方向。图片、文字等 token 仍参与原 Joint Attention。
两个方向使用同一次前向的原 Q、K、V 和原 softmax 概率。</p>
<div class="formula">
O′<sub>T</sub> = O<sub>T</sub> + α m<sub>R</sub>(μ<sub>R,same</sub> − μ<sub>R,all</sub>)<br>
O′<sub>R</sub> = O<sub>R</sub> + β m<sub>T</sub>(μ<sub>T,same</sub> − μ<sub>T,all</sub>)
</div>
<p>m 是原 Joint Attention 分给对应视频组的概率总和；μ 是组内归一化后的 V 加权和。
same 仅包含同时间 bin 的空间 token，all 包含该视频的所有 token。
α=1 或 β=1 表示将对应视频组的概率全部分配到同时间 bin，组外概率保持原值。</p>
<p>这里保持的是本次 Attention、每个 query 和 head 的组概率。
更新后的 hidden states 会进入后续层，后续层的 Q、K、V 和组概率也会随之改变。
因此两种方向都可能影响动作、身份和构图，实验分别检查这些结果。</p>
<details><summary>Attention 概率的等价形式</summary>
<p>对生成视频中的一个 query i，记原概率为 A<sub>ij</sub>，
R 为全部参考视频 keys，R<sub>τ</sub> 为对应时间 bin 的 keys。
在 R<sub>τ</sub> 内重新归一化原 logits，得到概率 B<sub>ij</sub>；
R<sub>τ</sub> 外的 B 为 0。修正为：</p>
<div class="formula">A′<sub>ij</sub> = (1−α)A<sub>ij</sub> + αm<sub>R</sub>B<sub>ij</sub>，j ∈ R<br>
Σ<sub>j∈R</sub>A′<sub>ij</sub> = m<sub>R</sub></div>
<p>R 之外沿用原概率。反向项交换参考与生成视频的角色，使用 β。
代码通过两项 Attention 输出之差实现这次替换，计算时复用原 Q、K、V。</p></details>
<p>待验证的机制是：限制参考 hidden states 接收跨时间的目标特征，
使后续 DiT 层保留更清楚的时间对应关系。新增反向约束也会接收带噪目标信息，
因此实验同时检查动作时间、身份编辑和重影。</p>
<p>参考视频的初始 latent 在各采样步保持固定；其 hidden states 会在一次 DiT
前向的各层之间更新。反向引导作用于这些 hidden states，随后经下一层 Attention
影响生成视频。</p>
<p>这个改动针对跨两层的传播路径：第 ℓ 层中，时刻 τ 的参考 token
可以接收其他时刻 t′ 的生成特征；第 ℓ+1 层中，生成 token 即使只读取时刻 τ
的参考，也会间接收到前一层混入的 t′ 特征。双向时间约束同时限制这两次跨视频
Attention，检验这种间接传播是否影响动作对齐。</p>
<h2>2. 与已有工作的关系</h2>
<p><a href="https://arxiv.org/html/2609.11507v1#S3.SS3">DIAL</a> 的推理阶段
利用上一采样步的主体 Attention 图，向生成视频 query 到主体参考 keys 的
logits 加偏置，调整主体参考的影响强度。本轮约束参考视频与生成视频的时间对应，
并在每个方向分别保持原跨视频组概率，重新分配组内不同时间的概率。</p>
<p><a href="https://arxiv.org/html/2601.14250v1">OmniTransfer</a> 的非对称 Attention
限制参考分支读取目标分支；<a href="https://arxiv.org/html/2609.11638v1">Vidu S2</a>
训练了帧对应的视频交互；
<a href="https://arxiv.org/abs/2609.27901">RecCAR</a> 使用双向对应关系的 KL 约束。
<a href="https://arxiv.org/html/2508.09983v1">Story2Board</a> 在推理中根据双向
Attention 匹配选择对应位置，并混合参考与目标的 V。
本轮在已训练 H3 的推理中组合两个方向的同时间条件化，并分别保持原跨视频组概率。
反向同时间项已在我们之前的 R25 中单独测试；本轮检验它与正向引导的组合。</p>
<h2>3. 实验</h2>
<p>三组样例各比较四种编辑条件：(α,β)=(0,0)、(1,0)、(0,1)、(1,1)。
后两种是本轮新增推理。使用匹配的原提示词、种子、初始噪声和条件缓存；
在 20 步采样的第 1–9 步应用引导，物理动作窗口沿用各自已有对照。</p>
<p>视频时间范围分别为：机舱第 0–97 帧、饮酒第 0–104 帧、Sam 舞蹈第 50–65 帧。
模型按 latent 时间 bin 操作；Sam 对应的完整 bin 覆盖第 47–67 帧。
这些视频帧位置与上述去噪采样步是两个独立坐标。</p>
<p>动作时间按同一事件在原片与编辑成片中的帧位置比较，正值表示延后。
机舱与饮酒的事件区间由逐帧检查确定，时间误差取区间中点之差的绝对值，
再对三个事件求平均。Sam 舞蹈沿用第 50–65 帧的手臂方向序列匹配，
并复核另外三个动作时间段；测量在成片后进行。
视频为 24 fps，一帧约 42 毫秒。各列按相同帧编号并排显示。
MF 沿用 IVEBench 的 Motion Fidelity 实现，三组采用相同评测口径。
表内另列编辑完成情况，便于同时判断动作对齐与编辑质量。耗时记录同时标注当次服务器。
共享 GPU 的其他任务会影响耗时；Sam 双向版本生成期间，共享负载下降，后半程采样变快。</p>
__CASES__
<h2>4. 结果</h2><p>__CONCLUSION__</p>
</main></html>"""
    document = (document.replace("__SUMMARY__", esc(findings["summary"]))
                .replace("__FIGURE__", (ROOT / "method.svg").read_text().replace(
                    '<svg ', '<svg class="method" ', 1))
                .replace("__CASES__", "".join(cards))
                .replace("__CONCLUSION__", esc(findings["conclusion"])))
    output = ROOT / "index.html"
    output.write_text(document)
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--final", action="store_true")
    build(parser.parse_args().final)
