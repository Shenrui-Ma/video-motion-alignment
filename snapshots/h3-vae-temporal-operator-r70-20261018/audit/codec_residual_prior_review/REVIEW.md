# VAE 往返残差补偿：有界查重

审查日期：2026-10-18。只读论文核对；未实现算子、未运行 GPU，现行 R64/R71 实验继续。

**结论：这两个候选可以作为 H3 的工程诊断，但“decode→变换→encode，再加回 VAE 残差”和 identity 下恢复原 latent 已有直接先例，单独提出该公式不足以作为新的架构贡献。** LookingGlass 给出空间变换后的残差补偿；LongE2V 已将重编码加残差用于视频时间翻转。后续若继续，需要验证 H3 时间压缩下如何运输残差、怎样确定可靠的物理时间对应，以及真实编辑任务中的净收益。

## 候选的确切数学

令 E、D 为同一 H3 VAE 的编码和解码，Rφ 为 RGB 帧上的物理时间重采样，Lφ 为 latent 上预定义的对应运输；ε(z)=z−E(D(z))。

- A：Tφ(z)=E(RφD(z))+ε(z)=z+[E(RφD(z))−E(D(z))]。
- B：Tφ(z)=E(RφD(z))+Lφ ε(z)。

当 φ=id 且 Lid=I，两个式子在代数上均恢复 z。实际实现还需同一归一化、确定性编码、相同裁剪/量化以及浮点误差检查；不能直接承诺逐位一致。这个 identity 性质只是实现自检。

## 最直接的已有方法

**LookingGlass，CVPR 2025，§4.1，Eq.7–8。** 对当前预测 clean latent，先在像素空间做视图变换与融合，再重编码；另计算 z−E(D(z))，按视图映射运输后加回。论文明确讨论 VAE 不具备变换等变性、早期预测的重编码失真，并明确 identity 单视图下恢复 z。其目标是图像多视图幻象。B 与其“运输 codec residual”的结构直接相近；A 是保留原坐标残差的更简化选择。不能把论文多视图公式机械地令 N=1 就宣称完全等于任意非恒等 φ，因为该条件会同时消掉往返视图映射。

[arXiv §4.1](https://arxiv.org/html/2504.08902v1#S4.SS1)；[CVPR 正式论文](https://openaccess.thecvf.com/content/CVPR2025/html/Chang_LookingGlass_Generative_Anamorphoses_via_Laplacian_Pyramid_Warping_CVPR_2025_paper.html)。

**LongE2V，§3.3，Fig.5、Eq.3–6。** 指出 3D VAE 的 latent 时间翻转与像素时间翻转后编码不等价；对预测 clean 视频做 decode→像素时间翻转→encode，计算两个方向各自的往返残差，再跨方向注入。论文直接引用 LookingGlass。这里已经出现“视频时间变换、重编码、codec residual correction”的组合。与候选的区别是双方向/时间翻转和跨分支残差，候选拟用单个 H3 当前预测及一般单调 φ。LongE2V 的主体模型经过训练，不能将整套系统写成 training-free。

[arXiv §3.3](https://arxiv.org/html/2607.08770v1#S3.SS3)；[作者项目](https://cdfan0627.github.io/LongE2V-page/)；[作者代码](https://github.com/cdfan0627/LongE2V)。本次确切公式依据论文，未声称核验其代码实现。

## 用户指定的其他近邻

- **PixelMan**：Method 的 Eq.1–2、6 是像素操作的编码 anchor 加上两个去噪分支预测之差，用于编辑、融合和补洞。残差来自 denoiser 分支；已核方法部分未使用 z−E(D(z)) 的 codec 残差定义。[论文](https://arxiv.org/html/2412.14283v2#S3)。
- **ReNoise**：§3.1–3.2 的迭代 inversion 与 noise correction 修正反演/采样轨迹，所核方法不等同于 VAE 往返残差补偿。[论文](https://arxiv.org/html/2403.14602v1#S3)。
- **LatentWarp**：§4 用光流运输前帧 latent 并根据遮挡/光度残差控制当前帧融合；其 residual mask 指像素帧的 warp 差异，不能与 codec residual 混称。[论文](https://arxiv.org/html/2311.00353v1#S4)。

这里的范围是上述论文方法正文及直接新增的两篇先例；没有据此声称所有文献中不存在其他等价式。

## 对 H3 候选的具体风险

1. A 把原时间坐标上的 ε 加到新时间坐标，可能重新注入旧姿态和重影。ε 可能含动作信息，不能假定它只含颜色或纹理。
2. B 需要运输 ε。R70 已观察整体 latent 时间插值不等价于物理 retiming；小残差上的同样操作是否可用仍要实测。不能把 Lφ 的适用性由 identity 推出。
3. D 非线性，所以 D(Tφ(z)) 没有自动等于 Rφ(D(z)) 的保证。后续去噪还可能撤销或放大一次修正。
4. 对当前 clean endpoint 做上述操作，再由 v′=(zσ−Tφ(x0))/σ 改 Euler 方向，属于 endpoint 约束的一般换算。σ 很小时需预先定义有限、稳定的介入范围。
5. 一次操作含解码以及至少两个编码输入。沿用已实际测量的 encoder/decoder 配置，单独记录新增耗时/显存，不能把只看最终图像的后处理代价当作在线代价。

## 最小可否决诊断建议

复用已冻结 R70 的同一实际 z、同一 φ 和物理有效帧定义；保留全部已测时刻与失败样例，不按视觉结果挑参数。比较原 z、latent warp、像素 warp 后编码、A、B，以及直接 RGB warp 的可视目标。

- identity：检查 latent 相对/绝对误差、解码误差；若没有达到预先写明的数值容差，先停止实现层的效果比较。
- 非 identity：在相同物理时间上比较姿态、重影、身份/外观，特别检查 17 帧分组边界；独立保留 RGB warp 的后处理强对照。
- 若 A/B 没有稳定降低“重编码导致的额外漂移”，或把原来可见动作拖回旧时刻，就停在失败诊断，不进入完整采样。
- 只有可建立同一动作的时间对应时，才解释为动作时序纠正；输入/输出动作内容不同的 IVEBench 案例不能靠重采样补成正确动作。

可能继续研究的部分是 H3 的时间坐标与残差运输规则，以及与可靠动作对应结合后的因果证据。应将 LookingGlass/LongE2V 的残差补偿明确作为借鉴或对照，不以改名或 identity 性质主张独立创新。
