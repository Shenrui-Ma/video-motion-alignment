# H3 动作时间对齐：候选改进与文献核对

2026-10-20。本文是供选择的研究方案；三个主候选与一个坐标消融尚未运行。当前已安排的固定引导与时间相位补偿实验继续按原配置执行。

## 已知事实与选择顺序

本地已试过参考视频组内同时间 attention 替换、动态残差 DC、空间边缘保留 SP、反向参考读取约束、目标路径重定时，以及时间相位补偿。新的方案应改变一个明确的机制，保留这些已完成对照。

建议的选择顺序：

1. **先补“正向同时间引导＋限制反向读取”的组合格**：代码改动小，已有两个单项结果，可快速测交互作用。
2. **以跨 query 的参考时间覆盖约束作为算法主候选**：把“每个 query 各自挑参考帧”改成“多个输出时刻共同分配参考时间的使用量”。
3. **按实际修正增量选择 Attention head 和层**：研究哪些干预真正进入 residual stream，减少与外观编辑冲突的修正。
4. **部分 RoPE 频带补偿保留为坐标消融**：已有频带调制工作非常接近，适合解释全频补偿的作用。

Flow matching 的速度向量是沿去噪时间的变化方向，物体在视频里的速度沿物理时间变化。这两种导数需分别建模。用 flow 向量投影、干净 latent 时间差分或 RoPE 重定时作为单独创新，已有 FlowMotion、SWIFT、MOFT、ReTime 等直接先验；这类工具仍可用于下面的具体机制。

## 统一记号及实际作用位置

在 H3 一个主 DiT block 中，经过 RMSNorm 和 RoPE 的 Q/K 与 V 进入联合 Self-Attention。这里的参考视频、角色参考图、文本、输出视频是不同 token 区段。

对输出视频的某个 query/head，设原始 Attention 输出为 \(o_i\)，参考视频区段的总概率为 \(m_i\)，其组内归一化概率为 \(a_{ij}\)。\(j\) 属于参考视频 token；\(\mu_i^R=\sum_j a_{ij}V_j\)。原方法把这部分改成对应物理时刻的参考视频条件均值：

\[
o_i'=o_i+m_i(\mu_i^{same}-\mu_i^R).
\]

修改发生在 `optimized_attention` 返回后、`out_proj` 前；随后经 `out_proj` 和该 token 的 AdaLN gate 加入 residual stream。保持的 \(m_i\) 是本次 Attention softmax 中参考视频这一组 keys 的总概率。该操作改变组内时间分配，整条生成轨迹会随后续层和 Euler 更新改变。

本机代码证据：`h3-timing-ive-reference-origin-r132-20261020/design/H3_model.py` 的 `Attention.forward`、`out_proj`、`_mod_gate`。时间坐标从真实 packed layout 读取；H3 的 latent 时间 bin 覆盖像素帧数按 1、4、4、4、4 循环，使用实际物理时间及有效帧范围。

## 候选一：跨 query 的参考时间覆盖约束

### 假设

短事件受到长时间相似姿态的竞争，可能出现多个输出时刻反复读取同一段参考内容，而参考中的短事件很少被读取。原有逐 query 的同时间替换能强制读取对应片段，但会对全部被选 query 施加同一种约束。

这里把多个输出时刻连成一个小规模优化问题：对欠缺读取的参考时间增加使用量，同时保留 Q/K 内容匹配和物理时间邻近性。是否存在这种“欠覆盖”，应首先用已知延后样本的实际 attention 统计验证。

### 机制与公式

在少量层和 heads 中，按输出时间 bin、局部空间 tile 汇总条件概率，得到 \(A_{ij}\)。\(i\) 是输出时间与局部区域，\(j\) 是参考时间 bin，每行和为 1。时间内的空间对应仍由原始 attention 决定。

令 \(\rho_i\) 表示有效物理时长与可见运动支持的归一化权重；\(G_{ij}\) 是以对应物理时刻为中心、具有有限宽度的时间核。参考时间的期望使用量为 \(b_j=\sum_i\rho_iG_{ij}\)。求：

