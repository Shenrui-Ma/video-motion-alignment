# H3 same-time 引导的动态强度与按修正方向分配 heads：文献核查及数学方案

日期：2026-10-23。范围：只读审计本地实现、原论文及作者代码；本文不记录新的 GPU 实验结果。研究对象是已取得较好结果的全去噪过程 `alpha=.25` same-time 弱引导。动态强度和 head 分配应先作为两个独立变量验证。

## 1. 核心建议

最值得优先验证的是：**根据“当前 same-time 修正在参考视频局部时间变化方向上的成分”求解连续强度，同时以相同修正能量对照测试 head 分配**。它与旧 direction gate 的区别明确：不再把 attention 的时间重心当成动作延迟，不再只将 .25 往下压，而是用一个显式二次目标决定何时加强、何时减弱。这个目标衡量的是内部特征代理量；其与最终动作时间误差的联系需要实验建立。

第二个可独立实现的方案是：**对当前 same-time 混合使用精确 attention KL 剂量约束**。它可以完全复用已经计算的三个 LSE，数学关系干净，额外计算少，适合作为具有解释性的动态剂量基线。但它本身只控制分布改变的大小：让同帧概率更大并不直接识别动作错误，不能把纯 KL 限幅当作已解决时间对齐。

泛称“动态 guidance”“投影 guidance”“动态选 heads”“attention trust region”均已有直接先例。具体创新应落在：参考视频**物理时间**的局部 Value 变化是否能预测 same-time 修正的收益，以及能否在相同编辑质量／修正剂量下改善动作时间一致性。后文逐项区分这些先例；没有因为某个数学工具已有先例而否定这个具体机制。

## 2. 当前实现及不可混淆的两个时间轴

冻结实现见 `inference/package/custom_nodes/H3Study/core.py`；`innovation/direction_runtime/frozen.py` 固定 SHA256，core 为 `2dba7d615092491ad5b696b81ae2c0d41e9cae3760046aeefbdf33ad0d543691`。当前已读实现中，Flash attention 返回 output 和 LSE；`_aligned_attention` 已返回同帧 LSE。

对一个去噪调用、一个 block、一个 head、一个画布 query，记：

- `O`：该 query 对全部多模态 K/V 的原生 attention 输出。
- `R`：同一 query 只对完整参考视频 K/V 的归一化输出。
- `S_t`：同一 query 只对参考视频对应物理时间 bin 的输出。
- `m=exp(LSE_ref-LSE_full)`：完整 attention 分配给参考视频的总质量。
- `D=m(S_t-R)`：原有 same-time 修正方向。

当前操作为 `O'=O+alpha*D`，`alpha=.25`。在同一输入状态、同一次 attention 中，它保留参考视频总质量及非参考部分，只重新分配参考视频内部的读出。它不保证后续层和最终视频的所有非动作属性恒定。

本文 `t` 表示视频物理时间，`n` 表示去噪步。参考视频相邻时刻的 Value 切向，与去噪轨迹上的 score／velocity 切向是不同对象。现有架构每层更新参考 token；因此局部时间特征应从当前层、当前调用计算，不宜默认跨层语义不变。

本地旧诊断已有反例：attention 时间重心有明显偏移，最终动作却接近对齐。因此不能直接写“attention 时间分布就是动作时间的后验概率”。低 reference mass、周期动作、多峰读出以及结构头均会破坏这个解释。

## 3. 方案 A：参考 Value 局部时间方向驱动的连续强度

### 3.1 同 query 的局部条件读出

在固定的少量画布 query probes 上额外计算：

`S_- = Attn(Q, K_ref[t-1], V_ref[t-1])`

`S_+ = Attn(Q, K_ref[t+1], V_ref[t+1])`

使用中心差分 `b=S_+-S_-`，将当前修正 `D=m(S_t-R)` 投影到 `b` 张成的方向：

\[
D_T=\frac{\langle D,b\rangle}{\|b\|^2}b,\qquad D_N=D-D_T.
\]

退化的近零方向不参与统计，回退现有 .25。数值实现可用极小相对正则；此时应称“正则化投影”，不要宣称严格正交或能量严格相加。可选的两维 secant 子空间为 `B=[S_t-S_-, S_+-S_t]`，但它和 `D` 都含 `S_t`，容易因共同噪声产生自相关；建议中心差分作为主版本，两维 secant 仅作消融。若使用 ridge `B(B^TB+epsilon I)^-1B^T`，它也不是严格正交投影。若实验需要严格正交性质，应对小 Gram 矩阵作谱截断伪逆。

