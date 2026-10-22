# 时间概率 cost 与信息预算：机制核查

**判断：不建议把这一版本直接追加为新 GPU 方法。** 精确 KL 控制适合作为 attention 改变量的基线；新增“时间距离减少量”效用仍缺少动作修复依据。它在数学上仍是已有分组 logit 偏置的特例。CPU 反例显示，它能严格满足预算、提高自己的目标，同时削弱真正有输出修正量的 query。先保留为离线诊断与剂量约束研究。

本文件复用 `adaptive_strength_20261023/research.md` 第 4 节的 Bernoulli KL 推导，新增内容是物理时间效用的实际含义、精确聚合、两项预算、可证伪反例和 H3 成本。没有部署、生成视频或修改队列。

## 1. 所控制的对象

索引 i 表示一个 DiT 层、去噪步、head 与生成 query；t 是该 query 所属视频时间 bin。原参考视频内部的时间概率为

\[
p_i(j)=\sum_{k\in\text{reference bin }j}
 \frac{\exp(q_i^Tk/\sqrt d)}{\sum_{r\in\text{reference video}}\exp(q_i^Tr/\sqrt d)}.
\]

同时间概率记 s_i=p_i(t)，完整 packed attention 中参考视频的总概率记 m_i。现有修正 `O + α m(S_t−R)` 在时间概率层等价于

\[
p_{i,\alpha}=(1-\alpha_i)p_i+\alpha_i\delta_t.
\]

δ_t 表示把质量放入同时间 **bin**；这个 bin 内空间 keys 的条件概率仍由原 QK 决定，不是只选一个 token。参考组总质量 m_i 和组外概率保持。

## 2. 时间 cost 必须先去掉打包 origin

H3 `_video_t_grid` 的时间坐标是 `origin + exclusive_cumsum((1,4,4,4,4)×5/3)`。参考和生成序列有各自的 packed origin。直接使用两者原始 RoPE 坐标之差，会把打包位置误当成物理时间差。

使用相对序列 origin 的时间：

\[
\tau_j=\frac{\mathrm{pos}_{j,0}-\mathrm{origin}_{ref}}{5/3},\qquad
\tau_t=\frac{\mathrm{pos}_{t,0}-\mathrm{origin}_{out}}{5/3},\qquad
c_i(j,t)=\left(\frac{\tau_j-\tau_t}{L}\right)^2.
\]

L 固定为该缓存视频的时间跨度，使 cost 无量纲。这里使用 H3 时间 bin 起点，保持其不均匀间隔；没有修改 Q/K 的 RoPE，也没有把 bin 起点当成 VAE 精确感受野。绝对距离也可选，但第一版只研究上述平方距离。两者都把早、晚对称处理。

概率域须与原算子一致：R 仍覆盖完整参考视频段，含原有 padding bins；记录 padding 概率，并用其真实缓存坐标计算 cost。仅对有效 bins 重新归一化会改变 s、m 和 KL 的定义，应作为另一个明确方案。

## 3. 新 utility 的简化揭示了什么

令 `C_i=Σ_j p_i(j)c_i(j,t)`。因为 c_i(t,t)=0，时间 cost 减少量**恰好**为 α_i C_i。保持参考质量后的线性效用是 `m_i α_i C_i`。

沿用旧 KL 公式，令 r_i=s_i+α_i(1−s_i)：

\[
K_i(\alpha)=r_i\log(r_i/s_i)+(1-r_i)\log\frac{1-r_i}{1-s_i}.
\]

带固定探测权重 w_i 的分配问题：

\[
\max_{0\le\alpha_i\le.5}\sum_i w_i m_i C_i\alpha_i,
\qquad \sum_i w_i m_i K_i(\alpha_i)\le B,
\qquad B=\sum_i w_i m_i K_i(.25).
\]

B 是当前观测行上固定 .25 的总 KL。它允许行间重分配；逐行各自给 `B_i=K_i(.25)` 再反解只会得到 .25。只分配一个共享 α 也退化为 .25。

未触及边界时，KL 对偶变量 λ 给出

\[
\operatorname{logit}(r_i)=\operatorname{logit}(s_i)
 +\frac{C_i}{\lambda(1-s_i)}
=\operatorname{logit}(s_i)
 +\frac{\mathbb E[c_i(j,t)\mid j\ne t]}{\lambda}.
\]

**因此它仍是同时间组的 logit 偏置，偏置大小取决于非同时间注意力的平均距离。** 若各行这个条件距离相同，它就是同一个共享 logit 偏置。优化器没有获得动作语义、速度、延迟方向或修正后收益；新增信息只有距离一阶矩。采用 `c=1[j≠t]` 可完全免去新的 per-bin 统计，但所有行的条件距离都等于 1，又回到旧的共享偏置方案。

## 4. 凸性、KKT 与第二个预算

当 0<s_i<1：

