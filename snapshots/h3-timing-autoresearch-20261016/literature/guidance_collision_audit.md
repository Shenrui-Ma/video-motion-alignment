# H3 动作时间错位：运动引导与时间路由撞题审查

核查日期：2026-10-16（Asia/Shanghai）。范围：MotionEcho、FlowMotion、MotionGrounder、ReaDiT、FRESCO、RoPECraft，以及沿检索链发现的时间路由、运动解耦工作。基于 arXiv 正文、作者项目页和可见官方代码；没有运行这些框架。本文不能证明不存在未检索到的同类工作。

## 结论与今晚建议

**尚不能把“动态局部注意力增强”“根据运动误差开关引导”“光流约束”“时序位置控制”“静态/动态特征分离”中的任何一项声称为新的架构贡献。** 这些方向均有直接或高度相近的先例。

值得做一个便宜而严格的机制试验：在保持输出 query 分配给参考视频的总注意力质量不变的条件下，只调整它在参考视频物理时间轴上的读取分布，检验动作时间偏移能否缩小，且外观编辑不退化。若成立，再判断是否需要只给时变残差独立路由。当前可保留的是**可证伪的机制假设**，不是“已找到空白/已证明创新”。

推荐最小对照：原始 H3、原有 ×3 参考增强、保持参考总质量的同时间窗路由、保持相同质量但错位时间窗的负对照。至少一个既有失败样例加一个既有成功样例；同 prompt/seed/帧率/输入裁剪/采样器/LoRA/数值内核。成功样例是检查干预是否破坏本来正确的动作。

## 最接近工作的机制与边界

