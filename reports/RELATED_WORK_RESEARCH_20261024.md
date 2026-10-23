# 动作细粒度控制视频编辑：相关工作与原文证据目录

更新：2026-10-24。内容：论文机制、模型架构、训练与推理设置、已核结果、原文及代码出处、仓库既有文献记录。配套机器索引：[literature_sources.json](research_sources_20261024/literature_sources.json)。项目进展另见 [研究进展 V1.1](cloud/视频编辑中动作时间对齐-研究进展V1.1.html)。

## 1. 文献范围与阅读记录

本轮从既有研究笔记提取 **220 个去重 arXiv 引用**，逐条通过 arXiv 官方元数据核对标题、作者和日期，另加入 **6 个本轮查阅来源**，合计 **226 条**。其中 **19 条**在本轮复核了具体原文方法、实验或附录，**136 条**有历史机制笔记，**71 条**为历史引用入口。历史引用涵盖视频编辑、运动迁移、注意力控制、动态 guidance、数学、评估与系统材料；完整名单见附录，所有旧笔记路径与片段见 JSON。

记录分为以下主题，分组用于定位材料：

- 视频编辑与参考条件：Vidu S2-Editing、Wan-Animate-2、RefDrop、RefGAP、QK-Edit、HALO、DIAL、EditVid、MotionEcho。
- 扩散引导与控制：Adaptive Guidance、Limited-Interval Guidance、Feedback Guidance、SOC Adaptive Guidance、Dynamic CFG、IB CFG、APG、Autoguidance。
- 编辑轨迹与表示：FlowEdit、AV-FlowEdit，以及第 5–6 节的图像方法、时空对应、RoPE、运动表示、头层分配与时间评价。

**接手 Agent 阅读本目录各篇总结时，须完整阅读对应原文和附录。** 本文件记录导航和本轮已读取范围；论文版本、章节、公式、图表、数据规模、代码版本构成阅读账本。图像公式、图中伪代码和补充视频需要查看其原始内容。

### 原文核对字段

| 字段 | 记录内容 |
|---|---|
| 时间坐标 | 视频物理时间、扩散采样时间、网络层深度及单位 |
| 干预位置 | Q/K/V、logits、attention 输出、latent、velocity、RoPE 或训练损失；参考 token 的访问范围和概率归一化 |
| 训练与计算 | 骨干、evaluator、head selector、LoRA、条件编码器的训练状态；推理反传、额外 rollout、第二模型调用 |
| 观测与决策 | 控制量、状态估计、参数选择和更新方程 |
| 实验协议 | source videos、edits、seeds、帧数、几何、采样器、指标模型、聚合与人评单位 |
| 版本来源 | 正式论文、preprint、代码 commit、作者结果、本地实现或复现记录 |

## 2. 方法对象与字段分类

| 研究对象 | 本目录收录工作 | 原文中的机制字段 |
|---|---|---|
| source 与 target 的同时间访问 | Vidu S2-Editing、Wan-Animate-2、Sync-LoRA、UNIC | 时间坐标、条件 token 范围、共享或分离的分支、训练方式 |
| 参考特征与参考组总权重 | RefDrop、RefGAP | 读出混合、reference mass、logit 偏移、区域与层参数 |
| Q/K/V 与 MM-SA 子矩阵 | QK-Edit、DIAL、Ctrl-X | 视觉与文本 token、替换或偏置对象、源/目标特征 |
| 头/层分配 | HALO、HeadRouter、HeadHunter、ReaDiT | 头功能辨识、选择规则、readout、特征注入 |
| 动态强度和启停 | FBG、SOC、Dynamic CFG、IB CFG、AG | 状态、收益函数、阈值、求解器和额外计算 |
| 运动表示与轨迹 | MotionEcho、DiTFlow、RoPECraft、DMT、MOFT、FlowMotion | 光流、特征匹配、时序读出与测试时优化 |
| 编辑轨迹与区域保存 | FlowEdit、EditVid、AV-FlowEdit、FlowDirector | source/target 速度场、特征对应、掩码与混合规则 |

## 3. 直接相关方法：架构、算子、证据

### 3.1 Vidu S2-Editing

