# 可见部位观测与弱引导兜底：下一轮预注册建议

日期：2026-10-17。此文件提出待 root 冻结的实验设计；没有修改 producer、阈值或启动新推理。

## 1. 当前证据与最小改动

固定五条源姿态的已知时移诊断已完成。原 R55 对 2/5 条可检测 ±4、±8 帧；3/5 条在躯干归一化入口返回 UNKNOWN。既有 R56 arm-only 对 4/5 条恢复可靠检测；short_0352 仍缺少足够上肢覆盖。两版全部可报告 lag 均准确；零时移均未触发。源姿态的合成诊断用于检查观测能力，生成效果由下一轮配对视频评价。

最小版直接复用已冻结 R56 `arm_features.py`，保留左右肩—肘—腕的单位骨方向，以及原左臂、右臂、双臂三种 descriptor。原 source/target 在同一窗口、同一部位共同可见时才参与匹配。源图可见左臂、目标只可见右臂时，不作跨侧替代。

阈值全部沿用：confidence 0.3/0.5；coverage ≥0.8；有效帧 ≥8；窗口 16/32 帧、stride 4；lag ±24 帧；两置信 lag 差≤2；可干预 lag 绝对值>2；原匹配盆地/残差门；相对 gain>0.5；相邻两次观测同方向、共享部位且窗口重叠比例≥0.5。原 gain 的 ±2 帧 null comparison 及其 common-support 检查也保留。

**这里改变的是检测所需部位。执行器仍在被选时间段的全部空间 query 上路由。** 当前 `make_gain` 将所选 bin 的全部空间位置设为 1，没有肩肘腕位置的空间 mask。若以后只干预对应肢体位置，需要另列算法和对照。

## 2. 默认策略及 UNKNOWN 定义

Visible-Only 为默认方案：完成当前 Native endpoint 的解码和 pose 后，运行可见上肢 scanner 与原 signed selector；满足原连续两次证据条件时采用局部时间路由。UNKNOWN 清空前次候选，当前步采用 Native。

兜底实验的 `U_n` 定义为：第 n 步观察任务完整返回、索引/父链/物理域验证通过，但该次所有 window×descriptor 的 `baseline` 均为 `unknown`，或合法科学状态为 `unknown_visibility`。具体原因分别记录 coverage、匹配歧义、残差形态不一致等。

以下状态各自保留：

- **全部 UNKNOWN**：尚无可靠动作时移判断；默认跳过反馈，独立兜底臂可按第 3 节执行。
- **有可靠窗口，候选数为 0**：包含 lag≈0、收益不足或仅部分窗口可观测。保留 Native；局部 UNKNOWN 不扩张成全片兜底。
- **已有候选，等待第二次持续证据**：沿原 persistence 等待，不提前触发兜底。
- **观察任务数为 0**：若尚未产生完整观测，不把它当同步，也不启动 UNKNOWN 兜底。技术错误、缺文件、索引或数据绑定错误走原失败处理。
- **有效窗口数为 0，但观察任务已完整返回**：属于科学 UNKNOWN，按 `U_n` 处理。每步同时记录 observation_complete、可靠行数、候选数和原因，避免混淆两个“0”。

## 3. 唯一弱引导候选

预先建议 `alpha=0.25`、零基去噪 index `6..14`（半开区间 `[6,15)`），其余步骤 alpha=0。共 20 个 Euler 步，采用原 sigma 序列。固定范围：90 帧模型画布的全部 27 个时间 bin、全部空间 query、全部 50 个 DiT block；radius=0、time_offset=0。原有效视频前缀及 padding 排除规则用于评价；全画布执行包含末端 padding 对应的 bin，日志明确这一点。

弱引导使用当前已有算子：

`O' = O + 0.25 × m_ref × (O_same_time_ref − O_ref)`

这里的 0.25 是每个 attention block 内路由修正的系数，不能解释为“运动被纠正 25%”，也不是对两个最终视频或最终 latent 的 25% 混合。它是未经效果优化的首个弱强度候选；本轮不扫 alpha、不按样例调参。区间取已有 R29 的 `[6,15)`，便于保留既有工程和历史比较口径。

Visible+weak-fallback 的每步决策按以下次序：

1. 原 Visible selector 达到 ON：采用其原局部时间路由，alpha=1。
2. 否则，当前为 `U_n` 且 n∈[6,15)：采用固定弱全片路由。
3. 其余状态采用 Native。

这三种执行状态互斥。弱兜底不写入 selector 的候选历史，也不伪造 lag 或部位信息；下一步继续从真实当前状态计算 Native endpoint。若一段样例每步都 UNKNOWN，该臂在区间内退化为 Weak-only，这是预期行为。

