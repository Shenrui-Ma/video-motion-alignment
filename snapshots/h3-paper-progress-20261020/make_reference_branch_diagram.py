from pathlib import Path
from build import svg, tx, box, arrow


def make_diagram():
    a = tx(24, 34, '参考分支的时间相位对齐', 25, weight='600')
    a += tx(24, 68, '同一个 DiT Block 内：联合 Attention + 两次参考视频 Attention', 19, color='#526277')
    a += box(24, 106, 265, 76, '原始 Q、K、V', 'Q / K 已施加原始 MM-RoPE', size=20)
    a += arrow(289, 144, 338, 144)
    a += box(338, 106, 370, 76, '完整多模态 Self-attention', 'text · refs · audio · video', size=20)
    a += arrow(708, 144, 758, 144)
    a += box(758, 106, 390, 76, '原始 Attention 输出 O', '同时保存 softmax 的 logsumexp', size=20)

    a += tx(24, 232, '只取输出视频 query 和参考视频 K / V', 20, weight='600')
    a += box(24, 264, 265, 76, '原始视频 query q', '取自上方 Q 的视频部分', size=20)
    a += arrow(289, 302, 338, 302)
    a += box(338, 264, 370, 76, 'softmax(q Kᵀᵣ / √d) Vᵣ', '参考视频所有时间位置', size=21)
    a += arrow(708, 302, 758, 302)
    a += box(758, 264, 390, 76, '原参考加权 Value：z', '及参考概率总和 m', size=20)

    a += box(24, 386, 265, 76, 'q′ = Rtime(−Δ) q', '只在此分支旋转时间相位', fill='#e4f4ee', stroke='#459c81', size=20)
    a += arrow(156, 340, 156, 386)
    a += arrow(289, 424, 338, 424)
    a += box(338, 386, 370, 76, 'softmax(q′ Kᵀᵣ / √d) Vᵣ', '同一组参考 K / V；所有时间参与', fill='#e4f4ee', stroke='#459c81', size=21)
    a += arrow(708, 424, 758, 424)
    a += box(758, 386, 390, 76, '对齐分支的加权 Value：zΔ', '对应参考与输出的时间原点', fill='#e4f4ee', stroke='#459c81', size=20)

    a += tx(24, 530, 'm = exp(LSEᵣ − LSEall)', 21, weight='600')
    a += tx(24, 562, '原 softmax 中参考视频', 18)
    a += tx(24, 589, '所有 key 的概率总和', 18)
    a += box(338, 516, 810, 90, 'O′ = O + αm (zΔ − z)', '替换参考部分的条件概率分布，再进行输出投影 Wₒ', fill='#e4f4ee', stroke='#459c81', size=25)
    a += arrow(953, 462, 953, 516)
    a += '<path d="M1158,144 H1170 V502 H1110 V516" stroke="#64748b" stroke-width="2" fill="none" marker-end="url(#arr)"/>'
    a += '<path d="M1148,302 H1158 V488 H790 V516" stroke="#64748b" stroke-width="2" fill="none" marker-end="url(#arr)"/>'
    a += arrow(290, 561, 338, 561)
    a += tx(24, 659, '本次配置：第 7–15 个去噪步，全部 50 个 DiT Block，α = 1。', 20, weight='600')
    a += tx(24, 695, 'Δ 由 PackedLayout 的时间原点差计算；图中展示计算路径，成片结果在实验部分报告。', 18, color='#526277')
    return svg(1190, 724, a, '只在辅助视频参考Attention分支旋转query时间相位的计算路径')


if __name__ == '__main__':
    p = Path(__file__).parent / 'assets' / 'reference_branch.svg'
    p.write_text(make_diagram())
    print(p)
