# 候选 C：当前预测视频的时间重映射——查重与可否决条件

2026-10-18。只读研究审查；未实现候选、未启动 GPU、未改 R64 等实验。本目录的软件副本用于核查公开实现。以下差别是机制描述，尚不构成新颖性或有效性结论。

**目前判断：可以先做可否决诊断；直接插值 H3 latent 时间轴后声称修复动作时间，证据不足。** 最接近的新增先例包括 ReTime 和已有 H3 Motion Lab。候选需要回答的具体问题是：固定长度的当前 clean endpoint，能否通过参考动作相位估计的单调映射纠正时间，并在保留编辑内容时优于最终视频的同映射后处理。

## 1. 已有机制与候选的交集

| 原始来源 | 核实的方法 | 候选仍需验证的差别 |
|---|---|---|
| [TempoControl v3 §4](https://arxiv.org/html/2510.02226v3#S4) | 聚合视频对文本的注意力为时间信号，以目标时间 mask 的相关性、强度、空间熵损失优化 noisy latent；早期若干步内更新，可按相关性提前停。 | 本候选重采样当前视频内容；其 φ 来自参考与编辑后动作的对应关系。动态采样引导本身已有。 |
| [FlowMotion v2 §§3.2–3.4](https://arxiv.org/html/2603.06289v2#S3) | 用 z₀预测及源视频的 forward-noised 预测做 latent alignment 与跨帧差分 alignment，并正则当前 velocity。 | 候选在自己的预测内容上改变物理时间索引，参考只给对应关系；需证明对应正确及外观保持。endpoint/velocity 层的运动引导已有。 |
| [LatentWarp v1 §4](https://arxiv.org/html/2311.00353v1#S4) | 源视频光流把上一帧生成的 noisy latent 空间对齐到当前帧；遮挡/残差 mask 决定融合；末段停用。 | 本候选改变物理时间索引。用 warp 后的生成 latent 影响后续去噪、处理可见性和末段停止已有。 |
| [WorldForge v1 §§3.2–3.4](https://arxiv.org/html/2509.15130v1#S3) | 在每步 x₀预测中融合由几何 warp 得到的轨迹 latent，再加噪继续；按 flow 相似性选择通道，并比较引导/原预测。 | 本候选搬动当前编辑内容，且 φ 表示动作相位。warp、x₀校正、返回采样轨迹这一组合已有。 |
| [RVD v1 §3.1、B.2](https://arxiv.org/html/2609.36496v1#A2.SS2) | 训练 dynamics bottleneck/renderer；在其 dynamics token 时间轴重采样，0.5×最近邻加平滑、2×隔点取样。retiming 操作无需额外训练。 | 原生 H3 endpoint 与已训练 dynamics representation 的性质不同。不能把 RVD 全框架称 training-free，也不能把“时间 token 重采样”作为空白。 |
| [ReTime v1 §4.1](https://arxiv.org/html/2604.22554v1#S4.SS1) | SigLIP 帧间距离拟合语义进度，逆映射给时间坐标；分频、随去噪步衰减地修改 temporal RoPE，再生成，可迭代校正。论文标 SIGGRAPH 2026。 | 候选使用源动作对应与当前单次去噪 endpoint；需证明逐步干预有收益。内容驱动的自动 retiming、不同去噪阶段的强度已经覆盖。 |

另检索到 [Prioritizing Faithfulness 的 OpenReview 原文 §4.1/算法2](https://openreview.net/pdf?id=2wSORykWAc)：每步优化空间 homography，变换 clean prediction 后继续合成。该 PDF 的索引正文可读，直接打开遇站点验证；未据此确认最终发表版本。它进一步说明“变换 x₀再返回采样”是已有通用模式。

## 2. H3 Motion Lab：已核固定源码的直接软件先例

固定 [commit f4868b4a08e8a504ce86db54a17961d399ffa2bc](https://github.com/matlowai/ComfyUI-MAINodes/tree/f4868b4a08e8a504ce86db54a17961d399ffa2bc)，提交时间 2026-08-29。已归档 README、motion.py、两份 workflow 及 SHA。

`motion.py` 的实际路径：

- `H3JerkOracle`（704）、`_profile_to_plan`（880）：由 latent 时间变化给局部 hold 数量。
- `H3TimeSmear`（1661）在 **RGB 帧轴**重复帧，`H3V2VInit`（2326）接 VAE 编码后续采样；`H3ExactRecover`（1754）选每组首帧恢复原时间长度。
- `H3ProbeSchedule`（3704）可提前截断第一遍；实际 probe workflow 的 sampler **denoised_output** 同时进入 oracle 和 decode→smear→encode。
- `temporal_insert_map/fill`（2639/2681）、`H3TemporalInsert`（2709）按 H3 物理帧中心计算 **latent 时间轴插值**，原 token 可固定。
- `H3MidInsert`（2920）在中途 noisy latent 插入时间位置、补偿插值噪声方差，然后继续剩余 sigma。

这些路径针对快速运动的清晰度/重生成。所核代码未进行源视频与编辑视频的动作相位匹配。候选 C 的限定差别为固定长度、相位驱动的 clean endpoint 重映射；“自身 latent、中途插值、继续去噪”均已有 H3 实现。

README 中“一个 token 不能容纳四个姿态”的原因说明不能直接采信：H3 的通道与 decoder 同时编码多个时间位置。软件作者对清晰度和插值残差的测量属于其报告，本次未复现实验。

固定源码链接：[motion.py](https://github.com/matlowai/ComfyUI-MAINodes/blob/f4868b4a08e8a504ce86db54a17961d399ffa2bc/motion.py)，[early x₀ workflow](https://github.com/matlowai/ComfyUI-MAINodes/blob/f4868b4a08e8a504ce86db54a17961d399ffa2bc/examples/archive/motion_pipeline_probe_expert.json)。

## 3. H3 的 physical retiming 必须单独验证

本实验 pinned `comfy/ldm/minimax/vae.py` SHA 为 `40c4bf2db63279e0d13eb8de2c8a4602207a90cf9350f94afbee7aeed8b757ea`，与 R64 parent_core_hashes 相同。

代码显示：encoder 按17帧分块并使用 temporal convolution（544–557）；ViT decoder 展开 latent 的 T/H/W，经3D RoPE和36层 Transformer，投影出每 token 四帧的空间块（261–318）；decode 还有重叠块、前置帧移除及融合（609–657）。因此位置分箱 `(1,4,4,4,4)` 是坐标约定，不能当成独立帧存储。R64 `layout.py:20` 也明确 bins 不等于精确 VAE 感受野。

设 D/E 为包含原生归一化的解码/编码，Rφ 为 RGB 物理时间重采样，Lφ 为 latent 时间轴插值。架构没有保证：

`D(Lφ(z)) = Rφ(D(z))`。

固定长度的物理变换可定义为 `E(Rφ(D(z)))`，但会增加 VAE 往返误差和成本。是否值得采用，要与 identity 往返及 latent 近似分开测量；跨17帧边界和同块内偏移应分别检查。

## 4. endpoint 修正的数学及适用域

σ 表示噪声水平，τ 表示视频物理时间。沿当前 flow 参数化：

`x₀_hat = zσ − σ v`

`x₀_target = Wφ(x₀_hat)`

`v′ = (zσ − x₀_target) / σ`

`z_next′ − z_next = (σ − σ_next) / σ · (x₀_target − x₀_hat)`。

这是 clean endpoint 与 Euler velocity 的代数换元；创新性不能来自最后一条公式。σ=0 时该表达式不定义，Wφ 的实际坐标及强度另需约定。若 g(τ)=s(τ−d)，补偿应取 g(τ+d)；尾部没有对应帧的范围必须显式排除或定义边界操作。

单调时间映射只改变已有动作的发生时刻。若生成内容改变动作种类、幅度不足、动作已消失，或左右臂需要互相冲突的时间映射，它不能同时满足目标。全帧重采样还会移动背景/镜头的时间；局部空间重采样会出现边界与遮挡问题。可见性不足时应保持 UNKNOWN。参考只给 φ 可避免显式复制其外观，但后续 VAE/生成过程仍可能改变身份，需实际检查。

## 5. 最小对照和停止条件（设计；本目录未执行）

1. **最终视频可否对齐。** 使用已冻结 Native 与已有 pose；同一个单调 φ 同时评价左右臂，保留原物理时间、边界 valid mask、全有效片和预定前2秒。报告源对自身零偏移及预定正负偏移。若一臂改善以另一臂恶化为代价，或需非单调/大段重复才能匹配，停止“单一全画面 retiming 解决此例”的解释。可见性不足属于不可评价。
2. **H3 算子是否正确。** 选固定的实际 x₀和 φ，比较 `D(Lφ(z))`、`Rφ(D(z))`、`D(E(Rφ(D(z))))`；另有 φ=identity 的 E/D 往返。固定跨/不跨17帧边界的偏移，报告动作时间、身份细节、重影、边界，保留全部结果。若 latent warp 的时间方向不对或伪影明显，暂停将其接入采样。
3. **在线有无额外作用。** 前两关通过后，才比较原生生成、最终视频同φ后处理、identity endpoint 干预、候选在线重映射。先固定φ隔离执行算子的作用，再评估自动φ。若最终后处理达到同等结果而在线更慢/更差，当前证据支持后处理。重复轮数、解码成本和额外模型 forward 都须记录。

源与生成动作对应失败的案例继续保留；已看过的 fitness 等属于开发性诊断。本审查没有证明候选尚无人提出，也没有证明它在 H3 有效。
