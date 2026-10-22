#!/usr/bin/env python3
"""Self-contained SVG method figures. All heatmaps are illustrative."""
from pathlib import Path
from html import escape
import math
import json

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "redrawn"
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
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="{height}" viewBox="0 0 1440 {height}" role="img" class="research-figure">',
            f"<title>{escape(title)}</title>",
            "<defs>",
            '<marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="#55647a"/></marker>',
            '<marker id="bluearrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="#246ac4"/></marker>',
            '<pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="#f4f5f8"/><path d="M-2 2 L2 -2 M0 8 L8 0 M6 10 L10 6" stroke="#b8c1d0" stroke-width="1"/></pattern>',
            "</defs>",
            '<style>.research-figure text{font-family:"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",Arial,sans-serif;fill:#172335} .research-figure .math{font-family:"Times New Roman","PingFang SC",serif} .research-figure .small{fill:#55647a}</style>',
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
        svg = "\n".join(self.parts)
        prefix = p.stem + "-"
        import re
        ids = re.findall(r'id="([^"]+)"', svg)
        for old_id in ids:
            svg = svg.replace('id="' + old_id + '"', 'id="' + prefix + old_id + '"')
            svg = svg.replace('url(#' + old_id + ')', 'url(#' + prefix + old_id + ')')
        p.write_text(svg, encoding="utf-8")
        return p