| 工作与一手证据 | 已有机制 | 对本方案的创新限制与可判别差异 |
|---|---|---|
| [MotionEcho v2](https://arxiv.org/html/2506.19348v2)，2025-06 首发，2026-07 改题；[作者页](https://euminds.github.io/motionecho/) | 蒸馏学生的预测端点重新加噪后交给完整教师生成运动对齐端点，再与学生端点插值。运动损失滑动平均超过阈值时启用教师，教师达到另一阈值可提前结束。使用既有模型，测试时不训练权重。 | “误差大才引导、达到要求就停止”已经存在。我们的候选不引入教师，干预参考→输出的信息读取，不蒸馏端点。仅去掉教师并换一条 loss 不自动构成贡献。作者页当前代码仍标 Coming soon；不能声称已做原版复现。 |
| [FlowMotion](https://arxiv.org/html/2603.06289v1)，2026-03；[官方 run.py](https://github.com/HKUST-LongGroup/FlowMotion/blob/main/run.py) | 由 flow 预测得到干净 latent 估计，联合对齐源/目标 latent 和相邻帧差分；将模型预测视为常量，优化 latent，避免完整反传；还用累计运动方向约束速度更新。公开代码默认只优化前 10 个去噪步，每步 3 次优化。 | “无需教师、用 flow/latent 差分监测并引导运动”已有。候选要改变 attention 读取路径，保持原始模态竞争预算；与直接减少 latent 差异的优化目标不同。必须比较 motion/edit trade-off，不能仅比较运动指标。 |
| [MotionGrounder](https://arxiv.org/html/2604.00853v1)，2026-04；[作者页](https://kaist-viclab.github.io/motiongrounder-site/) | GMFlow 得到参考轨迹，降采样到 latent；用参考轨迹位移监督生成视频 attention 推导的可微位移，并优化 latent。另以对象 mask 与对象 caption attention 的对齐损失做多主体绑定。 | 光流/轨迹差异图、对象局部监督、attention-derived displacement 均已有。其目标是源→目标运动场和对象语义空间对应；我们应检验真实动作时间相位，而非把该方法换一个局部 mask。项目页代码当前标待发布。 |
| [ReaDiT](https://arxiv.org/html/2609.04649v1)，2026-09 | 冻结 DiT，从单层中间特征训练约 53M readout，预测深度/姿态/边缘；运动版本学习点描述子对应，再对参考光流施加 latent 梯度引导。空间和运动 readout 分别训练。 | “从中间层读出运动再反馈”已有，且该 readout 不是 training-free。无新 readout 的注意力路由可区分，但只能在确实不引入训练监督时这样表述。论文明确快运动和 temporal upsampling 是局限，不能据此直接宣称我们的机制解决了它。 |
| [FRESCO CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/papers/Yang_FRESCO_Spatial-Temporal_Correspondence_for_Zero-Shot_Video_Translation_CVPR_2024_paper.pdf)；[官方代码](https://github.com/williamyang1991/FRESCO) | 以参考视频的跨帧光流和帧内自相似共同约束注意力及中间特征，支持不训练的视频翻译；处理快速运动、遮挡和局部光流不可靠等情形。 | “空间+时间对应约束、只让相关位置交换特征”不是新思想。其约束主要保证翻译帧之间的一致对应；我们的任务要把参考和输出之间的时间偏移作为独立对象，而非泛称 temporal consistency。 |
| [FLATTEN](https://arxiv.org/abs/2310.05922)，2023-10 / ICLR 2024 | 参考光流轨迹限定不同帧中哪些 patch 互相 attend，不训练原模型。 | 不能说首个基于运动约束 attention 路由的方法。必须区分同轨迹跨帧特征聚合与同一事件的参考→输出绝对时间保真。 |
| [RoPECraft](https://arxiv.org/html/2505.13344v1)，2025-05 / NeurIPS 2025；[作者页](https://berkegokmen1.github.io/RoPECraft) | 参考光流变形空间 RoPE，测试时继续以 flow-matching 目标和 Fourier 相位正则优化；初始化中保持时间 RoPE 不动，因为作者观察到改动它会导致解码伪影。 | “修改 RoPE 来控制运动”已有。参考/输出时间读取校正是不同操作，但简单改变时间坐标不应被直接命名为全新机制。Fourier phase 和动作发生的物理时间 phase 也不能混为一谈。 |
| [Temporal State Transport / TST](https://arxiv.org/html/2609.08505v1)，2026-09；[官方代码](https://github.com/lytang63/temporal-state-transport) | 把跨帧 attention 看作运输算子，以行熵与谱熵之差诊断过混合/碎片化；论文通过 query 温度调节做推理时纠正，带层/去噪步调度。 | “诊断 temporal attention 再动态调节”“temporal transport”已有。它不要求参考视频时间真值，不约束参考模态总质量，不以源/目标动作相位差作目标。见下方代码/论文差异。 |
| [TS-Attn](https://arxiv.org/html/2604.19473v1)，2026-04 | 从主体的 text-video attention 提取运动相关区域；将多事件提示分配到时间区间，在局部区域增强对应事件、抑制其他事件；强度由 attention 分布调节，training-free。 | “局部主体+时间区间+注意力重分配”已有。它路由文本事件而非参考帧；我们的非文本时间读取和参考质量守恒可成为操作区别，但不能把时间 mask 本身当创新。 |
| [Temporal Context Routing / TCR](https://arxiv.org/html/2609.02367v1)，2026-09；[作者页](https://dagroup-pku.github.io/Temporal-Context-Routing.github.io/) | 将脚本时间区间与文本表示分离，以物理秒计算时长归一的 Gaussian bias，加在视频/音频对文本的 attention logits；训练和推理都使用，并训练 LoRA。 | “物理时间 side channel”“独立于语义的时间 routing”已有。候选是 frozen H3 内参考视频内容的条件时间分布校正，无脚本文本时标监督；这是应被实验检验的特定差异，不是概念首创。 |
| [PoCo](https://arxiv.org/html/2604.03738v1)，2026-04 / CVPR 2026 | 在 RoPE 中增加参考身份 side-information 轴，让视觉相似参考按实体归属检索；另有 shot-local text attention。 | 不能说首个以结构信息校正内容相似性主导的参考检索。PoCo 解决跨参考身份绑定，候选解决同一参考内部动作时刻绑定；必须测因果贡献。 |
| [OmniTransfer](https://arxiv.org/html/2601.14250v1)，2026-01 | temporal transfer 对参考加空间 RoPE offset；appearance transfer 加时间 offset。参考分支只读自身，目标分支读参考和自身，缓解复制及混淆。 | “外观/运动走不同参考路径、按任务改变时空位置”已有。候选若宣称静态/动态独立路由，应明确到同一次 motion-preserving edit 的两个分量，而非复述任务级路由。 |
| [MOFT](https://arxiv.org/html/2405.14864v1)，2024-05 / NeurIPS 2024 | 减去特征的时间均值去除内容相关项，PCA 选择运动通道，随后以运动特征损失引导 latent。 | 直接减时间均值得 motion residual 已有。我们的可能差异仅在于 residual 被放入新的信息读取算子，并以静态路径不受干预和时刻保真验证，不是 residual 提取本身。 |
| [MotionAdapter](https://arxiv.org/html/2601.01955v1)，2026-01 | 从 full attention 提取跨帧位移，以 DINO 对应将运动适配到目标内容，再引导 latent；处理较大形状与语义差异。 | 不能说首个解耦外观和运动，或首个为目标内容改造参考运动。直接 V residual 路由无需外部 DINO/运动场优化是操作差异，仍需验证有效。 |
| [HALO](https://arxiv.org/html/2607.11081v1)，2026-07 | 分析运动专门化与空间结构专门化 attention heads；以语义对应优化运动位移，以低熵 heads 特征注入保结构，不更新权重。 | 仅选运动 heads、让外观 heads 不改已经相近；不能称为新的解耦架构。应与简单选头/全头的干预比较。 |
| [DeT](https://arxiv.org/abs/2503.17350)，2025-03 / ICCV 2025；[CVF 论文](https://openaccess.thecvf.com/content/ICCV2025/papers/Shi_Decouple_and_Track_Benchmarking_and_Improving_Video_Diffusion_Transformers_For_ICCV_2025_paper.pdf) | 在 DiT 中增加共享 temporal kernel，并用 dense trajectory supervision；对单个源视频训练，报告约 500 steps。 | 时序分量专用模块和轨迹约束已有。我们 frozen 模型内无训练的 router 与其实现不同，但仍须避免“第一个解决 DiT 时空纠缠”的主张。 |

## 两项必须纠正的技术理解

### Flow velocity 不是物理光流

去噪模型的 v(z,s) 是对扩散/flow 时间 s 的 latent 变化方向；物理运动则是视频时间 t 上的像素、特征或轨迹变化。两者的轴不同。不能把 v 的两个 channel 当成 (dx,dy)，也不能仅因 v 改变就断言某个动作延迟。FlowMotion 自己也对原始 velocity、denoised latent 和 clean-latent prediction 做了区分（论文 Appendix A）。

### “归一化重分配”仍可能与 logits bias 完全等价

令一行原 attention 为 A_j=exp(L_j)/Z，R 为参考视频 token 集，m=sum_R A_j。若定义：

```text
A'_j = m A_j w_j / sum_{k in R}(A_k w_k),  j in R
A'_j = A_j,                              j outside R
```

则在参考 logits 上加入

```text
b_j = log w_j + log(sum_R exp(L_k)) - log(sum_R exp(L_k) w_k)
```

即可得到完全相同的 A'。因此“我们改 softmax 后的权重，所以不同于 logits 加偏置”不成立。该算子可区分于**固定组常数**增强，但不是不同于所有 bias 的数学范式。创新必须落在被控制的变量、约束、可验证的故障机制及效果，而非换一种公式写法。

同样，参考总 attention mass 不变，也不保证输出向量范数不变、其他模态的后续层贡献不变、最终身份不变。只能宣称当前被修改这一 attention 行上的严格代数性质。

## 候选机制的精确定义（本轮提出，尚未证明）

对某个生成 query i，参考 attention 可分解成：

```text
A[i,t,x] = m[i] p[i,t] C[i,x|t]
m[i]       = 分给参考视频的总 attention 质量
p[i,t]     = 选取参考时刻 t 的概率
C[i,x|t]   = 在给定参考时刻内选择空间位置 x 的概率
```

原始语义 attention 联合决定这三者。候选将控制对象收窄到 p：以 query 对应的物理时间 τ(i) 和保留动作时间的任务约束，构造 p'；m 和 C 保留。输出修正为：

```text
O' = O + m[i] sum_t (p'[i,t]-p[i,t]) sum_x C[i,x|t] V[t,x]
```

第一轮先用已知同时间窗的软 prior，不添加误差检测、门控阈值或学习，以减少解释歧义。物理时间必须依据读取帧、帧率、VAE temporal receptive field 和 patchify 规则映射，不能使用为了区分多参考而人工偏置的 RoPE 时间编号作为秒数。

从数学上看，这仍是 attention 控制的一种，**不能保证达到“架构创新”标准**。将时间边缘分布与语义空间条件分布显式分开，是本次要验证的结构性因子；若只是一个 Gaussian mask 无独立因果收益，应降级为启发式 baseline。

### 第二阶段仅在第一阶段可用后考虑

保持静态值通路，单独修改时变值残差的路由：

```text
V[t,x] = mu[x] + dV[t,x]
O' = O + m[i] sum_t (p'[i,t]-p[i,t]) sum_x C[i,x|t] dV[t,x]
```

其中简单时间均值去除来自已知思想（MOFT），不是原创。此结构的可测不变量是：参考 V 完全不随时间变化时 dV=0，干预严格为零。候选收益应是比 full-V 路由减少身份/背景复制，同时改善动作时间。必须注意固定像素的时间均值混有相机移动、遮挡、光照、形变，不等于干净的“外观”；没有验证前只能称静态/时变分量，不称解耦了身份和运动。

## 最小实验与否决条件

### 第 0 步：先排除测量与因果混淆

- 对比原视频、实际送入模型的参考帧序列、VAE encode→decode；确认 FPS、起点、端点、抽帧、padding、裁剪和输出时间戳一致。
- 诊断保持动作内容和局部相位：使用人工确定的短事件、可见关节角或归一化手部轨迹。先冻结观察时间窗，随后才看方法结果。
- 不允许用自由 DTW 对齐后的相似度作为唯一成绩，因为它可以消掉我们正要测的时间偏移。至少同时报告零位移误差、最优局部 lag、对齐后姿态误差。
- 保存参考读取的 p(t|q)、m(q)、干预量和参与层/步；attention 本身不是因果证据，必须配 intervention。

### 第 1 步：四臂机制试验

1. 原始 H3。
2. 原有 ×3 reference logit enhancement，记录实际 m 增幅，作为强度控制。
3. 固定 m 的正确物理时间路由；先温和宽窗，保留软尾部，避免把每帧强行独立处理。
4. 同一强度/同一 m 的错误时间中心（如偏移两个 latent temporal cells），作为负对照。

若第 3 臂成功再加入第 5 臂 residual-only router，以及第 6 臂固定 m 但不对准物理时间的 entropy-matched 分布。第 6 臂用于排除“只是 attention 变尖了”的解释，尤其针对 TST。

### 必须报告的量

- 短事件 onset/peak/offset 的绝对时间误差，单位帧和秒；由预先指定事件定义，不能事后挑最显著帧。
- 局部轨迹最优 lag（带足够置信度）与零 lag 误差。身体形状换了后需归一化/角度化，禁止直接比较整幅 RGB MSE。
- 本来无延迟样例的劣化率；遮挡或难测样例的不可判定率。
- 外观编辑成功、源身份泄漏、画面伪影、总推理时间和显存。
- 至少配对多 seed，再扩展第二素材；只报一个成功 seed 无法支持普遍有效。

### 预先声明的否决 / 调整规则

| 观察 | 应有决定 |
|---|---|
| 检查输入时间轴即可消除偏移 | 这是 pipeline 修正，不包装成模型研究创新 |
| 正确路由和错误路由同样有效 | 尚无时间对应机制证据，先查一般锐化/强度效应 |
| ×3 增强与路由同等有效，且同等编辑质量 | 尚无独立结构收益；保留为 baseline，不堆更多模块凑贡献 |
| 时刻准确但还原了源人物/损害编辑 | 存在控制-编辑权衡，不能算成功；再测 residual-only 路由 |
| 路由降低内部 attention lag，但输出事件不改善 | 内部统计不是有效控制目标，应改变假设 |
| 成功 seed 改善，原正确 seed 被破坏 | 需要可靠性判别，但动态阈值本身已有；先分析可预测的失效条件 |
| 多配对 seed 和第二素材均改善，同时编辑保持 | 可继续扩展机制与 baseline 审查；仍不能在 pilot 后宣称顶会级结论 |

## 官方代码核查注意事项

TST 论文给出 gamma=exp(tau_eff*(H_row-H_vN))，允许锐化或软化。但核查时官方 [main/tst/core.py](https://raw.githubusercontent.com/lytang63/temporal-state-transport/main/tst/core.py) 返回：

```text
1 + tau_eff * (1-diagonal_mean) * H_vN * (1-H_vN)
```

该版本只会增大温度缩放（非负 tau 时），并把空间/heads 统计聚合成标量。它不是论文公式的逐字实现。若加入 baseline，必须记录 commit，并分别标明 paper-formula adaptation / released-code adaptation，不能混用后声称复现官方实验。

MotionEcho 最新版本是 v2，标题已变为 When Distillation Breaks Motion Control: Restoring Generative Trajectories for Fast Video Generators；本审查使用 v2 的核心算法，避免沿用 v1 标题当作独立新论文。

## 审查边界

当前检索发现的最强概念重合是 TST、TS-Attn、TCR、OmniTransfer；最强运动引导比较对象是 FlowMotion、MotionGrounder、DiTFlow/RoPECraft。DIAL、Sync-LoRA、TempoControl、DynaEdit 的专门审查由并行研究任务负责，不在本文件重复判定。本文的“可区分”是说明操作和验证目标不同，绝不等于证明没有同类论文，或保证审稿人会认定贡献充分。

## 2026-10-16 凌晨实验附记（未改写先验审查）

截至 source05 第二种子 mass 评价完成：同时间路由在两个预先选定种子上均改善主窗动作时间，但普通 hard route 和既有 ×3 增强在第一种子也有效。不能据此主张参考总质量守恒是必要机制，也不能称已取得独立架构收益。第二种子的 native 与 mass 同时有大块背景变黑的编辑失败，动作 timing 改善与整体编辑成功必须分开报告。

目前完整的“同质量、错参考时间中心”负对照尚未完成。相对时间 RoPE 的 ±12 扰动不等同于将同帧 router 的参考时间中心改错，因而不能替代该机制对照。仅凭 correct-time router 成功仍未排除局部选择变尖或一般重分配的影响。

固定最后 9 个模型调用开启 mass 的实验仍保留约 11–12 帧主窗延后；这只否定该固定执行器/时段/强度的一次修复，不证明所有晚期控制不可能。额外 late6、late-hard 与相关素材迁移仍在运行。+12 相对坐标扰动主窗 lag 未变（+13），−12 尚未完成，不能提前宣称整个 phase actuator 不可行。

本附记只更新实验证据边界，不增加“无人做过”的文献主张。具体预登记和全部失败/拒绝结果见 analysis/pose 下的独立审查。

后续补充（−12 正式结果后）：原窗口的 RoPE−12 使主窗可靠延后从 +13 降至 +3，两阈值及已登记的 ±36 敏感度一致；+12 仍 +13，属于单侧饱和，不是已校准双向相位控制。固定 late11−12 可控性检验和原先缺失的同质量错参考 bin 两组对照已经独立登记，尚未出结果。详见 `analysis/pose/pilot/PHASE_PAIR_REVIEW.md`。

后续补充（late6 正式结果后）：同一执行器固定从 call6 开始，主窗双阈值 lag 为 +1/+1，原四窗0.3为 +1/0/+1/+1；call11 仍 +11/+12。step005 与 native 的 video/audio tensor 全等，固定55/86帧未见白色房间被破坏。这支持已测试 schedule 的可控性差异，不定位精确转折点，也不证明在线反馈成功：冻结双臂观察器在 step005 仍未知，6–9 未采样；腕坐标主窗因位移收益小而拒判亦完整保留。固定时段选取已有大量先例，不能仅凭 late6 优于 late11 声称架构创新。详见 `analysis/pose/pilot/LATE6_REVIEW.md`。

## 2026-10-16T06:28:50+08:00 错时刻对照补记

两条±4参考bin对照现已完成，不能继续把“正确时刻比错误时刻好”当作已通过的机制门。共同支持0.3下0/+4/−4方向误差为0.104/1.020/1.039，但0.5共同支持仅0.672，原定双阈值门未通过。+4还出现转背、遮挡及动作形状失败，不能解释为干净的相位转移；−4主窗可靠延迟仍为+11帧。该结果提供有限的时间对应线索，未排除内容/遮挡混淆，也未证明质量守恒相对普通hard的独立贡献。详analysis/pose/offset_specificity/offset_triplet_complete。

晚开控制需按执行器分别讨论：mass从调用11开始、hard从11开始都未充分修复；mass从6开始有效，但14次对9次调用有混淆。等9次调用的6..14对照和晚开的RoPE−12还在运行，不能提前宣称“可观察时已经不可控制”或“所有晚期控制无效”。


## Final empirical update — 2026-10-16

All planned CPU evaluations are complete. Earlier pending fields above are historical. The strongest new result is the equal-nine-call interval comparison: calls6–14 give +1/+1 frame lag, while calls11–19 give +11/+12, with actual operator and causal prefix audits passing. This establishes a selected-case interval/history effect, not a new dynamic-gating principle, equal sigma-dose, or an online controller. Hard mask and archived x3 also repair the first seed, so mass conservation is not necessary. The wrong-bin specificity gate fails at high-confidence shared support; semantic image/label main-effect gates both fail (A/B/C/D=13/5/13/13). Full minus12 RoPE partially helps, but late11 does not. GPU0 native replay is exact on five video/audio captures and all141 RGB frames.

No architectural novelty is established. Seed2 background failures, source07 abstentions and pre-window degradation remain part of the record. TokenFlow/NOVA additionally constrain generic multi-phase semantic fusion claims. See `analysis/pose/ROUND_FINAL_REVIEW.md` and JSON for every condition, unknown and gate.
