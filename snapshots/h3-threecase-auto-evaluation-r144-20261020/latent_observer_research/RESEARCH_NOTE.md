# 直接 latent / 内部特征运动观测：一手实现核查

核查日期：2026-10-20。仅阅读论文、作者代码及现有实验记录；没有推理、下载模型或修改运行包。代码固定版本及文件 SHA 见 `CODE_SOURCES.json`。

**用户提出的方向有明确先例，值得优先做低成本验证。** FlowMotion 已直接使用预测干净 latent 的时序差异；MOFT 和 DiTFlow 分别使用去静态成分的内部特征、跨帧 attention 对应。三者的运动约束都无需把每一步生成结果解码为 RGB 再运行姿态检测。现有 H3 朴素相邻差分失败，限定的是那一个读出方案。

| 工作 | 实际运动信号 | 额外依赖和计算 | 与当前任务的关系 |
|---|---|---|---|
| FlowMotion | 源/目标预测干净 latent，及帧间绝对差 | 源视频编码；加噪源的模型预测；目标优化前向。无外部光流、姿态或独立教师 | 与现有 x0 endpoint 最近，可复用当前普通分支输出研究廉价读出 |
| MOFT | 去时间均值、筛选运动通道的 denoiser 中间特征 | 参考特征通常从 DDIM inversion 提取；引导时反传到 noisy latent | 提供抑制静态外观差异的具体表示，不依赖人体关节 |
| DiTFlow | DiT 的跨帧 Q/K 对应形成空间位移 AMF | 源 latent 的 DiT 特征；跨帧注意力矩阵；优化 latent/位置嵌入的反传 | 可直接观察 token 运动，需核算 attention 矩阵开销 |

**FlowMotion：论文与代码均已查实。** 准确标题为 *FlowMotion: Training-Free Flow Guidance for Video Motion Transfer*，核查的是 arXiv:2603.06289v2（2026-03-17）。§3.2–3.4，式(2)–(9)以

\[
\hat z_0(t)=z_t-t\,v_\theta(z_t,t),\qquad
L=\alpha\|\hat z^s_0-\hat z^g_0\|^2+
\beta\|\Delta(\hat z^s_0)-\Delta(\hat z^g_0)\|^2
\]

