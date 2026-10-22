# 因果层强度预算

该方法独立改变 H3 50 个 DiT 层之间的引导强度分配。每个层内，所有选中视频时间 bin、空间 query 与 head 共享一个标量 alpha。它与逐 bin 强度场、head 分配、跨时刻参考覆盖分别测试。

## 1. 统计与作用位置

Attention 原输出记为 O，参考视频完整分支为 R，同时间分支为 S，参考贡献质量为 m。沿用固定引导的修正 D=m(S−R)，在 W_o 前施加 O+alpha_l D。文本与其他参考分支没有单独重加权。

仍使用同一 query、前后相邻参考 bin 的 8 个固定空间 probes，构造中心特征切向。将 D 在该切向上的投影能量 A 与正交补能量 B 汇总到每一层。选中窗口首尾 probes 不参与统计；引导仍作用于全部选中视频时间。

每层第一次有效完成时保存 A0/B0。随后以

rT=A/A0，rN=B/B0，u=rT/(rT+rN)

作为层质量。实现用两组能量的共同尺度规范后的交叉乘法计算，避免直接相除溢出。首个有效调用质量强制为 .5；已有 scalar-anchor 函数仅复用其状态、规范质量及审计，不采用其即时 alpha 闭式解。

在完整分辨率、实际选中的输出 query 范围测量

e_l=||D_l||²/(||O_l||²+epsilon)。

这是输出投影前的局部相对修正能量。epsilon 是累加 dtype 的 tiny；零/非有限能量、O²低于1e-8×max(O²,D²)的层不参加预算。共同缩放 O、D 不改变 e。A/B 的时间特征切向也可能包含外观差异，u 衡量内部特征方向相对锚点的变化。

## 2. 使用上一完整步分配下一步

第 s 步的层计划只使用第 s−1 步已完成的统计。令 I 为上一完整步有质量证据且能量有效的层，a0=.25，amax=.5，解：

max Σ_(l∈I) e_l u_l a_l

s.t. Σ_(l∈I) e_l a_l² ≤ a0² Σ_(l∈I) e_l，0≤a_l≤amax。

无证据层固定 a0，移出重分配集合，并保留它自身的基准预算。首步使用 a0；第一次完成的全部有效锚质量都是 .5，所以第二步仍是 a0。第三步起才可能出现不同的层强度。

KKT 的自由坐标满足 a_l=u_l/(2rho)，因此采用 a_l=min(amax,c u_l)。对固定上限集合 S，剩余集合 F 的

c=sqrt((B−amax²Σ_S e)/(Σ_F e u²))，B=a0²Σ_I e。

每次把超过 cap 的层固定到 cap；至多 |I| 次固定后结束。计算前将 e 除以最大值，控制求解中的尺度。质量相同则直接返回 a0，首两步逐元素保持 .25。所有质量为0时目标没有方向信息，选择 a0；部分质量为0且正质量层已达cap时，允许少用预算，审计记录 `positive_quality_cap_limited`。

这是线性目标加凸二次约束的优化。预算绑定且有正质量时，自由坐标由上述 KKT 确定；退化零质量情况按明确规则处理。没有根据视频样例修改参数。

## 3. 真实执行的因果边界

每层先取本步已冻结的 alpha。当前层原始 probe 统计或局部相对修正能量无效时，该层回到 .25；不重新分配尚未执行层的预算。这里的本地保护只检查原始有限性、非零统计和局部能量。A/B 相对旧锚过小的判据在完整 forward 结束后计算，仅决定下一步的层资格；若原始统计仍有效，本步保留上一已完成步的计划 alpha。50 层全部完成之后，才汇总一份50×8统计到CPU、更新每层锚、求下一步计划。中途没有读取未来层，也没有重跑 DiT。

逐步同时记录三项：

1. **计划预算**：Σ e_(s−1,l) a_plan² / [.25²Σ e_(s−1,l)]。
2. **实际执行的上一度量预算**：Σ e_(s−1,l) a_executed² / [.25²Σ e_(s−1,l)]；局部无效回退及浮点舍入会使其偏离计划。
3. **当前实际漂移**：Σ e_(s,l) a_executed² / [.25²Σ e_(s,l)]。

第三项在执行完后才能得到，首轮不做额外反馈补偿。分母为0时记录 null。该预算限定在上一采样步的投影前局部相对修正度量；W_o、AdaLN gate、后续层 Jacobian 与跨层交叉项决定最终 latent 的变化。

每次推理拥有独立 State、layer_plan 与 anchor 字典。按50层顺序完成才能产生下一计划；未完成的 forward 不更新锚或计划。完整采样结束后重用 patched MODEL、失败后重用状态、错序 block 或来源不严格等于当前 forward−1（首步来源−1）的计划都会拒绝执行。

## 4. 代价与审计

与 scalar anchor 一样，每层仍为5次 Attention 调用：原注意力、参考分支、同时间分支、两个相邻 bin 的 probe 分支。没有增加模型、完整 DiT 前向或 VAE 解码。增加一个目标 query 的 O 范数；D 范数沿用已有统计。

每完整去噪步集中传输最多50×8个 FP64统计，3200字节。water-filling 最多50次小集合固定。审计分别记录统计同步、water-filling CPU时间、完成控制总时间；GPU同步和 JSON 写入的总成本需真实 pilot 记录。

审计 schema `h3-causal-layer-budget-v1`：

- 每层：请求/实际alpha，A/B/count，A0/B0及anchor_step、created/used、规范质量、raw_probe_evidence_valid、current_evidence_valid（原始统计与局部能量）、current_anchor_evidence_valid/anchor_low_current_energy（结束后旧锚适用性）、next_plan_eligible、完整分辨率D²/O²/e、局部fallback、finite、调用次数。
- 每步：plan_source_forward、plan_for_forward、planned_alpha、actual_alpha、前后e、当前质量/有效层、三种预算/漂移、next_alpha/next_plan_for_forward、求解分支及耗时。

## 5. 验证与下一轮

25项 CPU 测试已通过：凸预算可行性、KKT自由比例和cap方向、随机可行解目标比较、能量尺度不变、无效层保护、低质量cap少用预算、当前漂移不等于旧预算；固定.25与冻结 Attention逐元素等价；真实probe前两步.25；完整20×50顺序因果、锚值固定、局部回退、未完成forward不分配、独立run和消费后拒绝复用。

第一轮只与固定.25、即时scalar anchor在相同样例比较。若有改善，再加固定置换层质量对照，检查是否依赖正确的层对应；实际剂量不同则加剂量匹配固定对照。本包尚未部署、没有视频结果。

## 统计开销口径

`statistics_transfer_bytes` 仅统计每个完整 forward 的 50×8 充分统计量主缓冲；审计 JSON 序列化还会读取逐层摘要，不能用该字段代表全部 CPU/GPU 传输字节。`controller_gpu_dispatch_seconds` 是主机提交张量计算的墙钟时间，未使用 CUDA event，不作为 GPU kernel 执行时长。