\[
K'_i(\alpha)=(1-s_i)\log\frac{s_i+\alpha(1-s_i)}{s_i(1-\alpha)},\qquad
K''_i(\alpha)=\frac{(1-s_i)^2}{r_i(1-r_i)}>0.
\]

所以最小化负线性效用、带 KL 上界和 box 的问题是凸问题。λ>0、权重为正的活跃行具有严格凹的拉格朗日子问题，解唯一。零 utility、零权重、s=1 或 KL 不活跃时会出现平坦解，不能统一声称严格唯一。

`math_prototype.py` 使用解析逐行解和 λ 单调二分。λ 增大，解的总 KL 单调不增；达到 α=.5 的行按上边界 KKT 保留。

只有 KL 相等仍可能增加总体 α。一个可独立检查的第二约束是

\[
\sum_i w_i m_i\alpha_i\le A=.25\sum_i w_i m_i.
\]

这是**参考质量加权的强度和**，不是实际搬移质量或输出 L2 能量。其对偶变量 ν≥0 使内点方程变为

\[
\operatorname{logit}(r_i)=\operatorname{logit}(s_i)
 +\frac{C_i-\nu}{\lambda(1-s_i)}.
\]

C_i≤ν 时取 α_i=0。固定 λ，对 ν 二分满足强度预算；外层再对 λ 二分满足 KL。对固定 dose 可行集合，两个不同 λ 的最优性不等式相加即可证明总 KL 随 λ 单调，支持这个双对偶求解。原型测试同时检查两预算、互补松弛、内点与 box 的 KKT。

数值例：同一四行上，固定 .25 效用为 .215；仅 KL 控制的效用 .270577、强度和 1.007108；双预算效用 .245373、强度和 .675，与固定 .25 相同。两者 KL 都是 .413762。KL 或强度和匹配仍未匹配 `Σ α_i² ||m_i(S_i−R_i)||²`；实验解释应继续记录实际修正能量。

## 5. 极小 s 与退化边界

- 保留 `log_s=LSE_same−LSE_ref`，不先转成低精度概率。`log_s=-1200` 时 `exp(log_s)` 已下溢为零，精确 KL 仍可用 log-space 求得有限值。
- 当 s→0 且 α>0，KL 约为 `α log(1/s)+α log α+(1−α)log(1−α)`，会很大。相同效用下，信赖域会压低几乎不受支持的同时间组；真正错位严重的 query 也可能受到这种压制。
- 若是真正 s=0，则任意正 α 的 forward KL 为无穷。数学上有限预算只能选 α=0；原型明确拒绝零支持输入，不用 epsilon 修改概率冒充精确预算。当前无 mask、有限 logits 的 softmax 在实数上有正支持；数值异常应先被审计发现。
- m=0 的行不产生参考修正，移出预算；s=1 时 S=R、KL 和修正均为零。原型显式记录其平坦选择。

## 6. 聚合与因果执行的精确边界

**每 head/query α。** 对已计算的这些行，目标、KL 和解都是精确的。给所有空间 query 计算新时间 cost 太贵。

**每时间 bin 共用 α。** 在该 bin 的探测行上保持 `Σ_i w_i m_i K_i(α_t)`，用一维单调求根，可得到精确的采样目标。线性效用可先汇总 C，但 KL 必须保留不同 s_i；不能先平均 p_t 再代入 KL。反例 s=(.01,.99)、α=.25：真实平均 KL=.311607，平均概率 .5 的 KL=.031584，低估约 9.87 倍。

**从探测点广播到整个 bin。** 对未观测空间 query 不再有精确预算保证。CPU 反例中，在高 s 的探测点选出较大 α 后，同 bin 一个低 s 的未观测点超过原 .25 的 KL。可把结论写成“探测分布上的信息预算”，并记录额外验证探测点误差。

**全层预算。** 单次顺序 DiT forward 无法在第一个 block 就取得当步最后一层的统计。三种口径必须区分：

1. 每层独立使用当前探测统计，控制该层自己的 .25 KL 预算；所有层完成后，加总的是各层各自实际轨迹上观测到的局部预算，没有跨层最优分配。
2. 上一步统计计划下一步跨层分配；这是因果可做的，但当前真实 KL 可能漂移。CPU 测试已构造超过当前 .25 总预算的例子。
3. 同步精确全层联合求解需要额外预探测 forward 或推迟应用，当前限制下不采用。

各层/各 head 的 KL 之和是控制器定义的局部信息预算；它没有自动成为最终视频生成分布的 KL。

## 7. 已通过的反例

