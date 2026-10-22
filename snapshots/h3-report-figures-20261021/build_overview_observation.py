from pathlib import Path
import math, json, hashlib
import xml.etree.ElementTree as ET
from drawing import Figure, mix, INK, MUTED, LINE, BLUE, PURPLE, ORANGE, TEAL, PALE
ROOT=Path(__file__).resolve().parent

def tokens(f,x,y,w,n,color,h=24):
    for j in range(n):
        f.rect(x+j*w/n,y,w/n-4,h,mix(color,.2+.13*(j%3)), 'none',3)

def overview():
    f=Figure(1200,'H3 单次去噪前向与时间对齐引导','从条件与带噪输入到 flow velocity；橙色标出参考视频时间对齐引导的计算位置。','图 1 / 推理架构')
    f.panel(48,164,1344,282,'多模态输入与 token 序列','A')
    cols=[(74,246,'编辑文本', '#8593a7'),(348,246,'角色参考图（可选）',PURPLE),(622,318,'参考视频 R',BLUE),(968,398,'带噪视频 T 与音频',ORANGE)]
    for x,w,title,co in cols:
        f.text(x+w/2,230,title,20,color=co,weight=650,anchor='middle')
    f.box(74,247,246,68,'文本编码 / 投影','Token Refiner', '#8593a7')
    f.box(348,247,246,68,'VAE 编码','图像 latent → patch tokens',PURPLE)
    f.box(622,247,318,68,'VAE 编码','时空 latent → patch tokens',BLUE)
    f.box(968,247,398,68,'当前采样状态 xσ','视频 / 音频 → tokens',ORANGE)
    for x,w,_,co in cols:
        f.line(x+w/2,322,x+w/2,352,co,1.7,True)
    f.text(74,375,'Concat',18,weight=650)
    groups=[(166,166,6,'文本','#8593a7'),(344,194,7,'图像',PURPLE),(550,310,12,'参考视频',BLUE),(872,140,5,'音频',TEAL),(1024,342,12,'生成视频',ORANGE)]
    for x,w,n,label,co in groups:
        tokens(f,x,358,w,n,co)
        f.text(x+w/2,410,label,16,color=co,anchor='middle')
    f.line(730,420,730,450,MUTED,1.7,True)
    f.panel(48,468,446,470,'MM Self-Attention','B')
    x,y,c=182,554,16
    data=[[.06+.25*math.exp(-abs(i-j)/1.7)+.04*((i*3+j)%5) for j in range(16)] for i in range(16)]
    f.heat(x,y,data,c,'#6985a8')
    bounds=[0,2,4,8,10,16]; labs=['文本','图像','参考 R','音频','生成 T']; colors=['#8593a7',PURPLE,BLUE,TEAL,ORANGE]
    for i in range(5):
        a,b=bounds[i:i+2]
        f.rect(x+a*c,y-13,(b-a)*c,7,colors[i],'none')
        f.rect(x-13,y+a*c,7,(b-a)*c,colors[i],'none')
        f.text(x-24,y+(a+b)*c/2+6,labs[i],16,color=colors[i],anchor='end')
    for z in bounds[1:-1]:
        f.line(x+z*c,y,x+z*c,y+16*c,'white',2)
        f.line(x,y+z*c,x+16*c,y+z*c,'white',2)
    f.text(x+128,529,'Keys / Values →',18,color=MUTED,anchor='middle')
    f.text(73,537,'Query ↓',16,color=MUTED)
    f.rect(x+4*c,y+10*c,4*c,6*c,'none',ORANGE,0,3)
    f.text(72,858,'生成 query → 参考视频 K/V',19,color=ORANGE,weight=650)
    f.lines(72,890,['选定参考视频内部的时间权重；','同一时间 bin 内仍包含空间 tokens。'],17,27)
    f.panel(516,468,876,470,'DiT Block ℓ：Attention 输出投影前修正','C')
    # same layer forward, branches show normalized values computed from QKV
    row=[(540,532,136,'RMSNorm','AdaLN 调制',BLUE),(702,532,146,'Q / K / V','线性投影',BLUE),(874,532,220,'Q/K RMSNorm','＋ MM-RoPE',BLUE),(1120,532,248,'Joint Attention','O = softmax(QKᵀ/√d)V',BLUE)]
    for xx,yy,w,a,b,co in row:f.box(xx,yy,w,70,a,b,co)
    for a,b in zip(row,row[1:]):f.line(a[0]+a[2]+3,567,b[0]-5,567,MUTED,1.7,True)
    # original output and auxiliary reference computations converge at correction
    f.box(540,656,394,92,'参考视频 Attention 两次计算','全部参考 zR  /  同时间参考 zR,τ',BLUE)
    f.path('M 982 606 L 982 632 L 737 632 L 737 651',BLUE,1.6,arrow=True)
    f.text(1076,637,'原输出 O',17,color=MUTED,anchor='middle')
    f.path('M 1244 605 L 1244 649',MUTED,1.7,arrow=True)
    f.box(1000,656,368,92,'逐 query / head 的输出修正','O′ = O + αmR (zR,τ − zR)',ORANGE)
    f.line(939,701,993,701,ORANGE,2,True)
    f.text(965,682,'δO',19,color=ORANGE,anchor='middle')
    f.text(552,779,'mR：原 Joint Attention 分给参考视频的概率总和',17,color=MUTED)
    f.path('M 1184 750 L 1184 806',ORANGE,1.8,arrow=True)
    bottom=[(540,818,226,'下一 Block ℓ+1','更新后的所有 tokens',BLUE),(790,818,254,'gate / residual → FFN','hℓ → hℓ+1',PURPLE),(1070,818,298,'合并 heads → out_proj','Concat(O′₁, …, O′H) WO',PURPLE)]
    for xx,yy,w,a,b,co in bottom:f.box(xx,yy,w,72,a,b,co)
    f.line(1065,853,1050,853,MUTED,1.7,True)
    f.line(785,853,771,853,MUTED,1.7,True)
    f.text(954,920,'依次通过 50 个 DiT Block，随后输出本步 flow velocity。',17,anchor='middle',color=MUTED)
    f.panel(48,960,1344,169,'采样更新与最终解码','D')
    f.box(72,1024,250,70,'输出头','预测 flow velocity vθ',BLUE)
    f.box(355,1024,310,70,'采样器更新','xσ′ = Sampler(xσ, vθ, σ, σ′)',PURPLE)
    f.line(326,1059,349,1059,MUTED,1.7,True)
    f.path('M 669 1059 L 710 1059 L 710 1018 L 904 1018',MUTED,1.7,arrow=True)
    f.path('M 710 1059 L 710 1092 L 904 1092',MUTED,1.7,arrow=True)
    f.text(794,1008,'继续采样',16,color=BLUE,anchor='middle')
    f.text(794,1081,'采样完成',16,color=TEAL,anchor='middle')
    f.rect(912,990,456,55,mix(BLUE,.07),mix(BLUE,.38),6)
    f.text(1140,1013,'回到 A：更新带噪输入与 σ',19,weight=650,anchor='middle')
    f.text(1140,1035,'再次执行 50 个 DiT Block',16,color=MUTED,anchor='middle')
    f.rect(912,1064,456,49,mix(TEAL,.07),mix(TEAL,.38),6)
    f.text(1140,1094,'VAE 解码 → 编辑后的视频帧',19,weight=650,anchor='middle')
    f.footer('结构与 Attention 分布为机制示意。R 表示参考视频；T 表示正在生成的视频；σ 表示当前采样噪声水平。')
    return f.save('01_denoising_architecture.svg')

