#!/usr/bin/env python3
"""Time-coordinate and auxiliary-phase figures, using the source Figure primitives."""
from html import escape
import math
import re
from drawing import Figure, INK, MUTED, LINE, BLUE, PURPLE, ORANGE, TEAL, PALE, mix


def math_text(f, x, y, text, size=18, color=INK, weight=400, anchor="start", cls="math"):
    """SVG text with explicit subscripts/superscripts, retaining 16 px minimum."""
    fragments = []
    pos = 0
    for match in re.finditer(r"([_^])\{([^}]+)\}", text):
        fragments.append(escape(text[pos:match.start()]))
        shift = round(-size * .18 if match[1] == "_" else size * .36, 1)
        fragments.append(f'<tspan baseline-shift="{shift}px" font-size="{max(16, round(size * .72, 1))}">{escape(match[2])}</tspan>')
        pos = match.end()
    fragments.append(escape(text[pos:]))
    f.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}" class="{cls}" style="fill:{color}">{"".join(fragments)}</text>')


def label_text(f, x, y, text, size=18, **kw):
    renderer = math_text if "_{" in text or "^{" in text else f.text
    if renderer == math_text:
        renderer(f, x, y, text, size, **kw)
    else:
        renderer(x, y, text, size, **kw)


def label_box(f, x, y, w, h, title, lines=(), color=BLUE, size=18):
    f.rect(x, y, w, h, mix(color, .065), mix(color, .36), 6)
    if not lines:
        label_text(f, x + w / 2, y + h / 2 + 6, title, size, weight=600, anchor="middle")
    else:
        label_text(f, x + w / 2, y + 28, title, size, weight=600, anchor="middle")
        for i, line in enumerate(lines):
            label_text(f, x + w / 2, y + 53 + 24 * i, line, 16, color=MUTED, anchor="middle")


def grid(f, x, y, columns=4, rows=3, cell=18, color=BLUE):
    for r in range(rows):
        for c in range(columns):
            f.rect(x + c * cell, y + r * cell, cell - 2, cell - 2,
                   mix(color, .12 + .055 * (r * columns + c)), "none", 1)


def token_group(f, x, y, n=12, width=144, height=22, color=BLUE):
    cell = width / n
    for i in range(n):
        f.rect(x + i * cell, y, cell - 2, height,
               mix(color, .12 + .055 * i), "none", 2)


def figure_footer(f, text):
    f.line(48, f.height - 49, 1392, f.height - 49, LINE)
    f.text(48, f.height - 21, text, 16, color=MUTED)


def time_coordinates():
    f = Figure(1130, "两个独立坐标：视频时间与去噪步", 
               "视频时间决定读取哪一组参考 tokens；去噪步决定在哪次 DiT 前向启用输出修正。",
               "图 2  /  时间坐标与 token 映射")
    f.panel(48, 164, 1344, 414, "物理帧经 causal VAE 压缩，再展开每个 bin 的全部空间位置", "A")
    f.text(72, 252, "物理视频帧", 20, weight=600)
    f.text(72, 281, "示例：17 帧 → 5 个 bin", 17, color=MUTED)
    # The 1,4,4,4,4 group sizes express the physical-to-latent map, not token counts.
    start, step, fw = 425, 51, 43
    physical = [(0, 1), (1, 4), (5, 4), (9, 4), (13, 4)]
    centers = [432 + 202 * i for i in range(5)]
    for i in range(17):
        f.rect(start + i * step, 226, fw, 44, mix(BLUE, .14 + .05 * (i % 4)), "none", 3)
        f.text(start + i * step + fw / 2, 254, str(i), 16, anchor="middle")
    for b, (first, count) in enumerate(physical):
        left, right = start + first * step, start + (first + count - 1) * step + fw
        f.path(f"M{left} 278 V287 H{right} V278", BLUE, 1.5)
        mid = (left + right) / 2
        f.text(mid, 310, "1 帧" if count == 1 else "4 帧", 16, color=BLUE, anchor="middle")
        f.line(mid, 318, centers[b], 344, MUTED, 1.4, True)
    f.text(72, 376, "时间 latent bin", 20, weight=600)
    f.lines(72, 405, ["causal VAE 时间压缩", "每个 bin 保留完整 H′ × W′ 网格"], 17, 27, color=MUTED)
    for b, cx in enumerate(centers):
        f.text(cx, 366, f"bin {b}", 18, color=BLUE, weight=600, anchor="middle")
        grid(f, cx - 36, 380)
        f.line(cx, 440, cx, 475, MUTED, 1.5, True)
    f.text(72, 500, "patchify → flatten", 20, weight=600)
    f.text(72, 529, "按时间拼接空间 tokens", 17, color=MUTED)
    for b, cx in enumerate(centers):
        token_group(f, cx - 72, 487)
        f.text(cx, 538, f"R{b}：全部空间 tokens", 16, color=BLUE, anchor="middle")

    f.panel(48, 598, 1344, 213, "参考与生成视频按相对物理时间对应", "B")
    f.text(72, 684, "参考 R", 19, color=BLUE, weight=600)
    f.text(72, 771, "生成 T", 19, color=ORANGE, weight=600)
    for b in range(5):
        x = 180 + b * 142
        token_group(f, x, 663, n=6, width=108, height=25, color=BLUE)
        f.text(x + 54, 652, f"R{b}", 16, color=BLUE, anchor="middle")
        f.line(x + 54, 699, x + 54, 733, MUTED, 1.5, True)
        f.text(x + 69, 721, f"τ{b}", 16, color=MUTED)
        token_group(f, x, 745, n=6, width=108, height=25, color=ORANGE)
        f.text(x + 54, 795, f"T{b}", 16, color=ORANGE, anchor="middle")
    f.line(919, 642, 919, 789, LINE)
    f.lines(946, 665, ["τ 来自相对于视频起点的物理时间", "再通过 VAE 映射定位 latent bin。", "每个 Tτ query 可读取 Rτ 的全部空间。"], 18, 31)

    f.panel(48, 831, 1344, 228, "去噪步 k 只控制补丁开关与强度 α", "C")
    f.text(72, 911, "采样顺序 k", 18, color=MUTED)
    x0, cw = 458, 44
    for k in range(1, 21):
        f.text(x0 + (k - 1) * cw + 19, 911, k, 16, color=MUTED, anchor="middle")
    f.text(72, 953, "当前：全程弱引导", 20, color=BLUE, weight=600)
    f.text(300, 953, "α = 0.25", 19, color=BLUE)
    f.text(72, 1003, "对照：固定区间强引导", 20, color=TEAL, weight=600)
    f.text(327, 1003, "α = 1", 19, color=TEAL)
    for k in range(1, 21):
        x = x0 + (k - 1) * cw
        f.rect(x, 928, 38, 35, mix(BLUE, .28), "none", 3)
        f.rect(x, 978, 38, 35, mix(TEAL, .72) if 7 <= k <= 15 else PALE, LINE if not 7 <= k <= 15 else "none", 3)
    f.text(72, 1040, "τ 选参考时间位置；k 选去噪前向。两个坐标共同决定一次修正何时、对哪些 tokens 生效。", 18)
    figure_footer(f, "机制示意 · 上方帧跨度示例为 1、4、4、4、4；去噪调度独立于视频的物理时长。")
    return f.save("02_time_coordinates.svg")


