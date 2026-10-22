# H3 动作时间错位：时间对齐近邻与创新边界核实

检索日期：2026-10-16。范围：视频编辑/动作迁移的帧同步、参考时间路由、时间 RoPE、事件时间控制及相邻注意力方法。此文件是独立的文献否定性审查，不汇报任何本轮 H3 实验结果。不能据此声称穷尽文献或证明不存在同类工作。

## 决策结论

“输出视频 query 只/优先读取相同时刻的参考视频 key”已经存在非常明确的先例：Vidu S2-Editing 与 Wan-Animate-2。二者比 DIAL 更直接撞候选的时间路由核心。改成共享/重置时间 RoPE 也已有 UNIC、VideoCoF、Sync-LoRA；按动作时间控制 attention 与动态达阈值停止已有 TempoControl 等。

因此，不能以“我们第一次将参考增强改成时间对齐”作为创新主张。当前还可以实验的更窄问题是：**冻结的通用编辑模型是否存在参考组内部的时间分配失配；能否在不增加该组即时总注意力的条件下修正，同时比同帧硬 mask 与普通软 bias 更好地保持编辑能力。** 这只是尚待检验的组合假说，不是已确认的新架构，也不保证论文贡献。

## 三种时间必须分开

- 物理视频时间 τ：帧的 PTS/FPS、动作发生的时间；本课题的延迟应在这里测量。
- 去噪时间 s/σ：从噪声到视频的求解进度。DIAL/TempoControl 的启用区间位于这里。
- 模型位置坐标 p：RoPE 使用的坐标，经 VAE 时间压缩、patchify、额外参考图位置等映射而来，不能直接等于原视频帧号。

下面矩阵的“直接重合”指概念或干预接口重合，不表示两篇方法完全相同，也不表示已移植到 H3。

## 风险总表

