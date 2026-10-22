# 时间均匀、等修正能量的 field 消融

计划状态：`review_only`。独立节点 `H3TemporalGainFieldUniformEnergy`。待主线程审查，不进入 active manifest。

## 目的

field 的平均 α 不能直接表达修正剂量，因为不同时间 bin 的修正向量 D 能量不同。主线程在已完成的1000次调用记录上计算

`Σ applied_energy / (.25² × Σ correction_energy)`：

- 机舱：1.0491868731，能量等效 α 为 .256074559。
- 饮酒：1.0709916298，能量等效 α 为 .258721814，而简单平均 α 约 .24505。

这里的分母使用各自 field 实际轨迹的 D，计算在同一个 D 上固定 `.25` 的反事实剂量；不是另一条独立 weak 轨迹的能量。这组事实说明，需要把“整体修正剂量变化”和“如何把强度分配到时间位置”拆开比较。数值来源是主线程已完成 field 审计汇总，本包不重算或改写这些已完成结果。

## 同一次前向内的控制

完全保留原 `H3TemporalGainField` 的同 query 相邻参考特征、A/B统计、逐层逐 bin 首次有效锚、归一化、平滑参数 .625 和 box QP。原 `controller.py`、`components.py`、`frozen.py` 按字节复制，未修改。

QP先得到候选 `a_t`。D的真实布局是 `[1,H,T,S,D_head]`，已有代码在完整分辨率上计算

\[
E_t=\sum_{h,s,d}D_{h,t,s,d}^2.
\]

令 M 为本次 `solver_succeeded` 的时间 bin 集合。仅在这个集合中应用

\[
b=\sqrt{\frac{\sum_{t\in M}E_ta_t^2}{\sum_{t\in M}E_t}},\qquad
\tilde a_t=\begin{cases}b&t\in M\\.25&t\notin M.\end{cases}
\]

因此本次前向中，候选与实际系数满足

\[
\sum_t E_t\tilde a_t^2=\sum_t E_ta_t^2
\]

至浮点转换误差。候选在 `[0,.5]` 内，能量非负，因此 b 自然在同一范围。RMS的分子、分母用 float64 归约，b 再转回原修正 dtype。每层每个去噪步重算，不缓存 b。最终总修正能量日志也以 float64 归约；完整分辨率各 bin 的原始能量测量和实际修正 dtype 保持原实现。

端点、新建锚、无证据、QP失败的 bin 均保持 `.25`。即使某个 bin 已有历史锚，本次无可用证据也不参与 RMS。多个有效区间可共享 b；无证据区间本身仍固定 `.25`。这样去掉所有有效区间之间的时间剂量差异。原 QP 依旧在无证据位置切断平滑边。

没有可变 bin，或可变能量总和小于等于源统计 dtype 的最小正正规数时，统一回 `.25`，记录 `near_zero_energy_fallback`。这是下溢保护，不是按样例设定的阈值。非有限、负能量、FP64归约溢出、越界候选或非可变 bin 的候选不是 `.25` 会明确失败，不伪造匹配成功。

## 隔离的因素与仍然变化的因素

这个对照保留每次前向候选 field 的修正剂量，移除可变 bin 之间的强度分配，检验时间位置选择是否带来独立收益。控制器计算和 attention 次数保持不变：native、全参考、同时间、前邻和后邻，共5次；没有额外 DiT、VAE 或 RGB 模型。

实际应用的系数改变后，后续 hidden state、attention、D 和 A/B 会改变。因此各自轨迹上的能量匹配不等于两条独立视频轨迹的逐步能量一致，也不等于 W_o 后或最终 latent 的等能量。b仍随层和去噪步变化；只有有效视频时间 bin 之间的强度被统一。

## 审计

- `candidate_alpha` / `control.alpha`：原 QP 候选，保留锚、A/B、归一化、区间及 KKT 信息。
- `alpha`：实际应用的时间均匀系数。
- `uniform_energy`：可变集合、完整 E 加权的分子/分母、b、候选与实际总能量、误差、近零回退。
- KKT只对候选检查；不把均匀化后的系数称为原 QP 的最优解。
- `audit.py` 先核对实际 RMS、边界、mask与能量，再复用冻结的 field 独立审计检查候选 KKT、跨步锚及20×50执行记录。
- 旧模型复用保护、每run状态隔离、非目标 token 保持和有效时间窗口均沿用原实现。

## 文件与准备图

- `uniform.py`：新的小向量能量匹配；`attention.py` 在原 QP 后调用它。
- `nodes.py` / `__init__.py`：独立节点注册，默认关闭。
- `field_audit_base.py`：本次复制的原独立field审计；`audit.py` 增加本消融检查。
- `pilots/build.py`：从冻结机舱、饮酒 field 两图生成待审图。只允许节点14输出前缀和节点50方法变化；prompt、seed、cache、模型、几何、sampler以及所有 QP参数不变。
- `pilots/jobs.json` 为 `review_only`，每条 `max_attempts=1`。未创建发布标记，未修改全局队列。
- `test_result.json` / `CPU_INTEGRATION.json` / `READY.json` 保存最终CPU验证与源码哈希。

先完成 CPU/dense attention/真实 wrapper 审计和图差分验证，再由主线程决定是否开展两条视频推理。本包未运行新视频，尚无效果结论。
