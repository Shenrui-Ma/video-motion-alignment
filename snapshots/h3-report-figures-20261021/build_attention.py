#!/usr/bin/env python3
"""Rebuild figures 3 and 5 from the original Figure/panel/heatmap design."""
from drawing import Figure, ROOT, OUT, INK, MUTED, LINE, BLUE, PURPLE, ORANGE, TEAL, PALE, mix
from html import escape
import json
import math
import re


def node(f, x, y, w, h, title, sub=None, color=BLUE):
    f.rect(x, y, w, h, mix(color, .065), mix(color, .4), 6)
    if sub is None:
        f.text(x + w / 2, y + h / 2 + 6, title, 18, weight=600, anchor="middle")
    else:
        f.text(x + w / 2, y + 26, title, 18, weight=600, anchor="middle")
        f.text(x + w / 2, y + 51, sub, 16, color=MUTED, anchor="middle")


def math_subscripts(f):
    """Typeset variable subscripts without embedding a math renderer."""
    for i, part in enumerate(f.parts):
        if part.startswith("<text ") and "_" in part:
            size = float(re.search(r'font-size="([0-9.]+)"', part).group(1))
            a, content = part.split(">", 1)
            content = content.replace("out_proj", "OUTPROJPLACEHOLDER")
            content = re.sub(r"_([A-Za-z0-9]+(?:,[A-Za-z0-9τ]+)?)",
                             lambda m: f'<tspan baseline-shift="sub" font-size="{max(16, round(size*.72))}">{m.group(1)}</tspan>', content)
            f.parts[i] = a + ">" + content.replace("OUTPROJPLACEHOLDER", "out_proj")


def footer(f, text):
    f.line(48, f.height - 49, 1392, f.height - 49, LINE)
    f.text(48, f.height - 21, text, 16, color=MUTED)


def sequence(f):
    f.text(48, 178, "联合 token 序列", 21, weight=650)
    f.text(1392, 178, "R：参考视频　T：生成视频", 17, color=MUTED, anchor="end")
    groups = [("文本", 150, "#8593a7", 5), ("角色参考图", 210, PURPLE, 7),
              ("参考视频 R", 360, BLUE, 12), ("输出音频", 165, TEAL, 5),
              ("生成视频 T", 375, ORANGE, 12)]
    x = 48
    for title, width, color, n in groups:
        f.text(x + width / 2, 205, title, 17, color=color, weight=600, anchor="middle")
        s = (width - 10) / n
        for j in range(n):
            f.rect(x + j * s, 218, s - 4, 22, mix(color, .18 + .11 * (j % 3)), "none", 3)
        x += width + 14


def joint_matrix(f, x=168, y=352, c=18, dual=False):
    n = 16
    bounds = [0, 2, 4, 8, 10, 16]
    labels = ["文本", "角色图", "参考 R", "音频", "生成 T"]
    colors = ["#8593a7", PURPLE, BLUE, TEAL, ORANGE]
    data = []
    for i in range(n):
        raw = [1. + 4 * math.exp(-abs(i - j) / 2.) + .25 * ((i*5+j*3) % 5) for j in range(n)]
        data.append([v / sum(raw) for v in raw])
    f.heat(x, y, [[v * 3 for v in row] for row in data], c, "#6985a8")
    for b in bounds[1:-1]:
        f.line(x + b*c, y, x + b*c, y + n*c, "white", 3)
        f.line(x, y + b*c, x + n*c, y + b*c, "white", 3)
    for i in range(5):
        a,b = bounds[i:i+2]
        f.rect(x+a*c, y-13, (b-a)*c, 7, colors[i], "none")
        f.rect(x-13, y+a*c, 7, (b-a)*c, colors[i], "none")
        f.text(x-25, y+(a+b)*c/2+5, labels[i], 16, color=colors[i], anchor="end")
    f.text(x+144, y-30, "Keys / Values →", 18, color=MUTED, anchor="middle")
    f.text(72, y-30, "Query ↓", 17, color=MUTED)
    f.rect(x+4*c, y+10*c, 4*c, 6*c, "none", ORANGE, sw=3)
    if dual:
        f.rect(x+10*c, y+4*c, 6*c, 4*c, "none", BLUE, sw=3)
    return data


def normalize(row):
    return [v / sum(row) for v in row]