这里 `D_T` 只能解释为“沿参考视频局部时间变化的特征成分”，`D_N` 是其余成分。人物运动、镜头运动、遮挡与照明都可能进入 `D_T`；衣服和身份也可能随时间改变。不要把两者命名为已经分离出的纯动作和纯外观。

### 3.2 用二次目标求 alpha

在同一 block 的 probes 上汇总 `E_T=sum||D_T||²`、`E_N=sum||D_N||²`、`E_D=sum||D||²`，定义：

\[
J(\alpha)=(1-\alpha)^2E_T+\lambda\alpha^2E_N
+\mu(\alpha-\alpha_0)^2E_D,\qquad\alpha_0=.25.
\]

第一项希望补足局部时间方向的 same-time 修正；第二项约束其余特征改变；第三项在证据不强时靠近已验证弱引导。闭式解为：

\[
\alpha^*=\operatorname{clip}_{[0,\alpha_{max}]}
\frac{E_T+\mu\alpha_0E_D}{E_T+\lambda E_N+\mu E_D}.
\]

初期固定 `alpha_max=.5`，`mu=1`，`lambda` 仅在开发集选择一次。`lambda=3` 时，`alpha*=.25` 的平衡条件是 **E_T=E_N**；不是 1:3。`lambda=1` 和 3 是合理的少量开发消融，不能每个测试案例单独选择。

这个公式实际改变的是完整修正 `alpha D`，暂时不直接只注入 `D_T`。这样保留现有 same-time 算子的方向及组内概率解释，先把“自动选强度”这一项做清楚。

### 3.3 从强度延伸到 head 分配

把每个 head 的时间方向比例记为 `f_h=E_T,h/E_D,h`，完整分辨率的原始修正能量记为 `e_h=sum||D_h||²`。先用如下等剂量实验隔离“选 heads”与“总量变少”：

\[
\max_{0\le a_h\le a_{max}}\sum_h e_hf_ha_h,
\quad\sum_h e_ha_h^2=\alpha_0^2\sum_h e_h.
\]

未达到上界时 KKT 给出 `a_h=tau*f_h`，用一维求解满足预算。若有用 heads 全部达到上界，剩余预算可分给零效用 heads，以保证公平对照；生产策略是否必须花完预算是另一问题。

这个预算只保证**拼接前 head 空间**的修正能量相同。实际 block residual 是 `sum_h W_o,h(a_hD_h)`，各 head 可相互抵消／增强。不能把前者报告为严格相同的输出 residual 能量。进一步可以在少量 probes 上用 `W_o,h` 及实际 residual gate 的 pullback 度量估计 head 贡献；这有额外矩阵运算，并且逐 head 能量之和仍不包含交叉项。

如果要直接以 block 输出能量约束，构造小 Gram 矩阵 `G_hk=<W_o,h D_h, W_o,k D_k>`，预算变为 `a^T G a`。它能反映 head 抵消，但成本和优化复杂度都高于第一轮，适合在 raw-head 等剂量实验有收益后再做。

### 3.4 当前 forward 所需张量、成本、调度

- 已有：Q、参考视频 K/V、R、S_t、m、原始 D。
- 新增：同一组 probes 的前后邻 bin 条件 attention 输出。两类批处理 attention 调用，不需要额外完整 DiT forward、不需要 backward、不需要 VAE/RGB/姿态追踪器。
- 若每个 bin 使用 P 个 probes，新增 QK 量级约 `2*H*T*P*N_spatial*d`；P 远小于整帧 query 数，但额外 kernel dispatch 和布局拷贝仍要计时。
- 可先每 block 一个 alpha；再独立测试每 head 一个 alpha。2×2 空间采样可能错过手指／手部，需与更密的固定采样核对，不宜选择“看见失败后才手动移 probe”。
- 全去噪过程均运行；不是固定开始／结束时刻。
- 用当前层的统计立即控制该层是因果可执行的。当前一步所有 50 层统计汇总后，再反过来控制同一步前面的层，会要求重跑；若要每去噪步统一 alpha，只能用上一步统计或承认额外 forward。第一步可用 .25。

### 3.5 机制风险和验证目标

这是“给定 same-time 目标，按局部时间特征成本自适应分配”的代理目标，不是从 RGB 标注反推的真实动作损失。需要检验：高 `f_h` 是否对应引导后更好的动作相位，而不是仅对应镜头运动、参考外观复制或数值波动。中心切向在周期动作折返点可能接近零，快速大幅非线性变化也不适合一阶近似。没有可靠信号时回退 .25，可以保留当前已有效方法。