\[
\min_{X\ge0,\;X\mathbf1=\rho}
\mathrm{KL}(X\|\mathrm{diag}(\rho)A)
\lambda_t\sum_{ij}X_{ij}(\tau_i-\tau_j)^2
\lambda_c\mathrm{KL}(X^\top\mathbf1\|b).
\]

\[
P_{ij}=X_{ij}/\rho_i,\qquad
o_i'=o_i+m_i\sum_j(P_{ij}-A_{ij})\mu_{ij}.
\]

\(\mu_{ij}\) 是该输出 query 对参考时间 bin \(j\) 的条件 Attention 均值。实现时用小矩阵求共享的列缩放因子，再在参考子 Attention 内应用；最终重新归一化到原 \(m_i\)。对聚合 tile 的因子进行广播后，要记录实际细粒度列质量偏差，因为广播近似与精确小矩阵解不同。

真正新增的依赖是：一个输出时刻怎样使用参考，会影响其他输出时刻的分配。仅对单个 query 施加硬同时间约束会回到现有 SP/Full 形式；有限宽度和有限 \(\lambda_c\) 才保留这个候选的自由度。只靠总覆盖仍允许时间置换，因此物理时间成本是必要项。

自动窗口可由 \(|P-A|\) 的时空分布给出。去噪过程中反复计算小矩阵，达到稳定且修改幅度低于观测噪声时结束该次引导。启动阈值、停止阈值和置信度尚需在开发样本上校准；不能直接把任意固定数值称为自动推导。

### 最接近工作及区别

- **Sinkformers** 用 Sinkhorn 将 attention 从行归一化扩展为双随机矩阵；**unbalanced OT style transfer** 早已采用软列边缘缓解重复匹配。上面的优化方法采用这套已知数学。
- **FreeMix** 在相邻源视频帧之间用 OT 建立空间特征对应。这里的运输轴是多个输出时刻对参考时间 bin 的使用分配。
- **DIAL、RefGAP** 对参考 logits 进行引导。RefGAP 改变参考组总概率、保留组内比例；这里保持组总概率并约束组内跨时间覆盖。
- 现有本地 DC/SP 的数学排除针对单 query 的空间边缘与时间边缘。跨 query 的列约束增加了耦合，但“加 Sinkhorn”本身属于成熟方法。

### 最小实验与风险

先在同一已知故障样本上，保存少量层的 \(A\)、物理时间、有效支持和列质量。比较原同时间引导、仅时间成本、时间成本＋软列约束；统一修正范数及运行区间。第二步加入一个重复动作片段和一个普通编辑已对齐的片段。

通过条件：短事件原先确有欠覆盖；加入列约束后，成片事件时间误差与局部动作误差同时下降，角色与背景编辑保持成功。主要风险是强行均衡参考使用量、把遮挡当作漏动作、或平均不同空间主体。只做全局时间矩阵时，局部短事件也可能被背景淹没。

计算不涉及额外完整 DiT forward、VAE 解码或 DWPose。额外开销来自局部 Q/K 统计和带时间因子的参考 Attention；其真实耗时需测，不能从小矩阵尺寸推断整项成本。

## 候选二：按实际修正增量选择 Attention head 和层

### 假设

同样的 attention 概率变化，通过不同 head 的 V、`out_proj` 和 AdaLN gate 后，对 residual stream 的影响不同。全层全 head 引导可能包含作用很弱的修改，也包含主要改变外观的修改。选择依据应包含“这次修正实际写入了什么”。

### 机制与公式

对少量候选层/head，在当前 Q/K/V 上计算原方法的修正：

\[
\delta o_{\ell h}(i)=m_{\ell h}(i)
(\mu_{\ell h}^{same}(i)-\mu_{\ell h}^{R}(i)),
\]
\[
D_{\ell h}(i)=g_\ell(i)\odot
W_{\ell,h}^{O}\delta o_{\ell h}(i).
\]

\(D\) 是该 head 在 Attention residual 加法位置产生的精确局部增量。只计算 sampled queries 的 \(D\)，无需逐 head 重跑整个模型。

设 \(c_{\ell h}\) 是参考内部相邻帧 Q/K 双向匹配的一致性；\(\bar D_{\ell h}\) 是经过时间对应后的均值；\(\nabla_\tau D\) 以物理时间计算。一个可直接验证的排序分数为：