**出处**：[原文 2609.11638v1](https://arxiv.org/html/2609.11638v1)，§3.2、§5；[项目](https://vidu.com/vidu-stream)。完整标题为 *Vidu S2: Real-Time Interactive, Editable, and Spatial Video Generation*（2026-09）。

Editing 分支先训练双向视频编辑，再构建因果流式模型并蒸馏。Frame-aligned attention 让 target frame 读取相同时间的 source frame；参考图片可被所有帧访问。source 流与 target 同步消费。编辑数据包含 80 万条 source videos，按风格、主体、背景、试衣分成四个各 20 万条的互斥子集。§5 使用 OpenVE、Sparkle、RefVIE、ViViD；表 2 的 Sparkle Overall 为 **3.74**，foreground motion **4.00**。上述数值来自 Editing 分支。

### 3.2 Wan-Animate-2

**出处**：[原文 2608.06009v2](https://arxiv.org/html/2608.06009v2)，§3、§5；[项目](https://humanaigc.github.io/wan-animate-2/)；[代码](https://github.com/Wan-Video/Wan-Animate-2)。

使用 clean-reference / noisy-target 双分支，共享 QKV；参考分支在扩散时间 0 处理，target 在当前噪声时间处理，文本 cross-attention 分开。TimeAlignRoPE 将同时间 source/target 对齐，SparseRef 让 target 只访问同时间 reference K/V，target 内仍保留全时空 attention。训练共享 QKV，视点控制另用 cross-attention LoRA。Lite 通过 teacher-forcing、误差缓冲及 self-forcing 蒸馏流式模型；§5.5 报告 **400×720、24 fps、4 GPU、3 DiT steps**。§5.4 人评整体偏好超过 70%。

### 3.3 RefDrop：参考特征权重

**出处**：[原文 2405.17661v1](https://arxiv.org/html/2405.17661v1)，§3–5；[NeurIPS 2024 正式论文](https://papers.nips.cc/paper_files/paper/2024/file/3b057de5a2e38bd8fa10201866c20dbf-Paper-Conference.pdf)；[项目](https://sbyebss.github.io/refdrop/)。

Reference Feature Guidance 把 self 与 reference attention 读出显式混合：`c·Attn(Q,K_ref,V_ref)+(1−c)·Attn(Q,K_self,V_self)`，可扩展到多参考和负权重。图像使用 ProtoVision-XL（SDXL 微调模型），视频使用 SVD-img2vid-xt-1-1；冻结模型，将首帧特征注入后续帧的空间 self-attention，视频示例 c=0.2。§5 人评 44 人，每类从约 100 个任务中抽 10 组。

### 3.4 RefGAP：在线参考质量补偿

**出处**：[原文 2609.35708v1](https://arxiv.org/html/2609.35708v1)，§3.2–3.4、附录 E–H。

RefGAP 在线测量 reference attention mass，对 edit-region 的 reference logits 加正偏置，对 keep-region 加负偏置，使用两个全局系数与层剖面。它保留参考组内部相对比值，调节参考组总质量。40 条 head-swap 验证样本、4 个开发模型选参，迁移到 3 个保留模型；覆盖 JoyAI、LoomVideo、FLUX.2、VACE、Qwen-Image-Edit、OmniGen2 等。附录 G 表 19 中 JoyAI head-swap ID **0.507→0.644**、keypoint error **0.043→0.085**；表 20 中 Qwen 背景任务 DINO **0.299→0.042**。

### 3.5 QK-Edit：MM-DiT 的视觉 Q/K 注入

**出处**：[ICCV 2025 正式论文](https://openaccess.thecvf.com/content/ICCV2025/papers/Shen_QK-Edit_Revisiting_Attention-based_Injection_in_MM-DiT_for_Image_and_Video_ICCV_2025_paper.pdf)；[arXiv 全文 2610.17829v1](https://arxiv.org/html/2610.17829v1)，§3、§4、§6–9。arXiv 于 2026-10 补上传，会议年份按正式版本记录。

冻结 FLUX / HunyuanVideo，在 target denoising 中替换视觉 Q、K，保留 target V；source Q/K 来自原生成轨迹或真实视频反演。作者通过 MM-SA 象限分析选择同时控制 vision→text 与 vision→vision。TGVE+ 真实编辑表 3：ViCLIP-dir **0.196**、ViCLIP-out **0.258**、CLIP-frames **0.921**、PickScore **20.52**；Flatten 的方向分数为 0.204。HiLo 自建 43 条高分辨率长视频，表 4 QK 替换 CLIP-frames **0.908**。

### 3.6 HALO：运动头与结构头分工

**出处**：[原文 2607.11081v1](https://arxiv.org/html/2607.11081v1)，§3–5、附录 C–F；[项目](https://sunyj-hxppy.github.io/halo)；[代码](https://github.com/SunYJ-hxppy/HALO-Official-code)。正式标题为 *Controlling Motion Transfer in Diffusion Transformers via Attention Heads*。

通过跨帧 attention 位移与 RAFT 的方向一致性/相关性辨识 motion heads；语义对应修正位移，并以运动损失优化 latent。低熵 structural heads 接收参考 V，以保结构。主模型 CogVideoX，50 denoising steps、12 optimization steps、CFG 7；主表 MF **66.2**、FTD **19.4**。附录 Wan 使用 25 参考帧、21 输出帧，表 11 MF **71.6**、FTD **18.3**。

### 3.7 DIAL：主体注意力反馈与偏好训练

**出处**：[原文 2609.11507v1](https://arxiv.org/html/2609.11507v1)，§3、§4、附录 B/C。正式标题为 *Harnessing Intrinsic Subject-Aware Attention for Controllable Multi-Subject Video Generation*。

Phase I 从 privileged DiT block 提取 intrinsic subject grounding map，以前一步的 map 产生空间 logit bias，作用在 video queries→reference-image keys；跳过前 20% 采样步。Phase II 使用 DPO / rank-16 LoRA，14k PhantomData、48 H100、800 steps。模型为 Kaleido、Phantom。OpenS2V 有 180 prompts、320 case-subject instances；附录 B 表 4 在关闭 Phase I 时，Kaleido 检出主体 **155/320→163/320**。

### 3.8 EditVid：图像编辑器扩展到视频

**出处**：[原文 2609.04190v1](https://arxiv.org/html/2609.04190v1)，§4–5、附录 A.3；[项目](https://plan-lab.github.io/editvid)。正式标题为 *One Editor, Many Edits: A Unified Training-Free Framework for Diverse Video Editing*。

冻结 FLUX.2-Klein-9B，默认 4 步；通过前帧 K/V 记忆、cycle-consistent 全局 anchor 对应与 attention 后特征注入保持时间一致性；再以源/编辑轨迹差生成 soft mask，做随去噪阶段变化的 latent blending。表 1 FiVE editing accuracy **78.16**；表 3 IVEBench：total **0.6847**、quality **0.8114**、compliance **0.4587**、fidelity **0.7839**。自建验证 50 视频（24 general、26 subject），消融 30 视频。

### 3.9 MotionEcho：按运动误差触发教师回路

**出处**：[原文 2506.19348v2](https://arxiv.org/html/2506.19348v2)，§3.4–3.5、§4、§7–8；[项目](https://euminds.github.io/motionecho/)；[代码入口](https://github.com/euminds/motionecho)。

用历史 motion loss 均值触发教师辅助，教师损失低于第二阈值时提前退出；在学生与教师轨迹间做测试时 latent 优化。VideoCrafter2→TurboV2 与 Wan2.1-1.3B→Video-BLADE 分别验证。TurboBench 为 22 个 source、66 edits；DavisBench 为 34 个 source，各 3 个难度提示。表 2 Wan/Video-BLADE 的 DMT 8-step 方案：MF **0.732**、TC **0.963**、TA **0.313**、49 秒/A100-40G；Wan-DMT MF 为 0.622。本地 10-17 代码审查记录的仓库当时仍是项目页。

## 4. 扩散 guidance 的动态强度、区间与方向

以下论文涉及扩散 guidance 的强度、启停、方向或引导模型选择。各行记录控制信号、实现成本和对应实验。

| 工作与原文 | 观测与算法 | 架构/训练/成本 | 原文结果与阅读锚点 |
|---|---|---|---|
| [Adaptive Guidance，2312.12487](https://arxiv.org/html/2312.12487v1)；[AAAI 2025](https://ojs.aaai.org/index.php/AAAI/article/download/32192/34347) | conditional / unconditional 方向余弦接近后停用额外分支；LinearAG 用历史预测的仿射组合 | LDM / EMU；AG 推理免训练，NAS 用于发现策略 | 表 1：AG 阈值 0.991，29.6±1.3 NFE 对 CFG 40；1000 prompts 人评 498 对 502。读方法、policy search、LinearAG 与附录 |
| [Limited-Interval Guidance，2404.07724](https://arxiv.org/html/2404.07724v1)；[NeurIPS 2024](https://papers.neurips.cc/paper_files/paper/2024/file/dd540e1c8d26687d56d296e64d35949f-Paper-Conference.pdf) | guidance 仅作用于一段 σ 区间，边界对齐 solver steps；对强度及上下界网格搜索 | EDM2、DiT、SDXL；冻结模型 | 表 1：ImageNet-512 EDM2-XXL FID 1.81→1.40，32 步中 6 步引导。读 §3–4、离散化附录 |
| [Feedback Guidance，2506.06085](https://arxiv.org/html/2506.06085v1)；[NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/73c90c0c16fe835bc58a815d4a8f28be-Abstract-Conference.html) | 假设 conditional distribution 含 additive unconditional contamination；沿 Markov chain 累计后验似然比，映射为状态依赖 guidance；校正自参照偏差并限幅 | EDM2-XS / T2I；复用 conditional、unconditional 预测；[作者代码](https://github.com/FelixKoulischer/Feedback-Guidance-of-Diffusion-Models) | v1 表 1 PFODE FID：CFG 2.97、LIG 2.31、FBG-pure 2.50；64 NFE。原文锚点：Eq.8–11、§3.4、附录 B |
| [SOC Adaptive Guidance，2505.19367](https://arxiv.org/html/2505.19367v1)；[AISTATS 2026 正式 PDF](https://openreview.net/pdf?id=mef54yiI1L) | 最大化终端 conditional confidence，减去轨迹 KL 代价；HJB 推导状态相关标量增益；Girsanov importance weights 支持 policy SGD | 学习标量 `w(t,x,c)`，基础 score 模型冻结；低维 HJB 与可扩展 policy learning 两条路线 | §4 Eq.18–23、§5 Algorithm 5；实验含低维示例与指导图像。本轮读取控制问题推导与 policy learning 算法 |
| [Dynamic CFG，2509.16131](https://arxiv.org/html/2509.16131v1) | noisy-latent CLIP / discriminator / preference / OCR evaluator 给候选下一状态打分；逐步离散贪心选 CFG，评价器权重随得分变化调整 | LDM 865M/2B、Imagen 3；另训练 latent evaluators；复用两分支预测，约 1% FLOPs 增量 | Gecko / GenAI-Bench 人评胜率 53.6% / 53.8%，MARIO 55.5%、GeckoNum 54.1%。读 §3、§4、附录 A.1–A.4 |
| [IB CFG，2610.13369](https://arxiv.org/html/2610.13369v1) | 用 conditional/unconditional score 的能量差作为 Fisher 信息差估计，与 IB 阈值比较；首次跨阈值后开启剩余采样的 CFG | DiT / SiT / flow 扩展；阈值参数 β*；启停判据仍求两分支 | 表 1：ImageNet-256、50k、250 步，DiT-XL/2、ω=1.6，FID 2.71→2.06。原文锚点：Eq.26–27、Algorithm 1、flow 假设与附录实现 |
| [APG，2410.02416](https://arxiv.org/html/2410.02416v1) | 在 clean/denoised prediction 空间，把 guidance update 分成条件预测的平行与正交部分，压低平行项；加范数限幅与 reverse momentum | EDM2、DiT、SD2.1、SDXL、SD3；冻结模型；投影前统一 prediction parameterization | 表 1：DiT-XL/2、w=4，FID 19.14→9.34；SDXL、w=15，26.29→25.35。读 §4、附录 Algorithm 1 与超参数表 |
| [Autoguidance，2406.02507](https://arxiv.org/html/2406.02507v2)；[EDM2 代码](https://github.com/NVlabs/edm2) | 用质量更差的同条件模型替代 unconditional guide，分离质量提升与条件偏好 | 需要更弱/较少训练的 guide model | ImageNet FID：64² 1.01、512² 1.25；读模型配对与预算协议。它与 2023 Adaptive Guidance 是不同工作 |

### 控制变量分类

FBG 从误差模型和似然比构造状态相关系数；SOC 定义终端目标与轨迹控制代价；Dynamic CFG 使用经过训练的 latent evaluator 选择候选系数；IB CFG 以信息量阈值触发引导；AG 根据两分支预测的收敛减少调用；APG 对引导向量做几何分解。这些条目的状态、目标函数和作用位置分别在原文公式与实现中给出。

## 5. 图像与音视频轨迹方法

### 5.1 FlowEdit

[原文 2412.08629v1](https://arxiv.org/html/2412.08629v1)；[ICCV 2025 正式页](https://openaccess.thecvf.com/content/ICCV2025/html/Kulikov_FlowEdit_Inversion-Free_Text-Based_Editing_Using_Pre-Trained_Flow_Models_ICCV_2025_paper.html)；[代码](https://github.com/fallenshock/FlowEdit)。在冻结 SD3 / FLUX 上，用共享扰动下 source/target velocity 之差构造直接编辑 ODE，对多个噪声配对取均值。§5 Eq.8–9 与 Algorithm 1 给出关键更新；`n_max` 决定编辑路径长度，`n_avg` 控制估计方差。§5.2 使用 1000 张猫图转狗图，分析结构保存、transport cost、FID/KID。

### 5.2 AV-FlowEdit

[原文 2610.13072v1](https://arxiv.org/html/2610.13072v1)，§3–4。冻结 LTX-2 的双分支音视频生成器，各自 VAE，通过预训练 cross-modal interaction 共同生成。source/target flow 差同时作为编辑方向与保留线索；flow-saliency EMA、音频事件活跃度、多尺度低频位移和 denoising-stage schedule 共同控制区域保护。表 1：CLIP-F **0.920**、CLIP-T **0.273**、Obj **0.673**、DINO **0.592**、CLAP **0.255**、LPAPS **4.10**、IB **0.320**、AVAlign **0.297**；同表 AvED DINO 0.956、AVAlign 0.42。

### 5.3 图像方法的既有记录

- **MasaCtrl**：target Q 读 source K/V 的 mutual self-attention。[原文](https://arxiv.org/html/2304.08465v1)
- **Ctrl-X**：分离结构特征注入和 attention 加权的 appearance statistics，免训练、免反传。[原文](https://arxiv.org/html/2406.07540v1)
- **Stable Flow**：按 block 干预结果辨识 vital layers，再进行特征注入。[原文](https://arxiv.org/html/2411.14430v2)
- **PAG / HeadHunter / SoftPAG**：以改变 attention 的模型作为对照预测，再外推；头选择可按目标搜索。[PAG](https://arxiv.org/html/2403.17377v1)、[HeadHunter](https://arxiv.org/html/2506.10978v1)、[代码](https://github.com/cvlab-kaist/HeadHunter)
- **Training-free Loss Guidance**：对外部目标梯度采用 Polyak 步长、尺度归一化与扰动稳健化。[原文](https://arxiv.org/html/2403.12404v2)



## 6. 既有机制调研全景

本节依据仓库历史审查文件整理，原文标题已用官方元数据核正。每条完整出处、旧笔记、阅读片段和版本在 JSON 中。本节的机制概述来自历史记录，具体阅读范围保留在索引中。

### 6.1 视频时间对齐与结构化条件

| 工作 | 模型与历史机制记录 | 原文 |
|---|---|---|
| Sync-LoRA | LTX-Video，参考/目标共享时间 RoPE、不同 diffusion time；rank-128 LoRA，历史笔记记录 512 paired videos、5000 steps。后续 LTX-2.3 发布变体单独记账 | [2512.03013](https://arxiv.org/html/2512.03013v1) |
| UNIC | 统一 in-context video editing，task-aware RoPE 为 source/camera/audio 共享时间坐标，为身份/风格分配偏移；训练式统一框架 | [2506.04216](https://arxiv.org/html/2506.04216v1) |
| VideoCoF | Wan 视频编辑器增加 temporal reasoner / reasoning frame，reasoning 与 source/target 的位置索引分工 | [2512.07469](https://arxiv.org/html/2512.07469v2) |
| MinT / ReRoPE | 时间区间化文本事件、局部相对 RoPE、temporal cross-attention；学习事件边界条件 | [2412.05263](https://arxiv.org/html/2412.05263v1) |
| TS-Attn | 从文本-视频 attention 找运动区域，将多事件提示分到时间区间，局部增强/抑制；冻结模型 | [2604.19473](https://arxiv.org/html/2604.19473v1) |
| TempoControl | 对视频生成的 temporal attention 施加时序控制；涉及时间路由与去噪调度 | [2510.02226](https://arxiv.org/html/2510.02226v3) |
| TIE | 将事件时间区间编码为频率上的积分形式，包含区间长度信息 | [2605.10543](https://arxiv.org/html/2605.10543v1) |
| VideoCanvas / Video-As-Prompt | 任意时空 patches / 视频语义作为上下文，包含语义 token 与 dense latent 条件 | [2510.08555](https://arxiv.org/html/2510.08555v1)、[2510.20888](https://arxiv.org/html/2510.20888v1) |
| OmniTransfer / FullDiT2 | 统一视频迁移与高效 in-context 条件；涉及 reference→generation 的依赖与缓存 | [2601.14250](https://arxiv.org/html/2601.14250v1)、[2506.04213](https://arxiv.org/html/2506.04213v1) |
| Identity as Presence / Slot-ID | 身份视频、声音与 temporal identity encoding，涉及 reference 通路的信息隔离 | [2603.17889](https://arxiv.org/html/2603.17889v1)、[2601.01352](https://arxiv.org/html/2601.01352v1) |
| Kiwi-Edit / Bernini / Baton | 语义 planner / Qwen 表征与 dense source latent 共同条件；涉及语义网格到视频 latent 的坐标映射 | [2603.02175](https://arxiv.org/html/2603.02175v1)、[2605.22344](https://arxiv.org/html/2605.22344v2)、[2605.25195](https://arxiv.org/html/2605.25195v1) |

### 6.2 运动迁移、表示与反向优化

| 工作 | 历史机制记录 | 原文 |
|---|---|---|
| DMT | Space-time diffusion features 描述参考运动，测试时优化；文中包含 MF 评价 | [2311.17009](https://arxiv.org/html/2311.17009v1) |
| MOFT | 从预训练视频模型抽取 motion features，利用 motion-sensitive channels 控制 | [2405.14864](https://arxiv.org/html/2405.14864v2) |
| DiTFlow | DiT 跨帧 attention motion flow，优化 latent 或 positional embeddings；历史记录包含 3D RoPE 梯度路径 | [2412.07776](https://arxiv.org/html/2412.07776v2) |
| RoPECraft | 光流轨迹初始化空间 RoPE，再以 flow / Fourier-phase 目标优化；冻结模型，测试时反传 | [2505.13344](https://arxiv.org/html/2505.13344v1) |
| STR-Match | 分离 2D 空间与 1D 时间 attention relevance，以相似性匹配做 latent 优化 | [2506.22868](https://arxiv.org/html/2506.22868v1) |
| TeDiO | 关注跨帧 attention 的相邻时间对角线与局部 roughness，早期 latent 优化 | [2605.14136](https://arxiv.org/html/2605.14136v1) |
| MotionAdapter | 全 attention 位移与 DINO 对应结合，适配源/目标语义和形状差异 | [2601.01955](https://arxiv.org/html/2601.01955v1) |
| MotionGrounder | GMFlow 轨迹降采样到 latent，以空间锚点处理多物体运动 | [2604.00853](https://arxiv.org/html/2604.00853v1) |
| Reenact Anything | 逐帧 motion-textual embedding 反演，实例级优化细粒度运动 | [2408.00458](https://arxiv.org/abs/2408.00458) |
| FlowMotion | predicted latent 运动损失，velocity 方向投影及去噪轨迹平均 | [2603.06289](https://arxiv.org/html/2603.06289v2) |
| MotionFlow / Frame Guidance | attention 驱动运动迁移与 frame-level control；原始定义与其他同名 flow 方法分开 | [2412.05275](https://arxiv.org/html/2412.05275v1)、[2506.07177](https://arxiv.org/html/2506.07177v2) |
| Motion by Queries | query 侧运动/身份权衡 | [2412.07750](https://arxiv.org/html/2412.07750v3) |
| QWERTY | Query-warped DiT motion control | [2607.01869](https://arxiv.org/abs/2607.01869) |
| TrajLoc | 训练轨迹/外观编码器与 LoRA，使用局部轨迹 attention 条件 | [2607.00861](https://arxiv.org/html/2607.00861v1) |
| Motion4Motion / MotionCoach | inference-time 跨主体运动与专业运动编辑条件 | [2607.11644](https://arxiv.org/html/2607.11644v1)、[2610.12963](https://arxiv.org/html/2610.12963v1) |
| Decouple and Track / DiViD | 可训练运动适配、静态/动态因子分解 | [2503.17350](https://arxiv.org/html/2503.17350v1)、[2507.13934](https://arxiv.org/html/2507.13934v2) |

### 6.3 连续时间、对应关系与 VAE 表示

| 工作 | 历史机制记录 | 原文 |
|---|---|---|
| TokenFlow | 跨帧 diffusion-feature correspondence 与特征传播，保持编辑一致性 | [2307.10373](https://arxiv.org/html/2307.10373v2) |
| FLATTEN / FRESCO | 光流约束 attention / 空间时间对应的优化与传播 | [2310.05922](https://arxiv.org/html/2310.05922v2)、[2403.12962](https://arxiv.org/html/2403.12962v1) |
| LatentWarp / QueryWarp | 光流或姿态推导 warp，遮挡与残差决定 latent/query 融合；QueryWarp 正式标题为 Zero-Shot Video Translation via Token Warping | [2311.00353](https://arxiv.org/html/2311.00353v1)、[2402.12099](https://arxiv.org/abs/2402.12099) |
| Text2Video-Zero / EVE | 后续帧读取首帧 K/V 的一致性路线；EVE 包含 depth inversion | [2303.13439](https://arxiv.org/html/2303.13439v1)、[IJCAI 2024 EVE](https://www.ijcai.org/proceedings/2024/0075.pdf) |
| ReTime | Semantic Progress Function 表示视频语义进程，涉及 retiming 与 RoPE | [2604.22554](https://arxiv.org/html/2604.22554v1) |
| RIFLEx / Untwisting RoPE | 时间长度外推、shared attention 的频率选择 | [2502.15894](https://arxiv.org/html/2502.15894v1)、[2602.05013](https://arxiv.org/html/2602.05013v1) |
| Making Time Editable / RVD | 可训练时间适配或 dynamics bottleneck，通过时间重采样控制播放进程 | [2606.10183](https://arxiv.org/html/2606.10183v1)、[2609.36496](https://arxiv.org/html/2609.36496v1) |
| DLFR-VAE | 按片段复杂度调整 temporal latent rate；研究 VAE 编解码的幅度、相位、频率变化 | [2502.11897](https://arxiv.org/html/2502.11897v2) |
| MAGVIT-v2 / Alias-Free LDM | causal tokenizer 与空间 shift equivariance | [2310.05737](https://arxiv.org/abs/2310.05737)、[2503.09419](https://arxiv.org/html/2503.09419v1) |
| Warped Diffusion / LookingGlass | 空间 warp 与 denoiser equivariance、Laplacian pyramid；涉及几何控制与噪声协变 | [2410.16152](https://arxiv.org/html/2410.16152v2)、[2504.08902](https://arxiv.org/html/2504.08902v1) |
| TeleMorpher | 身体对应部位与局部变形协同，实现 motion-location 联合编辑 | [2606.19676](https://arxiv.org/html/2606.19676v1) |

### 6.4 在线控制、分配与内部状态

| 工作 | 历史机制记录 | 原文 |
|---|---|---|
| HeadRouter | 对照重建/编辑分支 head-output 余弦，以 sigmoid 路由 head 权重 | [2411.15034](https://arxiv.org/html/2411.15034v1) |
| IAM | attention coherence、语义风险、KL trust region；含离线稀疏分类器与在线 PGD | [2607.14945](https://arxiv.org/html/2607.14945v1) |
| CAT | guidance 的切向/法向分解、曲率预算和 Armijo 回溯 | [2609.21251](https://arxiv.org/html/2609.21251v1) |
| CFG-Ctrl | 状态相关 gain 与方向控制，作用在 conditional/unconditional velocity 残差 | [2603.03281](https://arxiv.org/html/2603.03281v1) |
| DiFA | 历史预测对齐、相关观测与 Kalman/因果共识视角，修正 forward-process 偏差 | [2607.17972](https://arxiv.org/html/2607.17972v1) |
| Fisher-Preserving Guidance | diffusion policy 的 Fisher / 低秩 Jacobian 投影 | [2605.29937](https://arxiv.org/html/2605.29937v1) |
| ReaDiT | 冻结 DiT 中间层，训练约 53M readout 预测结构/运动，使用 readout 梯度引导 | [2609.04649](https://arxiv.org/html/2609.04649v1) |
| Attention analysis / physics analysis | 分析空间/时间头、跨帧 stripe、运动头归因与 ablation | [2504.10317](https://arxiv.org/html/2504.10317v1)、[2504.12027](https://arxiv.org/html/2504.12027v2)、[2609.23658](https://arxiv.org/html/2609.23658v1) |
| TST | 以时间状态传输和频谱失衡分析视频生成，涉及低/高频 motion 分配 | [2609.08505](https://arxiv.org/html/2609.08505v1) |
| AlignVid / FAME | QK 缩放、attention 能量调度、区域掩码与公平性 | [2512.01334](https://arxiv.org/html/2512.01334v1)、[2510.22960](https://arxiv.org/html/2510.22960v1) |
| DTR | video-LLM 的 anchor-frame dominance 修正；下游任务是视频理解 | [2604.12582](https://arxiv.org/html/2604.12582v1) |
| EG-Sparse | 竞争域选择与 head globalization，研究 sparse attention 的预算分配 | [2610.14672](https://arxiv.org/html/2610.14672v1) |
| Sinkformers / ESPFormer / ASAG | 双随机 attention、transport 约束或 Sinkhorn 引导 | [2110.11773](https://arxiv.org/abs/2110.11773)、[2502.07962](https://arxiv.org/html/2502.07962v1)、[2511.07499](https://arxiv.org/html/2511.07499v1) |
| MPC-Flow / CoDe / Lookahead | 重规划、分块控制、未来 continuation 评价；计算涉及规划深度与候选数 | [2601.23231](https://arxiv.org/html/2601.23231v1)、[2502.00968](https://arxiv.org/html/2502.00968v2)、[2602.03211](https://arxiv.org/html/2602.03211v1) |
| DRM / reward steering / soft value decoding | noisy latent reward、stepwise candidate selection 和 value-guided decoding | [2605.25661](https://arxiv.org/html/2605.25661v1)、[2501.06848](https://arxiv.org/html/2501.06848v2)、[2408.08252](https://arxiv.org/html/2408.08252v3) |

### 6.5 视频编辑轨迹与区域保护

| 工作 | 历史机制记录 | 原文 |
|---|---|---|
| DynaEdit | 冻结 Wan2.1-14B I2V，source/target flows 相似性加权与随阶段变化的噪声相关；HunyuanVideo-1.5 扩展 | [2603.17989](https://arxiv.org/html/2603.17989v1) |
| FlowDirector | source-target flow steering；Wan2.1-1.3B 官方 V1 代码已有本地静态审查，执行细节见第 7 节 | [2506.05046](https://arxiv.org/html/2506.05046v1) |
| FlowAnchor / SAM-Flow | 稳定编辑信号、source anchoring 与 masked flow | [2604.22586](https://arxiv.org/html/2604.22586v1)、[2606.06228](https://arxiv.org/html/2606.06228v1) |
| OAVC / Weighted Velocity Guidance | 在 velocity 上分离 source-preserving 与编辑方向，加入对象/背景保护 | [2609.06288](https://arxiv.org/html/2609.06288v1) |
| SAMA / NOVA | 语义锚点与 motion alignment 分解，或 sparse control / dense synthesis | [2603.19228](https://arxiv.org/html/2603.19228v1)、[2603.02802](https://arxiv.org/html/2603.02802v1) |
| WorldForge | 以几何 warp 的轨迹 latent 介入 clean prediction、按 flow 相似性选择通道，处理 camera control | [2509.15130](https://arxiv.org/html/2509.15130v1) |
| FreeMask / Ada-VE / AdaFlow | 掩码设计、运动先验、关键帧选择与 attention slimming | [2409.20500](https://arxiv.org/html/2409.20500v1)、[2406.04873](https://arxiv.org/html/2406.04873v1)、[2502.05433](https://arxiv.org/html/2502.05433v1) |
| PFB-Diff / PixelMan / RePaint | 特征渐进融合、像素锚点加 denoiser 差、masked diffusion sampling | [2306.16894](https://arxiv.org/html/2306.16894v2)、[2412.14283](https://arxiv.org/html/2412.14283v1)、[2201.09865](https://arxiv.org/html/2201.09865v4) |

### 6.6 动作时间评价与基准

| 工作 | 评价用途 | 原文 |
|---|---|---|
| Temporal Cycle-Consistency (TCC) | 表征空间的双向时间匹配，分辨动作进程与持续时间 | [1904.07846](https://arxiv.org/abs/1904.07846) |
| DILATE | 把形状误差与时间路径偏移分离，时间项使用 `Ω_ij=(i−j)^2/k^2` | [1909.09020](https://arxiv.org/abs/1909.09020) |
| Drop-DTW / alignment in the wild | 允许缺失片段与 outliers，处理漏动作、多余动作和不同持续时间 | [2108.11996](https://arxiv.org/abs/2108.11996)、[2111.09301](https://arxiv.org/html/2111.09301v1) |
| Uncertainty-DTW / DTW reliability | 衡量匹配不确定性与对齐可靠度 | [2605.25110](https://arxiv.org/html/2605.25110v1)、[2607.15443](https://arxiv.org/html/2607.15443v1) |
| FlexiAct | 动作迁移方法与专门评估；项目已有实现及专题交接 | [2505.03730](https://arxiv.org/html/2505.03730v2) |
| IVEBench | 指令视频编辑基准及官方评价链路；其数据规模与评测配置见专题 | [2510.11647](https://arxiv.org/html/2510.11647v1)、[代码](https://github.com/RyanChenYN/IVEBench) |
| V2V-Bench / OmniEdit-Bench / NRVBench | 综合视频编辑与非刚体编辑任务覆盖 | [2606.05665](https://arxiv.org/html/2606.05665v1)、[2608.05049](https://arxiv.org/html/2608.05049v1)、[2601.18340](https://arxiv.org/html/2601.18340v1) |
| Frame phase / FastBench | sparse sampling 对短事件的遗漏、采样相位与评价稳定性 | [2610.08649](https://arxiv.org/html/2610.08649v1)、[2610.12427](https://arxiv.org/html/2610.12427v1) |

## 7. 仓库中的历史原文与代码核查

| 本地证据 | 历史记录内容 |
|---|---|
| [timing_prior_art.md](../snapshots/h3-timing-autoresearch-20261016/literature/timing_prior_art.md) | 早期时间先验、模型时钟、同时间路由和关键位置的原文/代码入口 |
| [guidance_collision_audit.md](../snapshots/h3-timing-autoresearch-20261016/literature/guidance_collision_audit.md) | 动态引导、候选算子和既有方法的机制对照 |
| [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) | 头层、方向与控制器候选的证据依据及旧选择理由 |
| [dynamic_guidance_primary_check.txt](../snapshots/h3-paper-progress-20261017/audit/dynamic_guidance_primary_check.txt) | AG、IB CFG、Dynamic CFG 等动态近邻的逐节审查 |
| [adaptive_strength/research.md](../snapshots/execution-20261022/innovation/adaptive_strength_20261023/research.md) | 10-23 自适应 α 研究对应的先前技术、数学设计与实验出发点 |
| [MOTIONECHO_WAN_IMPLEMENTATION_CHECK.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/MOTIONECHO_WAN_IMPLEMENTATION_CHECK.txt) | MotionEcho 官方仓库当时的内容、论文 Wan 配置、复现缺口 |
| [SECOND_WAN_BASELINE_IMPLEMENTATION_CHECK.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/SECOND_WAN_BASELINE_IMPLEMENTATION_CHECK.txt) | FlowDirector / Sync-LoRA 的代码可用性和默认行为核查 |

**FlowDirector 历史代码记录**：[官方仓库](https://github.com/Westlake-AGI-Lab/FlowDirector) 的历史审查固定 commit `cecd56e30820b279f35acaa18597f4da25fa4f42`，对应 V1，骨干 Wan2.1-T2V-1.3B，审查文件为 `edit.py`、`wan/text2video.py`。旧记录指出：DAG 对所有同大小子集完整平均会得到零均值趋势；`conflict_mask` 在该代码路径被计算后未被消费。该记录描述上述 commit 的静态代码分析。

**MotionEcho 历史代码记录**：10-17 审查记录官方仓库当时是项目页，Wan 参数来自正文和附录；记录包含教师、学生、motion extractor 与测试时 Adam 迭代配置。本轮原文复核范围见 JSON。

## 8. 阅读覆盖与资料缺口

本轮 19 条原文复核覆盖了具体方法、结果表或指定附录，逐篇范围记录在 JSON 的 `reading_coverage` 中。全篇图表视觉、图中伪代码与全部补充视频尚未完成逐项阅读；历史笔记及引用入口按原记录归档。以下为当前资料缺口：

| 条目 | 尚缺资料或核查 |
|---|---|
| 核心方法全篇阅读 | 已复核章节之外的全正文、完整附录、补充视频及图中伪代码；全篇视觉核查字段统一记为 false |
| RefGAP / DIAL / AV-FlowEdit / IB CFG | 当前官方代码、数据清单、原始逐样本评测结果；本文使用所链接 arXiv 版本 |
| EditVid | 实际 IVEBench 子集或完整集规模、逐任务分布、长视频处理和官方评分版本 |
| Vidu S2 / Wan-Animate-2 | 编辑分支 checkpoint 开放清单、完整评测样本、用户研究规模及对应流式/离线设置 |
| MotionEcho / FlowDirector | 官方代码当前 revision 的可运行性；本文保留历史代码审查日期及 commit |
| 第 6 节扩展清单 | 当前机制概述来自历史笔记，定量结果与完整实验设置未在本轮逐篇复核 |
| 71 条引用入口 | 当前记录含题名、作者、日期、原文地址与旧笔记出处 |

数值绑定本文所标论文版本、表号、模型、数据集、规模和单位。MF、TC、FID、CLIP 等指标的特征模型、归一化及抽样协议按各论文定义记录。完整原文通过作者、arXiv 与正式出版链接获取。

## 附录：历史引用与本轮新增文献总目录

下表标题来自 arXiv 官方 API，来源列指向首次检索到的本地研究记录；所有出现位置、摘要片段及复核字段在 JSON 中。标记：**原文复核**=本轮阅读了具体方法/实验；**历史机制**=旧笔记存在机制或章节审查；**引用入口**=保留的阅读线索。元数据核验与全文阅读分别记录。


共 226 条：19 条原文复核、136 条历史机制记录、71 条引用入口。历史机制分类依据旧片段中章节、公式或机制词；分类描述现存笔记覆盖。

| arXiv | 官方题名 | 记录状态 | 历史来源 |
|---|---|---|---|
| [1101.1438](https://arxiv.org/abs/1101.1438) | Optimal detection of changepoints with a linear computational cost | 引用入口 | [LITERATURE.txt](../snapshots/h3-timing-auto-motion-r26-20261017/analysis/phase_consistent_segmentation_design/LITERATURE.txt) |
| [1608.00859](https://arxiv.org/abs/1608.00859) | Temporal Segment Networks: Towards Good Practices for Deep Action Recognition | 引用入口 | [semantic_phase_robustness_prior_art.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_phase_robustness_prior_art.txt) |
| [1904.07846](https://arxiv.org/abs/1904.07846) | Temporal Cycle-Consistency Learning | 历史机制 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/source_anchor_observability_20261017/REVIEW.txt) |
| [1909.09020](https://arxiv.org/abs/1909.09020) | Shape and Time Distortion Loss for Training Deep Time Series Forecasting Models | 历史机制 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/public_failure_followup_20261017/REVIEW.txt) |
| [2001.07628](https://arxiv.org/abs/2001.07628) | Set Membership identification of linear systems with guaranteed simulation accuracy | 引用入口 | [LITERATURE_AND_ATTRIBUTION.txt](../snapshots/h3-timing-auto-motion-r26-20261017/analysis/phase_shape_profile_candidate_v2/LITERATURE_AND_ATTRIBUTION.txt) |
| [2011.14214](https://arxiv.org/abs/2011.14214) | Truly shift-invariant convolutional neural networks | 历史机制 | [phase_matched_reference_bank_review.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/phase_matched_reference_bank_review.txt) |
| [2105.05217](https://arxiv.org/abs/2105.05217) | Representation Learning via Global Temporal Alignment and Cycle-Consistency | 引用入口 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/observer_correspondence_review_20261017/REVIEW.txt) |
| [2108.11996](https://arxiv.org/abs/2108.11996) | Drop-DTW: Aligning Common Signal Between Sequences While Dropping Outliers | 引用入口 | [missing_support_controller_review.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/missing_support_controller_review.txt) |
| [2110.11773](https://arxiv.org/abs/2110.11773) | Sinkformers: Transformers with Doubly Stochastic Attention | 引用入口 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2111.09301](https://arxiv.org/abs/2111.09301) | Learning to Align Sequential Actions in the Wild | 历史机制 | [capacity_temporal_transport_review.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/capacity_temporal_transport_review.txt) |
| [2111.14818](https://arxiv.org/abs/2111.14818) | Blended Diffusion for Text-driven Editing of Natural Images | 引用入口 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/locality_spillover_review_20261017/REVIEW.txt) |
| [2201.09865](https://arxiv.org/abs/2201.09865) | RePaint: Inpainting using Denoising Diffusion Probabilistic Models | 历史机制 | [rollback_collision_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/rollback_collision_audit.txt) |
| [2210.12192](https://arxiv.org/abs/2210.12192) | Conditional Diffusion with Less Explicit Guidance via Model Predictive Control | 引用入口 | [ROOT_SCOPE.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/nonlocal_response_candidate_20261017/ROOT_SCOPE.txt) |
| [2211.09275](https://arxiv.org/abs/2211.09275) | Robust adaptive model predictive control with persistent excitation conditions | 引用入口 | [LITERATURE_AND_ATTRIBUTION.txt](../snapshots/h3-timing-auto-motion-r26-20261017/analysis/phase_shape_profile_candidate_v2/LITERATURE_AND_ATTRIBUTION.txt) |
| [2301.11093](https://arxiv.org/abs/2301.11093) | Simple diffusion: End-to-end diffusion for high resolution images | 引用入口 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2303.13193](https://arxiv.org/abs/2303.13193) | VADER: Video Alignment Differencing and Retrieval | 历史机制 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/source_anchor_observability_20261017/REVIEW.txt) |
| [2303.13439](https://arxiv.org/abs/2303.13439) | Text2Video-Zero: Text-to-Image Diffusion Models are Zero-Shot Video Generators | 历史机制 | [round2_architecture_candidates.txt](../snapshots/h3-timing-autoresearch-20261016/literature/round2_architecture_candidates.txt) |
| [2303.15259](https://arxiv.org/abs/2303.15259) | Temporal Alignment of Human Motion Data: A Geometric Point of View | 引用入口 | [READING_AND_CANDIDATE.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/phase_shape_identifiability_20261017/READING_AND_CANDIDATE.txt) |
| [2304.06841](https://arxiv.org/abs/2304.06841) | Video alignment using unsupervised learning of local and global features | 引用入口 | [REVIEW.md](../snapshots/h3-vae-temporal-operator-r70-20261018/audit/phase_shape_prior_review/REVIEW.md) |
| [2304.08465](https://arxiv.org/abs/2304.08465) | MasaCtrl: Tuning-Free Mutual Self-Attention Control for Consistent Image Synthesis and Editing | 引用入口 | [next_quality_actuator_20261016.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/next_quality_actuator_20261016.txt) |
| [2305.18264](https://arxiv.org/abs/2305.18264) | Gen-L-Video: Multi-Text to Long Video Generation via Temporal Co-Denoising | 历史机制 | [semantic_phase_robustness_prior_art.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_phase_robustness_prior_art.txt) |
| [2306.14878](https://arxiv.org/abs/2306.14878) | Restart Sampling for Improving Generative Processes | 历史机制 | [rollback_collision_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/rollback_collision_audit.txt) |
| [2306.16894](https://arxiv.org/abs/2306.16894) | PFB-Diff: Progressive Feature Blending Diffusion for Text-driven Image Editing | 引用入口 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/locality_spillover_review_20261017/REVIEW.txt) |
| [2307.10373](https://arxiv.org/abs/2307.10373) | TokenFlow: Consistent Diffusion Features for Consistent Video Editing | 历史机制 | [semantic_phase_robustness_prior_art.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_phase_robustness_prior_art.txt) |
| [2309.05019](https://arxiv.org/abs/2309.05019) | SA-Solver: Stochastic Adams Solver for Fast Sampling of Diffusion Models | 引用入口 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2310.05737](https://arxiv.org/abs/2310.05737) | Language Model Beats Diffusion -- Tokenizer is Key to Visual Generation | 历史机制 | [vae_phase_observer_prior_art.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/vae_phase_observer_prior_art.txt) |
| [2310.05922](https://arxiv.org/abs/2310.05922) | FLATTEN: optical FLow-guided ATTENtion for consistent text-to-video editing | 历史机制 | [PRIOR_ART_REVIEW.txt](../snapshots/h3-timing-pose-observer-r15-20261016/PRIOR_ART_REVIEW.txt) |
| [2311.00353](https://arxiv.org/abs/2311.00353) | LatentWarp: Consistent Diffusion Latents for Zero-Shot Video-to-Video Translation | 历史机制 | [REVIEW.md](../snapshots/h3-vae-temporal-operator-r70-20261018/audit/codec_residual_prior_review/REVIEW.md) |
| [2311.11325](https://arxiv.org/abs/2311.11325) | MoVideo: Motion-Aware Video Generation with Diffusion Models | 历史机制 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2311.17009](https://arxiv.org/abs/2311.17009) | Space-Time Diffusion Features for Zero-Shot Text-Driven Motion Transfer | 引用入口 | [round2_architecture_candidates.txt](../snapshots/h3-timing-autoresearch-20261016/literature/round2_architecture_candidates.txt) |
| [2311.18830](https://arxiv.org/abs/2311.18830) | MotionEditor: Editing Video Motion via Content-Aware Diffusion | 引用入口 | [semantic_motion_conflict_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_motion_conflict_audit.txt) |
| [2312.00845](https://arxiv.org/abs/2312.00845) | VMC: Video Motion Customization using Temporal Attention Adaption for Text-to-Video Diffusion Models | 引用入口 | [round2_architecture_candidates.txt](../snapshots/h3-timing-autoresearch-20261016/literature/round2_architecture_candidates.txt) |
| [2312.06640](https://arxiv.org/abs/2312.06640) | Upscale-A-Video: Temporal-Consistent Diffusion Model for Real-World Video Super-Resolution | 历史机制 | [counterfactual_geometry_appearance_scope.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/counterfactual_geometry_appearance_scope.txt) |
| [2312.07536](https://arxiv.org/abs/2312.07536) | FreeControl: Training-Free Spatial Control of Any Text-to-Image Diffusion Model with Any Condition | 引用入口 | [layer_selective_motion_guidance_review.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/layer_selective_motion_guidance_review.txt) |
| [2312.12487](https://arxiv.org/abs/2312.12487) | Adaptive Guidance: Training-free Acceleration of Conditional Diffusion Models | 原文复核 | [research.md](../snapshots/execution-20261022/innovation/adaptive_strength_20261023/research.md) |
| [2401.18085](https://arxiv.org/abs/2401.18085) | Motion Guidance: Diffusion-Based Image Editing with Differentiable Motion Estimators | 引用入口 | [pose_swept_query_support_review.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/pose_swept_query_support_review.txt) |
| [2402.02583](https://arxiv.org/abs/2402.02583) | DiffEditor: Boosting Accuracy and Flexibility on Diffusion-based Image Editing | 引用入口 | [rollback_collision_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/rollback_collision_audit.txt) |
| [2402.10491](https://arxiv.org/abs/2402.10491) | Make a Cheap Scaling: A Self-Cascade Diffusion Model for Higher-Resolution Adaptation | 引用入口 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2402.12099](https://arxiv.org/abs/2402.12099) | Zero-Shot Video Translation via Token Warping | 历史机制 | [REPORT.md](../snapshots/h3-observer-correspondence-r61-20261017/prior/evidence/REPORT.md) |
| [2403.03206](https://arxiv.org/abs/2403.03206) | Scaling Rectified Flow Transformers for High-Resolution Image Synthesis | 引用入口 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2403.12002](https://arxiv.org/abs/2403.12002) | DreamMotion: Space-Time Self-Similar Score Distillation for Zero-Shot Video Editing | 引用入口 | [self_similarity_motion_guidance_addendum.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/self_similarity_motion_guidance_addendum.txt) |
| [2403.12404](https://arxiv.org/abs/2403.12404) | Understanding and Improving Training-free Loss-based Diffusion Guidance | 历史机制 | [research.md](../snapshots/execution-20261022/innovation/adaptive_strength_20261023/research.md) |
| [2403.12962](https://arxiv.org/abs/2403.12962) | FRESCO: Spatial-Temporal Correspondence for Zero-Shot Video Translation | 历史机制 | [PRIOR_ART_REVIEW.txt](../snapshots/h3-timing-pose-observer-r15-20261016/PRIOR_ART_REVIEW.txt) |
| [2403.14602](https://arxiv.org/abs/2403.14602) | ReNoise: Real Image Inversion Through Iterative Noising | 历史机制 | [REVIEW.md](../snapshots/h3-vae-temporal-operator-r70-20261018/audit/codec_residual_prior_review/REVIEW.md) |
| [2403.15249](https://arxiv.org/abs/2403.15249) | Spectral Motion Alignment for Video Motion Transfer using Diffusion Models | 引用入口 | [REVIEW.md](../snapshots/h3-vae-temporal-operator-r70-20261018/audit/phase_shape_prior_review/REVIEW.md) |
| [2403.17377](https://arxiv.org/abs/2403.17377) | Self-Rectifying Diffusion Sampling with Perturbed-Attention Guidance | 历史机制 | [native_observer_followup_scope.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/native_observer_followup_scope.txt) |
| [2404.07724](https://arxiv.org/abs/2404.07724) | Applying Guidance in a Limited Interval Improves Sample and Distribution Quality in Diffusion Models | 原文复核 | 本轮原文 |
| [2405.14864](https://arxiv.org/abs/2405.14864) | Video Diffusion Models are Training-free Motion Interpreter and Controller | 历史机制 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2405.17661](https://arxiv.org/abs/2405.17661) | RefDrop: Controllable Consistency in Image or Video Generation via Reference Feature Guidance | 原文复核 | 本轮原文 |
| [2405.17880](https://arxiv.org/abs/2405.17880) | Diffusion Rejection Sampling | 历史机制 | [rollback_collision_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/rollback_collision_audit.txt) |
| [2405.20325](https://arxiv.org/abs/2405.20325) | MotionFollower: Editing Video Motion via Lightweight Score-Guided Diffusion | 引用入口 | [next_quality_actuator_20261016.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/next_quality_actuator_20261016.txt) |
| [2406.02507](https://arxiv.org/abs/2406.02507) | Guiding a Diffusion Model with a Bad Version of Itself | 原文复核 | [query_time_posterior_gate_review.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/query_time_posterior_gate_review.txt) |
| [2406.04873](https://arxiv.org/abs/2406.04873) | Ada-VE: Training-Free Consistent Video Editing Using Adaptive Motion Prior | 引用入口 | [motioncoach_adave_overlap_20261017.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/motioncoach_adave_overlap_20261017.txt) |
| [2406.06508](https://arxiv.org/abs/2406.06508) | Monkey See, Monkey Do: Harnessing Self-attention in Motion Diffusion for Zero-shot Motion Transfer | 历史机制 | [round2_architecture_candidates.txt](../snapshots/h3-timing-autoresearch-20261016/literature/round2_architecture_candidates.txt) |
| [2406.07540](https://arxiv.org/abs/2406.07540) | Ctrl-X: Controlling Structure and Appearance for Text-To-Image Generation Without Guidance | 历史机制 | [round2_architecture_candidates.txt](../snapshots/h3-timing-autoresearch-20261016/literature/round2_architecture_candidates.txt) |
| [2406.19680](https://arxiv.org/abs/2406.19680) | MimicMotion: High-Quality Human Motion Video Generation with Confidence-aware Pose Guidance | 引用入口 | [REVIEW.md](../snapshots/h3-vae-temporal-operator-r70-20261018/audit/phase_shape_prior_review/REVIEW.md) |
| [2407.14958](https://arxiv.org/abs/2407.14958) | Temporal Residual Jacobians For Rig-free Motion Transfer | 引用入口 | [next_computation_path_candidates.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/next_computation_path_candidates.txt) |
| [2408.00458](https://arxiv.org/abs/2408.00458) | Reenact Anything: Semantic Video Motion Transfer Using Motion-Textual Inversion | 引用入口 | [timing_prior_art.md](../snapshots/h3-timing-autoresearch-20261016/literature/timing_prior_art.md) |
| [2408.08252](https://arxiv.org/abs/2408.08252) | Derivative-Free Guidance in Continuous and Discrete Diffusion Models with Soft Value-Based Decoding | 历史机制 | [same_state_candidate_selection_review.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/same_state_candidate_selection_review.txt) |
| [2408.12588](https://arxiv.org/abs/2408.12588) | Real-Time Video Generation with Pyramid Attention Broadcast | 历史机制 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2409.20500](https://arxiv.org/abs/2409.20500) | FreeMask: Rethinking the Importance of Attention Masks for Zero-Shot Video Editing | 引用入口 | [dual_pose_support_scope_20261016.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/dual_pose_support_scope_20261016.txt) |
| [2410.02416](https://arxiv.org/abs/2410.02416) | Eliminating Oversaturation and Artifacts of High Guidance Scales in Diffusion Models | 原文复核 | [research.md](../snapshots/execution-20261022/innovation/adaptive_strength_20261023/research.md) |
| [2410.16152](https://arxiv.org/abs/2410.16152) | Warped Diffusion: Solving Video Inverse Problems with Image Diffusion Models | 历史机制 | [native_endpoint_retiming_scope.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/native_endpoint_retiming_scope.txt) |
| [2410.24037](https://arxiv.org/abs/2410.24037) | TPC: Test-time Procrustes Calibration for Diffusion-based Human Image Animation | 引用入口 | [next_computation_path_candidates.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/next_computation_path_candidates.txt) |
| [2411.10932](https://arxiv.org/abs/2411.10932) | Constrained Diffusion with Trust Sampling | 历史机制 | [calibrated_stopping_margin_review.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/calibrated_stopping_margin_review.txt) |
| [2411.14430](https://arxiv.org/abs/2411.14430) | Stable Flow: Vital Layers for Training-Free Image Editing | 引用入口 | [layer_selective_motion_guidance_review.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/layer_selective_motion_guidance_review.txt) |
| [2411.15034](https://arxiv.org/abs/2411.15034) | HeadRouter: A Training-free Image Editing Framework for MM-DiTs by Adaptively Routing Attention Heads | 历史机制 | [research.md](../snapshots/execution-20261022/innovation/adaptive_strength_20261023/research.md) |
| [2411.15115](https://arxiv.org/abs/2411.15115) | Self-Correcting Text-to-Video Generation with Misalignment Detection and Localized Refinement | 引用入口 | [self_correction_uncertainty_review.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/self_correction_uncertainty_review.txt) |
| [2411.17041](https://arxiv.org/abs/2411.17041) | Free$^2$Guide: Training-Free Text-to-Video Alignment using Image LVLM | 引用入口 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/counterfactual_acceptance_review_20261017/REVIEW.txt) |
| [2412.04432](https://arxiv.org/abs/2412.04432) | Divot: Diffusion Powers Video Tokenizer for Comprehension and Generation | 历史机制 | [interim_claim_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/interim_claim_audit.txt) |
| [2412.05263](https://arxiv.org/abs/2412.05263) | Mind the Time: Temporally-Controlled Multi-Event Video Generation | 历史机制 | [timing_prior_art.md](../snapshots/h3-timing-autoresearch-20261016/literature/timing_prior_art.md) |
| [2412.05275](https://arxiv.org/abs/2412.05275) | MotionFlow: Attention-Driven Motion Transfer in Video Diffusion Models | 引用入口 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/locality_spillover_review_20261017/REVIEW.txt) |
| [2412.07750](https://arxiv.org/abs/2412.07750) | Motion by Queries: Identity-Motion Trade-offs in Text-to-Video Generation | 历史机制 | [motion_query_m2a_review.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/motion_query_m2a_review.txt) |
| [2412.07776](https://arxiv.org/abs/2412.07776) | Video Motion Transfer with Diffusion Transformers | 历史机制 | [DESIGN_REVIEW.txt](../snapshots/h3-timing-phase-rope-r17-20261016/DESIGN_REVIEW.txt) |
| [2412.08629](https://arxiv.org/abs/2412.08629) | FlowEdit: Inversion-Free Text-Based Editing Using Pre-Trained Flow Models | 原文复核 | 本轮原文 |
| [2412.12974](https://arxiv.org/abs/2412.12974) | Attentive Eraser: Unleashing Diffusion Model's Object Removal Potential via Self-Attention Redirection Guidance | 引用入口 | [next_quality_actuator_20261016.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/next_quality_actuator_20261016.txt) |
| [2412.14283](https://arxiv.org/abs/2412.14283) | PixelMan: Consistent Object Editing with Diffusion Models via Pixel Manipulation and Generation | 历史机制 | [REVIEW.md](../snapshots/h3-vae-temporal-operator-r70-20261018/audit/codec_residual_prior_review/REVIEW.md) |
| [2501.06848](https://arxiv.org/abs/2501.06848) | A General Framework for Inference-time Scaling and Steering of Diffusion Models | 历史机制 | [rollback_collision_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/rollback_collision_audit.txt) |
| [2501.07563](https://arxiv.org/abs/2501.07563) | Training-Free Motion-Guided Video Generation with Enhanced Temporal Consistency Using Motion Consistency Loss | 引用入口 | [self_similarity_motion_guidance_addendum.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/self_similarity_motion_guidance_addendum.txt) |
| [2501.16714](https://arxiv.org/abs/2501.16714) | Separate Motion from Appearance: Customizing Motion via Customizing Text-to-Video Diffusion Models | 引用入口 | [round2_architecture_candidates.txt](../snapshots/h3-timing-autoresearch-20261016/literature/round2_architecture_candidates.txt) |
| [2502.00968](https://arxiv.org/abs/2502.00968) | CoDe: Blockwise Control for Denoising Diffusion Models | 历史机制 | [same_state_candidate_selection_review.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/same_state_candidate_selection_review.txt) |
| [2502.05433](https://arxiv.org/abs/2502.05433) | AdaFlow: Efficient Long Video Editing via Adaptive Attention Slimming And Keyframe Selection | 历史机制 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/source_anchor_observability_20261017/REVIEW.txt) |
| [2502.07962](https://arxiv.org/abs/2502.07962) | ESPFormer: Doubly-Stochastic Attention with Expected Sliced Transport Plans | 引用入口 | [innovation_assessment.txt](../snapshots/h3-timing-autoresearch-20261016/literature/innovation_assessment.txt) |
| [2502.11897](https://arxiv.org/abs/2502.11897) | DLFR-VAE: Dynamic Latent Frame Rate VAE for Video Generation | 历史机制 | [dynamic_temporal_compression_scope_note.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/dynamic_temporal_compression_scope_note.txt) |
| [2502.15894](https://arxiv.org/abs/2502.15894) | RIFLEx: A Free Lunch for Length Extrapolation in Video Diffusion Transformers | 引用入口 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2503.01075](https://arxiv.org/abs/2503.01075) | Tackling Hallucination from Conditional Models for Medical Image Reconstruction with DynamicDPS | 引用入口 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/counterfactual_acceptance_review_20261017/REVIEW.txt) |
| [2503.09419](https://arxiv.org/abs/2503.09419) | Alias-Free Latent Diffusion Models: Improving Fractional Shift Equivariance of Diffusion Latent Space | 历史机制 | [phase_matched_reference_bank_review.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/phase_matched_reference_bank_review.txt) |
| [2503.16832](https://arxiv.org/abs/2503.16832) | Joint Self-Supervised Video Alignment and Action Segmentation | 历史机制 | [missing_support_controller_review.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/missing_support_controller_review.txt) |
| [2503.17350](https://arxiv.org/abs/2503.17350) | Decouple and Track: Benchmarking and Improving Video Diffusion Transformers for Motion Transfer | 历史机制 | [residual_branch_go_nogo.txt](../snapshots/h3-timing-autoresearch-20261016/analysis/residual_branch_go_nogo.txt) |
| [2503.22168](https://arxiv.org/abs/2503.22168) | Spatial Transport Optimization by Repositioning Attention Map for Training-Free Text-to-Image Synthesis | 引用入口 | [ROOT_OPERATOR_PRIOR_ART_20261017.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/ROOT_OPERATOR_PRIOR_ART_20261017.txt) |
| [2504.06232](https://arxiv.org/abs/2504.06232) | HiFlow: Training-free High-Resolution Image Generation with Flow-Aligned Guidance | 历史机制 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2504.08902](https://arxiv.org/abs/2504.08902) | LookingGlass: Generative Anamorphoses via Laplacian Pyramid Warping | 历史机制 | [REVIEW.md](../snapshots/h3-vae-temporal-operator-r70-20261018/audit/codec_residual_prior_review/REVIEW.md) |
| [2504.10317](https://arxiv.org/abs/2504.10317) | Analysis of Attention in Video Diffusion Transformers | 历史机制 | [timing_prior_art.md](../snapshots/h3-timing-autoresearch-20261016/literature/timing_prior_art.md) |
| [2504.12027](https://arxiv.org/abs/2504.12027) | Understanding Attention Mechanism in Video Diffusion Models | 引用入口 | [attention_entropy_observer_addendum_20261017.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/attention_entropy_observer_addendum_20261017.txt) |
| [2505.03730](https://arxiv.org/abs/2505.03730) | FlexiAct: Towards Flexible Action Control in Heterogeneous Scenarios | 历史机制 | [IVEBENCH_PROTOCOL_INTERPRETATION_REVIEW.md](../snapshots/h3-timing-ivebench-auto-r55-20261017/audit/IVEBENCH_PROTOCOL_INTERPRETATION_REVIEW.md) |
| [2505.13344](https://arxiv.org/abs/2505.13344) | RoPECraft: Training-Free Motion Transfer with Trajectory-Guided RoPE Optimization on Diffusion Transformers | 历史机制 | [DESIGN_REVIEW.txt](../snapshots/h3-timing-phase-rope-r17-20261016/DESIGN_REVIEW.txt) |
| [2505.14036](https://arxiv.org/abs/2505.14036) | Adaptive Inference-Time Scaling via Cyclic Diffusion Search | 历史机制 | [rollback_collision_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/rollback_collision_audit.txt) |
| [2505.19367](https://arxiv.org/abs/2505.19367) | Adaptive Diffusion Guidance via Stochastic Optimal Control | 原文复核 | 本轮原文 |
| [2506.01144](https://arxiv.org/abs/2506.01144) | FlowMo: Variance-Based Flow Guidance for Coherent Motion in Video Generation | 引用入口 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/self_refining_primary_20261017/REVIEW.txt) |
| [2506.02444](https://arxiv.org/abs/2506.02444) | SViMo: Synchronized Diffusion for Video and Motion Generation in Hand-object Interaction Scenarios | 历史机制 | [phase_feedback_second_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/phase_feedback_second_audit.txt) |
| [2506.04213](https://arxiv.org/abs/2506.04213) | FullDiT2: Efficient In-Context Conditioning for Video Diffusion Transformers | 历史机制 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2506.04216](https://arxiv.org/abs/2506.04216) | UNIC: Unified In-Context Video Editing | 历史机制 | [reference_origin_hypothesis_audit.txt](../snapshots/h3-timing-autoresearch-20261016/analysis/reference_origin_hypothesis_audit.txt) |
| [2506.05046](https://arxiv.org/abs/2506.05046) | FlowDirector: Training-Free Flow Steering for Precise Text-to-Video Editing | 历史机制 | [SECOND_WAN_BASELINE_IMPLEMENTATION_CHECK.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/SECOND_WAN_BASELINE_IMPLEMENTATION_CHECK.txt) |
| [2506.06085](https://arxiv.org/abs/2506.06085) | Feedback Guidance of Diffusion Models | 原文复核 | 本轮原文 |
| [2506.07177](https://arxiv.org/abs/2506.07177) | Frame Guidance: Training-Free Guidance for Frame-Level Control in Video Diffusion Models | 历史机制 | [coarse_to_pose_observer_scope_20261016.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/coarse_to_pose_observer_scope_20261016.txt) |
| [2506.10978](https://arxiv.org/abs/2506.10978) | Where and How to Perturb: On the Design of Perturbation Guidance in Diffusion and Flow Models | 历史机制 | [research.md](../snapshots/execution-20261022/innovation/adaptive_strength_20261023/research.md) |
| [2506.17220](https://arxiv.org/abs/2506.17220) | Emergent Temporal Correspondences from Video Diffusion Transformers | 历史机制 | [PRIOR_ART_REVIEW.txt](../snapshots/h3-timing-pose-observer-r15-20261016/PRIOR_ART_REVIEW.txt) |
| [2506.19348](https://arxiv.org/abs/2506.19348) | When Distillation Breaks Motion Control: Restoring Generative Trajectories for Fast Video Generators | 原文复核 | [PRIOR_ART_REVIEW.txt](../snapshots/h3-timing-pose-observer-r15-20261016/PRIOR_ART_REVIEW.txt) |
| [2506.20294](https://arxiv.org/abs/2506.20294) | Ctrl-Z Sampling: Scaling Diffusion Sampling with Controlled Random Zigzag Explorations | 历史机制 | [rollback_collision_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/rollback_collision_audit.txt) |
| [2506.22868](https://arxiv.org/abs/2506.22868) | STR-Match: Matching SpatioTemporal Relevance Score for Training-Free Video Editing | 历史机制 | [prior_art_addendum.txt](../snapshots/h3-timing-attention-observer-r48-20261017/evidence/prior_art_addendum.txt) |
| [2507.08422](https://arxiv.org/abs/2507.08422) | Training-free Mixed-Resolution Latent Upsampling for Spatially Accelerated Diffusion Transformers | 引用入口 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2507.13934](https://arxiv.org/abs/2507.13934) | DiViD: Disentangled Video Diffusion for Static-Dynamic Factorization | 历史机制 | [residual_branch_go_nogo.txt](../snapshots/h3-timing-autoresearch-20261016/analysis/residual_branch_go_nogo.txt) |
| [2508.15774](https://arxiv.org/abs/2508.15774) | CineScale: Tuning-Free High-Resolution Video Generation | 历史机制 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2509.15130](https://arxiv.org/abs/2509.15130) | Taming Video Models for 3D and 4D Generation via Zero-Shot Camera Control | 历史机制 | [REVIEW.md](../snapshots/h3-ivebench-heldout-metrics-r64-20261018/audit/candidate_self_retiming_review/REVIEW.md) |
| [2509.16131](https://arxiv.org/abs/2509.16131) | Dynamic Classifier-Free Diffusion Guidance via Online Feedback | 原文复核 | [research.md](../snapshots/execution-20261022/innovation/adaptive_strength_20261023/research.md) |
| [2510.00438](https://arxiv.org/abs/2510.00438) | BindWeave: Subject-Consistent Video Generation via Cross-Modal Integration | 历史机制 | [semantic_motion_conflict_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_motion_conflict_audit.txt) |
| [2510.02226](https://arxiv.org/abs/2510.02226) | TempoControl: Temporal Attention Guidance for Text-to-Video Models | 历史机制 | [reference_time_map_novelty.txt](../snapshots/h3-timing-autoresearch-20261016/analysis/reference_time_map_novelty.txt) |
| [2510.08555](https://arxiv.org/abs/2510.08555) | VideoCanvas: Unified Video Completion from Arbitrary Spatiotemporal Patches via In-Context Conditioning | 历史机制 | [semantic_address_prior_art.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_address_prior_art.txt) |
| [2510.11647](https://arxiv.org/abs/2510.11647) | IVEBench: Modern Benchmark Suite for Instruction-Guided Video Editing Assessment | 历史机制 | [README.md](../snapshots/h3-ive-task-repair-metrics-r100-20261019/audit/independent_native_review_short0114/mf_native_only/runtime/official_source/README.md) |
| [2510.20888](https://arxiv.org/abs/2510.20888) | Video-As-Prompt: Unified Semantic Control for Video Generation | 历史机制 | [report.txt](../snapshots/h3-timing-architecture-r2-20261016/audit/rope_prior_art_check_20261019/report.txt) |
| [2510.22960](https://arxiv.org/abs/2510.22960) | FAME: Fairness-aware Attention-modulated Video Editing | 历史机制 | [timing_prior_art.md](../snapshots/h3-timing-autoresearch-20261016/literature/timing_prior_art.md) |
| [2511.07499](https://arxiv.org/abs/2511.07499) | Toward the Frontiers of Reliable Diffusion Sampling via Adversarial Sinkhorn Attention Guidance | 历史机制 | [ROOT_OPERATOR_PRIOR_ART_20261017.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/ROOT_OPERATOR_PRIOR_ART_20261017.txt) |
| [2511.08633](https://arxiv.org/abs/2511.08633) | Time-to-Move: Training-Free Motion Controlled Video Generation via Dual-Clock Denoising | 引用入口 | [r27_exact_controller_overlap.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/r27_exact_controller_overlap.txt) |
| [2511.14712](https://arxiv.org/abs/2511.14712) | FreeSwim: Revisiting Sliding-Window Attention Mechanisms for Training-Free Ultra-High-Resolution Video Generation | 引用入口 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2511.18471](https://arxiv.org/abs/2511.18471) | Jacobian-Aware Posterior Sampling for Inverse Problems | 引用入口 | [ROOT_SCOPE.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/nonlocal_response_candidate_20261017/ROOT_SCOPE.txt) |
| [2511.20640](https://arxiv.org/abs/2511.20640) | MotionV2V: Editing Motion in a Video | 历史机制 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/public_failure_followup_20261017/REVIEW.txt) |
| [2511.20649](https://arxiv.org/abs/2511.20649) | Infinity-RoPE: Action-Controllable Infinite Video Generation Emerges From Autoregressive Self-Rollout | 历史机制 | [reference_time_map_novelty.txt](../snapshots/h3-timing-autoresearch-20261016/analysis/reference_time_map_novelty.txt) |
| [2511.21631](https://arxiv.org/abs/2511.21631) | Qwen3-VL Technical Report | 历史机制 | [semantic_address_prior_art.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_address_prior_art.txt) |
| [2512.00909](https://arxiv.org/abs/2512.00909) | TalkingPose: Efficient Face and Gesture Animation with Feedback-guided Diffusion Model | 历史机制 | [phase_controller_collision.txt](../snapshots/h3-timing-autoresearch-20261016/literature/phase_controller_collision.txt) |
| [2512.01334](https://arxiv.org/abs/2512.01334) | AlignVid: Training-Free Attention Scaling for Semantic Fidelity in Text-Guided Image-to-Video Generation | 历史机制 | [timing_prior_art.md](../snapshots/h3-timing-autoresearch-20261016/literature/timing_prior_art.md) |
| [2512.01426](https://arxiv.org/abs/2512.01426) | ResDiT: Evoking the Intrinsic Resolution Scalability in Diffusion Transformers | 历史机制 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2512.03013](https://arxiv.org/abs/2512.03013) | In-Context Sync-LoRA for Portrait Video Editing | 历史机制 | [reference_origin_hypothesis_audit.txt](../snapshots/h3-timing-autoresearch-20261016/analysis/reference_origin_hypothesis_audit.txt) |
| [2512.05076](https://arxiv.org/abs/2512.05076) | BulletTime: Decoupled Control of Time and Camera Pose for Video Generation | 历史机制 | [reference_time_map_novelty.txt](../snapshots/h3-timing-autoresearch-20261016/analysis/reference_time_map_novelty.txt) |
| [2512.07469](https://arxiv.org/abs/2512.07469) | VideoCoF: Unified Video Editing with Temporal Reasoner | 历史机制 | [reference_origin_hypothesis_audit.txt](../snapshots/h3-timing-autoresearch-20261016/analysis/reference_origin_hypothesis_audit.txt) |
| [2512.21734](https://arxiv.org/abs/2512.21734) | Knot Forcing: Taming Autoregressive Video Diffusion Models for Real-time Infinite Interactive Portrait Animation | 历史机制 | [reference_time_map_novelty.txt](../snapshots/h3-timing-autoresearch-20261016/analysis/reference_time_map_novelty.txt) |
| [2512.25075](https://arxiv.org/abs/2512.25075) | SpaceTimePilot: Generative Rendering of Dynamic Scenes Across Space and Time | 历史机制 | [reference_time_map_novelty.txt](../snapshots/h3-timing-autoresearch-20261016/analysis/reference_time_map_novelty.txt) |
| [2601.01352](https://arxiv.org/abs/2601.01352) | Slot-ID: Identity-Preserving Video Generation from Reference Videos via Slot-Based Temporal Identity Encoding | 历史机制 | [next_candidate_gate.txt](../snapshots/h3-timing-autoresearch-20261016/literature/next_candidate_gate.txt) |
| [2601.01955](https://arxiv.org/abs/2601.01955) | MotionAdapter: Video Motion Transfer via Content-Aware Attention Customization | 历史机制 | [guidance_collision_audit.md](../snapshots/h3-timing-autoresearch-20261016/literature/guidance_collision_audit.md) |
| [2601.14250](https://arxiv.org/abs/2601.14250) | OmniTransfer: All-in-one Framework for Spatio-temporal Video Transfer | 历史机制 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2601.18340](https://arxiv.org/abs/2601.18340) | Beyond Rigid: Benchmarking Non-Rigid Video Editing | 历史机制 | [event_benchmark_scope_check_20261016.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/event_benchmark_scope_check_20261016.txt) |
| [2601.18577](https://arxiv.org/abs/2601.18577) | Self-Refining Video Sampling | 历史机制 | [TTA_PHASE_ADVANTAGE_REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/TTA_PHASE_ADVANTAGE_REVIEW.txt) |
| [2601.23231](https://arxiv.org/abs/2601.23231) | Solving Inverse Problems with Flow-based Models via Model Predictive Control | 历史机制 | [ROOT_SCOPE.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/nonlocal_response_candidate_20261017/ROOT_SCOPE.txt) |
| [2602.01624](https://arxiv.org/abs/2602.01624) | PISCES: Annotation-free Text-to-Video Post-Training via Optimal Transport-Aligned Rewards | 引用入口 | [next_candidate_gate.txt](../snapshots/h3-timing-autoresearch-20261016/literature/next_candidate_gate.txt) |
| [2602.03211](https://arxiv.org/abs/2602.03211) | Lookahead Sample Reward Guidance for Test-Time Scaling of Diffusion Models | 历史机制 | [observability_control_gap_candidates.txt](../snapshots/h3-timing-autoresearch-20261016/literature/observability_control_gap_candidates.txt) |
| [2602.05013](https://arxiv.org/abs/2602.05013) | Untwisting RoPE: Frequency Control for Shared Attention in DiTs | 历史机制 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2602.08794](https://arxiv.org/abs/2602.08794) | MOVA: Towards Scalable and Synchronized Video-Audio Generation | 历史机制 | [semantic_address_prior_art.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_address_prior_art.txt) |
| [2602.09868](https://arxiv.org/abs/2602.09868) | Free-GVC: Towards Training-Free Extreme Generative Video Compression with Temporal Coherence | 引用入口 | [vae_phase_observer_prior_art.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/vae_phase_observer_prior_art.txt) |
| [2602.14157](https://arxiv.org/abs/2602.14157) | When Test-Time Guidance Is Enough: Fast Image and Video Editing with Diffusion Guidance | 引用入口 | [ROOT_SCOPE.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/nonlocal_response_candidate_20261017/ROOT_SCOPE.txt) |
| [2603.01000](https://arxiv.org/abs/2603.01000) | Let Your Image Move with Your Motion! -- Implicit Multi-Object Multi-Motion Transfer | 引用入口 | [semantic_motion_conflict_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_motion_conflict_audit.txt) |
| [2603.01623](https://arxiv.org/abs/2603.01623) | Adaptive Spectral Feature Forecasting for Diffusion Sampling Acceleration | 引用入口 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2603.02175](https://arxiv.org/abs/2603.02175) | Kiwi-Edit: Versatile Video Editing via Instruction and Reference Guidance | 历史机制 | [semantic_phase_robustness_prior_art.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_phase_robustness_prior_art.txt) |
| [2603.02802](https://arxiv.org/abs/2603.02802) | NOVA: Sparse Control, Dense Synthesis for Pair-Free Video Editing | 历史机制 | [semantic_phase_robustness_prior_art.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_phase_robustness_prior_art.txt) |
| [2603.03281](https://arxiv.org/abs/2603.03281) | CFG-Ctrl: Control-Based Classifier-Free Diffusion Guidance | 历史机制 | [research.md](../snapshots/execution-20261022/innovation/adaptive_strength_20261023/research.md) |
| [2603.06289](https://arxiv.org/abs/2603.06289) | FlowMotion: Training-Free Flow Guidance for Video Motion Transfer | 历史机制 | [REVIEW.md](../snapshots/h3-vae-temporal-operator-r70-20261018/audit/phase_shape_prior_review/REVIEW.md) |
| [2603.09819](https://arxiv.org/abs/2603.09819) | ConfCtrl: Enabling Precise Camera Control in Video Diffusion via Confidence-Aware Interpolation | 引用入口 | [missing_support_controller_review.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/missing_support_controller_review.txt) |
| [2603.10744](https://arxiv.org/abs/2603.10744) | Just-in-Time: Training-Free Spatial Acceleration for Diffusion Transformers | 历史机制 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2603.17555](https://arxiv.org/abs/2603.17555) | FrescoDiffusion: 4K Image-to-Video with Prior-Regularized Tiled Diffusion | 引用入口 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2603.17889](https://arxiv.org/abs/2603.17889) | Identity as Presence: Towards Appearance and Voice Personalized Joint Audio-Video Generation | 历史机制 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2603.17989](https://arxiv.org/abs/2603.17989) | Versatile Editing of Video Content, Actions, and Dynamics without Training | 历史机制 | [timing_prior_art.md](../snapshots/h3-timing-autoresearch-20261016/literature/timing_prior_art.md) |
| [2603.19228](https://arxiv.org/abs/2603.19228) | SAMA: Factorized Semantic Anchoring and Motion Alignment for Instruction-Guided Video Editing | 历史机制 | [semantic_phase_robustness_prior_art.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_phase_robustness_prior_art.txt) |
| [2603.19795](https://arxiv.org/abs/2603.19795) | Controllable Text-to-Motion Generation via Modular Body-Part Phase Control | 历史机制 | [reference_time_map_novelty.txt](../snapshots/h3-timing-autoresearch-20261016/analysis/reference_time_map_novelty.txt) |
| [2604.00853](https://arxiv.org/abs/2604.00853) | MotionGrounder: Grounded Multi-Object Motion Transfer via Diffusion Transformer | 历史机制 | [guidance_collision_audit.md](../snapshots/h3-timing-autoresearch-20261016/literature/guidance_collision_audit.md) |
| [2604.03738](https://arxiv.org/abs/2604.03738) | Rethinking Position Embedding as a Context Controller for Multi-Reference and Multi-Shot Video Generation | 历史机制 | [guidance_collision_audit.md](../snapshots/h3-timing-autoresearch-20261016/literature/guidance_collision_audit.md) |
| [2604.09073](https://arxiv.org/abs/2604.09073) | DRIFT: Harnessing Inherent Fault Tolerance for Efficient and Reliable Diffusion Model Inference | 历史机制 | [rollback_collision_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/rollback_collision_audit.txt) |
| [2604.12582](https://arxiv.org/abs/2604.12582) | Relaxing Anchor-Frame Dominance for Mitigating Hallucinations in Video Large Language Models | 历史机制 | [timing_prior_art.md](../snapshots/h3-timing-autoresearch-20261016/literature/timing_prior_art.md) |
| [2604.19473](https://arxiv.org/abs/2604.19473) | TS-Attn: Temporal-wise Separable Attention for Multi-Event Video Generation | 历史机制 | [guidance_collision_audit.md](../snapshots/h3-timing-autoresearch-20261016/literature/guidance_collision_audit.md) |
| [2604.22554](https://arxiv.org/abs/2604.22554) | Video Analysis and Generation via a Semantic Progress Function | 历史机制 | [REVIEW.md](../snapshots/h3-vae-temporal-operator-r70-20261018/audit/phase_shape_prior_review/REVIEW.md) |
| [2604.22586](https://arxiv.org/abs/2604.22586) | FlowAnchor: Stabilizing the Editing Signal for Inversion-Free Video Editing | 引用入口 | [ROOT_INITIAL_OVERLAP.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/ROOT_INITIAL_OVERLAP.txt) |
| [2605.09425](https://arxiv.org/abs/2605.09425) | AtteConDA: Attention-Based Conflict Suppression in Multi-Condition Diffusion Models and Synthetic Data Augmentation | 引用入口 | [semantic_motion_conflict_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_motion_conflict_audit.txt) |
| [2605.09442](https://arxiv.org/abs/2605.09442) | SWIFT: Prompt-Adaptive Memory for Efficient Interactive Long Video Generation | 历史机制 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2605.10543](https://arxiv.org/abs/2605.10543) | TIE: Time Interval Encoding for Video Generation over Events | 历史机制 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2605.14136](https://arxiv.org/abs/2605.14136) | TeDiO: Temporal Diagonal Optimization for Training-Free Coherent Video Diffusion | 历史机制 | [timing_prior_art.md](../snapshots/h3-timing-autoresearch-20261016/literature/timing_prior_art.md) |
| [2605.15307](https://arxiv.org/abs/2605.15307) | Sound Sparks Motion: Audio and Text Tuning for Video Editing | 引用入口 | [semantic_branch_sampling_diagnostic.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/semantic_branch_sampling_diagnostic.txt) |
| [2605.22344](https://arxiv.org/abs/2605.22344) | Bernini: Latent Semantic Planning for Video Diffusion | 历史机制 | [semantic_phase_robustness_prior_art.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_phase_robustness_prior_art.txt) |
| [2605.23192](https://arxiv.org/abs/2605.23192) | Occlusion-Aware Physics-Semantic Keyframe Selection for Robust Video Editing | 历史机制 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/source_anchor_observability_20261017/REVIEW.txt) |
| [2605.23891](https://arxiv.org/abs/2605.23891) | Smart-Insertion-V: Photorealistic Video Insertion via a Closed-Loop Feedback Dual-Stream Framework | 历史机制 | [architecture_novelty_gate.txt](../snapshots/h3-timing-autoresearch-20261016/literature/architecture_novelty_gate.txt) |
| [2605.24962](https://arxiv.org/abs/2605.24962) | Tempered Self-Similarity Alignment for Physically Plausible Video Generation | 引用入口 | [self_similarity_motion_guidance_addendum.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/self_similarity_motion_guidance_addendum.txt) |
| [2605.25110](https://arxiv.org/abs/2605.25110) | Uncertainty-DTW for Sequences and Visual Tokens | 历史机制 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/public_failure_followup_20261017/REVIEW.txt) |
| [2605.25195](https://arxiv.org/abs/2605.25195) | Baton: Explicit Semantic Blueprints for Joint Video-Audio Generation | 历史机制 | [semantic_phase_robustness_prior_art.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_phase_robustness_prior_art.txt) |
| [2605.25661](https://arxiv.org/abs/2605.25661) | DRM: Diffusion-based Reward Model With Step-wise Guidance | 历史机制 | [same_state_candidate_selection_review.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/same_state_candidate_selection_review.txt) |
| [2605.29937](https://arxiv.org/abs/2605.29937) | Fisher-Preserving Guidance: Training-Free Manifold Constraints for Safe Diffusion Control | 历史机制 | [research.md](../snapshots/execution-20261022/innovation/adaptive_strength_20261023/research.md) |
| [2606.02441](https://arxiv.org/abs/2606.02441) | Spatial-Temporal Decoupled Reference Conditioning for Identity-Preserving Text-to-Video Generation | 历史机制 | [semantic_motion_conflict_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/semantic_motion_conflict_audit.txt) |
| [2606.05665](https://arxiv.org/abs/2606.05665) | V2V-Bench: A Comprehensive Benchmark for Video-to-Video Generation Evaluation | 历史机制 | [event_benchmark_scope_check_20261016.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/event_benchmark_scope_check_20261016.txt) |
| [2606.06228](https://arxiv.org/abs/2606.06228) | SAM-Flow: Source-Anchored Masked Flow for Training-Free Image Editing | 引用入口 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/locality_spillover_review_20261017/REVIEW.txt) |
| [2606.06361](https://arxiv.org/abs/2606.06361) | Physics in 2-Steps: Locking Motion Priors Before Visual Refinement Erases Them | 历史机制 | [phase_controller_collision.txt](../snapshots/h3-timing-autoresearch-20261016/literature/phase_controller_collision.txt) |
| [2606.08780](https://arxiv.org/abs/2606.08780) | Beyond Consistency: Preserving Temporal Structure in Zero-Shot Video Editing | 引用入口 | [r27_exact_controller_overlap.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/r27_exact_controller_overlap.txt) |
| [2606.10183](https://arxiv.org/abs/2606.10183) | Making Time Editable in Video Diffusion Transformers | 历史机制 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2606.13861](https://arxiv.org/abs/2606.13861) | Temporal Backtracking Search for Test-time Generative Video Reasoning | 历史机制 | [rollback_collision_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/rollback_collision_audit.txt) |
| [2606.19676](https://arxiv.org/abs/2606.19676) | TeleMorpher: Toward Robust Simultaneous Motion-Location Editing | 历史机制 | [REPORT.md](../snapshots/h3-observer-correspondence-r61-20261017/prior/evidence/REPORT.md) |
| [2606.26754](https://arxiv.org/abs/2606.26754) | Capacity-Controlled Multi-View Stylization of 3D Gaussian Splatting | 历史机制 | [capacity_temporal_transport_review.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/capacity_temporal_transport_review.txt) |
| [2606.30611](https://arxiv.org/abs/2606.30611) | Reweighting Framewise Attention in Video Transformers for Facial Expression Understanding | 引用入口 | [REPORT.txt](../snapshots/h3-timing-architecture-r2-20261016/audit/temporal_capacity_prior_art_20261020/REPORT.txt) |
| [2607.00861](https://arxiv.org/abs/2607.00861) | TrajLoc: Trajectory-Attention Localization for Multi-Object Motion Control | 历史机制 | [timing_prior_art.md](../snapshots/h3-timing-autoresearch-20261016/literature/timing_prior_art.md) |
| [2607.01869](https://arxiv.org/abs/2607.01869) | QWERTY: Training-Free Motion Control via Query-Warped Video Diffusion Transformers | 历史机制 | [ROOT_OPERATOR_PRIOR_ART_20261017.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/ROOT_OPERATOR_PRIOR_ART_20261017.txt) |
| [2607.08770](https://arxiv.org/abs/2607.08770) | LongE2V: Long-Horizon Event-based Video Reconstruction, Prediction, and Frame Interpolation with Video Diffusion Models | 历史机制 | [REVIEW.md](../snapshots/h3-vae-temporal-operator-r70-20261018/audit/codec_residual_prior_review/REVIEW.md) |
| [2607.11081](https://arxiv.org/abs/2607.11081) | Controlling Motion Transfer in Diffusion Transformers via Attention Heads | 原文复核 | [research.md](../snapshots/execution-20261022/innovation/adaptive_strength_20261023/research.md) |
| [2607.11644](https://arxiv.org/abs/2607.11644) | Motion4Motion: Motion Transfer Across Subjects at Inference | 引用入口 | [prior_art_addendum.txt](../snapshots/h3-timing-attention-observer-r48-20261017/evidence/prior_art_addendum.txt) |
| [2607.14945](https://arxiv.org/abs/2607.14945) | Introspective Attention Modulation for Safe Text-to-Image Generation | 历史机制 | [research.md](../snapshots/execution-20261022/innovation/adaptive_strength_20261023/research.md) |
| [2607.15443](https://arxiv.org/abs/2607.15443) | Estimating the Reliability of Dynamic Time Warping Alignments Using Circumstantial Evidence | 历史机制 | [REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/public_failure_followup_20261017/REVIEW.txt) |
| [2607.17972](https://arxiv.org/abs/2607.17972) | DiFA: Inference-Time Forward-Process Alignment for Diffusion Models | 历史机制 | [research.md](../snapshots/execution-20261022/innovation/adaptive_strength_20261023/research.md) |
| [2607.19919](https://arxiv.org/abs/2607.19919) | Diffusion ReRoll: Revisable Denoising for Robotic Sequential Prediction | 历史机制 | [rollback_collision_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/rollback_collision_audit.txt) |
| [2607.26887](https://arxiv.org/abs/2607.26887) | Conformalized Rate-Adaptive Sensing | 引用入口 | [calibrated_stopping_margin_review.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/calibrated_stopping_margin_review.txt) |
| [2608.01740](https://arxiv.org/abs/2608.01740) | Disagree to Accelerate: Closing the Loop on Diffusion Feature Forecasts | 引用入口 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2608.05049](https://arxiv.org/abs/2608.05049) | OmniEdit-Bench: A Comprehensive Benchmark for Instruction-based Video Editing | 历史机制 | [event_benchmark_scope_check_20261016.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/event_benchmark_scope_check_20261016.txt) |
| [2608.06009](https://arxiv.org/abs/2608.06009) | Wan-Animate-2: Pushing the Application Boundaries of Character Animation | 原文复核 | [METHODS_AND_REPRODUCTION.txt](../snapshots/h3-timing-autoresearch-20261016/analysis/METHODS_AND_REPRODUCTION.txt) |
| [2608.07003](https://arxiv.org/abs/2608.07003) | HRDiT: Training-Free High-Resolution Image Generation with Off-the-Shelf Diffusion Transformer Models | 引用入口 | [CREDITS.md](../snapshots/h3-timing-architecture-r2-20261016/audit/community_h3_prior_art_20261019/snapshot/CREDITS.md) |
| [2608.26101](https://arxiv.org/abs/2608.26101) | RefVideo-6M: A Reliable Reference-Based Dataset for Instructional Video Editing | 引用入口 | [SUPPLEMENTAL_SCREEN_20261017.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/phase_shape_identifiability_20261017/SUPPLEMENTAL_SCREEN_20261017.txt) |
| [2609.02367](https://arxiv.org/abs/2609.02367) | The Missing Temporal Link: Temporal Context Routing for Script-Driven Audio-Video Generation | 历史机制 | [reference_origin_hypothesis_audit.txt](../snapshots/h3-timing-autoresearch-20261016/analysis/reference_origin_hypothesis_audit.txt) |
| [2609.04190](https://arxiv.org/abs/2609.04190) | One Editor, Many Edits: A Unified Training-Free Framework for Diverse Video Editing | 原文复核 | [AUTOMATION_REVIEW.txt](../snapshots/h3-timing-auto-motion-r26-20261017/design/AUTOMATION_REVIEW.txt) |
| [2609.04649](https://arxiv.org/abs/2609.04649) | ReaDiT Guidance: Control for Image and Video Generation using Diffusion Transformer Features | 历史机制 | [guidance_collision_audit.md](../snapshots/h3-timing-autoresearch-20261016/literature/guidance_collision_audit.md) |
| [2609.06288](https://arxiv.org/abs/2609.06288) | Object-Aware Background-Controlled Editing via Weighted Velocity Guidance | 历史机制 | [round2_architecture_candidates.txt](../snapshots/h3-timing-autoresearch-20261016/literature/round2_architecture_candidates.txt) |
| [2609.08505](https://arxiv.org/abs/2609.08505) | Temporal State Transport in Video Generation: Diagnosing and Correcting Spectral Imbalance | 历史机制 | [guidance_collision_audit.md](../snapshots/h3-timing-autoresearch-20261016/literature/guidance_collision_audit.md) |
| [2609.11507](https://arxiv.org/abs/2609.11507) | Harnessing Intrinsic Subject-Aware Attention for Controllable Multi-Subject Video Generation | 原文复核 | [PRIOR_ART_REVIEW.txt](../snapshots/h3-timing-pose-observer-r15-20261016/PRIOR_ART_REVIEW.txt) |
| [2609.11638](https://arxiv.org/abs/2609.11638) | Vidu S2: Real-Time Interactive, Editable, and Spatial Video Generation | 原文复核 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2609.19644](https://arxiv.org/abs/2609.19644) | ScientistTwo: Pioneering the Human Knowledge Frontier with Autonomous AI | 引用入口 | [framework_adaptation.txt](../snapshots/h3-timing-autoresearch-20261016/literature/framework_adaptation.txt) |
| [2609.21251](https://arxiv.org/abs/2609.21251) | Geometry-Aware Diffusion Guidance via Curvature-Adaptive Tubular Correction | 历史机制 | [research.md](../snapshots/execution-20261022/innovation/adaptive_strength_20261023/research.md) |
| [2609.23658](https://arxiv.org/abs/2609.23658) | Why Do Video Diffusion Models Violate Physics? Unveiling the Flaws in Attention Mechanisms | 历史机制 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2609.35708](https://arxiv.org/abs/2609.35708) | Mind the RefGAP: Correcting Reference Attention in Diffusion-Based Visual Editing | 原文复核 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2609.36496](https://arxiv.org/abs/2609.36496) | Reimagine Video Dynamics | 历史机制 | [REVIEW.md](../snapshots/h3-ivebench-heldout-metrics-r64-20261018/audit/candidate_self_retiming_review/REVIEW.md) |
| [2610.08649](https://arxiv.org/abs/2610.08649) | Stable Scores, Unstable Answers: Frame Phase and Option Order in Video Multiple-Choice Evaluation | 历史机制 | [phase_matched_reference_bank_review.txt](../snapshots/h3-timing-architecture-r2-20261016/literature/phase_matched_reference_bank_review.txt) |
| [2610.12427](https://arxiv.org/abs/2610.12427) | FastBench: Can Streaming VLMs Perceive High-Dynamic Real-World Streams? | 历史机制 | [interim_claim_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/interim_claim_audit.txt) |
| [2610.12963](https://arxiv.org/abs/2610.12963) | MotionCoach: Constructing Multimodal Guidance for Video Professional Motion Editing | 引用入口 | [motioncoach_adave_overlap_20261017.txt](../snapshots/h3-timing-auto-motion-r26-20261017/literature/motioncoach_adave_overlap_20261017.txt) |
| [2610.13072](https://arxiv.org/abs/2610.13072) | AV-FlowEdit: Training-Free Prompt-Driven Audio-Visual Editing with Event-Aware Spectral Trajectory Preservation | 原文复核 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2610.13369](https://arxiv.org/abs/2610.13369) | Opening the Black Box of Classifier-Free Guidance via Information Bottleneck | 原文复核 | [research.md](../snapshots/execution-20261022/innovation/adaptive_strength_20261023/research.md) |
| [2610.14672](https://arxiv.org/abs/2610.14672) | Competition Domains Matter: Selective Head Globalization for Training-Free Sparse Attention in Video Diffusion Transformers | 引用入口 | [MECHANISM_OPTIONS.md](../snapshots/h3-method-options-20261020/literature/MECHANISM_OPTIONS.md) |
| [2610.15281](https://arxiv.org/abs/2610.15281) | Imperfect Verifiers, Exact Targets: Inference-Time Scaling for Continuous Generation | 历史机制 | [rollback_collision_audit.txt](../snapshots/h3-timing-autoresearch-20261016/literature/rollback_collision_audit.txt) |
| [2610.17829](https://arxiv.org/abs/2610.17829) | QK-Edit: Revisiting Attention-based Injection in MM-DiT for Image and Video Editing | 原文复核 | 本轮原文 |
