# 按参考时间方向选择 Attention 修正：机制与最小实验

日期：2026-10-22。状态：设计提案，尚未运行。主十组与扩展队列继续使用冻结实现；本文仅描述独立实验分支。

## 1. 先检验哪一个问题

全程弱引导在当前区间对照中表现较好，下一步优先检验：能否保留其时间对齐收益，同时减少与动作时间无关的外观、构图变化。最小改动是为每个 Attention head 的既有修正分配不同强度，依据修正是否沿参考序列的时间变化方向决定。

优先做连续强度控制。Head 和 layer 的硬删除会同时改变信息流、修正量和计算量，放到第二阶段。

## 2. 现有实现的准确位置

H3 DiT 每个 block 的联合 Attention 已得到 Q、K、V 后，`TemporalAttentionOverride` 替换 Attention 运算。`route_attention` 返回合并 heads 的 Attention 输出，随后继续执行原 block 的输出映射、残差和 FFN。

针对一个输出视频 query q、head h、block l，设：

- O：该 query 对完整多模态序列的原 Attention 输出。
- R：该 query 只对参考视频全部 keys 做 softmax 后的输出。
- S_t：该 query 只对参考视频相同时间 bin t 的 keys 做 softmax 后的输出。
- m：完整 Attention 中分配给参考视频所有 keys 的概率之和。

现有计算为：

$$m=\exp\big(\operatorname{LSE}(QK_{ref}^{\top}/\sqrt d)-\operatorname{LSE}(QK_{all}^{\top}/\sqrt d)\big),$$
$$D=m(S_t-R),\qquad O'=O+\alpha D.$$

`m` 是每个 query、每个 head 的标量。α=1 时，参考视频部分全部改为同时间 bin 的特征；其他模态的原 Attention 输出贡献保留。0<α<1 时，参考视频内部做两种分布的凸组合。它修改的是 Attention 输出，未给 logits 增加参考权重。

主实现代码 `core.py:235–249` 对应 R、m、S_t 和 D。`schedule.py` 只决定在哪些去噪步骤调用该修正：early 为第1–9步、fixed 为第7–15步、late 为第12–20步、split 为第1–4与16–20步、global_weak 覆盖20步。

## 3. 最小新分支：参考时间方向控制修正强度

### 3.1 从同一次 Attention 得到时间方向

保持输出 query q 不变，分别用参考视频相邻时间 bin 的 K/V 得到 S_(t-1)、S_t、S_(t+1)。这些都是同一个 block、同一个 head 的特征，因此位于同一向量空间。

$$T_t=\frac{S_{t+1}-S_{t-1}}{2}.$$

两端采用单边差分；不足两个有效 bin 时停用该分支。T 表示“参考时间前进一个 bin，Attention 条件输出朝哪个方向变化”。它是特征的有限差分，不是 flow-matching velocity，也不是光流。

同时对每个时间 bin 取固定少量空间 query，计算其对参考视频不同时间 bin 的概率 p(k)：

$$p(k)=\frac{\sum_{j\in bin(k)}\exp(qk_j/\sqrt d)}{\sum_{j\in ref}\exp(qk_j/\sqrt d)},\quad \mu=\sum_k k\,p(k),\quad e=t-\mu.$$

e 是参考时间关注偏差；e>0 表示当前更偏向较早的参考内容，候选修正朝参考序列后移。该量需要用实验检验其与成片动作偏移的关系。它不是已经验证过的动作检测器。

为控制开销：每个 bin、每个 head 固定4个空间 query，分块计算其参考 logits；仅保留 p(k) 或均值。不得创建完整的输出视频×参考视频 Attention 矩阵。全片规则一致，采样点在实验前固定。

### 3.2 根据方向决定每个 head 的强度

构造需要的时间修正方向 U=eT。对原修正 D 计算正向一致度：

$$g=\max\left(0,\frac{\langle D,U\rangle}{\|D\|\|U\|+\epsilon}\right)^2,\qquad O'=O+\alpha_0gD.$$

