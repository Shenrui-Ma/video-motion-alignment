# Feature guidance 实现审查

日期：2026-10-23。审查者：独立只读实现／数学审查。审查版本：主模式已更新为 `dynamic_strength_dof`、已复制 controller、nodes 已建立的版本。未改生产实现，未启动 GPU；CPU 测试由数学实现协作者执行，本审查不重复其工作。

## 结论

当前默认 DOF 配置未发现阻挡实验的 tensor shape、reference mass 或执行因果错误。新增路径在一次原有 DiT forward 内完成，每个 block 使用该 block 已有 Q/K/V 与两类邻帧 probe attention，控制该 block 自己的修正。原有 50-block wrapper 的顺序校验和 finish-forward 边界得到保留。

发现一个直接调用 API 时的配置一致性问题，另有一项 audit 参数解释建议。主线程随后已修复两项，并经本审查者刷新源码确认；下文保留问题和修复依据。两者均不改变默认 `dynamic_strength_dof + centered` 实验的数值结果。

## 发现与建议

### 已修复 P2：低层配置可记录 secants，实际却运行 centered

位置：[attention.py](/workspace/research-user/DevProjects/video-motion-alignment/execution-20261022/innovation/feature_guidance/attention.py:20)，`FeatureConfig.__post_init__` 与 `feature_attention` 的 DOF 分支。

`FeatureConfig(mode='dynamic_strength_dof', basis='secants')` 当前通过类级校验。`nodes.py` 会拒绝这个组合，但直接使用 `attach`／`feature_attention` 时，DOF 函数固定用 centered，而 audit 的 `feature_config` 记录 secants。这可能污染消融配置标签。

最小修正：把 DOF 必须使用 centered 的组合校验同时放在 `FeatureConfig.__post_init__`。最小测试：直接构造该组合必须抛 ValueError，不依赖 Node.apply。

复核：类级组合校验现已加入。

### 已修复 P3：DOF 模式的 effective collateral 应单独记入 audit

位置：[prototype/controller.py](/workspace/research-user/DevProjects/video-motion-alignment/execution-20261022/innovation/adaptive_strength_20261023/prototype/controller.py:140)。

DOF 模式使用 `c=(1-alpha_prior)/alpha_prior`；默认 prior=.25 时 c=3。节点仍接受 `collateral=1` 并存进配置，但此参数只作用于原始 `dynamic_strength`。数值实现正确，建议在 DOF 返回结果里加 `effective_collateral`，或明确该 mode 下 config.collateral 未使用。最小测试：prior=.25 时有效值为 3；更改 legacy collateral 不改变 DOF 结果。

复核：State audit 已加入 `effective_collateral` 和 `collateral_parameter_used=False`。

## 已核对的正确行为

### Probe batch 与同 query 原则

`qe` 为 `[1,H,T*S,D]`。按每个 frame 相同空间 ids 选择后 reshape 成 `[H,T,P,D]`，再 permute 为 Flash 需要的 `[T,H,P,D]`；这里 T 被用作独立 batch 维，不是拼到 head 维。

参考 K/V 被重排为 `[T_ref,H,S,D]`，`bins=arange(lo,hi)` 使用完整参考视频的绝对 bin 索引。前后邻居读取分别取 `bins-1`、`bins+1`，两次调用均复用完全相同的 `probeq`。因此测量的是同一个 query 对不同参考物理时刻的条件读出，未把 Q 同时移动到邻帧。部分事件窗口也能访问事件窗口外、完整参考内的相邻 bin。

最少 Flash attention 调用数：inactive 为 1；fixed 为 full/ref/same 共 3；动态或 heads 为再加两类邻帧，共 5。radius=0 时 `_aligned_attention` 的所有同帧组长度相同，能够批处理。

### 边界定义

首尾 bin 使用 clamp：首 bin 的 previous 为 same-bin 条件读出，末 bin 的 following 为 same-bin 条件读出。因此端点是单侧差分；“切向不包含 S_t”只对内部 bins 成立。单 bin 参考时 previous=following，切向为零，控制器回退 .25。这是明确的边界条件，不是 shape 错误。

