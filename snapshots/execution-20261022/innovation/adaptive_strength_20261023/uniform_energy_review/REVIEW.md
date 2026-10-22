# Uniform-energy field 独立只读审查

结论：机制、同 forward 能量口径与实验隔离正确。发现的 FP64 归约溢出和遗漏能量字段校验已由作者修复；最终 READY 与源码哈希已逐项确认，可进行两条既定 pilot。

## 核对结果

1. `D=m(S_same−R_all)` 在同次 attention 调用中生成，布局为 `[1,H,T,S,D_head]`；`bin_energy` 对 `(batch,head,spatial,channel)` 全分辨率求平方范数，仅保留时间维。QP 候选、RMS 分配、实际 `D*alpha` 应用均使用本次 forward 的同一 D。统计 probe 仅用于 QP 的 A/B 信号，未替代完整修正能量。
2. 仅 `solver_succeeded` 的 bin 进入统一 RMS。窗口端点、无可靠证据、首次建立锚以及 QP 失败位置保持 `.25`。跨不连续可用区间共享一个 b；无效位置本身不被改变。固定模式仍跳过新控制器，使用原固定引导路径。
3. 候选 QP 与实际应用分开保存：`candidate_alpha` 通过原候选的归一化、锚、KKT 审计；`alpha` 验证同一次 forward 完整能量的加权 RMS。把全部候选、control.alpha、实际 alpha 与各能量字段一起伪造为 `.25`，仍被未修改的 QP 证据拒绝。完整重写原始 QP 证据与输入不可由自包含 JSON 真实性审计识别，运行产物 SHA 是溯源边界。
4. 独立比对两条 JSON 图：只有节点 `14`、`50` 改变，节点 `50` 输入仅 `audit_dir`、`mode` 不同；节点类为新包注册名。参考时间窗口、邻居索引、prompt、seed、cache、模型、采样器和 QP 参数未改变。`controller.py`、`components.py`、`frozen.py` 与原 field 按字节一致。
5. 当前等能量成立于本次候选与本次实际应用、合并 heads / W_o 之前。均匀化会改变后续轨迹，不能将不同运行的能量称为逐步相同。这一口径在 README、runtime schema 和审计中一致。

## 已修复的问题

- **FP64 归约溢出（发布前阻断，已修）**：逐元素有限并不保证总和有限。独立 CPU 反例 `E=[1,1e308,1e308,1]`、`a=[.25,.1,.4,.25]` 原先将内部 b 静默算成 0，误差约 `−1.7e307`。现检查非负 E 的 FP64 总和有限；由非负性和 `a≤.5`，该约束也保证加权分子及总修正能量不溢出。两条溢出反例均明确拒绝，FP32 `1e38` 的安全 FP64 归约保留。
- **审计字段遗漏（已修）**：原审计未检查 `applied_modifiable_energy`。现独立重算该值，单独修改此字段会被拒绝。
- 作者另将最终 `correction_energy` 与 `applied_energy` 日志改为 `bin_energy.double()` 归约，避免 RMS 安全但最终 FP32 日志求和溢出的不一致；该变更不修改 D、候选或实际输出。

## 计算与数值范围

`uniform_energy_alpha` 的输入校验包含一次 GPU 布尔归约读取，因此确有主机同步；CPU `solver_succeeded` 端点布尔读取不构成 GPU 同步。`uniform_host_dispatch_seconds` 覆盖主机调用及等待，不能视为纯 GPU kernel 耗时。这里只执行 CPU 检查，运行开销由 pilot 的真实计时给出。

原始完整修正能量统计仍按原 field 的 FP32（或测试 FP64）范数计算；新增 FP64 是小能量向量的归约。单个 bin 已发生的溢出会在 RMS 输入检查中被拒绝。近零回退使用源 dtype 最小正正规数，明确记录回退，此时不强称保留精确能量。

## 独立证据

- `PRE_FIX_OVERFLOW.json`：修复前 CPU 反例及源 SHA。
- `STATIC_CHECKS.json`：两图实际差异与冻结文件逐字比对。
- `review_cpu.py`：独立反例、边界与一致篡改检查，未调用 GPU。
- `CPU_REVIEW.json`：8 项独立检查及真实 CPU wrapper 20×50 JSON 的重放；已对最终 fixture_release 重放，所有被审 Python SHA 与最终本地源码一致。

没有修改包源码、实验图、部署状态或队列；没有生成新视频。

最终 READY SHA：`f494b28d02b2ca6f01712910e124c2c46ed1ac92397db5d867385615404a7423`。最终独立检查 8 项通过；完整 20×50 CPU wrapper 审计最大能量相对误差 `8.1545425e−8`、最大 KKT `7.0231232e−8`。详见 `SIGNOFF.json`。