## 4. 最少对照与归因

建议固定原五条、同一 prompt 版本、原种子/视频/条件/采样，保留全部结果，四臂如下：

| 实验臂 | 规则 | 主要比较 |
|---|---|---|
| Native | 普通编辑 | 给出原编辑、动作和时间表现 |
| Visible-Only | 可见上肢检测＋原动态局部路由；UNKNOWN 跳过 | 对 Native 检查可见部位反馈是否有效 |
| Visible+weak-fallback | Visible-Only＋第 3 节 UNKNOWN 兜底 | 对 Visible-Only 检查额外兜底收益/损害 |
| Weak-only | 每次均在 `[6,15)` 用 alpha=0.25 全片路由，不依赖 observer 决策 | 检查相同改善是否由普通固定引导就能得到 |

前三臂能测试加兜底的增量；若要解释动态选择的作用，Weak-only 应保留。四臂不要求相同 active step 数，记录真实额外 forward 和耗时即可。Native 与 Weak-only 可做被动离线观测用于解释，控制决策独立于这些观测。

当前已有 R54/R55 使用 P0 短 edit_prompt；R57 测试 P1 统一适配。后续四臂应选定并封存一个版本，共用同一 Native 父结果；P0 与 P1 分开展示。当前五条不依据生成结果筛除。额外新素材若加入，先按源视频可见部位与编辑任务预选，再整批评测。

每条同时展示编辑是否完成、原动作类型/顺序是否保留、可靠物理 lag/UNKNOWN、官方 MF、干预次数和总时长。UNKNOWN 不计为零时差；编辑失败仍保留在五条分母内。部分窗口/左右臂行用于诊断，不作为独立样本。若只在固定弱引导臂也有同等改善，应把收益归于固定先验，而非自动检测。

## 5. 历史设置核对

只读检查当前 `h3-timing-*-2026101[67]/configs/**/*.json`，排除 parents/revisions/memory_evidence 与超过 2 MB 的文件，共 1074 份。这个范围内没有找到 alpha=0.25 的设置，不能据此宣称所有历史从未使用。

- R29：`mass_preserve, alpha=1, index6..14, 全42bin/全空间/50层`，141 帧，两个旧源样例。
- R34：`alpha=1, index4` 单步全片，21 NFE。
- R39：`alpha=1, indices{2,4,5,6}` 全片，24 NFE。
- R17：alpha=0.5 用于局部帧 50..65 的 phase-RoPE 路径，index6..14；执行器不同。

因此本候选与上述完整设置不同；“较弱 alpha＋固定区间”属于参数对照，不能独立作为架构创新。

## 6. 先例核对与当前可主张范围

[DIAL §3.3, Eq.6–7 / Algorithm 1](https://arxiv.org/html/2609.11507v1) 用前一步主体 grounding map 调节 video-query→reference-key logits，Phase I 在最后 80% 步骤工作。参考注意力增强及固定采样区间已有先例。当前算子保留参考组总 attention mass，并约束组内同时间读取；其 softmax 重参数化不能单独构成新机制。

[Motion by Queries §4、Appendix B.10–11](https://arxiv.org/html/2412.07750v3) 已有 Q 注入、由预测 clean endpoint 得主体 mask、同时间帧 K/V 共享及 feature-flow 引导。借助外部检测模型观察预测端点、根据可见主体限制信息交互，都有相近基础。当前最小版的肢体观测不等于 MBQ 的空间 mask，也尚未提供空间局部执行器。

[MotionEcho §3.4](https://arxiv.org/html/2506.19348v2) 根据运动损失滑动平均触发教师指导，并以另一阈值提前终止；[TempoControl §4](https://arxiv.org/html/2510.02226v3) 使用时序相关度控制每步优化的停止。误差触发、动态停止和固定强度已有先例。本轮应检验的是观测适用域、拒判条件及失去观测时的收益/编辑损害；可见部位入口和弱兜底组合目前属于研究组件，独立创新需要后续证据。

## 可核对的本地证据

- `../observer_known_shift_sensitivity/REPORT.md` 与两版 `SUMMARY.json`：固定五条已知时移结果。
- R56 `arm_features.py`：既有上肢单位向量特征。
- R55 `scripts/timing_metrics.py`、`pairwise_gain.py`、`automatic_window_policy.py`：原可靠性和动态选择规则。
- R55 `extensions/H3AutomaticWindowRouter/dynamic_support.py:43`：时间 bin 内全部空间 query 的 mask。
- R55 `extensions/H3TemporalRouter/core.py:205`：alpha 的实际 block 内含义。
- `HISTORY_AND_SOURCE_BINDINGS.json`：本次读到的历史设置与文件 SHA。
