# 动作 phase / shape 区分与条件性时序修正：有界查重

2026-10-18；5 个直接相关 primary 来源的方法正文核对。未改模型、未跑 GPU。现有 R64/R71 继续原冻结实验。

**当前核对未找到完整覆盖“reference 与本次 x0 的单调配准→分开时间可解释部分与剩余姿态差→仅形状差可接受时修正→由 reference 的 VAE 往返误差校准容差”这一整套流程的论文。这个结果只覆盖本次查阅范围。** 单调配准、phase/amplitude 分解和误差门控都已有长期算法基础；组合尚待核对及验证，不能直接视为架构创新。

## 最接近的 5 项

1. **ReTime / Semantic Progress Function，§3.2、§4.1，Eq.7–8。** 先生成完整视频并估计单调语义进度 S，再令 τk=S⁻¹(k/(T−1))，将 τk 用作 temporal RoPE 的位置，并可再生成、再估计。这是无需训练、由观察结果决定时间重参数化的直接先例。所核方法使用整片语义进度及目标速度，不是 reference 与当前去噪 x0 的人体对应，也没有按配准后的姿态残差决定是否许可修正。

   [原论文](https://arxiv.org/html/2604.22554v1#S4.SS1)。已固定代码的逐步 schedule 审查见 R64consumer/audit/reference_phase_rope_review；不能把固定 schedule 写成逐步 x0 反馈。

2. **FlowMotion，§3.2–3.4，Eq.3–5。** 由 source 与 target 的速度预测得到 clean latent；优化同位置的 latent 误差与帧间差分误差：L=α‖x̂0src−x̂0‖²+β‖Δx̂0src−Δx̂0‖²。它直接重合于“在推理中比较 source/current prediction 并引导动作”的总路线。所核公式没有求单调 φ，也没有将配准剩余误差作为时序修正许可条件。其差分目标同时受到时差、姿态幅度与外观的影响。

   [原论文](https://arxiv.org/html/2603.06289v2#S3.SS3)。

3. **Spectral Motion Alignment，§3.2–3.4，Eq.17–18。** 对 motion vector 的空间 2D FFT 分别匹配 amplitude 与 phase spectrum，并增加时间 wavelet 对齐；目标包含对模型参数 θ 的优化。这里的 phase 是二维空间傅里叶相位，不能直接等同“动作何时发生”的时间位移。这是 motion representation 分解的相关先例，所核方法没有 reference/current x0 的单调时间配准及条件性 retiming 门。

   [原论文](https://arxiv.org/html/2403.15249v2#S3.SS3)。

4. **Video alignment using unsupervised learning of local and global features，§2.3，Eq.8。** 用人体姿态与局部/全局视觉特征构造帧间距离，以 DDTW 求单调路径。离对角线超过 margin 的匹配代价变为 D′ij=Dij[1+λ(d−m)]。无需重新训练的动作视频配准已经明确存在；它要求相似动作，并非视频生成中判断不同动作是否值得引导的机制。单靠低 DTW cost 仍会产生不同动作的局部伪匹配。

   [原论文](https://arxiv.org/html/2304.06841v1)。

5. **MimicMotion，§3.4 与 Fig.7。** 通过 keypoint/limb 的置信度缩放姿态图亮度，降低遮挡、错误关键点对动作生成的影响，并训练 PoseNet/视频模型。可见性影响指导强度已有直接生成先例；该方法未提供“reference VAE 往返误差→动作相位容差”的自校准机制。检测 confidence 不能直接作为经过校准的坐标噪声方差。

   [原论文](https://arxiv.org/html/2406.19680v2#S3.SS4)。

## 候选到底要多证明什么

下面是明确概念用的通用 registration 写法，并非已经实现或声称新公式。r(t) 为 reference 的可见部位特征，gσ(t) 为 D(x̂0σ) 上同类特征，Γ 是预先限制的单调时间映射族。

φ*=argminφ∈Γ [Σt w(t)‖gσ(t)−r(φ(t))‖² / Σt w(t) + λR(φ)]。

在**相同有效支撑**上计算 Eid（φ=id）与 Eφ（φ=φ*）。Eid−Eφ 表示该映射能解释多少观测误差；Eφ 是配准后仍存在的差异。另报告 φ−id 的实际时间改变量、路径约束和可见覆盖。

这不是严格的正交或因果误差分解：shape、视角、检测偏差、主体比例与相位彼此耦合；优化后误差较小也可能只是过拟合。若 φ 使用更多的配准自由度，必须用固定复杂度/速度约束及额外支持证据检验，不能把训练内下降直接当可解释性。更不能为每条输出调一个方便通过的阈值。

若 g(t)=r(t−d)，估计的对应是 φ(t)=t−d。真正修复 generated 视频应按 inverse mapping g(φ⁻¹(t)) 对齐。把参考中当前已匹配的 t−d 内容直接强化，可能继续保留延后。这一点与前一份 RoPE 审查一致。

## VAE self-calibration 的边界

可以先比较 r=P(source) 和 rV=P(D(E(source)))，得到同一输入经实际 codec 后的观测偏差。它能揭示当前 VAE/pose 管线的部分分辨率和压缩误差，但没有自动覆盖：

- 换身份后的 detector 偏差、身体比例差和遮挡变化；
- 早期 x0 的分布与最终视频差异；
- 单调配准本身的多解性、静态片段不可辨识性；
- 多次去噪观察之间的相关性。

因此参考往返误差只能作为一个受控校准输入。五篇所核正文中没有发现上述整套 self-calibration 门；后续还需核对 uncertainty-aware registration / selective guidance 的直接实现。不能由没有检索到来承诺不存在先例。

## 最小可否决验证（仅建议，未执行）

复用已冻结 R61/R62 的 source pose 与当前轨迹，不增加模型下载。先登记固定变换：零时移、已知±4/±8帧、纯幅度/姿态变化、固定跨动作配对、置信缺口。所有变体采用同一物理支持处理，记录实际越界和 UNKNOWN。

- 已知时移应得到正确方向；零时移应保持 identity。
- 纯幅度变化、跨动作配对应保留较高残差或拒绝时序修正；不能借灵活 φ 把它们全部解释成时差。
- 同一动作的小幅姿态差仍需保留，避免阈值只会全部拒绝。
- 在独立 source-only 校准集确定参数后，才到旧输出轨迹上审计；重放不证明在线修正后的收益。
- VAE roundtrip 如需实际 codec/pose 调用，另立工程诊断；本轮只查文献和复用既有证据。

优先研究价值是“什么时候单调时间修正有资格解释当前误差，以及拒绝时如何保持原生成”的可检验规则。是否形成独立贡献取决于公式、校准和反例结果，而不是单独给 DTW 或阈值更换名称。

## 既有 H3 执行记录

已重新读取 2026-10-16 的 next_computation_path_candidates.txt。该文档记录：phase −12 全程仅单侧改善到 +3 帧，晚起未充分修复；offset +4 的形状/覆盖不合格，−4 未明显修复，完整预登记 specificity 门失败。本次依据为已归档总结，未重新运行或逐项重算其原始张量。当前 reference-RoPE/phase 候选须继承这些失败事实；上面的 phase/shape 门只是观察侧理论候选，尚无在线实现授权。