对齐运动，并约束速度更新方向。这里的 flow 是生成模型的 flow-matching velocity。作者代码 `run.py` 的 `compute_motion_difference`（118–139行）实际堆叠**相邻绝对差和每帧对其他所有帧的绝对差**；并非仅计算有符号相邻导数。`_apply_guidance_step`（238–285行）构造源/目标 endpoint、两项 MSE 并更新 latent；`calc_velocity` 使用 `no_grad`，避免穿过 DiT 内部反传，但优化循环仍重新调用 DiT。`clean_latent` 是公开实现中的另一个选项。最终保存阶段才 VAE 解码。[论文](https://arxiv.org/html/2603.06289v2#S3)、[固定代码 f5b4dcf](https://github.com/HKUST-LongGroup/FlowMotion/blob/f5b4dcfc2ac00d21c05e2290111dde468ddb1d9d/run.py#L118)

**MOFT：均值去除作用于中间特征。** *Video Diffusion Models are Training-free Motion Interpreter and Controller*，arXiv:2405.14864v2（2024-11-01），§3 式(1)(2)为
\[
M_{f,c}=X_{f,c}-F^{-1}\sum_i X_{i,c},\quad c\in C_{\rm motion}.
\]
运动通道由 PCA 分析确定；§4 式(3)匹配区域内的参考/生成 MOFT，梯度更新 noisy latent。作者 `animatediff/pipelines/pipeline.py` 687–731行明确提取中间特征、时间去均值、加载通道掩码和参考特征、MSE、反传。论文选择 AnimateDiff upper block 1 的特征；不能直接假定 H3 第几层等价。它支持无需逐步 RGB/外部光流的运动表示，但完整控制算法的反传成本仍在。[论文](https://arxiv.org/html/2405.14864v2#S3)、[固定代码 44ec33d](https://github.com/xizaoqu/MOFT/blob/44ec33d5eafb99a0dd18bc620dd7d5d5eed3d544/animatediff/pipelines/pipeline.py#L687)

**DiTFlow：attention flow 是直接的空间对应。** *Video Motion Transfer with Diffusion Transformers*，CVPR 2025。§4 式(3)–(8)从
\[
A_{ij}=\operatorname{softmax}(\tau Q_iK_j^\top/\sqrt d)
\]
取得 patch 对应：参考使用 argmax 位移；生成分支用可微的加权位移
\[
\widetilde\Delta_{ij}(p)=\sum_q A_{ij}(p,q)(q-p),
\quad L_{\rm AMF}=\|\Delta^{ref}-\widetilde\Delta^{gen}\|^2.
\]
官方 `guidance_utils/motion_flow_utils.py::compute_motion_flow` 5–58行实现两种模式；`motion_guidance.py::load_attn_features` 构造参考，`compute_motion_flow_loss` 和 `guidance_step` 执行匹配/优化。此处没有调用 RAFT/GMFlow；flow 来自 DiT 自身 Q/K。完整 all-pairs 矩阵有显存成本，不能直接把 Flash attention 的现有输出当作已取得 AMF。[论文](https://arxiv.org/html/2412.07776v2#S4)、[固定代码 d6f740a](https://github.com/ditflow/ditflow/blob/d6f740a29bdcfc40dbead78fdbf75689af766e2e/guidance_utils/motion_flow_utils.py#L5)

外部依赖需要逐方法区分。**FRESCO**（CVPR 2024）确实从输入 RGB 通过 GMFlow 求光流/遮挡，再约束特征；`run_fresco.py::get_models` 装载 GMFlow，`run_keyframe_translation` 在调用生成前执行 `get_flow_and_interframe_paras(flow_model, imgs)`。这不意味着它每个采样步都解码生成 x0 再估光流。[作者实现](https://github.com/williamyang1991/FRESCO/blob/main/run_fresco.py)

**MotionEcho** 的准确 v2 标题为 *When Distillation Breaks Motion Control: Restoring Generative Trajectories for Fast Video Generators*，arXiv:2506.19348v2（2026-07-08）。§3.3–3.5使用完整扩散教师修正蒸馏学生 endpoint，并按运动损失自适应调用教师；DiT 版本可复用 MOFT/DiTFlow 表示。它属于需要教师计算的路线。本轮只核实论文，不声称审过其完整代码。[原文](https://arxiv.org/html/2506.19348v2#S3)

对 H3 的直接含义是：**先替换昂贵的观察信号，仍可保留现有 Attention 干预算子。** 现有 ordinary forward 已产生 x0，可先比较 endpoint 差分描述；若外观混淆严重，再比较 MOFT 式内部特征或 Q/K 对应。只做只读信号抽取不必照搬这些论文的整个梯度优化循环，因而其完整算法运行时间也不是我们观察器的成本预测。

还需解决的具体问题是“运动表示→有符号物理时延”。上述核心公式主要匹配同一帧序下的运动，未直接给出本项目的局部 lag、共同可见支持和拒判策略。H3 的独立17帧→5 latent分块及非均匀时间覆盖必须映射正确；既有常量视频周期、已知延迟控制可复用作校准。原生 Wan/AnimateDiff/CogVideoX 与 H3 的表示不同，本轮没有实测 H3 适配效果或省时比例。

现有局部证据入口：

- `h3-timing-architecture-r2-20261016/literature/vae_phase_observer_prior_art.txt`：先前 H3 周期控制与一手出处。
- `h3-timing-architecture-r2-20261016/audit/latent_temporal_signal_diagnostic_20261020/`：已有 x0 差分/相位去均值诊断。
- 本目录相邻 `../online_monitor/EARLY_STEP_TIMING.json`：当前 RGB 观察器实测耗时，CPU pose 约143–157秒/步、独立 decoder 阶段约54–57秒/步；该记录支持优先替换观察链，而非继续用主 DiT 速度解释整步耗时。