1. **静态 Value 消耗预算。** 两行 s 都为 .1。第一行远距离注意力很强、C=.9，但全部参考 V 相同，实际 D=m(S−R)=0；第二行 C=.009，实际 D=−.9。固定 .25 的总 KL 为 .377755。最优重分配给静态行 α=.372944，给第二行 α=.001953；效用从 .22725 增至 .335667，第二行到目标 S 的误差从 .675 增至 .898242。求解正确，动作相关效用却选错。
2. **提前和延后无法区分。** 参考时间概率围绕 t 镜像，s 和平方距离矩相同，控制器给出相同 α。概率离散度没有提供延迟的符号。
3. **重复姿态与语义对应。** 参考多个时刻可能具有同一姿态或同一物体；远时刻 K 更匹配当前主体/衣着并不必然是时间错误。只给相同 p、不同 V/语义的两个问题，控制器必然同解，真实修正后果可相反。
4. **五角色周期可产生距离信号。** 构造只关注 `j mod 5=t mod 5` 的静态视频，仍有明显正 cost。项目已有 `latent_phase_calibration_20261023/POSTHOC_ROLE_ANALYSIS.md` 检出 H3 组内角色差异；这不是本原型观测到 attention 五周期的实证，而是必须区分的混杂来源。后续若采集概率，应先做源视频自比和同角色/跨角色分层。

## 8. H3 可取得什么，成本在哪里

已核查冻结源码 `H3Study/core.py::flash_attention_lse`、`_aligned_attention` 与 H3 `_video_t_grid`。原路径已有 LSE_all、LSE_ref、LSE_same，能直接得到 m 与 s，**精确 KL 本身无需新 attention**。

距离 utility 要求每参考 bin 的概率 `p_i(j)=exp(LSE_{ij}−LSE_ref,i)`，原有三个 LSE 不包含这个一阶矩。选择每有效 query bin 8 个固定空间 probes、所有 heads，可对参考 key bins 流式计算 LSE：每次用所有 probe queries、一个 bin 的 K/V 调用现有 Flash，只保留 LSE；逐 bin 累加 C，输出读数丢弃。无需额外完整 DiT/VAE，但约增加 T 次小-query attention 调用/层/步，且当前 aten Flash 同时计算不需要的 AV。

用本批典型尺寸 T=32、H=56、P=8、S=3772、D=128 估算：

| 项 | 大小或次数 |
|---|---:|
| 直接物化所有 probe-to-reference QK 概率 | 6.45 GiB FP32，拒绝此路径 |
| 全部 bin LSE（可以继续流式） | 1.75 MiB FP32 |
| 单次小-query Flash 输出 | 3.5 MiB BF16 |
| 只传 m/s/C 三个 probe 统计数组 | 168 KiB/层；1000 次约 164 MiB |
| 50 层×20 步、32 个参考 bins | 约 32000 次额外小-query调用 |
| QK 算术量/一次完整 packed self-attention（忽略文字） | 约 0.053%，不代表实际延迟比例 |

优先流式切 K/V，不为所有时间配对复制完整 reference tensor。大量 launch、内存读取、控制器同步和 bin 级精确 KL 求根可能主导开销；当前只有 CPU 数学时间，没有 GPU 延迟结论。缩少 heads/probes 会改变估计覆盖，必须单列采样口径。

## 9. 与已有方法的区别及推进选择

| 方法 | 作用与信号 | 本候选相对它的实际差别 |
|---|---|---|
| DIAL Phase I | 从前一去噪步主体空间 grounding map 得到主体参考 attention 的 logit 偏置，控制身份保持。 | 本候选保留视频参考总质量，在其内部偏向同物理时刻；时间距离代替空间主体图。两者都含 attention 分组偏置，不能仅凭“动态权重”立论。来源：[DIAL §3.3](https://arxiv.org/html/2609.11507v1#S3.SS3)。 |
| APG | 在条件去噪预测方向上分解 CFG 更新，配合范数限幅和 reverse momentum。 | 本候选直接作用于一层参考 attention 的条件概率与 KL，不修改全模型 CFG 更新。来源：[APG §4](https://arxiv.org/html/2410.02416v1#S4)。 |
| 当前 causal layer budget | 用上一完整步 A/B 相对锚点质量、pre-W_o 修正相对能量分配下一步层强度。 | 本候选把效用换成概率时间距离，把预算换成精确行 KL；去掉 Value 切向假设，但也丢掉实际修正方向和大小。若跨层运行，仍需同样的因果滞后处理。 |

**推进选择：先停在本轮 CPU 证据。** 闭式求解和凸性已经明确，继续给优化器起名或换求解器不会补上缺失的动作信息。若后续已有 forward 允许记录少量内部概率，先检验 C、s、同角色周期和已标定动作误差的关系，再决定是否做 KL 剂量基线；当前不增加 GPU 实验。

可复现文件：`math_prototype.py`、`test_math.py`、`NUMERICAL_EXAMPLES.json`、`TEST_RESULTS.json`。**22 项 CPU 测试通过**，包括概率层与 token 层 KL 等价、导数/凸性、单行退化、双对偶 KKT、极小支持、精确分组以及上述反例。