## 4. 方案 B：精确 reference 内部 KL 剂量控制

### 4.1 已有三个 LSE 给出精确关系

令 `p_j` 为参考视频内部原始 attention 概率，S 为同帧 key 子集：

\[
s=\sum_{j\in S}p_j=\exp(LSE_{same}-LSE_{ref}),\quad
r_j=p_j\mathbf1[j\in S]/s.
\]

现有输出混合等价于 `p_alpha=(1-alpha)p+alpha*r`。修改后的同帧总质量为 `a=s+alpha(1-s)`。S 内部、其补集内部的相对概率都不变，因此：

\[
D_{KL}(p_\alpha\Vert p)
=a\log(a/s)+(1-a)\log((1-a)/(1-s))
=KL_{Bernoulli}(a\Vert s).
\]

完整 packed attention 的 KL 为 `m*KL_Bernoulli(a||s)`，因为参考组总质量 m 与非参考项保持原样。这个结论来自当前算子的代数性质，不需要假设 attention 是动作后验。

### 4.2 真正会动态改变 alpha 的预算设计

一种最直接的独立基线是：在与测试集分离的开发 trace 上统计固定 .25 的平均／分位 KL，确定一个跨去噪步固定的预算 kappa，冻结之后逐 query/head 求解：

\[
\alpha_i=\max\{\alpha\in[0,\alpha_{max}]:
m_i KL_B(s_i+\alpha(1-s_i)\Vert s_i)\le\kappa\}.
\]

若担心不同层天然尺度不同，可开发集确定每层预算，但不能把每个当前状态的 .25 KL 直接当该状态预算。

两个退化设置必须避开：

1. 对每个 i 设置 `kappa_i=KL_i(.25)`，再反解 alpha_i，结果就是 .25。
2. 当前所有 heads 的 .25 KL 求和做预算，再只求一个共享 alpha，结果也还是 .25。

另一种方式是在固定总预算下按不同 utility 分配：

\[
\max_{a_i\in[s_i,1]}\sum_i m_i w_i(a_i-s_i),\quad
\sum_i m_i KL_B(a_i\Vert s_i)\le K.
\]

未饱和解为 `a_i=sigmoid(logit(s_i)+w_i/lambda)`，`alpha_i=(a_i-s_i)/(1-s_i)`。如果所有 `w_i` 相同，它就是共享的组内 logit 偏置重新参数化；真正的任务信息来自如何定义及验证 `w_i`，不是 sigmoid 形式本身。可在方案 A 独立有效后用其时间特征效用作为 w_i，第一轮不要同时堆叠两个新模块。

### 4.3 成本、失败模式和含义

- 当前 `_aligned_attention` 已返回 LSE_same；full/ref LSE 也已存在。无需任何新 QK 或 DiT forward。
- 需要 FP32 的 exp/log 与单调标量求解。逐 query/head 的大量 bisection kernel 会带来实际延迟；可先 head/bin 汇总或拟合查表，但近似方案要记录实际 KL 误差。不要把“无额外 attention”写成“零开销”。
- 计算保持 log-space，处理 s 接近 0/1、m 接近 0、非有限值；clip epsilon 会令极端值的 KL 变成近似。
- s 很小时，同样搬入一部分同帧质量的 KL 很高，控制器会变保守。这可能恰好削弱最需要修正的样本。它衡量分布距离，不衡量修正的真实性。
- s 接近 1 时可允许较大的 alpha，但 D 往往很小；必须同时报告实际输出修正能量。
- 这里的 KL 是一个 attention row 的分布差异。跨 heads／layers 的 KL 求和是一种预算定义，不是最终视频分布 KL，也不自动给出最终编辑质量界限。

## 5. 逐项文献核查

以下都链接到原论文或作者仓库。只将论文具体操作作为先例，不以“都涉及控制／投影”直接认定相同方法。每篇核查重点是作用张量、控制信号、额外计算与任务目标。