\[
s_{\ell h}=c_{\ell h}
\frac{\|\nabla_\tau D_{\ell h}\|^2}
{\|D_{\ell h}\|^2+\epsilon}
-\beta\frac{\|\bar D_{\ell h}\|^2}
{\|D_{\ell h}\|^2+\epsilon}.
\]

该式把可靠的跨帧对应、随时间变化的修正和静态修正分开。先测试排序是否有效，再决定固定选层还是逐步更新。原 Attention 和 FFN 仍正常执行，选择开关控制的是额外时序修正。

更强的后续版本可以对极少量 token 做一次 block 内的反事实 FFN，再比较下一层 Q/K 的时序对应变化；这会增加计算，需在简单分数有价值之后单独评估。当前公式没有把高分等同于最终动作修复，因果作用仍由实际选 head 的成片消融测量。

### 最接近工作及区别

- **HALO** 已识别运动 heads、按低熵选择结构 heads，并引导 latent 或注入参考 V。
- **Why Do Video Diffusion Models Violate Physics?** 已用 attribution patching 与置零消融测 head 对 flow velocity 的贡献。因果选 head 已有明确先例。
- **EG-Sparse** 已在每层每步依据熵决定跨 head 共享稀疏预算，包含 value-aware 排序。
- **RefGAP** 已依据参考组概率自适应调整强度，并由验证集 profile 选择全层或后半层。

可探索的具体区别是：选择对象为既有“保持参考总概率的时序修正”；评分作用于经过 `out_proj` 和 AdaLN 后的实际增量，并结合局部运动可靠性。新主张应围绕这套分配是否减少编辑副作用、提高相同计算预算下的时序修复。

### 最小实验与风险

沿用同一强度、区间及简单提示词，对比全 head 引导、等数量随机 heads、HALO 式可靠运动/低熵 heads、上述增量评分。所有稀疏版本匹配 head 数和修正总范数，避免把“引导变弱”误当作选对了位置。

优先在一个“引导改善时间但出现重影”的样本和一个“角色替换受引导改变”的样本上测试。主要风险是时间变化能量偏爱抖动；静态与运动方向也会重叠。跨帧一致性和最终编辑质量是必要检查。

## 候选三：正向同时间引导与反向参考读取限制的组合

### 假设与已有证据

正向操作是输出 query 读取参考视频；反向操作是参考 query 读取输出视频。H3 联合 Attention 允许两个方向。同层所有 Q/K/V 同时生成，因此改变参考行会从下一层开始影响输出。

既有 R25 单故障样例记录：普通编辑约 13 帧时间误差、正向 Full 约 1 帧、反向 BLOCK 约 8 帧。各项单独有效，组合格尚待在实际文件中复核后补齐。由于 Full 已接近时间误差下限，此组合最有价值的观察是重影、局部动作和编辑完成度。

### 作用位置

输出视频 query 沿用现有同时间引导。参考视频 query 在指定时空范围改为读取除输出视频之外的 keys：

\[
O_T'=O_T+m_R(\mu_{same}-\mu_R),\qquad
O_R'=\mathrm{Attn}(Q_R,K_{\neg T},V_{\neg T}).
\]

BLOCK 必须重新对剩余 keys 归一化；简单减去原输出视频项会改变 Attention 的尺度。人物参考图、文本和其他区段继续按已定义的范围处理。

这里测试的是 H3 局部边的组合。封住参考视频到输出视频这一条直接读取边后，文本和音频仍可能提供间接交互；H3 每个 forward 会重新构造参考输入。

### 先验与可研究缺口

**OmniTransfer、Identity as Presence、FullDiT2** 已有参考不读取生成目标的非对称结构。**Vidu S2-Editing** 采用时间对应帧交互。非对称 attention 的原则可直接借鉴并引用。

可验证的缺口是冻结 H3 中，正向时间选择与反向局部限制的交互：是否保留正向的时间修复，同时减少深层参考特征被目标状态影响后产生的副作用。

### 最小实验

普通编辑、正向 Full、反向 BLOCK、二者组合构成 2×2。保持实际输入、noise、sigma、backend 和提示词一致，优先复测已支持效果的样本。报告两个因素的主效应和组合交互：

