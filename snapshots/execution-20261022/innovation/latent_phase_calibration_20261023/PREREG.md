# Latent 相位读出：预先冻结的 CPU 诊断

2026-10-23；在读取任何 cross-identity 数值之前冻结。

目的：检验不经过 RGB/VAE 的低成本观测能否识别已知位移，并初步区分旧 native 的明显动作延迟与固定 .25 接近对齐的结果。不是新方法评测，不调整已运行方法。

样例固定为 short_0358 饮酒、long_0059 手帕。每例 source、native、global_weak；预测取零基 step9 与 sampler_final。source 与生成均用已缓存 FP32 video latent，只在 CPU 读取，禁止 CUDA、VAE、姿态模型和 DiT。源／生成形状、prompt、seed、文件证据见相邻 LATENT_DIAGNOSTIC_INPUTS.md。

读出参数一次冻结：

- 仅保留完整覆盖真实有效帧的 latent bin。按 frame_spans=(1,4,4,4,4) 重复计算帧中心，24fps。
- 每帧 latent 用固定4×4自适应平均池化；在 float64 特征上做时间中心差分。时间端点排除。原始 padding 不裁成不同大小；所有方法使用同一空间网格。
- 参考侧中心差分的逐通道 RMS（跨时间、网格）作尺度；最小尺度为非零通道 RMS 中位数的0.1倍，绝对下限1e-8。参考和目标用同一尺度。
- 每个时间点的24×4×4向量 L2 归一化，cosine代价 1−cos。能量低于1e-10标无信息，不当0时差。
- 全时间代价矩阵均保存；匹配带宽为±6 bin。单调路径相邻目标点的参考索引增量允许0/1/2，偏离1的代价固定0.05；起止自由但须在带宽内。反向再匹配一次。
- 歧义按所选路径点与带内相距至少2 bin的最佳备选代价差判断；差<0.02标 ambiguous（备选更优时差为负，同样拒绝）。路径点余弦≤0、前后循环误差>1bin也不纳入“可信”摘要，但保存所有原始路径及原因。歧义不是零误差。
- 已知移位 δ=−2/−1/0/+1/+2，非循环、无填充；对 source、每份生成分别自比较。用逻辑目标bin与实际来源bin构造真值，比较匹配索引误差和物理秒误差。校准成功门槛：至少90%有效位置匹配误差≤0.5bin，非零移位的可信点偏移方向正确；可信覆盖率另报，不拿低覆盖冒充成功。
- 静态偏置控制：float64池化特征每通道加固定linspace(−5,5)，不改变时间差分。归一化描述子最大差≤1e-8、匹配路径相同视为通过。
- 两个阶段依次运行：先全部自移位与偏置，再原样计算source→native/weak。不依据cross-identity分数调整尺度、网格、带宽、阈值或窗口。

事件窗口已冻结：饮酒 bottle_lowered [14,18]、bottle_reaches_lips [37,40]、bottle_leaves_lips [80,84]；手帕窗口从旧 ANNOTATION.json 原样读取并写入 INPUTS.json。事件摘要使用所匹配 source bin 的帧覆盖区间与事件窗口有交集的路径点，若没有点则 missing，不外推。正偏移表示生成晚于参考。全局均值与事件摘要分开，因为前者可能被静态背景或无关运动主导。

保留所有结果、失败与歧义；自校准通过不意味着跨身份相位有效。native明确的9/10.5帧或16帧延迟为粗粒度外部检查；weak接近地板只检查明显误报，不要求亚bin一致。若算法只在自匹配通过、cross-identity与冻结事件矛盾，结论是本读出尚不适合作为动态控制收益标签，不重新调参凑结果。

执行入口：`CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python phase_calibration.py --inputs INPUTS.json --host-key 41 --out results_41.json`；.9使用 `--host-key 9`。输入原地读取，仅小结果JSON回传。记录脚本／prereg／输入manifest和实际tensor文件SHA、张量签名、CPU时间、全部曲线和矩阵。
