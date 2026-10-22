"""Render an explanatory vector figure and a matching local inspection PNG."""
import html
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
WIDTH, HEIGHT = 1440, 1130
FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
image = Image.new("RGB", (WIDTH, HEIGHT), "#f9fafc")
draw = ImageDraw.Draw(image)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">']
svg.append(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#f9fafc"/>')
ink, muted, blue, orange, green = "#17243a", "#56667e", "#397bc1", "#ce763b", "#198575"


def box(x, y, w, h, fill, stroke="#cbd4e0", radius=8):
    draw.rounded_rectangle((x, y, x + w, y + h), radius, fill, stroke, 1)
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')


def text(x, y, content, size=21, fill=ink):
    font = ImageFont.truetype(FONT, size)
    draw.text((x, y), content, font=font, fill=fill)
    svg.append(f'<text x="{x}" y="{y + size}" font-family="Arial Unicode MS,Arial,sans-serif" font-size="{size}" fill="{fill}">{html.escape(content)}</text>')


def line(x1, y1, x2, y2, fill=muted, width=2):
    draw.line((x1, y1, x2, y2), fill, width)
    svg.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{fill}" stroke-width="{width}"/>')


def arrow(x1, y1, x2, y2, fill=muted):
    import math
    line(x1, y1, x2, y2, fill, 2)
    angle = math.atan2(y2 - y1, x2 - x1)
    points = [(x2, y2)] + [
        (x2 - 9 * math.cos(angle + a), y2 - 9 * math.sin(angle + a))
        for a in (-0.45, 0.45)
    ]
    draw.polygon(points, fill)
    svg.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in points)}" fill="{fill}"/>')


def matrix(x, y, mode):
    """Illustrative 3-group, 4-bin attention; never a measured attention map."""
    labels = ["text / image", "reference R", "generated T"]
    colors = ["#e5eaf1", "#ddebf9", "#fae8dc"]
    cell = 26
    for g in range(3):
        text(x + g * 4 * cell + 3, y - 32, labels[g], 15, muted)
    for i in range(12):
        for j in range(12):
            g, h = i // 4, j // 4
            fill = colors[h]
            selected = (g == 2 and h == 1 and mode >= 1) or (g == 1 and h == 2 and mode == 2)
            if selected:
                fill = blue if i % 4 == j % 4 else "#ffffff"
            elif g == h:
                fill = ["#c4ccd9", "#9bbfe2", "#e6b18d"][g]
            box(x + j * cell, y + i * cell, cell - 2, cell - 2, fill, fill, 0)
    for g, label in enumerate(["other Q", "ref Q", "target Q"]):
        text(x - 76, y + g * 104 + 40, label, 15, muted)
    text(x + 6, y + 322, "列：K / V 的来源；行：query 的来源", 16, muted)


text(38, 24, "双向同时间 Attention：干预位置与概率分配", 31)
text(38, 68, "候选方法 R151 · 示意图中的颜色与概率用于说明运算，实验 Attention 数值另行记录。", 19, muted)
box(30, 110, 1380, 186, "#ffffff")
text(48, 122, "H3 单流 DiT：一个 block 内的改动", 22)
for x, w, label, color in [
    (48, 208, "多模态 hidden states", "#e9eef6"),
    (294, 216, "Q / K / V + RoPE", "#e9eef6"),
    (548, 260, "Joint Attention", "#e9eef6"),
    (846, 246, "本轮双向时间重分配", "#e0f1ed"),
    (1130, 256, "out_proj → residual", "#e9eef6"),
]:
    box(x, 171, w, 50, color)
    text(x + 12, 181, label, 19)
for a, b in [(256, 294), (510, 548), (808, 846), (1092, 1130)]:
    arrow(a + 4, 196, b - 5, 196)
text(50, 242, "输入：文字、参考图片、参考视频、带噪目标视频等 token；两种视频各有时间 × 空间 token。", 19, muted)
text(50, 268, "输出经 FFN 与后续 block 更新。每个去噪步重新使用原参考条件；不在这里解码 RGB。", 18, muted)

titles = ["原 Joint Attention", "已验证的正向引导", "本轮新增：双向引导"]
for i, x in enumerate([118, 578, 1038]):
    text(x - 64, 323, titles[i], 23)
    matrix(x - 20, 395, i)
text(45, 755, "蓝色对角：仅在同一物理时间 bin 内分配该视频组的注意力，仍允许匹配该 bin 内所有空间位置。", 20)
text(45, 785, "每一行原本分给该视频的概率总和保持不变；文字、图片及其他组的概率保持原值。", 20, muted)

box(30, 835, 675, 180, "#ffffff")
box(725, 835, 685, 180, "#ffffff")
text(50, 850, "生成 query → 参考视频", 22, blue)
text(745, 850, "参考 query → 生成视频", 22, orange)
text(50, 889, "O′T = OT + α mR (μR,same − μR,all)", 24)
text(745, 889, "O′R = OR + β mT (μT,same − μT,all)", 24)
text(50, 932, "mR：原 softmax 分给参考视频的概率总和。", 19, muted)
text(50, 962, "μ：对应视频组内归一化后的 V 加权和。", 19, muted)
text(745, 932, "mT：原 softmax 分给生成视频的概率总和。", 19, muted)
text(745, 962, "same 取同时间 bin；all 取该视频的全部 token。", 19, muted)
text(40, 1042, "2 × 2 实验：普通编辑 (0,0) ｜正向 (1,0) ｜反向 (0,1) ｜双向 (1,1)", 24, green)
text(40, 1082, "20 步 Euler 中第 1–9 步、50 个 block；只改两个视频方向的选定 query 行。", 19, muted)
svg.append("</svg>")
(ROOT / "method.svg").write_text("\n".join(svg))
image.save(ROOT / "method.png")
print(ROOT / "method.svg")