| 工作及来源 | 已有具体机制 | 与本方案的重合及可明确区分的部分 |
|---|---|---|
| [DIAL, §3.3 与附录 C.2](https://arxiv.org/html/2609.11507v1) | 首 20% 去噪不引导、后 80% 引导；用前一次的主体空间 grounding map 调整主体图像 keys 的 attention logits。 | 已有数据相关的空间权重。当前方案保住 source-video 总质量，调节其内部对应物理时间的读出；动态 alpha 本身应与具体时序信号绑定。原文是“最后 80%”，不是“80% 之后才开始”。 |
| [IAM, §3.3 Eq.5–13](https://arxiv.org/html/2607.14945v1) | attention 概率上的 coherence、语义风险、KL trust-region 目标；离线训练稀疏 logistic regressor；PGD 后重新计算 velocity。原文用 warm start 与小步长隐式处理 KL。 | attention KL、自适应 head/time modulation 已有先例。这里可区分为质量守恒的一维同帧混合、精确 Bernoulli KL、无训练语义判别器、无 PGD／额外 DiT。仅说“attention trust region”不构成区别。 |
| [APG, §4 / Algorithm 1](https://arxiv.org/html/2410.02416v1) | 将 CFG 更新对条件去噪预测分解成平行／正交分量，抑制平行项，范数限幅并加 reverse momentum。作者强调先转换到 denoised prediction。 | 投影、范数控制已有。这里的基是同一 query 对源视频相邻物理时刻的 Value 条件读出；作用于单层 source-reference 分量，不是最终 CFG 去噪预测。 |
| [FlowMotion, §3.3–3.4 Eq.6–9](https://arxiv.org/html/2603.06289v2) | 用预测 latent 的运动变化优化目标 latent；将当前 velocity 投影到从初始噪声累计得到的平均去噪 velocity，压低正交分量。 | 同属无训练视频动作迁移，并已有方向投影。它的参照方向在**去噪轨迹**上；这里的参照方向沿**视频物理时间**，只用于选择现有 attention 修正强度／heads。 |
| [HALO, §3–4 与附录 C](https://arxiv.org/html/2607.11081v1)；[作者 V 注入代码](https://github.com/SunYJ-hxppy/HALO-Official-code/blob/a4933506563a32ac38a17ba071d34ea6c428788e/guidance_utils/custom_modules_inject_final.py#L95) | 识别跨帧 motion heads 和低熵 structural heads；前者构造语义运动引导，后者选择性注入参考 V。 | 视频动作相关 head 选择已有直接先例。这里是对当前实际候选修正 D 的局部时间成分在线定量，并做等修正预算分配；不把低 entropy 直接当动作正确性。 |
| [HeadRouter, §4.1 Eq.12–18](https://arxiv.org/html/2411.15034v1) | 比较重建／编辑分支的对应 head 输出余弦，归一化差异后以 sigmoid 重加权整个 head 输出。 | 输入自适应、按 feature 相似性给 heads 加权已有。这里无需重建分支，只重分配参考视频内部修正；效用来自参考物理时间变化及实际 D，而不是两个语义分支差异。 |
| [HeadHunter / SoftPAG, §4](https://arxiv.org/html/2506.10978v1)；[作者代码](https://github.com/cvlab-kaist/HeadHunter) | 迭代搜索符合质量／风格目标的 heads；attention map 与 identity map 连续插值构造弱模型。作者仓库也提供 Fisher–Rao、SLERP、log-linear 等路径。 | 连续 attention 混合、head 选择、信息几何路径都有先例。这里在线以当前参考时间读出选择 alpha，不是预搜索 heads 后构造 negative guidance 分支。 |
| [Understanding and Improving Training-free Loss-based Diffusion Guidance, §4.2 / Algorithm 2](https://arxiv.org/html/2403.12404v2) | 对外部条件损失的反向梯度使用 Polyak 步长，按预测噪声范数与梯度平方范数调节；另有 random augmentation。 | 自适应 guidance 步长已有。这里的闭式解优化内部局部二次代理，不需要条件损失反传；也不继承其全局收敛条件。 |
| [CAT, §4.2](https://arxiv.org/html/2609.21251v1) | 将引导梯度分为 score 的法向／切向，依据曲率预算联合求强度；用 Armijo 回溯检查实际目标下降，需要方向导数及候选评估。 | 几何预算、动态强度、line search 都已有。这里不做 true objective line search，也不声称有限步最终视频误差下降保证；仅解低成本内部代理。 |
| [CFG-Ctrl, §3.3–3.4](https://arxiv.org/html/2603.03281v1) | 将 CFG 写成随状态变化的 gain 与映射作用于条件／无条件 velocity 残差，提出 sliding-mode 控制。 | 泛称“按状态控制增益和方向”已有。具体区别仍要依靠 reference 内部时间读出及测得的时序收益，不能仅凭控制论术语。 |
| [DiFA, §4.3–4.5](https://arxiv.org/html/2607.17972v1) | 将连续去噪预测看成相关观测，建立 Kalman 视角、对齐历史预测并作因果共识和偏差引导。 | 无训练、基于不确定性／历史一致性的强度调整已有。当前 attention 时间分布未校准为动作 posterior，暂不采用一个没有观测误差模型的“Kalman 动作延迟估计”。 |
| [Fisher-Preserving Guidance, §3 与附录 G](https://arxiv.org/html/2605.29937v1) | 在 diffusion policy 中以 Fisher/低秩 Jacobian 结构投影引导，结合敏感度不确定性混合动作；讨论隐藏空间 pullback 度量。 | 为输出度量下比较 heads 提供数学近邻，但对象是动作策略的任务约束，不是 source-video same-time attention。采用 W_o 度量是合理工程／数学修正，不应独占宣称新思想。 |

补充查阅的动态区间近邻：[Adaptive Guidance](https://arxiv.org/html/2312.12487v1) 在条件／无条件预测余弦足够接近后停止 CFG；[DynamicCFG](https://arxiv.org/html/2509.16131v1) 通过训练的 noisy-latent 评价器在线选择 CFG；[Opening the Black Box of CFG](https://arxiv.org/html/2610.13369v1) 用条件／无条件 score 差异阈值决定启用时机。因此，从固定区间改成样本相关区间，可以是方法组件，但这个概括本身已有研究。

## 6. 最小消融和可成立的论文论点

先冻结所有输入、seed、采样器、步数、LoRA、分辨率、提示词和 reference 时间映射。已有全流程 .25 是主对照，不把更强但失真的版本当成唯一 baseline。

### 第一步：只改变标量强度

1. 固定 alpha=.25。
2. Value 中心切向的 block 动态 alpha；记录每层／步 alpha 和 E_T/E_N。
3. 开发集冻结 KL 预算的动态 alpha；与第 2 项独立。
4. 使用第 2 项平均强度／平均实际修正剂量的固定标量对照，排除只是整体力度不同。
5. 在少量机制诊断案例上做中心切向、两维 secant、打乱参考时间邻居三者对照。真实邻居不优于打乱邻居时，不宜把收益解释为利用物理时间结构。

### 第二步：只改变 head 分配

固定 .25 等能量预算，比较所有 heads 均匀、时间特征效用分配、随机打乱 head 效用。记录拼接前修正能量，并在 probes 上报告 W_o 后合成 residual 的变化。若动态总量与 head 分配都有效，再组合；每步／每层调度和输出度量只作为后续增量。

### 必须同时记录的结果

- 动作时间偏移、事件发生时刻／持续时间误差和 Motion Fidelity；总分改善需要看是否只来自整体形状复制。
- 角色／外观编辑成功度、背景和结构保留、明显伪影；使用统一评估口径。
- 多样本 paired seed 的全部结果、退化比例、alpha 分布、fallback／饱和比例，以及 wall time／显存。开发集与测试集分开，展示既含成功也含失败。

可争取的机制结论是：“参考条件读出中与局部物理时间变化有关的成分，预测 same-time 修正的收益；据此连续调节引导并在 heads 间分配，可在相同修正预算下改善动作相位。”最先要验证这个预测关系。若只有 KL 剂量控制有效，论文的论点应落在 reference attention 剂量与编辑保真之间的定量关系，不应借用尚未成立的时间特征分离解释。

## 7. 已核对的本地依据

- `innovation/direction_runtime/frozen.py`：冻结源码位置与 hash。
- `inference/package/custom_nodes/H3Study/core.py`：同输入状态的 mass-preserve 公式、full/ref/aligned LSE、Flash 路径。
- `innovation/direction_runtime/runtime.py`：旧 centroid/concentration/cos gate，仅能压低原强度。
- `innovation/temporal_coverage_v2/attention.py`：多时间 bin 条件读出变体，不是本轮主基线。
- `snapshots/h3-timing-architecture-r2-20261016/literature/query_time_posterior_gate_review.txt`：时间 attention 重心不等于动作偏移的本地反例。
- `snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md`：已有 Value 时间差分／输出投影度量讨论，避免把此前候选重新包装为全新发现。
- `innovation/adaptive_strength_20261023/prototype/controller.py`：数学实现协作者正在构建的 CPU 原型；本文核查的是公式及研究边界，不将原型存在当成视频效果已验证。

检索边界：以上是截至 2026-10-23 的直接相关原始文献与所列作者代码核查。DIAL 本轮核对的是原文，未声称审阅不存在于本地的官方实现。关于“尚未见到同一个组合”的判断限于已核查范围；真正的区别由明确作用张量、控制目标及消融证据建立。
