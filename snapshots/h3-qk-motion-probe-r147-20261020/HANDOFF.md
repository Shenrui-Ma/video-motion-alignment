# R147：单层 Q/K 运动观察诊断

实现完成，9 项 CPU 测试通过。尚未接入 GPU 推理；没有新增 DiT、VAE、光流网络或姿态网络前向。所有修改位于本目录。

## 作用位置与计算

在 H3 第 26 个 DiT block（零起始索引 25）的 attention override 入口，读取已经经过 RMSNorm 与 RoPE 的 Q/K。此处在 attention 和该层时序干预之前。每次读取当前采样轨迹的普通前向；此前层或此前采样步的引导可能已影响这些特征，应在实验解释中保留这一点。

从实际 attention head 数量中等距选 4 个；例如 32 heads 选择 0、10、21、31。对参考视频内部以及输出视频内部，分别计算相邻 latent 时间位置的局部匹配。查询点每隔 4 个空间 patch 取一个，候选点仍在完整 patch 网格内，半径 2。实际 23×41 网格共有 66 个查询点，每点至多 25 个候选。

相似度为选定 heads 的 cosine 平均。正向 Q(t) 匹配 K(t+1)，反向用同一相似度关系从选中的 K(t+1) 查找 Q(t)，要求互为最近邻且第一、第二名差值超过数值去重阈值 1e-6。该阈值只排除平局；本模块没有干预起停阈值、延迟估计或 controller。返回 4×4 空间区域的平均 dx、dy、位移幅度、互惠匹配支持比例、cosine 间隔以及非零位移比例。静态或全部匹配不确定时返回 `UNKNOWN`。

每次同时记录两个版本：

1. 原始 Q/K。
2. 在副本上消去时间 RoPE，空间 RoPE 保留。使用实际 `PackedLayout.position_ids` 和实际 checkpoint `diffusion.rope.inv_freq`。H3 时间通道是 `[0:16]` 与 `[48:64]`，其余通道原样保留。float16/bfloat16 模型中先前的旋转已经量化，因此逆旋转是有限精度的近似。

时间位置按 H3 的 `(1,4,4,4,4)` 帧覆盖周期逐项记录。107 帧采样、105 有效帧、32 bins 的饮酒样例只使用完全有效的相邻 bins，排除末端含 padding 的 bin31。输出包含每个 bin 的实际帧范围、中心秒数、两种视频的实际 RoPE 时间值，避免把所有 bins 误当成固定 4 帧。

## 最小接入

把 `qk_motion_probe.py` 复制到新实验隔离包对应 extension 内。在模型和实际 geometry 已知时只创建一次：

```python
from .qk_motion_probe import QKMotionProbe
state.qk_motion_probe = QKMotionProbe(
    diagnostic_dir, inv_freq=diffusion.rope.inv_freq,
    valid_frames=105, fps=24,
)
```

在 `TemporalAttentionOverride.__call__` / `ReferenceOriginAttentionOverride.__call__` 内，计算 attention 之前调用：

```python
if self.block == 25:
    state.qk_motion_probe.observe(
        q, k, self.plan, state.layout_object.position_ids,
        physical_step=physical_euler_index,
        pass_kind="ordinary", block_index=self.block,
    )
# 原有 attention 继续执行一次；Q、K、V 与 attention 返回值都不改。
```

R146 固定推理已经约定 20 次前向对应 20 次 Euler 更新，因此其 `state.forward_index` 可在该前提下传作 `physical_euler_index`。R144 这类额外 Full 前向实现应读取 transaction 的 `physical_index`，仅在 native/ordinary 分支调用；额外分支传 `pass_kind="full"` 会直接跳过。该模块拒绝同一步重复 ordinary 记录。

接入方应把观察诊断错误写入独立错误记录，并禁用后续观察，使诊断异常不会中断已授权的视频实验。原始 `observe` API 保留显式异常，便于 CPU 测试和集成发现布局错误。此处未改动任何现有实验文件。

## 验证

`test_probe.py` 覆盖已知平移、静态、平局、零向量、32 bins 与 padding、只消去时间 RoPE、Q/K/position/RNG 不变、相同输入的 attention 输出逐值相同且仅调用一次、单步文件体积限制和错误 geometry。

`CPU_TIMING.json` 使用实际 32×23×41 patch geometry 的合成张量，CPU 4 线程，选择 4 heads。32 heads 以单个合成 head 的 expanded view 提供，避免分配无用途的大张量。GPU 未初始化，模型和 VAE 前向数均为 0。每步文件约 72 KB，计算临时局部特征张量上界 844800 float32 元素（3.38 MB），未创建 S×S 或完整空间匹配矩阵。实际 GPU 同步计时由 CUDA events 记录，CPU 计时包含 descriptor 回传；最终 JSON 序列化不包含在 `compute_and_copy_wall_seconds` 内。

## 待验证

真实 H3 Q/K 由不同投影得到，局部 cosine 匹配的准确性需要实测；合成平移验证的是实现与符号方向。下一步先观察 R146 饮酒样例的 descriptors、支持比例、不同时间 RoPE 处理的差异和实际耗时，再决定是否用来估计时差。DiTFlow、MOFT 已使用 DiT 特征提取运动，本模块作为其思路在 H3 上的诊断实现记录，不把特征匹配家族本身写成创新。

## 2026-10-20 最后修正与冻结

几何缓存接受数值完全相同的 `PackedLayout.position_ids` 克隆。每步将位置张量与首次CPU快照逐值比较；任一时间或空间坐标变化均拒绝记录。新增32 bins连续两步克隆位置测试及坐标变更拒绝测试。R147保持prepared，不接入R146/R148，不启动GPU实验。