α0 取当前全程弱引导的实际登记值，所有方法共用；g∈[0,1]。每个 head、时间 bin 单独计算，可先对固定空间采样的值取均值，广播到该 bin；下一阶段再测空间细分。

直观解释：如果既有修正主要沿“把参考动作往所需时间方向推进”的方向，就接近原弱引导；如果修正主要改变其他特征，强度下降。保持 D 的原方向、只改变非负系数，仍保留原先参考总概率 m 的代数性质。

同层各 head 的 g 不同，使修改集中到有方向支持的 heads。层级第一版仅记录该层修正比例，不按预选层号裁掉整层。若后续发现部分层持续 g≈0，再做独立 layer-selection 对照；即时跳过这些层可使用上一步的统计，但必须另外检验其滞后误差。

### 3.3 仅作为稳定措施的修正幅度上限

若需要防止少量 query 的修正过大，可令：

$$c=\min\left(1,\frac{\rho\operatorname{RMS}(O)}{\operatorname{RMS}(\alpha_0gD)+\epsilon}\right),\qquad O'=O+c\alpha_0gD.$$

ρ 应先根据现有全程弱引导的实际修正比例统计确定，预先冻结后再评测。首轮关闭该上限，先隔离方向选择的效果；预算归一化本身属于已有常用控制工具。

## 4. 与已有工作的关系

