# 恒定 α = 0.25 的控制算子核对

结论：主十组原全程弱引导与新 `feature_anchor`、`feature_gain_field`、`feature_layer_budget` 在相同 Q/K/V、时间窗口和 α = 0.25 下，使用同一参考质量保持算子。现有 FP32 回归与新增 FP32/BF16/FP16 CPU 边界测试均逐值一致。当前六张新 pilot 图的像素帧窗口、去噪步、50 层范围也与各自原全程弱引导一致。

## 1. 原实验实际实现追溯

`manifest_preparation/catalog.json` 的十张全程弱引导图分为：

| 样例 | 实际节点 |
|---|---|
| short_0252、short_0358、long_0039、long_0059、short_0085、short_0274 | H3FixedSchedule |
| short_0343、short_0114、crouch__movie_man_4、long_0167 | H3StudySchedule |

前六条分别由其 runtime 指向的 `producer_seal` 查回实际部署源码。六份 `deploy_manifest.json` 的 SHA 与 runtime 一致，清单内 core/layout/schedule 的 SHA 与文件一致。六份旧 `core.py` 和 `layout.py` 也分别与新方法固定依赖完全一致：

- core：`2dba7d615092491ad5b696b81ae2c0d41e9cae3760046aeefbdf33ad0d543691`
- layout：`d71a0a34956c1c57e534f906df3dc954bc6b4ab02b33f78f0b0ba913e6acca08`

旧、新 schedule 的唯一代码差异是新版本增加 `fixed` 和 `native` 两个选项。`global_weak` 始终为 `range(20)`；`ScheduleState` 和块包装器逻辑相同。后四条直接使用这份冻结 H3Study。

全部十张图均为 `mass_preserve, alpha=.25, radius=0, time_offset=0`，作用于全部 20 步和 50 层。每个案例的有效帧末端从其图读取，没有改成 padded 视频末端。六张新 anchor/field/layer pilot 图分别沿用机舱 `[0,97]`、饮酒 `[0,104]` 的像素帧窗口。

完整逐文件 SHA、部署清单验证和图参数见 [source_evidence.json](source_evidence.json)。

## 2. 实际算子

针对生成视频中选定时间 bin 的 query，旧、新代码都计算：

\[
O=\operatorname{Attention}(Q,K_{\rm all},V_{\rm all}),\quad
R=\operatorname{Attention}(Q,K_{\rm ref},V_{\rm ref}),\quad
S_t=\operatorname{Attention}(Q_t,K_{{\rm ref},t},V_{{\rm ref},t}).
\]

\[
m=\exp\bigl(\min(0,\operatorname{LSE}_{\rm ref}-\operatorname{LSE}_{\rm all})\bigr),\qquad
O'_t=O_t+\alpha\,m_t(S_t-R_t).
\]

- `m` 是当前 head/query 的原注意力中，全部参考视频 token 的概率总和。LSE 相减和修正均按 FP32 精度处理生产使用的低精度输入。
- `R` 的 keys/values 是**完整参考视频段**，包含该段已有的 padded bins；它不是选定事件窗口，也不包含参考图片、文字或音频。新方法保持这一口径。
- `S_t` 使用同一个生成 query，读取参考视频相同时间 bin 的全部空间 token。`latent_lo` 参与索引，因此部分窗口不会从参考第零个 bin 重新计数。
- α = 0.25 时，参考内部的读出为 `0.75 R + 0.25 S_t`，参考质量 `m` 保持；α = 1 才完全换成同时间读出。
- 只改生成视频选定 query 行。文字、参考图、参考视频、参考音频、生成音频和窗口外生成视频的输出行保持原值。
- 修正位于 `optimized_attention` 的输出，随后进入原 H3 `out_proj`，再走原 DiT block 的 gate/residual。新方法没有另乘 W_o、跳过 W_o 或把修正移到其后。

新方法用相邻参考 bins 的两次小 query 探测估计控制量；这两次读数只用于算 α。首尾统计排除不会删掉这些 bin 的弱引导，field 首尾仍为 α = 0.25。

## 3. 已有测试证据复用

这些测试直接调用冻结 `core.route_attention` 与新函数，没有分别重写两边公式。本次不重复整套运行。

| 包 | 既有断言 | 已通过测试数 |
|---|---|---:|
| feature_anchor | `test_fixed_exact_frozen_oracle`：fixed 输出 `torch.equal` 旧算子；`test_first_anchor_step_exact_fixed_and_five_calls`：首个锚点步与 fixed 完全相同；独立 head/time/probe 循环核对 R/S/m；窗口外 query 完全保持 | 35 |
| feature_gain_field | 同名 fixed/首步/独立探测循环测试；`test_time_field_broadcast_and_full_resolution_energy_dense_oracle` 核对每 bin 广播及完整修正能量 | 43 |
| feature_layer_budget | `test_fixed_and_budget_prior_equal_frozen_oracle`：fixed 和 layer_budget 的请求 α=.25 均与旧算子 `torch.equal`；`.375` 同样精确对照；真实包装器前两步与旧算子相同 | 25 |

证据分别是 `feature_anchor/READY.json` 指向的 `prototype/anchor_test_result.json`，以及另两包各自的 `test_result.json`。本次重新核对所有被导入源码与其 READY 的 SHA，全部一致。

## 4. 新增缺口测试

[test_boundaries.py](test_boundaries.py) 仅补原测试未完整覆盖的边界；结果 [TEST_RESULTS.json](TEST_RESULTS.json) 为 **5/5 通过，0.084 秒**。

1. 调用真实旧 `validate_layout`，组合文字、参考图、参考音频、参考视频、生成音频、生成视频，验证部分帧范围映射到正确 bin 和 token 区间。
2. 对 FP32/BF16/FP16，各调用真实旧算子和三个新 fixed 路径，输出逐值相同；非目标行与原注意力逐值相同。
3. 用完整注意力概率直接求和校验 `m`，同时记录真实调用的 Q/K/V 切片，核对全参考 R、同 query 和同 bin S 的 batched 轴顺序。
4. 调用旧、新真实 override，确认有 mask 时均在执行注意力前拒绝，避免出现不同掩码语义。
5. 执行实际 H3 `Attention` 类的源 AST，仅把外部算子换成小型 CPU 依赖；捕获 `out_proj` 输入，确认正是各路由函数的结果，且四条路径的投影后结果也逐值相同。

本次为相同 CPU attention 后端下的算子与调用位置核对；没有重新生成视频、对比机器速度或改动线上包、模型、队列。生产 FP16/BF16/FP32 路径已覆盖。FP64 调试输入采用新代码保留双精度、旧代码中间强转 FP32 的不同算术约定，不在本次生产精度等价结论内。

## 5. 对当前实验解释的影响

恒定 α 的底层弱引导没有随节点更名悄悄改变。新结果与原全程弱引导的差异，应继续从实际 α 的层/步/bin 分布、控制统计和生成轨迹分析。原数据集案例间的 prompt、seed、几何和有效帧范围仍按各自既有实验保持。
