from pathlib import Path
from build import svg, tx, box, arrow


def make_diagram():
    drawing = tx(24, 32, '参考视频与生成视频的时间位置编码', 24, weight='600')
    drawing += tx(24, 65, '位置编码对照：单个参考视频；相同时间采样与空间网格', 18, color='#526277')
    drawing += tx(24, 112, '原始 PackedLayout', 22, weight='600')
    drawing += tx(24, 155, '参考视频', 19)
    drawing += tx(24, 225, '生成视频', 19)
    drawing += box(220, 126, 280, 52, 'τ₀ … τ₃₁', fill='#e4f4ee', stroke='#459c81', size=19)
    drawing += box(710, 196, 280, 52, 'τ₀ … τ₃₁', fill='#eee8fa', stroke='#a18ac4', size=19)
    drawing += tx(220, 199, '时间坐标起点 r₀', 17)
    drawing += tx(710, 272, '时间坐标起点 r₀ + Δ', 17)
    drawing += '<path d="M220,284 H710" stroke="#9b6742" stroke-width="2"/>'
    drawing += tx(465, 308, 'Δ 来自实际序列布局', 18, anchor='middle', color='#9b6742')
    drawing += tx(24, 363, '原点对齐', 22, weight='600')
    drawing += tx(24, 406, '参考视频', 19)
    drawing += tx(24, 476, '生成视频', 19)
    drawing += box(220, 377, 280, 52, 'τ₀ … τ₃₁', fill='#e4f4ee', stroke='#459c81', size=19)
    drawing += box(220, 447, 280, 52, 'τ₀ … τ₃₁', fill='#eee8fa', stroke='#a18ac4', size=19)
    drawing += '<path d="M220,369 V510" stroke="#64748b" stroke-width="1.5" stroke-dasharray="5 5"/>'
    drawing += tx(534, 408, '生成视频／音频：t′ = t − Δ', 21, weight='600')
    drawing += tx(534, 445, '同一物理时刻的参考与输出具有相同时间坐标。', 18)
    drawing += tx(534, 477, '帧顺序、采样时刻、空间坐标保持。', 18)
    drawing += tx(24, 552, '作用位置', 21, weight='600')
    drawing += box(24, 575, 265, 66, '时间坐标 t′', 'PackedLayout → 新旋转表', size=19)
    drawing += arrow(289, 608, 332, 608)
    drawing += box(332, 575, 265, 66, 'MM-RoPE(Q, K)', '每个 DiT Block', fill='#e4f4ee', stroke='#459c81', size=19)
    drawing += arrow(597, 608, 640, 608)
    drawing += box(640, 575, 265, 66, 'Attention → 输出 O', '沿用原始注意力计算', size=19)
    drawing += tx(24, 687, '这一变更影响输出 tokens 与其他模态的相对位置关系；使用完整成片检验编辑和时序。', 18)
    drawing += tx(24, 721, '横向位置为示意。R122 实际 Δ = 178.333333 个位置坐标单位；Δ 的单位不同于动作延迟帧数。', 17, color='#526277')
    return svg(1120, 748, drawing, '原始时间坐标与原点对齐的对照及MM-RoPE作用位置')


if __name__ == '__main__':
    path = Path(__file__).parent / 'assets' / 'aligned_rope.svg'
    path.write_text(make_diagram())
    print(path)