def auxiliary_phase():
    f = Figure(1110, "辅助 RoPE 时间相位：在参考分支旋转 query", 
               "原始 Joint Attention 保持原路径；额外分支读取参考视频全部时间位置，并在 out_proj 之前加入替换量。",
               "图 5  /  参考分支时间相位对齐（已搁置）")
    f.panel(48, 164, 1344, 410, "主路径与两个参考分支：只在辅助分支使用旋转后的 q′", "A")
    main = [
        (72, 220, "原始 Q / K / V", ["Q/K 已经 RMSNorm", "及原始 MM-RoPE"], BLUE),
        (322, 240, "完整 Joint Attention", ["softmax(QK^{⊤} / √d)V", "保存 LSE_{all}"], BLUE),
        (592, 80, "O", [], BLUE),
        (722, 240, "输出修正 O → O′", ["加入 αm_{R} (z_{Δ} − z_{R})", "逐 query、逐 head"], ORANGE),
        (992, 140, "merge heads", ["合并各 head"], PURPLE),
        (1162, 206, "out_proj", ["gate → residual", "随后 RMSNorm / FFN"], PURPLE),
    ]
    for x, w, title, sub, color in main:
        label_box(f, x, 226, w, 103, title, sub, color, 18)
    for l, r in zip(main, main[1:]):
        f.line(l[0] + l[1] + 3, 276, r[0] - 7, 276, MUTED, 1.7, True)
    f.line(181, 330, 181, 376, MUTED, 1.5, True)
    label_box(f, 72, 382, 220, 167, "取原始张量的子集", ["q_{T} · K_{R} · V_{R}"], BLUE)
    for b in range(5):
        f.text(99 + 38 * b, 469, f"R{b}", 16, color=BLUE, anchor="middle")
        token_group(f, 83 + 38 * b, 482, n=2, width=34, height=23)
    f.text(182, 532, "所有参考时间 bins", 17, color=BLUE, anchor="middle")
    f.line(293, 413, 329, 413, MUTED, 1.6, True)
    f.path("M307 413 V508 H329", MUTED, 1.6, arrow=True)
    label_box(f, 338, 382, 365, 68, "z_{R} = softmax(q_{T} K_{R}^{⊤} / √d) V_{R}", ["原始 q_{T}；同时计算 LSE_{R}"], BLUE, 19)
    label_box(f, 738, 382, 166, 68, "z_{R} 与 m_{R}", ["保留参考概率总和"], BLUE)
    f.line(707, 414, 730, 414, MUTED, 1.6, True)
    label_box(f, 338, 480, 365, 68, "q′ = R_{time}(−Δ) q_{T}", ["z_{Δ} = softmax(q′ K_{R}^{⊤} / √d) V_{R}"], PURPLE, 20)
    label_box(f, 738, 480, 166, 68, "z_{Δ}", ["同一组 K_{R} / V_{R}"], PURPLE, 21)
    f.line(707, 512, 730, 512, MUTED, 1.6, True)
    f.path("M906 413 H928 V337", BLUE, 1.7, arrow=True)
    f.path("M906 512 H951 V337", PURPLE, 1.7, arrow=True)
    math_text(f, 984, 399, "m_{R} = exp(LSE_{R} − LSE_{all})", 21)
    f.lines(984, 435, ["沿用原 Joint softmax 中", "参考视频概率总和。", "q′ 的结果只进入输出修正分支。"], 17, 28, color=MUTED)

    f.panel(48, 596, 638, 440, "相位插入点：仅旋转时间维度的二维 pairs", "B")
    band = [(72, 226, "时间 pairs：旋转", PURPLE), (298, 182, "H pairs：原值", BLUE), (480, 182, "W pairs：原值", BLUE)]
    for x, w, title, color in band:
        f.rect(x, 655, w - 3, 43, mix(color, .15), "none", 3)
        f.text(x + (w - 3) / 2, 683, title, 17, color=color, weight=600, anchor="middle")
    f.text(72, 728, "一个时间 pair 的平面", 18, weight=600)
    cx, cy, radius = 211, 860, 91
    f.circle(cx, cy, radius, "none", LINE, 1.3)
    f.line(94, cy, 332, cy, LINE, 1.3, True)
    f.line(cx, 973, cx, 746, LINE, 1.3, True)
    a, b = math.radians(61), math.radians(18)
    x1, y1 = cx + radius * math.cos(a), cy - radius * math.sin(a)
    x2, y2 = cx + radius * math.cos(b), cy - radius * math.sin(b)
    f.line(cx, cy, x1, y1, BLUE, 3, True)
    f.line(cx, cy, x2, y2, PURPLE, 3, True)
    math_text(f, x1 + 3, y1 - 10, "q_{j}", 21, color=BLUE)
    math_text(f, x2 + 10, y2 + 4, "q′_{j}", 21, color=PURPLE)
    rr = 60
    ax, ay = cx + rr * math.cos(a), cy - rr * math.sin(a)
    bx, by = cx + rr * math.cos(b), cy - rr * math.sin(b)
    f.path(f"M{ax} {ay} A{rr} {rr} 0 0 1 {bx} {by}", PURPLE, 2, arrow=True)
    math_text(f, 274, 794, "−ω_{j}Δ", 18, color=PURPLE)
    f.text(331, 882, "x", 17, color=MUTED, cls="math")
    f.text(221, 754, "y", 17, color=MUTED, cls="math")
    f.text(372, 782, "每个时间 pair 独立旋转", 18)
    math_text(f, 372, 811, "转角由频率 ω_{j} 与 Δ 决定", 18, cls="")
    math_text(f, 372, 865, "θ′_{j} = θ_{j} − ω_{j}Δ", 24, color=PURPLE)
    math_text(f, 372, 910, "‖q′_{j}‖ = ‖q_{j}‖", 24)
    math_text(f, 372, 955, "q′_{H/W} = q_{H/W}", 24)
    f.text(72, 1008, "图中弧线展示相位旋转；角度与维度分区为机制示意。", 16, color=MUTED)

    f.panel(708, 596, 684, 440, "替换量、时间原点与读取域", "C")
    f.rect(732, 653, 636, 74, PALE, "none", 6)
    math_text(f, 1050, 684, "O′ = O + αm_{R} (z_{Δ} − z_{R})", 29, anchor="middle")
    f.text(1050, 714, "参考概率总和保持；参考组内部的加权特征改变", 17, color=MUTED, anchor="middle")
    math_text(f, 738, 767, "Δ = t_{生成,0} − t_{参考,0}", 25)
    f.lines(738, 798, ["Δ 是序列打包产生的 RoPE 时间原点差，", "由 PackedLayout 给出；单位为模型的位置坐标。", "物理动作时间由视频时间 τ 的映射单独描述。"], 18, 28)
    f.line(732, 875, 1368, 875, LINE)
    f.text(738, 909, "相位对齐：q′ 仍读取全部参考时间", 19, weight=600)
    f.rect(738, 938, 98, 42, mix(ORANGE, .16), "none", 4)
    math_text(f, 787, 965, "q′_{Tτ}", 20, color=ORANGE, anchor="middle")
    f.line(846, 959, 892, 959, MUTED, 1.8, True)
    for b in range(5):
        x = 905 + b * 89
        token_group(f, x, 938, n=3, width=72, height=42, color=BLUE)
        f.text(x + 35, 1008, f"R{b}", 17, color=BLUE, anchor="middle")
    figure_footer(f, "时间通道旋转及角度为机制示意。")
    return f.save("06_auxiliary_phase.svg")


if __name__ == "__main__":
    for p in (time_coordinates(), auxiliary_phase()):
        print(p)