TEMPORAL = [[.18,.52,.20,.10], [.30,.19,.39,.12], [.12,.39,.18,.31], [.10,.18,.49,.23]]
SPATIAL = [.50,.30,.20]
P = [[mass*s for mass in row for s in SPATIAL] for row in TEMPORAL]
SAME = [[(SPATIAL[j%3] if j//3 == i else 0.) for j in range(12)] for i in range(4)]
MIXED = [[.75*p + .25*s for p,s in zip(row, same)] for row,same in zip(P,SAME)]


def temporal_map(f, x, y, data, cell=18, color=BLUE, qlabel="T", klabel="R"):
    for i,row in enumerate(data):
        for j,p in enumerate(row):
            f.rect(x+j*cell, y+i*cell, cell, cell,
                   "white" if p == 0 else mix(color, min(.91, p / .50 * .91)), "white", sw=.8)
    f.rect(x,y,12*cell,4*cell,"none",LINE)
    for j in range(4):
        f.text(x+(j*3+1.5)*cell,y-12,f"{klabel}{j}",16,color=MUTED,anchor="middle")
        if j:
            f.line(x+j*3*cell,y,x+j*3*cell,y+4*cell,"white",2.6)
    for i in range(4):
        f.text(x-11,y+(i+.5)*cell+5,f"{qlabel}{i}",16,color=MUTED,anchor="end")


def legend(f,x,y,color=BLUE):
    f.text(x,y,"0",16,color=MUTED)
    for j in range(30):
        f.rect(x+20+j*3.4,y-13,3.5,15,mix(color,.91*j/29),"none")
    f.text(x+132,y,"0.5",16,color=MUTED)
    f.text(x+172,y,"组内概率；各行总和 = 1",17,color=MUTED)


def figure3():
    f = Figure(1290, "参考视频内部的 Attention 时间重分配",
               "保留原 Joint Attention 的参考组概率总和；按同一 temporal bin 重分配组内时间与空间权重", "图 3  /  参考视频时间引导")
    sequence(f)
    f.panel(48,262,464,546,"定位被修改的联合矩阵区段","A")
    f.panel(532,262,860,546,"放大参考组：普通、弱引导与完全替换","B")
    joint_matrix(f)
    f.lines(72,680,["橙框：生成 Q → 参考 K/V", "m_q = 该 query / head 的参考总概率", "其他 token 组的 Value 加权和保持原值。"],18,31)
    f.path("M456 586 L487 586 L487 480 L553 480", ORANGE, 1.8, arrow=True)
    xs=[591,859,1127]
    for x,title,color in zip(xs,["原分布 p_R","α = 0.25 · 弱引导","α = 1 · 完全替换"],[BLUE,ORANGE,ORANGE]):
        f.text(x+108,328,title,19,color=color,weight=650,anchor="middle")
    for x,data,color in zip(xs,[P,MIXED,SAME],[BLUE,ORANGE,ORANGE]):
        temporal_map(f,x,370,data,18,color)
    f.text(xs[0]+108,474,"跨时间、跨空间读取",17,color=MUTED,anchor="middle")
    f.text(xs[1]+108,474,"仍保留跨时间权重",17,color=ORANGE,anchor="middle")
    f.text(xs[2]+108,474,"只保留对应 bin",17,color=ORANGE,anchor="middle")
    f.text(565,514,"每个 R bin 含 3 个空间 token；同 bin 内按 QK 相似度分配。",18,color=MUTED)
    legend(f,565,549,ORANGE)
    f.rect(556,570,812,92,PALE,"none",6)
    f.text(962,607,"p′ = (1 − α) p_R + α p_same",28,anchor="middle",cls="math")
    f.text(962,640,"O′_q = O_q + α m_q (z_q,τ − z_q)",28,anchor="middle",cls="math")
    f.text(558,696,"z_q：全部参考 tokens 的组内归一化 Value 加权和",18)
    f.text(558,728,"z_q,τ：同时间 bin 内组内归一化的参考 Value 加权和",18)
    f.text(558,767,"当前弱引导 α = 0.25；各 query / head 的 m_q 保持原值。",18,weight=600)
    f.panel(48,830,1344,388,"计算位置：参考 Attention 修正每个 head 的 O，随后拼接并投影","C")
    y=904
    specs=[(72,180,"Q / K / V","线性投影",BLUE), (274,170,"Q/K RMSNorm","＋ MM-RoPE",BLUE),
           (466,200,"Joint Attention","O 与 LSE_all",BLUE), (914,190,"逐 query / head","O_q → O′_q",ORANGE),
           (1128,130,"拼接 heads","Concat",PURPLE), (1280,88,"out_proj","W_O",PURPLE)]
    for x,w,title,sub,color in specs:
        node(f,x,y,w,76,title,sub,color)
    for a,b in zip(specs,specs[1:]):
        f.line(a[0]+a[1]+3,y+38,b[0]-7,y+38,MUTED,1.7,True)
    f.text(790,927,"原 O、LSE_all",17,color=MUTED,anchor="middle")
    f.path("M359 980 L359 1055 L460 1055",BLUE,1.7,arrow=True)
    node(f,466,1018,340,86,"两次参考 Attention 计算","全部 R → z_q；同 bin R → z_q,τ",BLUE)
    f.path("M806 1060 L893 1060 L893 985 L914 965",ORANGE,1.8,arrow=True)
    f.text(830,1090,"LSE_R",16,color=MUTED)
    f.text(72,1146,"m_q = exp(LSE_R − LSE_all)",24,cls="math")
    f.text(72,1178,"LSE 来自对应 QK logits 的 log-sum-exp。",17,color=MUTED)
    f.text(914,1052,"α m_q (z_q,τ − z_q)",24,cls="math")
    f.text(914,1085,"修正加在各自 head 输出上",18,color=ORANGE)
    f.line(1128,1124,1368,1124,LINE)
    f.text(1128,1153,"投影后：gate → residual",17)
    f.text(1128,1181,"→ FFN → 下一 Block",17)
    footer(f,"Attention 分布为机制示意；组内热图逐行归一化，颜色使用相同概率尺度。")
    math_subscripts(f)
    return f.save("03_reference_attention.svg")


def figure5():
    f = Figure(1320, "双向时间 Attention：同时修正两组 query 的输出",
               "同一 Block 内共用原 Q/K/V、Joint Attention 输出 O 和 LSE；两方向分别修正自己的 query rows", "图 4  /  双向时间引导")
    sequence(f)
    f.panel(48,262,464,508,"两个方向位于相反的矩阵区段","A")
    f.panel(532,262,860,508,"各自保留对方组总概率，再对齐同时间 bin","B")
    joint_matrix(f,dual=True)
    f.text(72,685,"橙框：生成 Q_T → 参考 K_R/V_R",18,color=ORANGE,weight=600)
    f.text(72,720,"蓝框：参考 Q_R → 生成 K_T/V_T",18,color=BLUE,weight=600)
    f.text(738,328,"正向：生成 query 读取参考",19,color=ORANGE,weight=650,anchor="middle")
    f.text(1168,328,"反向：参考 query 读取生成",19,color=BLUE,weight=650,anchor="middle")
    temporal_map(f,594,370,SAME,24,ORANGE,"T","R")
    temporal_map(f,1024,370,SAME,24,BLUE,"R","T")
    f.text(738,502,"p_R,same · α = 1",23,anchor="middle",cls="math")
    f.text(1168,502,"p_T,same · β = 1",23,anchor="middle",cls="math")
    f.text(558,538,"每个 bin 含多个空间 token；每行组内概率总和 = 1。",18,color=MUTED)
    f.rect(556,558,812,112,PALE,"none",6)
    f.text(962,603,"O′_T = O_T + α m_R (μ_R,same − μ_R,all)",26,anchor="middle",cls="math")
    f.text(962,647,"O′_R = O_R + β m_T (μ_T,same − μ_T,all)",26,anchor="middle",cls="math")
    f.text(558,705,"m_R / m_T：当前 query / head 在原联合 softmax 中",18)
    f.text(558,736,"分给对方视频组的概率总和；same / all 表示同 bin / 全部。",18)
    f.panel(48,792,1344,450,"修正独立 query rows；参考 hidden states 经后续 Block 继续传播","C")
    y=860
    specs=[(72,152,"Q / K / V","原线性投影",BLUE),(248,170,"Q/K RMSNorm","＋ MM-RoPE",BLUE),
           (442,190,"Joint Attention","原 O、LSE_all",BLUE),(870,200,"修正后的 O′","按原 token 顺序",ORANGE),
           (1094,138,"拼接 heads","Concat",PURPLE),(1256,112,"out_proj","W_O",PURPLE)]
    for x,w,title,sub,color in specs:
        node(f,x,y,w,72,title,sub,color)
    for a,b in zip(specs,specs[1:]):
        f.line(a[0]+a[1]+3,y+36,b[0]-7,y+36,MUTED,1.7,True)
    f.text(748,880,"原 O、LSE_all",17,color=MUTED,anchor="middle")
    f.path("M333 932 L333 990 L436 990",BLUE,1.7,arrow=True)
    f.path("M333 990 L333 1082 L436 1082",BLUE,1.7,arrow=True)
    f.text(72,990,"同一组原 Q/K/V",18,color=BLUE)
    f.text(72,1021,"并行计算两个方向",18,color=MUTED)
    node(f,442,958,310,70,"Q_T → K_R / V_R","μ_R,all · μ_R,same · LSE_R",ORANGE)
    node(f,442,1050,310,70,"Q_R → K_T / V_T","μ_T,all · μ_T,same · LSE_T",BLUE)
    # The two corrections remain separate query rows; heads are concatenated above.
    f.rect(870,958,200,162,"white",LINE,6)
    f.rect(871,959,198,54,mix(ORANGE,.10),"none",5)
    f.rect(871,1013,198,54,mix(BLUE,.09),"none")
    f.text(970,993,"T rows：O_T + ΔO_T",17,color=ORANGE,weight=600,anchor="middle")
    f.text(970,1047,"R rows：O_R + ΔO_R",17,color=BLUE,weight=600,anchor="middle")
    f.text(970,1097,"其他 rows：原 O",17,color=MUTED,anchor="middle")
    f.path("M752 993 L864 993",ORANGE,1.8,arrow=True)
    f.path("M752 1085 L813 1085 L813 1047 L864 1047",BLUE,1.8,arrow=True)
    f.text(808,978,"ΔO_T",19,color=ORANGE,anchor="middle")
    f.text(808,1116,"ΔO_R",19,color=BLUE,anchor="middle")
    f.line(970,958,970,938,MUTED,1.8,True)
    f.path("M1312 932 L1312 967",PURPLE,1.8,arrow=True)
    node(f,1138,973,230,64,"gate → residual / FFN",None,PURPLE)
    f.line(1253,1037,1253,1063,PURPLE,1.8,True)
    node(f,1138,1069,230,64,"下一 Block：新 Q/K/V",None,PURPLE)
    f.text(1138,1163,"更新的参考 hidden states",17,color=PURPLE)
    f.text(1138,1191,"继续影响后续层生成。",17,color=PURPLE)
    f.text(72,1168,"已测双向配置：α = β = 1；采样第 1–9 步；全部 50 个 Block。",18,weight=600)
    f.text(72,1209,"固定参考 latent 在每步重新输入；hidden states 的更新沿 Block 方向传播。",18,color=MUTED)
    footer(f,"Attention 分布为机制示意。")
    math_subscripts(f)
    return f.save("05_bidirectional_attention.svg")


def validate(paths):
    import xml.etree.ElementTree as ET
    errors=[]
    for label,data in [("original_group",P),("weak_alpha_025",MIXED),("same_bin_alpha_1",SAME)]:
        assert all(abs(sum(row)-1)<1e-12 for row in data),label
    assert all(MIXED[i][j]>0 for i in range(4) for j in range(12) if j//3 != i)
    assert all(SAME[i][j]==0 for i in range(4) for j in range(12) if j//3 != i)
    for path in paths:
        root=ET.parse(path).getroot()
        ids=[v.attrib['id'] for v in root.iter() if 'id' in v.attrib]
        assert len(ids)==len(set(ids)),path
        assert all(float(n.attrib['font-size'])>=16 for n in root.iter() if 'font-size' in n.attrib),path
    return {"figures":[str(p) for p in paths],"row_normalized":True,"alpha_025_cross_time_retained":True,
            "alpha_1_cross_time_zero":True,"minimum_font_size":16,"all_svg_xml_valid":True,
            "unique_ids_per_figure":True,"head_operation":"concatenate, then out_proj"}


if __name__ == '__main__':
    paths=[figure3(),figure5()]
    print(json.dumps(validate(paths),ensure_ascii=False,indent=2))
