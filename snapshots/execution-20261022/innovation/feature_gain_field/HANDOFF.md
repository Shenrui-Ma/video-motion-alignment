# H3TemporalGainField 独立节点

节点已实现并通过 43 项 CPU 测试，尚未部署或提交视频。新包只位于 `innovation/feature_gain_field/`；原 `feature_anchor`、`feature_guidance` 和在线队列保持原状。冻结哈希见 READY.json。

## 方法与参数

- 节点类 `H3TemporalGainField`；`mode=gain_field`。`fixed` 仅保留固定引导等价测试与独立对照。
- 第一轮冻结：`alpha_prior=.25, alpha_max=.5, prior_weight=1, smoothness=.625, probes=8, basis=centered`；20 步、50 层、原完整有效视频时间范围。`gain_field` 会拒绝其他 prior/cap；零引导测试走 `fixed` 或 `enabled=False`。
- 同 query 的参考特征中心差分构造切向，原统计在 `[H,T,P]` 聚合 head 和空间 probe，保留视频时间 T。A/B 表示质量加权修正中沿该特征切向及其正交补的能量；没有用通道维度 128 做校准。
- 每个 layer/bin 在本 run 的首个有效步记录 A0/B0，该步该 bin 仍用 .25。后续使用 A/A0、B/B0 的共同尺度归一化，逐 bin 严格凸 box QP 求 alpha[T]。
- 对应位置仍为 H3 DiT 内 Attention 输出、W_o 之前：`O + alpha[t] * m * (S_same - R_all_reference)`，每个 bin 的 alpha 广播全部 heads 与空间 query。
- 无证据 bin 和所选有效窗口两端固定 .25；平滑边在这些 bin 处切断。窗口两端的单侧差分不参与统计。
- alpha 是连续强度，默认 μ=1 的支持区域理论下界为 1/28；不把它描述成二元开关或实际测得的动作延迟。
- 每层仍为 5 次 Attention 调用：全序列、参考分支、同时间、前参考 bin probes、后参考 bin probes。没有增加 DiT 前向或 VAE 解码。
- 详细目标、凸性证明、KKT 与 λ=.625 的无量纲解释见 `../temporal_gain_field/DESIGN.md`。

## 运行状态与开销

- State.anchors 每层拥有独立 CPU 向量状态，绑定 step/layer/绝对 bin 坐标/配置；重复或倒序 step、时间窗口移位、二次重用已完整采样的 patched MODEL 都显式拒绝。每个新推理必须独立 run_id、新节点状态。
- 每层一次显式 `3×T` FP64 小统计向量到 CPU；求解后 alpha[T] 回原设备。GPU 同步等待计入 `statistics_transfer_seconds`，不能据此当成纯传输带宽；`controller_cpu_seconds` 单独测求解/状态更新。
- 1000 次 CPU 原型测量：T=29/41 平均 0.881/0.929 ms；这不含 GPU 同步、Attention 或审计 I/O。实际推理耗时需新 pilot 记录。
- `head_energy` 和新增 `bin_energy` 均使用完整分辨率修正统计；`applied_energy=Σ_t alpha_t² bin_energy_t`。这是 W_o 前的实际局部修正能量，不是能量预算守恒方法。

## 审计字段

新 schema `h3-temporal-gain-field-v1`，保留 `feature_forward_summaries[].layers[]`。每层：

- `alpha[T]`、`latent_bin_indices[T]`、`alpha_mean/min/max`。
- `control`: A/B/count，A0/B0，anchor_created/initialized/anchor_step，usable_evidence，normalized_temporal/complement，quadratic_diagonal/rhs，edge_weights，unsmoothed_alpha，solver_succeeded/fallback_to_prior。
- `control.segments[]`：局部半开区间、converged、iterations/limit、KKT residual/tolerance、gradient、box 激活数。没有证据或首步时 segments 为空，alpha 仍 .25。
- 精确完整分辨率 `bin_energy`、`head_energy`、`correction_energy`、`applied_energy`、finite_output；5 次 Attention；CPU 求解/统计同步耗时及小向量字节数。
- 原核心的执行计数、route 计数、first_attention 与 expected_sampling_steps 继续保留。失败的 QP 段显式退回 .25 并记录 converged=false，不能统计成成功求解。

## 验证

43 项 CPU 测试通过，详情 test_result.json。包括 18 项数学状态测试及独立小矩阵穷举 oracle、fixed .25 与冻结核心逐元素等价、首步等价、dense 逐 head/time/probe 对照、逐 bin 全分辨率能量/广播、非目标保持、未知 bin 隔离、短窗口、尺度、独立层/运行状态、消费完毕后拒绝复用。20 步×50 层完整 mock 产生 1000 次有限修正与 1000 条审计，所有支持段 KKT 通过。

测试使用 .9 已有 PyTorch，独立目录 `/tmp/h3_gain_field_node_cpu_20261023`，`CUDA_VISIBLE_DEVICES=''`；没有 GPU 模型、下载或队列修改。

## 下一步交接

父线程独立审查冻结代码与 audit 后，先用一条原样例的新 run_id 运行 pilot；保持 prompt/seed/cache/model/几何。核对首步 alpha 全 .25、后续每 bin 有有限变化、端点/无证据保持 .25、1000 段调用计数、KKT、SHA、采样与控制开销。原 scalar anchor 和固定 .25 作为匹配对照。后续若有改善，再单独测 λ=0 与实际剂量匹配的固定强度；本轮不叠加 head、coverage 或 layer 分配。
