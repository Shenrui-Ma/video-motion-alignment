#!/usr/bin/env python3
"""Self-contained SVG method figures. All heatmaps are illustrative."""
from pathlib import Path
from html import escape
import math
import json

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)
INK = "#172335"
MUTED = "#55647a"
LINE = "#d9e0eb"
BLUE = "#246ac4"
PURPLE = "#7954bd"
ORANGE = "#df8423"
TEAL = "#238c88"
PALE = "#f7f9fc"


def mix(color, a):
    color = color.lstrip("#")
    rgb = [int(color[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(255 * (1 - a) + c * a):02x}" for c in rgb)


class Figure:
    def __init__(self, height, title, subtitle, label):
        self.height = height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="{height}" viewBox="0 0 1440 {height}" role="img">',
            f"<title>{escape(title)}</title>",
            "<defs>",
            '<marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="#55647a"/></marker>',
            '<marker id="bluearrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="#246ac4"/></marker>',
            '<pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="#f4f5f8"/><path d="M-2 2 L2 -2 M0 8 L8 0 M6 10 L10 6" stroke="#b8c1d0" stroke-width="1"/></pattern>',
            "</defs>",
            '<style>text{font-family:"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",Arial,sans-serif;fill:#172335} .math{font-family:"Times New Roman","PingFang SC",serif} .small{fill:#55647a}</style>',
            f'<rect width="1440" height="{height}" fill="white"/>',
        ]
        self.text(48, 49, label, 16, color=BLUE, weight=700)
        self.text(48, 88, title, 30, weight=650)
        self.text(48, 119, subtitle, 17, color=MUTED)
        self.line(48, 140, 1392, 140, LINE)

    def rect(self, x, y, w, h, fill="white", stroke=LINE, r=0, sw=1):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def text(self, x, y, s, size=18, color=INK, weight=400, anchor="start", cls=""):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}" class="{cls}" style="fill:{color}">{escape(str(s))}</text>')

    def lines(self, x, y, strings, size=18, step=27, **kw):
        for n, s in enumerate(strings):
            self.text(x, y + n * step, s, size, **kw)

    def line(self, x1, y1, x2, y2, color=MUTED, width=1.5, arrow=False, dash=False):
        marker = ' marker-end="url(#arrow)"' if arrow else ""
        ds = ' stroke-dasharray="5 4"' if dash else ""
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"{marker}{ds}/>')

    def path(self, d, color=MUTED, width=1.5, fill="none", arrow=False):
        marker = ' marker-end="url(#arrow)"' if arrow else ""
        self.parts.append(f'<path d="{d}" stroke="{color}" stroke-width="{width}" fill="{fill}"{marker}/>')

    def circle(self, x, y, r, fill="white", stroke=LINE, width=1):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

    def panel(self, x, y, w, h, title, tag=None):
        self.rect(x, y, w, h, "white", LINE, 10)
        if tag:
            self.text(x + 20, y + 31, tag, 18, color=BLUE, weight=700)
            self.text(x + 54, y + 31, title, 20, weight=650)
        else:
            self.text(x + 20, y + 31, title, 20, weight=650)

    def box(self, x, y, w, h, label, sub=None, color=BLUE):
        self.rect(x, y, w, h, mix(color, .07), mix(color, .38), 6)
        self.text(x + w / 2, y + (h / 2 + 6 if not sub else 26), label, 18, weight=600, anchor="middle")
        if sub:
            self.text(x + w / 2, y + 49, sub, 14, color=MUTED, anchor="middle")

    def heat(self, x, y, data, cell, color=BLUE, grid=True):
        for i, row in enumerate(data):
            for j, v in enumerate(row):
                self.rect(x + j * cell, y + i * cell, cell, cell,
                          mix(color, min(.91, max(.035, float(v)))),
                          "white" if grid else "none", sw=.8)
        self.rect(x, y, len(data[0]) * cell, len(data) * cell, "none", LINE)

    def footer(self, text):
        self.line(48, self.height - 49, 1392, self.height - 49, LINE)
        self.text(48, self.height - 21, text, 14, color=MUTED)

    def save(self, name):
        self.parts.append("</svg>")
        p = OUT / name
        p.write_text("\n".join(self.parts), encoding="utf-8")
        return p