H3 latent bin 的物理跨度不完全相同。当前 rank-one 投影对切向乘一个正的时间间隔倒数不敏感，但各 bin 在 block 汇总中按 probe 数等权；它不是按像素帧持续时间加权的平均。当前实验记录应称 latent-bin 内部统计。

### Mass 与修改范围

`log_mass=ref_lse.float()-full_lse[...,qa:qb].float()`，再 clamp(max=0) 和 exp，吻合冻结 FP32 LSE 路径。正式 fp16/bf16 推理下，`same-ref` 与质量乘法、alpha 应用均在 FP32，最后 cast 回 full dtype。

只改 `full[:,:,qa:qb]`，文本、参考图、参考视频、音频以及事件窗外目标 token 的当前层输出保持原生 full attention。这里是当前 invocation 的代数不变性，不承诺后续层不受变化影响。

### DOF 强度公式

主函数采用 rank-one 时间切向能量 `E_T`、其余 `E_N/(D-1)`、整体 `E_D/D`，并使用 `c=(1-a0)/a0`。在等每维方差假设下，闭式解回到 a0=.25；与未做维数校准时在 D=128 的各向同性输入上自然降到约 .129 的现象有明确区别。

当前 centered 分支已去掉 ridge 缩减，非退化时是标准 rank-one 正交投影；secants 分支仍是 ridge 版本，不能继承精确正交分解声明。能量控制、caps、低信号回退都在 GPU 张量上实现，没有在每层用 `.item()` 进行强制同步。

### Head 预算口径

`head_energy=correction.square().sum((0,2,3))` 使用所有选中目标 queries 和通道，不只是 probes。`heads_budget_strength` 接收这份完整能量，仅以 probes 估计效用。预算因此严格针对 attention head 输出拼接之前的 `sum_h alpha_h²||D_h||²`。

audit 已写 `before head merge`，口径正确。这个数不包含 W_o 投影与不同 heads 的交叉项；不应改写成“相同最终 residual 能量”。

### 50-block 执行与 audit

`Block` 继承冻结 `EventBlockPatch`，保留 block 顺序、每块恰好一次 attention override、CFG/并行交错拒绝、采样 schedule 一致性检查。所有 50 个 blocks 均安装 wrapper；未选中的 blocks 原生读出，但仍计入完整 forward。

feature records 先累积，只有第 50 个 block 成功完成时才调用 `finish_forward`，随后调用父类 finish 更新 completed_forward_calls 并落盘。控制器使用当前 block 的统计，没有读取未来 block 数据；未额外调用完整 DiT 或中间 VAE。

当前 `step_*` 本质上限制 forward_index。对现有单 forward/采样步的 Euler 配置二者一致；若以后换成每采样步多次模型评估的求解器，应该重新定义或显式标明按 NFE 调度。

`controller_host_dispatch_seconds` 正确命名为 host dispatch；CUDA 异步执行时它不是 GPU 运算耗时。新增 kernel 的实际成本应以统一 wall time 或 CUDA event 测量。

## 建议补齐的 CPU 测试

这些建议已发送给负责 `test_feature_attention.py` 的协作者，不在本审查中重复实现。

1. H>1、T>1、P>1 的带索引哨兵输入：batch probe attention 对照显式逐 time/head 循环，排除 head/time 重排混淆。
2. lo>0、hi<T_ref 的部分事件区间：Q 固定，邻 K/V 来自完整参考的正确绝对 bin；事件区间外输出逐元素不变。
3. 首尾 bin、单 bin、S<probes：验证单侧差分、低信号回退及 probe ids 不重复。
4. fixed=.25 对照冻结 mass_preserve：使用相同 FP32 LSE 合同；同时验证 inactive/alpha0 只调用 full attention。
5. heads_budget 对完整修正张量计算预算，而不是仅 probes 预算；all-constant、mixed-valid、saturated heads 均检查。
6. 完整跑通 50 个 fake blocks：completed_forward_calls 只增加一次、records 恰为 50、routed count 符合选择区间；中间块抛异常不能增加 completed_forward。
7. 直接 FeatureConfig 的 DOF/secants 非法组合，以及 DOF effective collateral 的审计值。

审查限制：本报告基于当前源码与数学核对；GPU Flash 数值、实际 H3 接口、显存、速度和最终视频效果由后续单例验证覆盖。没有为了完成本审查改动主文件或占用服务器。