- **HALO，Controlling Motion Transfer in Diffusion Transformers via Attention Heads（2026）**：依据 Attention 模式识别运动 heads，用跨帧位移图引导 latent 优化，并按熵选择结构 heads 注入参考特征。它已经覆盖“选择运动 heads 做 training-free 动作迁移”的总思路。本提案要检验的具体增量是：用参考时间的反事实有限差分，决定已有同时间修正对当前 head 的方向适用性，再连续调节修正强度。[原文 §3–4](https://arxiv.org/html/2607.11081v1)
- **HeadRouter（2024）**：比较重建与编辑分支的 head 语义敏感性，自适应选择并增强 heads，另做图像／文本 token refinement。因此“动态选 head”需要引用它；本提案使用参考时间改变造成的特征方向，未增设重建分支。[原文 §4.1](https://arxiv.org/html/2411.15034v1)
- **HeadHunter / SoftPAG（2025）**：按目标迭代搜索 heads，并连续地把选中 head 的 Attention 朝单位矩阵插值，用扰动模型构造引导。选择 heads、设置连续强度已有明确先例。[作者主页](https://cvlab-kaist.github.io/HeadHunter/)；[原文](https://arxiv.org/abs/2506.10978)
- **APG（2024/2025）**：将 CFG 差向量按条件预测分解为平行和垂直分量，再缩放与加动量。本提案的方向来自参考时间有限差分，作用于 DiT 内部参考 Attention 修正；投影、余弦选择与范数约束这些数学工具仍应归入共同基础。[原文 §4](https://arxiv.org/html/2410.02416v1)
- **DIAL（2026）**：用主体 grounding map 在输出 query→参考 keys 的 logits 上加偏置，改变参考影响强度。现有质量保持修正和本提案都在参考子组的输出上操作；这里的新问题是修正方向的可用性与选择。[原文 §3.3](https://arxiv.org/html/2609.11507v1)

截至本次主文检索，最接近的是 HALO 与 HeadRouter。拟投稿贡献应落在“参考时间有限差分对修正适用性的判别、及其带来的可复现编辑／时间对齐改善”；目前状态为待验证提案。

## 5. 最小实验与判据

先在已有的机舱角色替换、饮酒加眼镜、书本改蓝三项上运行；用主批次相同的简单提示词、seed和采样配置。若收益成立，再在预先固定的扩展样本上验证。

| 方法 | 用途 |
|---|---|
| 普通编辑 | 任务与动作保持对照 |
| 冻结的全程弱引导 | 当前主要比较对象 |
| 全程弱引导＋方向强度 g | 唯一新增方法 |
| 全程统一缩小 α，匹配新增方法的累计修正 RMS | 检验收益是否仅来自整体更弱 |
| 打乱各 head 的 g，保持每层平均值与分布 | 检验方向与 head 的对应是否有作用 |

后两项只在前三项出现可测改善后执行，避免无差别扩张算力。

必须记录：每步采样时间；每层／head 的 g 分布；均值 e；累计修正 RMS；选中比例；新增邻 bin Attention 的调用次数与耗时。最终成片计算当前统一指标。动作时间误差沿用预先确定的事件规则；MF、编辑完成与时间偏移分别列出。

继续条件：至少两个已知问题样例的时间误差改善或维持，同时编辑遵循/内容保持指标改善；扩展集再检验一致性。若 g 无法优于等修正量的统一减弱，归为强度调参；若打乱 head 选择效果相同，方向信号没有得到支持；若时间对齐明显退化，回到全程弱引导并检查 e 与动作偏移的关系。

新增条件输出开销超过全程弱引导采样时间的15%时，先记录并减少 probe 频率，不因此增加额外完整前向。首轮只测推理开销，暂不开展专门效率优化。

## 6. 最可能失败的位置

1. 同一姿态重复出现，p(k) 的均值落在两次动作之间，e 失去可解释性。需同时记录分布的多峰程度，多峰判别作为后续单独模块；已确认低信号时返回 UNKNOWN，跳过本步反馈修正。
2. T 混入相机移动、光照变化和遮挡。方向一致可能只是背景匹配；用人物与动物、固定与运动相机的扩展样本分别报告。
3. 小动作被4点空间采样漏掉。若出现这种模式，再扩大为固定网格，比较成本和覆盖率，避免只针对单条结果挑坐标。
4. 在近似线性的参考特征轨迹中，D 本身就近似 eT，g 会普遍接近1；此时新模块退化为已有弱引导，算法设计需转向保护编辑语义或跨输出时刻的参考覆盖约束。
5. 相邻时间 bin 有不同物体时，有限差分不连续；若T范数过低或输入非有限，记录原因并返回 UNKNOWN，跳过本步反馈修正。数值epsilon只用于稳定除法，不充当动作阈值。

## 7. 实现边界

独立节点/文件提供 `direction_gated` 模式。冻结的主队列继续导入原 `core.py` 与 `schedule.py`。新分支复用 `flash_attention_lse`、`_aligned_attention` 和布局划分，只在 `correction` 与 `changed` 之间插入 g，额外取 time_offset=-1/+1 的局部条件输出。参考图片、文本、音频以及输出视频之间的原 Attention 维持原函数结果。

没有新的模型服务，没有训练，没有逐步VAE解码，没有DWPose，也没有第二次完整DiT前向。新kernel次数与工作内存仍须实测。

代码依据与校验：

- /Users/researcher/DevProjects/video-motion-alignment/execution-20261022/inference/package/custom_nodes/H3Study/core.py；SHA256 `2dba7d615092491ad5b696b81ae2c0d41e9cae3760046aeefbdf33ad0d543691`。
- /Users/researcher/DevProjects/video-motion-alignment/execution-20261022/inference/package/custom_nodes/H3Study/schedule.py；SHA256 `8cc187efc98c00280c321368c7471066970ae2aa633f52dd885160dc4190ae89`。

## 8. CPU原型与验证

`direction_gate.py` 是纯Python参考实现，仅表达单个head／bin的向量代数。`test_direction_gate.py` 共8项测试通过：正向／反向时间路由、方向冲突、正交变化、低信号跳过、连续权重、参考总概率保持、单边差分和等修正能量系数。

原型暂定阈值为：内部路由重心偏差至少0.25bin、参考时间分布浓度至少0.15（1减归一化熵）、时间方向范数至少1e-6。前两项是待实验校准的超参数；最后一项是特征数值保护。它们尚无成片性能依据，正式最小实验前应冻结。

UNKNOWN对应反馈修正系数0。原型尚未加入多峰判别、空间tile、GPU向量化、层跳过或自动归一化预算；主十组代码和调度未改动。

等能量函数先在同一组记录的D上求统一α，使累计平方修正量相同；用该α重新生成后轨迹可能改变，需要重新统计实际修正量。在不同head间直接比较原始向量余弦会混淆不同通道空间，原型所有方向比较均限制在同一head内。