\[
I=Y_{Full+Block}-Y_{Full}-Y_{Block}+Y_{Native}.
\]

每个 \(Y\) 只代表同一种结果量；时间误差、重影率、编辑成功分别计算。若组合仅重复 Full 的时间收益，记录其质量和成本即可；若以更弱的正向干预实现相同修复且降低重影，才形成进一步优化的依据。

## 保留候选：只补偿部分时间 RoPE 频带

目前全频补偿可写为 \(\tilde q_b=R(-\omega_b\Delta)q_b\)。保留方案令：

\[
\tilde q_b=R(-g_b\omega_b\Delta)q_b,\qquad g_b\in[0,1].
\]

仅辅助计算输出 query 对参考视频 keys 时使用 \(\tilde q\)；原主 Attention 沿用原坐标。先比较全频、低频、高频、无补偿，再考虑用实际 Q/K 的相位敏感度选择 \(g_b\)。相位敏感度只表示某频带对 logits 的影响，运动语义需要另外验证。

**ReTime** 已按频带混合原时间和重定时时间；**Untwisting RoPE** 已对共享参考 attention 的频带进行选择；**RIFLEx** 已修改特定时间频率；**TIE** 采用区间积分得到 sinc 频率调制；**Making Time Editable** 训练 FPS 与 latent-time adapters。该方向的具体问题是 H3 辅助参考分支的固定原点补偿范围，适合作为现有 phase 操作的机制消融。

## 本轮暂缓的路线

- 将 DC 或 SP 换写为硬边缘 KL/Sinkhorn：现有数学审查已说明退化关系。
- 对目标 latent 做时间重采样：R4 已有负面结果。重新尝试需先改变其错误假设。
- 将 flow velocity 投影称作动作速度分解：FlowMotion 已做去噪速度投影；运动的物理时间导数仍需另外估计。
- 直接把 H3 参考条件加到与输出相同的噪声：本机条件采用 `0.999*z+0.001*noise` 和相应 token timestep，强扰动会改变训练时条件分布。它可作为参数诊断，优先级低于上述机制实验。

## 主要来源

- [DIAL](https://arxiv.org/html/2609.11507v1)
- [RefGAP，§3.2–3.4](https://arxiv.org/html/2609.35708v1)
- [HALO，§3–4](https://arxiv.org/html/2607.11081v1)
- [DiTFlow](https://arxiv.org/html/2412.07776v2)
- [Motion heads 与 RoPE 物理规律分析，§4.2、§6](https://arxiv.org/html/2609.23658v1)
- [EG-Sparse](https://arxiv.org/html/2610.14672v1)
- [Sinkformers](https://arxiv.org/abs/2110.11773)
- [Unbalanced OT attention，§3.2–3.3](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/ipr2.12403)
- [FreeMix，ICCV Workshops 2025](https://ieeexplore.ieee.org/document/11374499/)
- [OmniTransfer，§4.3](https://arxiv.org/html/2601.14250v1)
- [Identity as Presence，§3.3](https://arxiv.org/html/2603.17889v1)
- [FullDiT2](https://arxiv.org/html/2506.04213v1)
- [Vidu S2-Editing](https://arxiv.org/html/2609.11638v1)
- [ReTime，§4.1](https://arxiv.org/html/2604.22554v1)
- [Untwisting RoPE，§5](https://arxiv.org/html/2602.05013v1)
- [RIFLEx](https://arxiv.org/html/2502.15894v1)
- [TIE，§3.1–3.3](https://arxiv.org/html/2605.10543v1)
- [Making Time Editable，§2](https://arxiv.org/html/2606.10183v1)
- [FlowMotion](https://arxiv.org/html/2603.06289v2)
- [AV-FlowEdit，§3](https://arxiv.org/html/2610.13072v1)
- [MOFT](https://arxiv.org/html/2405.14864v2)
- [SWIFT](https://arxiv.org/html/2605.09442v1)

本轮新补的 AV-FlowEdit 同时采用 flow 差分显著性、音频活动、多尺度低频位移和噪声阶段调度；后续若使用 flow 差异自动控制引导位置与时间，应将其列为直接对照。本文检索覆盖上述论文及其相邻引用，候选的可发表贡献取决于最终机制与成片证据。