| 工作 | 主要接口 | 训练/优化 | 与候选的碰撞 |
|---|---|---|---|
| [Sync-LoRA](https://arxiv.org/html/2512.03013v1) | 物理帧时间＋去噪时刻，二者分开编码。 | trained_lora | high_task_and_time_rope |
| [TempoControl](https://arxiv.org/html/2510.02226v3) | 控制物理时间上的概念分布；在去噪步骤中闭环优化。 | frozen_model_test_time_latent_optimization | high_dynamic_gate_and_event_timing |
| [DynaEdit](https://arxiv.org/html/2603.17989v1) | 重点是采样轨迹上的噪声关联，不等于校正视频物理时间的延迟。 | frozen_model_inference_wrapper | medium_motion_preservation_objective |
| [DIAL](https://arxiv.org/html/2609.11507v1) | Phase I 使用采样过程最后 80% 的步骤，即跳过开头约 20%；不是走完 80% 才启用。 | phase_I_frozen_phase_II_trained_dpo_lora | direct_reference_logit_amplification |
| [UNIC](https://arxiv.org/html/2506.04216v1) | 物理时间坐标。 | trained_unified_dit | direct_time_coordinate_alignment |
| [VideoCoF](https://arxiv.org/html/2512.07469v2) | 物理帧坐标及源目标对齐。 | trained_editing_dit | direct_time_rope_and_motion_misalignment |
| [Vidu S2-Editing](https://arxiv.org/html/2609.11638v1) | 明确物理帧一一对齐。 | trained_bidirectional_then_causal_and_distilled | direct_same_time_reference_routing |
| [Wan-Animate-2](https://arxiv.org/html/2608.06009v2) | 物理时间一致，参考与目标空间位置另区分。 | trained_qkv_and_optional_view_lora_distillation | direct_same_time_reference_routing |
| [TS-Attn](https://arxiv.org/html/2604.19473v1) | 物理事件时间区间＋早期采样步骤。 | frozen_model_attention_intervention | high_temporal_redistribution |
| [MinT / ReRoPE](https://arxiv.org/html/2412.05263v1) | 物理事件边界。 | trained_on_temporally_grounded_data | high_temporal_rope_and_soft_transition |
| [RoPECraft](https://arxiv.org/html/2505.13344v1) | 跨帧轨迹＋采样早期；初始变形保留时间项。 | frozen_model_test_time_rope_optimization | high_rope_motion_transfer |
| [STR-Match](https://arxiv.org/html/2506.22868v1) | 物理相邻帧；逐采样步骤 latent 优化。 | frozen_model_test_time_latent_optimization | medium_internal_motion_correspondence |
| [TeDiO](https://arxiv.org/pdf/2605.14136) | 物理帧邻接＋预设早期采样区间。 | frozen_model_test_time_latent_optimization | medium_local_internal_instability_guidance |
| [EVE](https://www.ijcai.org/proceedings/2024/0075.pdf) | 首帧锚定而非源目标同一物理帧对应。 | frozen_model_test_time_latent_optimization | low_name_collision_frame_align_attention |
| [Analysis of Attention in Video Diffusion Transformers](https://arxiv.org/html/2504.10317v1) | 视频物理帧间联系。 | analysis_and_zero_shot_transfer | medium_attention_motion_mechanism |
| [TrajLoc](https://arxiv.org/html/2607.00861v1) | 每帧空间轨迹。 | trained_encoders_and_lora | medium_attention_replacement_and_renormalization |
| [FAME](https://arxiv.org/html/2510.22960v1) | 跨帧外观/结构关系。 | frozen_model_attention_intervention | medium_masked_logit_guidance |
| [DTR](https://arxiv.org/html/2604.12582v1) | 参考视频的帧证据分配＋自回归文本步骤。 | frozen_decoder_attention_intervention | cross_domain_temporal_rebalancing |
| [Reenact Anything](https://arxiv.org/abs/2408.00458) | 细粒度逐帧运动表征。 | per_instance_motion_embedding_optimization | medium_fine_motion_time_representation |
| [AlignVid](https://arxiv.org/html/2512.01334v1) | 采样步骤调度；无原视频逐帧时钟。 | frozen_model_qk_scaling | medium_attention_scaling_and_scheduling |

## 逐篇证据

### 1. Sync-LoRA

首发：2025-12-02；核查版本：v1。任务：人像编辑，保留说话、眨眼、视线、上身动作的逐帧同步。

源视频 clean latent 与目标 noisy latent 共享注意力及物理时间对应的 3D RoPE；用各 token 的去噪时刻区分分支。训练同步外观配对视频上的 rank-128 LoRA，使用常规 flow matching 目标。

**边界判断：**不能声称首次研究逐帧动作同步或首次复用源/目标时间坐标。与冻结 H3 的组内注意力重路由并非同一实现。当前仓库检查只有 README/资产，不能当作已发布原论文完整训练代码。README 的 LTX-2.3 权重也不能自动等同论文 LTX-Video 版本。

来源：[论文](https://arxiv.org/html/2512.03013v1)，定位：§3；同步指标附录。 [官方仓库](https://github.com/SagiPolaczek/Sync-LoRA)。 检查 commit：3868f06a19ba88eee1e37059f7884f9f45f37071。

### 2. TempoControl

首发：2025-10-02；核查版本：v3 (2026-04-01)。任务：T2V 中指定概念、动作何时出现，包含音频节奏对齐。

空间聚合 video→text cross-attention 得到概念时间曲线 a；对 latent 优化 −Pearson(a,m)+幅度项+空间熵项。每个去噪步设优化上限，相关度过阈值即停；代码还先判断相关度决定该步是否优化。

**边界判断：**动态检查、需要时引导、满足阈值就停已被实现。区别可在原视频视觉时间对应、无 latent 反传和保留组总 mass；不能把动态启停本身当贡献。

来源：[论文](https://arxiv.org/html/2510.02226v3)，定位：§4；wan/text2video.py:624–734。 [官方仓库](https://github.com/Shira-Schiber/TempoControl)。 [已核实的实现位置](https://github.com/Shira-Schiber/TempoControl/blob/ac28c443ec112e0da6f9f5cbca26a2218d8d12dc/wan/text2video.py#L624)。 检查 commit：ac28c443ec112e0da6f9f5cbca26a2218d8d12dc。

### 3. DynaEdit

首发：2026-03-18；核查版本：v1。任务：内容、动作及动态编辑，允许改变源运动。

SGA 对多次噪声采样的源/目标预测速度差做源结构相似度加权；ANC 在相邻去噪步骤间逐渐提高噪声相关性，稳定编辑路径。

**边界判断：**未观察到输出帧→参考帧的显式时间路由或组总 mass 约束。已定位项目页，未定位官方完整模型实现，不把这一检索结果说成代码不存在。

来源：[论文](https://arxiv.org/html/2603.17989v1)，定位：§3；项目 https://dynaedit.github.io/ 。

### 4. DIAL

首发：2026-09-10；核查版本：v1。任务：多参考图的主体保真、空间绑定与语义漂移控制。

Phase I 在 video query→指定 reference key 的 logits 上加 log(γ)×前一步主体空间 grounding map；普通 softmax。Phase II 另训练 DPO/LoRA，不能把整篇统称无需训练。

**边界判断：**参考特征统一或局部增权直接重合；未见物理帧对应路由与参考组总 mass 守恒。论文把 uniform gain 也作为基线。未定位官方实现。

来源：[论文](https://arxiv.org/html/2609.11507v1)，定位：§3.3–3.4，Eq.(6)，§4.3。

### 5. UNIC

首发：2025-06-04；核查版本：v1。任务：统一多条件视频编辑。

条件 token 与生成 token 联合建模；对需要逐时对应的参考视频、相机、音频复用目标的时间 RoPE 坐标；身份/风格条件使用独立时间偏移，任务 embedding 区分条件。

**边界判断：**直接占据“源目标时间坐标对齐”策略。不是无需训练的 H3 校正插件，也未见精确参考 mass 守恒。官方项目 https://zixuan-ye.github.io/UNIC/；完整实现未核实。

来源：[论文](https://arxiv.org/html/2506.04216v1)，定位：位置编码部分；ICLR 2026 版本 https://openreview.net/pdf?id=Vb4nE3WWf5 。

### 6. VideoCoF

首发：2025-12-08；核查版本：v2 (2026-04-05)。任务：带 reasoning frame 的统一指令编辑及长度外推。

[源, reasoning, 目标] 的时间位置分别设为 [1..F,0,1..F]，源保持 clean；避免时间连续拼接与额外 reasoning 帧造成坐标碰撞。

**边界判断：**论文明确展示错误 RoPE 导致“提衣服”动作未执行，不能说此类动作错位与时间坐标关系没人研究。实现仍为全注意力，不是组 mass 守恒路由。

来源：[论文](https://arxiv.org/html/2512.07469v2)，定位：§3.3、§4.4、补充§6；rope_apply。 [官方仓库](https://github.com/knightyxp/VideoCoF)。 [已核实的实现位置](https://github.com/knightyxp/VideoCoF/blob/f45b8009616b3ef8e2024a7da585249b4c74fc2b/videox_fun/models/wan_transformer3d.py#L137)。 检查 commit：f45b8009616b3ef8e2024a7da585249b4c74fc2b。

### 7. Vidu S2-Editing

首发：2026-09-10；核查版本：v1。任务：换装、换角色、风格及背景替换，保持源视频动作与时间。

frame-aligned attention：每个目标帧仅访问同一时间源帧；参考图对所有目标帧可见；训练初期目标内部保持双向注意力，随后训练因果流式版本。

**边界判断：**这是候选最直接撞点，强于 DIAL：对应时间 source-key 路由已经明确提出。公开仓库当前主要提供资料/API，未见完整模型实现；并未声称或保证每行原参考总 mass 不变。

来源：[论文](https://arxiv.org/html/2609.11638v1)，定位：简介 Vidu S2-Editing；§3.2。 [官方仓库](https://github.com/shengshu-ai/Vidu-S)。

### 8. Wan-Animate-2

首发：2026-08-06；核查版本：v2 (2026-08-08)。任务：角色图＋驱动视频的动作迁移，另支持视角控制。

双分支共享 QKV；Time-Align RoPE 对齐源目标时间；Sparse-Ref Attention 限制 latent query 只读对应时间 reference K/V，latent 内部 full attention。

**边界判断：**同帧路由已有公开实现。mask 的 refkv_frame 加 1 与额外图像帧有关，不能照抄至 H3。它是受训架构，非冻结模型的测试时校正；代码未见保持修改前参考总 mass 的条件。

来源：[论文](https://arxiv.org/html/2608.06009v2)，定位：§3.2–3.4；wan_animate_2_model.py:566。 [官方仓库](https://github.com/Wan-Video/Wan-Animate-2)。 [已核实的实现位置](https://github.com/Wan-Video/Wan-Animate-2/blob/3ad2fef7d61d6200c9c653e0fe47be7616b323f3/wanxiang/models/wan_animate_2_model.py#L566)。 检查 commit：3ad2fef7d61d6200c9c653e0fe47be7616b323f3。

### 9. TS-Attn

首发：2026-04-21；核查版本：v1。任务：多事件 T2V，按指定事件时间段生成。

早期步骤将 video→event text attention 按事件时间分区：在运动区域增强匹配文本、抑制不匹配文本，并由当前注意力强度调节；消融区分时间重分配与整体增强。

**边界判断：**“时间重分配比简单增权更重要”不是全新解释。条件是文本事件，非原视频帧；未观察到原参考组 mass 精确守恒。代码 URL 已由官方来源定位，未逐函数审查。

来源：[论文](https://arxiv.org/html/2604.19473v1)，定位：方法和消融。 [官方仓库](https://github.com/Hong-yu-Zhang/TS-Attn)。

### 10. MinT / ReRoPE

首发：2024-12-06；核查版本：v1。任务：多事件 T2V，显式控制每个事件起止时间。

将第 n 个事件 [s_n,e_n] 重标定为固定长度 L：t_tilde=(t-s_n)L/(e_n-s_n)+(n-1)L，video 与事件文本用相应 ReRoPE；额外 temporal cross-attention 学习控制。

**边界判断：**已讨论硬 mask 在事件边界产生不连续，以及软位置先验的优势。不是 raw reference-video query/key 校正。RoPE 的位置偏置不能在任意 Q/K 内容上视作严格单调距离核。

来源：[论文](https://arxiv.org/html/2412.05263v1)，定位：§3.2、§4.5；CVPR 2025 官方项目 https://mint-video.github.io/ 。

### 11. RoPECraft

首发：2025-05-19；核查版本：v1。任务：参考视频运动转移到不同内容。

参考光流位移扭曲空间 RoPE 复指数；早期对 RoPE 优化，使预测 flow-matching 速度靠近参考 latent 构造的目标速度，并以傅里叶相位约束正则化。

**边界判断：**改 RoPE、运动场/相位指导已不是空白。不同于只重排参考键时间且保持该组总 mass。代码地址已定位，本轮未逐函数审查。

来源：[论文](https://arxiv.org/html/2505.13344v1)，定位：方法；NeurIPS 2025 项目 https://berkegokmen1.github.io/RoPECraft/ 。 [官方仓库](https://github.com/berkegokmen1/RoPECraft)。

### 12. STR-Match

首发：2025-06-28；核查版本：v1。任务：编辑保留运动且允许形状变化。

组合 2D 空间与 1D 时间注意力，构造相邻帧间像素关系 STR score；从源提取目标关系，再用负余弦目标优化编辑 latent，可带保留区域 mask。

**边界判断：**内在运动关系与源目标差异指导已存在。不是直接 reference-video 时间路由；官方项目的代码标签仍写 coming soon，仓库实现可用性未完整审查。

来源：[论文](https://arxiv.org/html/2506.22868v1)，定位：方法；https://jslee525.github.io/str-match/ 。 [官方仓库](https://github.com/jslee525/STR-Match_official)。

### 13. TeDiO

首发：2026-05-13；核查版本：v1。任务：T2V 的运动连贯、闪烁和抖动控制。

从 Q/K 提取同空间位置的 F×F 时间注意力；S(p) 为主及相邻对角线的相邻差平方和。选高 S 的 top-k 空间/头位置，早期对 latent 做梯度下降平滑对角线。

**边界判断：**局部内部信号定位不稳定并干预已有研究；其目标是平滑，不是参考动作时钟。不能把平滑分数提升当作短动作保真：动态幅度可能降低。未定位官方实现。

来源：[论文](https://arxiv.org/pdf/2605.14136)，定位：PDF §3、Eq.(4)–(9)。

### 14. EVE

首发：2024；核查版本：IJCAI 2024。任务：早期零样本视频编辑及外观连贯。

深度约束 inversion/采样；其 Frame-Align Attention 为 Q=W_Q z_i，K=W_K z_1，V=W_V z_1，所有当前帧读取首帧特征。

**边界判断：**名称相近但不是 Vidu/Wan 的同帧 source-reference mask，不能因 frame-align 名称误判完全重合。代码 URL 来自论文，未审查实现。

来源：[论文](https://www.ijcai.org/proceedings/2024/0075.pdf)，定位：PDF §3.4、Eq.(11)。 [官方仓库](https://github.com/alipay/Ant-Multi-Modal-Framework/tree/main/prj/EVE)。

### 15. Analysis of Attention in Video Diffusion Transformers

首发：2025-04；核查版本：v1。任务：研究视频 DiT attention 结构并进行跨提示词转移。

区分空间局部块和跨帧条纹结构，分析层/头差异；跨提示词注入 visual self-attention maps 可转移结构运动。

**边界判断：**不能把所有 attention head 都解释成运动；整体注入可限制内容编辑。此文不是 reference 分支组内质量守恒校正。

来源：[论文](https://arxiv.org/html/2504.10317v1)，定位：attention 结构分析及编辑实验。

### 16. TrajLoc

首发：2026-07-01；核查版本：v1。任务：多对象 I2V 点轨迹控制及身份保留。

用逐帧轨迹高斯热图替换对象文本 token 的 cross-attention 列并行归一化；训练轨迹/外观编码器及 LoRA。附录给 joint attention 替换/修正推导。

**边界判断：**注意力重分配再归一化已有明确数学处理；该归一化没有保持修改前整个视觉参考组的总 mass，也不处理源视频延迟。

来源：[论文](https://arxiv.org/html/2607.00861v1)，定位：§3.1–3.3、附录 C。 [官方仓库](https://github.com/Sela-Omer/traj-loc)。

### 17. FAME

首发：2025-10-27；核查版本：v1。任务：公平属性相关的视频编辑及运动稳定。

在 attention logits 中加公平区域 mask 与帧特征相似性项，后者使用 exp(−特征距离平方/温度)。

**边界判断：**不能仅凭其 time-decay 文字就说公式是物理 Δt 的 Gaussian；实际给出的项基于特征差。与本候选没有精确逐时路由＋组 mass 守恒等式重合。

来源：[论文](https://arxiv.org/html/2510.22960v1)，定位：方法公式。

### 18. DTR

首发：2026-04-14；核查版本：v1。任务：视频理解 LLM 的时间证据偏置与幻觉，非视频生成。

按帧平均 logits 得 s_i，构造相对最大值缺口 g_i，向视觉 logits 加 (α+β normalized(g_i))×|z|，主要修改中后 decoder 层。

**边界判断：**仅“训练免费地重平衡视频帧注意力”跨领域也非新意；无 query 对应输出视频物理时刻、无原视觉组 mass 守恒。

来源：[论文](https://arxiv.org/html/2604.12582v1)，定位：§3.2、Eq.(5)–(10)。 [官方仓库](https://github.com/ifwub234/DTR)。

### 19. Reenact Anything

首发：2024-08-01；核查版本：arXiv abstract and SIGGRAPH 2025 project。任务：参考视频语义运动迁移至不同主体。

对参考视频优化逐帧 motion textual embedding，再用于目标图驱动；backbone 冻结，但不是完全无测试时优化。

**边界判断：**本轮未完整审查全文实现，故只作为需要补查的近邻，不作精确不存在性论据。

来源：[论文](https://arxiv.org/abs/2408.00458)，定位：官方项目 https://mkansy.github.io/reenact-anything/ 及摘要。

### 20. AlignVid

首发：2025-12；核查版本：v1; project reports ICML 2026。任务：图生视频对文字编辑/新动作的执行不足。

放大 Q 或 K 调节 attention inverse temperature；按前景敏感 block 与去噪区间选择性启用，也讨论由 logit 能量自适应确定强度。

**边界判断：**“放大 attention 并选择层/步骤”已有训练免费实现思路。未见对参考视频组 mass 守恒的物理时间路由。

来源：[论文](https://arxiv.org/html/2512.01334v1)，定位：§5、附录 F；https://law1223.github.io/AlignVid/ 。


## 候选的准确数学定义与不能夸大的地方

设某层某头的单个输出 query 为 q，全键 logits 为 z_q，A_q=softmax(z_q)。R 表示**整组参考视频**键，m_q=Σ(j∈R) A_qj。希望按物理时间施加偏置 b_qj，例如在允许保留源动作的区域，使用时间距离的负代价；动作被用户要求修改的区域应禁用保真约束。

只在 R 内重分配，并保持该 query 对 R 的总 attention mass：

    A'_qj = m_q · A_qj exp(b_qj) / Σ(k∈R)[A_qk exp(b_qk)],  j∈R
    A'_qj = A_qj,                                              j∉R

等价的 pre-softmax 写法是：

    c_q = logsumexp(z_q,R) − logsumexp(z_q,R + b_q,R)
    z'_qj = z_qj + b_qj + c_q,  j∈R
    z'_qj = z_qj,               j∉R

该写法保持参考组的指数和，因而保留全行 softmax 的分母；这给出一个确实区别于普通 reference logit gain 的即时控制变量。它是常规条件概率重加权/归一化，不应把等式本身包装成新的数学机制。

必须明确六点：

1. 守恒的是**每个输出 query 对整个参考视频组的总 mass**，而非每个源帧分别的 mass。若每个源帧的 mass 都不变，就不能改变时间分配。
2. 它只保证当前层当前计算的 mass；更新后的隐藏状态会影响后续层/步骤，不能声称整个推理过程的模态权重完全不变。
3. m_q 很小时，组内重排不能无中生有地增加参考依赖。要记录 m_q 与时间分配两条量，不能只看对角化。
4. 若 b 仅依赖帧时间，则同一参考帧内部的相对空间注意力仍保持；这不自动保证主体身份、背景或肢体一致。
5. H3 的真实 token 布局、参考帧采样、causal VAE 对应关系必须由代码核对。相等 latent index 不必等于完全相同的物理感受野。
6. 若真正原因只是 FPS/抽帧/长度取整/额外图像坐标的配置错误，修复属于管线或工程纠错；不应把它包装成模型架构创新。

该形式与已审查近邻的区别是限定条件下的精确组 mass 守恒，而非“注意力调整”“同帧锚定”“动态调度”这些已广泛存在的上位概念。本轮未找到与上述全部条件完全相同的冻结视频编辑实现，但这不构成不存在性证明；还须扩大引用链检索并检验这个差别是否实际有用。

## 最小实验必须足以否定自己

同一源/目标形象、相同种子、采样步、CFG、分辨率、帧数与加速设置，至少保留以下版本。先用一个已知失配样例做机制试验，再用原本正确的样例做破坏性检查；不要按结果挑选种子。

| 编号 | 操作 | 要回答的问题 |
|---|---|---|
| B0 | 原始 H3 | 现象是否可复现 |
| B1 | 原实验的参考 logit 增权 | 改善是否只是增加条件强度 |
| B2 | 对应物理时刻的硬 mask | 已有 Vidu/Wan 思路直接迁移是否已足够 |
| B3 | 普通 soft 时间 bias，普通 softmax | 软路由是否已足够，不需要 mass 约束 |
| B4 | 同样 soft bias＋上述 mass 守恒 | 守恒是否改善动作和编辑保真之间的取舍 |
| B5 | B4 使用错误时间锚点（正负偏移/置乱） | 输出动作相位是否随因果干预可预测地变化 |

B2 应标为“借鉴已有机制的 H3 适配基线”，不能冒称官方 Wan/Vidu 模型结果。B1 也不能仅借 logit gain 就称完整 DIAL 复现；DIAL 还有 ISGM 与训练阶段。

评价先报告：未做时间形变对齐的 signed/absolute lag、关键事件 onset/peak/end、持续时间与动作幅度；同时报告身份/编辑执行、构图背景和画质、额外耗时。对于遮挡或骨架检测失败应记录置信度并保留人工检查。DTW 后的相似度只能作为辅助，不能用它消掉要研究的延迟再宣布成功。Sync-LoRA 的同步度量可借鉴，但大时间窗平滑会掩盖很短的动作；不能无条件照搬。

预先登记以下否定条件：

- B4 只赢 B0、未赢 B2/B3：只证明已知时间约束可能有用，不能证明新机制必要。
- B4 的时序指标通过保留原人物/衣服而变好：编辑能力倒退，不算任务成功。
- 只对挑中的一个 seed 有效、正常样例明显退化：不足以构成稳健校正方案。
- 错误时间锚点不产生可解释变化，或 attention 指标与视频误差无关联：尚不能用 attention 时间错配解释生成延迟。
- 过强对角化导致暂停、重复帧或过度平滑：说明动作取舍失败，不是“更一致”。

一个有价值的正结果应是：在相同预算下，B4 相对 B2/B3 带来可重复的 lag 减少，又不牺牲编辑目标；错锚点干预方向符合预测；层/头/去噪阶段日志支持而非替代最终视频证据。之后才值得做自适应启停或局部定位。没有该证据前，不建议给方法起名字或宣称已得到架构创新。

## 检索边界与实现核实等级

本轮检索覆盖论文标题、arXiv 全文、作者项目、官方 GitHub；进一步查找 frame-aligned attention、same-frame reference attention、temporal RoPE reset、motion timing preservation、time correspondence、temporal attention mask、attention mass/renormalization 等组合。直接阅读了主要全文方法；TempoControl、VideoCoF、Wan-Animate-2 的关键实际代码逐项核对。Sync-LoRA、Vidu S 的公开仓库只核对当前文件树；其余代码链接若未逐函数检查，均已注明。

Reenact Anything 本轮仅核对摘要和作者项目，未作完整实现判断。未定位某代码不等于代码不存在。检索范围未穷尽全部 motion transfer、轨迹控制、图像编辑、多模态注意力理论；特别是 mass-preserving reweighting 的跨领域先例仍可进一步追查。此文只能排除若干过宽的新颖性宣称，不能签发“无撞题证明”。