def observation():
    f=Figure(1180,'参考 Attention 的时间分布与同 bin 重分配','在一次 DiT 前向中提取参考时间概率，再在相同 Q/K/V 上计算 α = 1 的重分配。','图 4 / Attention 测量')
    f.panel(48,164,1344,174,'从 Attention 运算定位到参考视频时间轴','A')
    nodes=[(72,228,242,'DiT Block 26','第 6 次前向',BLUE),(344,228,270,'QK → Joint softmax','选择输出视频 query',BLUE),(644,228,320,'提取参考视频列','参考组归一化 → 按 bin 汇总',BLUE),(994,228,374,'8 heads × 8 空间位置','汇总中心邻域的时间概率',TEAL)]
    for x,y,w,a,b,c in nodes:f.box(x,y,w,74,a,b,c)
    for a,b in zip(nodes,nodes[1:]):f.line(a[0]+a[2]+4,265,b[0]-6,265,MUTED,1.7,True)
    f.panel(48,360,652,640,'普通 Attention：实测 QK 分布','B')
    f.panel(722,360,670,640,'同一输入：α = 1 的重分配','C')
    root=ET.parse(ROOT/'current-4.svg').getroot()
    cells=[n for n in root if n.tag.endswith('rect') and n.get('width')=='8.8']
    assert len(cells)==4042
    old=[cells[:2021],cells[2021:]]
    starts=[90.,660.];newx=[146,820];y=452;step=10.5
    checks=[]
    for k,ns in enumerate(old):
        xx=newx[k]
        out_colors=[]
        for n in ns:
            col=round((float(n.get('x'))-starts[k])/8.6)
            row=round((float(n.get('y'))-102)/8.6)
            assert 0<=col<47 and 0<=row<43
            fill=n.get('fill');out_colors.append(fill)
            f.rect(xx+col*step,y+row*step,step+.05,step+.05,fill,'none')
        f.rect(xx,y,47*step,43*step,'none',LINE)
        f.text(xx+47*step/2,424,'参考视频 temporal bin →',19,color=BLUE,anchor='middle')
        for col in [0,10,20,30,40,46]:
            f.text(xx+(col+.5)*step,931,str(col),16,color=MUTED,anchor='middle')
        for row in [0,10,20,30,42]:
            f.text(xx-13,y+(row+.5)*step+6,str(row),16,color=MUTED,anchor='end')
        f.parts.append(f'<text x="{xx-59}" y="{y+225}" transform="rotate(-90 {xx-59} {y+225})" font-size="18" fill="{ORANGE}" text-anchor="middle">生成视频 temporal bin</text>')
        f.text(xx+47*step/2,971,'每行表示一个输出时间 bin 对参考各时间 bin 的分配',16,color=MUTED,anchor='middle')
        checks.append(hashlib.sha256('\n'.join(out_colors).encode()).hexdigest())
    # preserve original colorbar rather than manufacturing probability samples
    bars=[n for n in root if n.tag.endswith('rect') and n.get('width')=='3.2']
    f.text(72,1040,'两图共享色阶',18,weight=650)
    f.text(72,1070,'概率 0–1 · 对数显示',16,color=MUTED)
    for i,n in enumerate(bars):f.rect(285+i*3.4,1043,3.5,18,n.get('fill'),'none')
    f.text(270,1058,'0',16,anchor='end',color=MUTED)
    f.text(640,1058,'1',16,color=MUTED)
    f.rect(690,1024,678,70,PALE,'none',6)
    f.text(1029,1053,'p′R = (1 − α)pR + αpR,τ',25,anchor='middle',cls='math')
    f.text(1029,1080,'此处 α = 1；同时间 bin 内的空间分配由 QK 决定。',17,anchor='middle',color=MUTED)
    f.footer('每行是参考组内归一化的时间概率；每个 bin 汇总空间 tokens。左为实测，右为 α = 1 的公式重分配。')
    p=f.save('04_measured_attention.svg')
    (ROOT/'measurement_preservation.json').write_text(json.dumps({'input':str(ROOT/'current-4.svg'),'output':str(p),'matrix_shape':[2,43,47],'per_matrix_color_sha256':checks,'original_colormap_cells':len(bars),'preserved':'every matrix cell fill and original colormap fill'},ensure_ascii=False,indent=2))
    return p

if __name__=='__main__':
    print(overview());print(observation())