def current_method():
    f = Figure(
        1110,
        "现有时序干预：在参考视频内部重分配 Attention",
        "主 DiT block · 输出视频 query 读取参考视频 keys · 先修正 Attention 输出，再进入 out_proj",
        "图 1  /  当前方法",
    )
    groups = [
        ("文本", 150, "#8593a7", 5),
        ("角色参考图", 210, PURPLE, 7),
        ("参考视频 R", 360, BLUE, 12),
        ("输出音频", 165, "#6d9c9a", 5),
        ("输出视频 T", 375, ORANGE, 12),
    ]
    f.text(48, 178, "联合 token 序列", 21, weight=650)
    f.text(1392, 177, "以图像＋视频条件为例；各区段长度为示意", 14, color=MUTED, anchor="end")
    x = 48
    for title, width, color, n in groups:
        f.text(x + width / 2, 207, title, 17, color=color, weight=600, anchor="middle")
        s = (width - 10) / n
        for j in range(n):
            f.rect(x + j * s, 220, s - 4, 32, mix(color, .16 + .11 * (j % 3)), "none", 3)
        x += width + 14
    # x total goes 1378; sequence occupies 1344 within canvas.
    f.panel(48, 276, 474, 440, "联合 Attention 概率矩阵", "A")
    f.panel(544, 276, 848, 440, "参考视频区段的时间分配", "B")
    x0, y0, cell = 156, 360, 17
    n = 16
    bounds = [0, 2, 4, 8, 10, 16]
    labels = ["文本", "角色图", "参考视频", "音频", "输出视频"]
    colors = ["#8593a7", PURPLE, BLUE, "#6d9c9a", ORANGE]
    data = [[.07 + .3 * math.exp(-abs(i - j) / 1.6) + .07 * ((i * 5 + j * 3) % 5) / 4 for j in range(n)] for i in range(n)]
    f.heat(x0, y0, data, cell, "#6985a8")
    for b in bounds[1:-1]:
        f.line(x0 + b * cell, y0, x0 + b * cell, y0 + n * cell, "white", 3)
        f.line(x0, y0 + b * cell, x0 + n * cell, y0 + b * cell, "white", 3)
    for z in range(5):
        a, b = bounds[z:z + 2]
        mid = (a + b) * cell / 2
        f.rect(x0 + a * cell, y0 - 13, (b - a) * cell, 7, colors[z], "none")
        f.rect(x0 - 13, y0 + a * cell, 7, (b - a) * cell, colors[z], "none")
        f.text(x0 - 24, y0 + mid + 5, labels[z], 14, color=colors[z], anchor="end")
    f.text(x0 + 136, y0 - 28, "Keys / Values →", 17, anchor="middle", color=MUTED)
    f.text(71, 341, "Query ↓", 16, color=MUTED)
    f.rect(x0 + 4 * cell, y0 + 10 * cell, 4 * cell, 6 * cell, "none", ORANGE, 0, 3)
    f.lines(73, 665, ["橙框：输出视频 Q → 参考视频 K/V", "实际修改只作用于选定时空范围。"], size=16, step=25)
    # Ref temporal rows: four physical output bins; 3 patches per reference bin.
    a = [
        [.80, .72, .52, .20, .13, .10, .10, .08, .07, .09, .08, .06],
        [.63, .55, .38, .39, .32, .21, .12, .09, .08, .06, .05, .06],
        [.38, .30, .23, .62, .55, .38, .26, .20, .17, .08, .07, .06],
        [.13, .10, .08, .38, .32, .25, .56, .48, .36, .22, .16, .13],
    ]
    b = []
    for i in range(4):
        b.append([(.78, .61, .44)[j % 3] if j // 3 == i else .04 for j in range(12)])
    xa, xb, yy, c = 600, 1014, 389, 25
    for xx, d, title, color in [(xa, a, "普通 Attention", BLUE), (xb, b, "同时间 bin 干预", ORANGE)]:
        f.text(xx + 150, 351, title, 20, color=color, weight=650, anchor="middle")
        f.heat(xx, yy, d, c, color)
        for j in range(4):
            f.text(xx + (j * 3 + 1.5) * c, yy - 13, f"R{j}", 15, color=MUTED, anchor="middle")
            f.line(xx + j * 3 * c, yy, xx + j * 3 * c, yy + 4 * c, "white", 2)
        for i in range(4):
            f.text(xx - 10, yy + (i + .5) * c + 5, f"T{i}", 14, color=MUTED, anchor="end")
    f.line(919, 440, 987, 440, MUTED, 2, True)
    f.text(953, 422, "重分配", 14, color=MUTED, anchor="middle")
    f.text(568, 529, "每个 R bin 内仍包含空间 patch；横轴小格表示空间 token。", 15, color=MUTED)
    f.rect(568, 548, 800, 74, PALE, "none", 6)
    f.text(968, 580, "o′ = o + mR · ( μsame − μR )", 29, anchor="middle", cls="math")
    f.text(968, 605, "mR：该 query / head 在原 softmax 中分配给参考视频的总概率", 16, color=MUTED, anchor="middle")
    f.lines(569, 651, ["干预前后均保持 mR；只改变参考视频内部的时间分配。", "同时间对应来自物理帧与 latent bin 映射。"], 17, 27)
    f.panel(48, 740, 1344, 300, "在主 DiT block 中的准确位置", "C")
    nodes = [
        (72, 814, 160, "Q / K / V", "线性投影", BLUE),
        (260, 814, 180, "Q/K RMSNorm", "＋ MM-RoPE", BLUE),
        (468, 814, 174, "Self-Attention", "softmax(QKᵀ) V", BLUE),
        (670, 804, 200, "Attention 输出修正", "o → o′", ORANGE),
        (898, 814, 160, "out_proj", "合并各个 head", PURPLE),
        (1086, 814, 274, "AdaLN gate → residual", "随后执行 RMSNorm / FFN", PURPLE),
    ]
    for xx, y, w, title, sub, co in nodes:
        f.box(xx, y, w, 76, title, sub, co)
    for l, r in zip(nodes, nodes[1:]):
        f.line(l[0] + l[2] + 3, 853, r[0] - 6, 853, MUTED, 1.7, True)
    f.line(724, 936, 724, 891, ORANGE, 1.8, True)
    f.lines(72, 948, ["进入 residual stream 的修正：", "δh = gateMSA ⊙ WO · δo"], 19, 31)
    f.lines(784, 944, ["修改点在 out_proj 之前。", "参考组概率约束作用于 Attention，后续层继续正常传播。"], 17, 29)
    f.footer("机制示意，非实测 attention。热图不表示具体实验的概率或效果；框线标出实际算子位置。")
    return f.save("01_current_attention.svg")


def block_matrix(f, x, y, mode):
    cell, half, total = 13, 8, 16
    for i in range(total):
        for j in range(total):
            r, c = i // half, j // half
            co = BLUE if c == 0 else ORANGE
            a = .10 + .37 * math.exp(-abs(i % 8 - j % 8) / 2.4)
            if r == 1 and c == 0 and mode in ("full", "both"):
                a = .72 if i % 8 // 2 == j % 8 // 2 else .035
            if r == 0 and c == 1 and mode in ("block", "both"):
                f.rect(x + j * cell, y + i * cell, cell, cell, "url(#hatch)", "white", sw=.5)
            else:
                if r == 0 and c == 0 and mode in ("block", "both"):
                    a = min(.78, a * 1.5)
                f.rect(x + j * cell, y + i * cell, cell, cell, mix(co, a), "white", sw=.5)
    f.rect(x, y, total * cell, total * cell, "none", LINE)
    f.line(x + half * cell, y, x + half * cell, y + total * cell, "white", 3)
    f.line(x, y + half * cell, x + total * cell, y + half * cell, "white", 3)
    f.text(x + 52, y - 13, "R keys", 15, color=BLUE, anchor="middle")
    f.text(x + 156, y - 13, "T keys", 15, color=ORANGE, anchor="middle")
    f.text(x - 10, y + 58, "R", 16, color=BLUE, anchor="end")
    f.text(x - 10, y + 162, "T", 16, color=ORANGE, anchor="end")
    if mode in ("full", "both"):
        f.rect(x, y + 104, 104, 104, "none", ORANGE, sw=2.5)
    if mode in ("block", "both"):
        f.rect(x + 104, y, 104, 104, "none", MUTED, sw=2)
        f.text(x + 156, y + 59, "BLOCK", 17, color=INK, weight=600, anchor="middle")


def candidates_attention():
    f = Figure(
        1180, "候选 Attention 结构：读取方向与跨时刻分配",
        "R：参考视频 · T：输出视频 · 第一部分补组合对照，第二部分研究跨 query 的时间覆盖",
        "图 2  /  待选择的结构实验",
    )
    f.panel(48, 162, 1344, 408, "同时间读取与反向 BLOCK 的四种组合", "A")
    specs = [
        (93, "普通编辑", "native", "保留两个读取方向"),
        (423, "正向 Full", "full", "T query 读取对应时间的 R"),
        (753, "反向 BLOCK", "block", "R query 去掉 T keys，并重新归一化"),
        (1083, "Full ＋ BLOCK", "both", "同时应用两个操作"),
    ]
    for x, title, mode, caption in specs:
        f.text(x + 104, 235, title, 21, weight=650, anchor="middle")
        block_matrix(f, x, 280, mode)
        f.text(x + 104, 520, caption, 14, color=MUTED, anchor="middle")
    f.text(72, 550, "图中抽取 R / T 子矩阵。文本、角色图、音频及其他 keys 的归一化在实际实现中同时保留。", 15, color=MUTED)
    f.panel(48, 592, 1344, 510, "跨 query 软时间覆盖：共享参考时间的使用量", "B")
    f.text(130, 670, "每行独立选择", 22, weight=650)
    f.text(660, 670, "加入共享的列约束", 22, weight=650)
    # Matrices deliberately not numerical probabilities; no fabricated result.
    aa = []
    bb = []
    for i in range(8):
        aa.append([.05 + .62 * math.exp(-((j - max(0, i - 2)) / 1.1) ** 2) + .17 * math.exp(-((j - 1) / .8) ** 2) for j in range(8)])
        bb.append([.05 + .61 * math.exp(-((j - i) / 1.25) ** 2) + .09 * math.exp(-((j - max(0, i - 1)) / 1.8) ** 2) for j in range(8)])
    xa, xb, yy, cell = 140, 670, 712, 29
    f.heat(xa, yy, aa, cell, BLUE)
    f.heat(xb, yy, bb, cell, PURPLE)
    for xx in (xa, xb):
        f.text(xx + 116, yy - 14, "参考物理时间 →", 16, color=MUTED, anchor="middle")
        f.text(xx - 23, yy + 26, "输", 16, color=MUTED)
        f.text(xx - 23, yy + 51, "出", 16, color=MUTED)
        f.text(xx - 23, yy + 76, "时", 16, color=MUTED)
        f.text(xx - 23, yy + 101, "间", 16, color=MUTED)
        f.text(xx - 23, yy + 126, "↓", 16, color=MUTED)
    # Independent arrows versus common marginal column coupling.
    for i in range(8):
        f.line(387, yy + (i + .5) * cell, 432, yy + (i + .5) * cell, mix(BLUE, .6), 1.6, True)
    f.lines(451, 779, ["各行分别", "归一化"], 17, 27, color=MUTED)
    f.path("M919 726 L943 726 L943 930 L919 930", PURPLE, 2)
    f.text(965, 795, "X · 1 = ρ", 23, cls="math")
    f.text(965, 823, "每行总质量固定", 16, color=MUTED)
    f.path("M685 958 L685 976 L888 976 L888 958", PURPLE, 2)
    f.lines(980, 876, ["列质量 c = Xᵀ · 1", "与期望时间覆盖 b 比较", "列缩放因子由所有行共同决定"], 18, 29)
    f.path("M960 885 C935 885 940 976 894 976", PURPLE, 1.8, arrow=True)
    f.text(131, 993, "长相似片段可能被多次读取", 16, color=MUTED)
    f.text(667, 1006, "保持有限时间宽度；邻近时刻仍可分配概率", 16, color=MUTED)
    f.rect(72, 1027, 1296, 52, PALE, "none", 5)
    f.text(720, 1061, "min  KL(X ‖ diag(ρ) A)  +  λt ⟨X, Ctime⟩  +  λc KL(Xᵀ1 ‖ b)", 25, anchor="middle", cls="math")
    f.footer("机制示意，非实测 attention。候选结构尚待实验；软列约束采用已有 OT / KL 方法，研究对象是 H3 的时间覆盖。")
    return f.save("02_direction_and_coverage.svg")


def phase_circle(f, cx, cy, radius, title, phase, corrected=None):
    f.circle(cx, cy, radius, "white", LINE, 1.5)
    f.line(cx - radius - 8, cy, cx + radius + 8, cy, LINE, 1)
    f.line(cx, cy - radius - 8, cx, cy + radius + 8, LINE, 1)
    def vec(theta, color, width=2.8):
        xx, yy = cx + radius * .83 * math.cos(theta), cy - radius * .83 * math.sin(theta)
        f.line(cx, cy, xx, yy, color, width)
        f.circle(xx, yy, 3.4, color, color)
        return xx, yy
    k = vec(.25, BLUE)
    q = vec(phase, ORANGE)
    f.text(k[0] + 8, k[1] + 5, "K", 15, color=BLUE, weight=600)
    f.text(q[0] - 10, q[1] - 7, "Q", 15, color=ORANGE, weight=600)
    if corrected is not None:
        z = vec(corrected, PURPLE)
        f.text(z[0] + 6, z[1] - 10, "Q̃", 17, color=PURPLE, weight=600)
        rr = radius * .65
        p1 = (cx + rr * math.cos(phase), cy - rr * math.sin(phase))
        p2 = (cx + rr * math.cos(corrected), cy - rr * math.sin(corrected))
        f.path(f"M{p1[0]} {p1[1]} A{rr} {rr} 0 0 1 {p2[0]} {p2[1]}", PURPLE, 1.5, arrow=True)
    f.text(cx, cy + radius + 32, title, 17, anchor="middle", weight=600)


def phase_and_heads():
    f = Figure(
        1680, "时间 RoPE 与按修正方向选择 head",
        "上：辅助参考 Attention 的时间相位补偿；下：依据局部误差与 residual 增量选择干预位置",
        "图 3  /  坐标消融与选择策略",
    )
    f.panel(48, 162, 1344, 542, "16 个时间通道对与相位补偿", "A")
    f.text(72, 230, "每个 head 的 128 维 Q / K", 19, weight=650)
    blocks = [
        ("0–15", "t", BLUE, 16),
        ("16–31", "h", "#98a8bc", 16),
        ("32–47", "w", "#b1bccb", 16),
        ("48–63", "t", BLUE, 16),
        ("64–79", "h", "#98a8bc", 16),
        ("80–95", "w", "#b1bccb", 16),
        ("96–127", "未旋转", "#d6dce5", 32),
    ]
    xx = 72
    for label, axis, color, n in blocks:
        w = n * 9.7
        f.rect(xx, 248, w - 3, 43, mix(color, .28), "white", 3)
        f.text(xx + (w - 3) / 2, 275, label, 17, color=INK, anchor="middle")
        f.text(xx + (w - 3) / 2, 315, axis, 16, color=BLUE if axis == "t" else MUTED, anchor="middle")
        xx += w
    f.text(72, 355, "时间二维对：(0,48), (1,49), …, (15,63)", 19, weight=600)
    startx, tile = 72, 30
    for i in range(16):
        x = startx + i * tile
        f.rect(x, 373, 26, 25, mix(BLUE, .12 + (15 - i) * .013), "white", 2)
        f.rect(x, 459, 26, 25, mix(PURPLE, .15 + i * .008), "white", 2)
        f.text(x + 13, 391, str(i), 12, anchor="middle")
        f.text(x + 13, 477, str(48 + i), 12, anchor="middle")
        f.line(x + 13, 401, x + 13, 453, mix(BLUE, .55), 1.3)
        f.circle(x + 13, 428, 7, "white", mix(BLUE, .7), 1)
        angle = .35 + i * .11
        f.line(x + 13, 428, x + 13 + 5 * math.cos(angle), 428 - 5 * math.sin(angle), BLUE, 1.5)
    f.lines(72, 522, ["每一对按 ωb · t 旋转；h / w 通道保持原值。", "固定原点差 Δ 来自 PackedLayout 的实际位置坐标。"], 16, 27)
    phase_circle(f, 699, 430, 65, "原始相位", 1.75)
    phase_circle(f, 921, 430, 65, "全频补偿", 1.75, .56)
    phase_circle(f, 1179, 430, 65, "部分频带补偿", 1.75, 1.02)
    f.text(921, 567, "Q̃b = R(−ωb Δ) Qb", 25, anchor="middle", cls="math")
    f.text(1179, 567, "Q̃b = R(−gb ωb Δ) Qb", 24, anchor="middle", cls="math")
    f.rect(72, 592, 1296, 80, PALE, "none", 6)
    f.lines(91, 622, ["相位补偿只用于额外的 T query → R keys 计算；原主 Attention 使用原始 Q / K。",
                     "gb ∈ [0,1] 控制每个时间频带。全频版本已有实现，部分频带属于待选消融。"], 17, 29)
    f.panel(48, 726, 1344, 876, "以固定网格特征变化与同时间状态选择修正", "B")
    f.box(72, 785, 232, 64, "原 Attention 输出", "各 head 的 Value 加权和", BLUE)
    f.box(342, 785, 228, 64, "out_proj ＋ gate", "投影到 residual 坐标", PURPLE)
    f.box(608, 785, 444, 64, "Y：Attention residual 更新后", "在这里测量；参考状态在本次选择中固定", ORANGE)
    f.box(1090, 785, 278, 64, "FFN", "测量发生在 FFN 之前", BLUE)
    for a, b in ((304, 342), (570, 608), (1052, 1090)):
        f.line(a + 4, 817, b - 7, 817, MUTED, 1.8, True)
    f.text(720, 884, "实际修正增量：rh = gate ⊙ WO,h · δoh", 23, anchor="middle", cls="math")
    f.line(72, 908, 1368, 908, LINE)

    f.text(76, 945, "候选层 × Attention heads", 20, weight=650)
    f.text(76, 974, "逐层决策；每次只合并同一层的增量", 16, color=MUTED)
    gx, gy, cw, ch = 111, 1014, 30, 36
    for r in range(5):
        f.text(gx - 14, gy + r * ch + 23, f"ℓ{r}", 15, color=MUTED, anchor="end")
        for c in range(10):
            active = (r, c) in {(0, 2), (1, 6), (2, 3), (2, 8), (3, 1), (4, 5)}
            f.rect(gx + c * cw, gy + r * ch, cw - 4, ch - 5,
                   mix(PURPLE, .57) if active else "#edf1f6", "white", 3)
            if active:
                f.circle(gx + c * cw + 13, gy + r * ch + 15, 3.5, "white", "white")
    for c in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9):
        f.text(gx + c * cw + 13, gy - 12, str(c), 12, color=MUTED, anchor="middle")
    f.text(80, 1230, "紫色：sh > 0 且匹配可靠的候选修正", 15, color=MUTED)
    f.text(80, 1258, "每层的原 Attention 与 FFN 正常执行。", 15, color=MUTED)
    f.line(435, 1105, 473, 1105, MUTED, 2, True)

    f.text(494, 945, "固定读出、空间对应与差分算子", 20, weight=650)
    f.text(494, 984, "HT = P(YT)； HR = W P(YR)", 25, cls="math")
    f.lines(494, 1016, ["P：共享线性投影；W：局部窗口内固定对应", "D：固定网格、按实际物理时间间隔求差分"], 16, 27, color=MUTED)
    f.text(494, 1090, "e0 = √λ0 (HT − HR)", 25, cls="math")
    f.text(494, 1128, "e1 = √λ1 D(HT − HR)", 25, cls="math")
    f.text(494, 1164, "e = (e0, e1)", 24, cls="math")
    f.text(494, 1208, "gh = (√λ0 P(rh),  √λ1 D P(rh))", 23, cls="math")
    f.text(494, 1250, "sh = −⟨e, gh⟩ ；选择 sh > 0", 24, cls="math")

    # Exact scalar minimization of the frozen, linear local proxy.
    px, py, ww, hh = 1085, 1195, 245, 175
    f.text(1203, 945, "冻结局部代理", 19, anchor="middle", weight=650)
    f.text(1203, 975, "选择强度 α", 18, anchor="middle", color=MUTED)
    f.line(px, py, px + ww, py, MUTED, 1.5, True)
    f.line(px, py, px, py - hh, MUTED, 1.5, True)
    coords = []
    for j in range(65):
        a = j / 64
        value = .12 + 1.9 * (a - .46) ** 2
        coords.append((px + a * (ww - 15), py - value * (hh - 10)))
    f.path("M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in coords), PURPLE, 3)
    ax = px + .46 * (ww - 15)
    ay = py - .12 * (hh - 10)
    f.circle(ax, ay, 5, ORANGE, "white", 1.5)
    f.line(ax, ay + 8, ax, py, ORANGE, 1.5, dash=True)
    f.text(ax, py + 25, "α*", 21, color=ORANGE, anchor="middle", cls="math")
    f.text(px + ww - 1, py + 25, "α", 21, color=MUTED, anchor="end", cls="math")
    f.text(1205, 1253, "E(α) = ½ ‖e + αg‖²", 22, anchor="middle", cls="math")
    f.rect(72, 1301, 1296, 113, PALE, "none", 5)
    f.text(720, 1337, "同层合并：r = Σh rh，g = Σh gh", 23, anchor="middle", cls="math")
    f.text(720, 1384, "α* = clip( −⟨e, g⟩ / ‖g‖²,  0,  αmax )，  0 ≤ α ≤ αmax ≤ 1", 27, anchor="middle", cls="math")
    f.lines(88, 1452, ["同时间状态项 e0 提供时间相位锚点；固定网格变化项 e1 比较局部时间变化。",
                      "P、W、D 与可信区域在本次计算中固定；‖g‖ = 0 时取 α = 0，所得强度精确最小化该局部二次目标。",
                      "需要验证：跨角色的比例、纹理和身份差异对这个特征代理的影响。"], 18, 33)
    f.text(88, 1570, "后续位移版：局部 Q/K soft matching ＋ Jacobian；在 sampled queries 上复核局部误差。", 17, color=MUTED)
    f.footer("机制示意，非实测 attention。选择规则为候选；局部代理与最终动作时序的关系待实测。")
    return f.save("03_rope_and_head_selection.svg")


if __name__ == "__main__":
    outputs = [current_method(), candidates_attention(), phase_and_heads()]
    manifest = {
        "figure_type": "native_svg",
        "scope": "mechanism_illustration",
        "measured_attention": False,
        "model_source": "/Users/researcher/DevProjects/comfyui-media-research-20261004/src/ComfyUI/comfy/ldm/minimax/model.py",
        "time_pairs": [[i, i + 48] for i in range(16)],
        "files": [p.name for p in outputs],
        "note": "All heatmaps, selections, and curves are illustrative, not experimental measurements."
    }
    (OUT / "FIGURE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print("\n".join(str(p) for p in outputs))
