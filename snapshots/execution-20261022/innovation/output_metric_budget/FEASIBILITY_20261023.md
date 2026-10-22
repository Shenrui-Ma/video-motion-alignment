# H3：把 head 预算移到输出投影与残差门之后

状态：只读源码核对、局部数学推导、11 项本地 CPU 检查完成。没有部署新节点或追加视频实验。本文补充 `FEASIBILITY.md`，保留已有原型。

**判断：这个方向适合先做度量审计，再决定是否实现分配器。** 它解决“投影前相同剂量，投影后剂量不同”的实际问题；收益取决于 head 效用是否可靠。当前切向效用与动作对齐改善的关联偏弱，更换范数本身不会修复这个关联。

## 1. 实际调用链与可访问接口

已核对缓存的实际 H3、Comfy 和量化后端源码；具体路径与 SHA 见文末证据。

```text
DiTBlock.forward
  adaln_proj(t_emb) → shift_msa, scale_msa, gate_msa, ...
  norm1(x) → scale/shift → attention(h)
      Q/K/V → optimized_attention → O ∈ R[N,7168]
      我们的修正：O + concat_h(α_h D_h)
      out_proj：INT8 Linear [7168 → 5376]
  x.addcmul_(out_proj(...), gate_msa[mod_row])
  norm2 → scale/shift → MLP → 第二次 gated residual
```

- `D_h=m_ref(S_t−R)_h`，包含原算法的参考视频总 attention 概率质量；本研究仅改变系数分配的预算度量。
- 56 heads，每 head 128 维；`out_proj.weight` 的存储形状为 `[5376,7168]`，无 bias。
- 已读 checkpoint header：INT8、输出行 scale `[5376,1]`、`int8_tensorwise`、ConvRot256。256 维旋转跨两个 head。
- `MixedPrecisionOps.Linear.forward_comfy_cast_weights` 在 `CastBiasWeightContext` 内获取本次有效 weight，随后 `weight.to(input.dtype)` 和 `F.linear`。`TensorWiseINT8Layout` 的真实分派调用 `comfy_kitchen.int8_linear`；它会动态量化每个输入行。
- `DiTBlock.forward` 的 `gate_msa` 是局部变量。现有 `args['attention']` 接口只传 `h/rope_freqs/transformer_options`，**没有传 gate**。当前 attention override 不能直接把它取出来。

gate 来自 `adaln_proj(t_emb)`，其行通过 `mod_segments` 选择；选择项既可能是单一行，也可能是逐 token 的行张量。实现应复用这次已经计算的 gate，按实际 token 行取值，并保留原 dtype 转换。不能假定所有模态、所有时间 token 共用同一 gate。

最小可实施的 gate 接入是局部 block 视图：复用原 norm、MLP、attention 及实际 `DiTBlock.forward`，仅用局部 `adaln_proj` 代理保存该次返回的 gate，交给同一调用里的局部 attention/out_proj 代理。gate 不额外计算，原模型模块不做全局属性替换。原 block/module hooks、prefetch/offload 语义及全 `.25` 等价需要单独测试；现有 block replacement 提供了调用位置，尚无已实现的 gate 捕获接口。

本文的 Gram 对应 **attention 分支经投影和 gate 后的局部增量**。整个 DiT block 随后还有 MLP；最终视频 latent 的变化涉及后续层和采样更新。

## 2. 投影前等能量不足以限制残差增量：严格反例

取两个 head 的修正各为标量 1，基准 `a₀=(.25,.25)`，候选 `a=(√.125,0)`，两者都在 `[0,.5]` 内，且

\[
\|a_0\|^2=\|a\|^2=.125.
\]

令输出投影为 `W=[1, −1+ε]`，gate=1，则

\[
E_0=(.25\varepsilon)^2,\qquad E(a)=.125,
\qquad \frac{E(a)}{E_0}=\frac{2}{\varepsilon^2}.
\]

ε=.001 时，输出增量能量是固定 `.25` 的 **2,000,000 倍**。ε 趋近零时比例无上界。问题来自跨 head 抵消，不是浮点误差。

即使 `W=I`，gate=`(100,1)`，同一对系数的 gated 能量也是 `625.0625` 与 `1250`。只纳入 W、遗漏 gate，仍然会漏掉当前残差分支的尺度变化。

即使准确控制 attention 残差，后续映射 `r→r+Kr` 也可把局部能量乘以 `(1+K)²`。因此本项预算应以 attention 残差分支命名，不能写成“整个 block／最终 latent 等能量”。

## 3. 含交叉项的 Gram

对同一批固定 query probes，令线性有效权重为 `W̄`，第 h 个 head 的列块为 `W̄_h`，对应 gate 为 `g_p`：

\[
Z_{ph}=g_p\odot(D_{ph}\bar W_h^T),\qquad
G_{hk}=\sum_p w_p\langle Z_{ph},Z_{pk}\rangle,\quad w_p\ge0.
\]

于是 `G=ZᵀZ` 半正定，且在线性代理内

\[
E(a)=a^TGa=\sum_p w_p\left\|\sum_h a_h Z_{ph}\right\|^2.
\]

所有 heads 使用同一组 query、相同输出坐标和相同权重。交叉项保留各 head 的加强与抵消；独立测每个 head 的范数后相加会丢掉这些项。

真实 INT8 算子记作 F。由于输入相关的量化 scale 和舍入，通常

\[
F(O+\delta)-F(O)\ne F(\delta),\qquad
F(O+\delta)-F(O)\ne\delta\bar W^T.
\]

因此 G 是线性代理的精确 Gram，实际量化修正仍需独立验证。直接用 `F(O+εD_h)−F(O)` 构造经验 Gram 也只能描述所取有限差分，多个 head 的非线性组合未必等于有限差分的线性和。

## 4. 少量 probes 时，先考虑完整输出小 Gram

先用 **每层 8 个总 query probes** 审计；不是每时间 bin 8 个。按有效视频范围固定分层选时间和空间位置，索引不依赖本次控制结果。单独保留另一组固定 query 做验证。这样能把输出坐标保持完整，避免先引入低维 sketch 的不可见方向。

存储 INT8 权重为 Q，逐输出行 scale 为 s，分组正交旋转为 H。线性代理满足

\[
\bar W=\operatorname{diag}(s)QH^T.
\]

无需展开整块 `W̄`：每个 head 的 128 维 D 先乘它在 H256 中对应的 128 行，得到 256 维旋转后的稀疏组；只读取 Q 中该 head 对应的 **256 列成对组**，与输出行小块相乘，再乘 s 和 gate。把两个 head 当作独立 128 列量化块处理会用错旋转坐标。

按输出维分块得到 `Z_tile[P,H,256]`，直接累加 `G += Z_tileᵀ Z_tile`，无需保留完整 Z。该方法访问原 INT8 weight 和小型浮点 tile，不反量化整个矩阵。

下面是 P=8、H=56、D=128、输入7168、输出5376、tile256 的理论规模；MAC 指一次乘加。

| 操作或暂存 | 每层规模 |
|---|---:|
| head 输入的成对组旋转 | 14,680,064 MAC |
| 成对组输出投影 | 616,562,688 MAC |
| 所有 head 交叉 Gram | 134,873,088 MAC |
| 三者合计 | 766,115,840 MAC |
| Q 的256输出行浮点 tile | 7 MiB |
| Z 输出 tile | 0.4375 MiB |
| 旋转后的稀疏 head 输入 | 0.4375 MiB |
| 56×56 Gram，FP32 | 12.25 KiB |
| 若保留完整 Z | 9.1875 MiB |
| 完整 FP32 权重，方案无需分配 | 147 MiB |

这些是算术量，不是实测运行时间。大量小 GEMM、权重 tile 转换与 offload 会影响实际速度；dense INT8 kernel 可能在更高理论运算量下仍更快。

**随机投影的使用条件。** 若 probe 数量增多，公共 `R∈R[5376,k]` 可以压缩输出。纳入 gate 后需要 `B_g=W̄ᵀdiag(g)R`；gate 随层和采样步变化，若逐 token gate 不同还需区分 gate 行。旧的静态 `B=W̄ᵀR` 不能在压缩后补乘高维 gate。本地 CPU 反例验证了这种信息丢失。

只计算一个 gate 行、k=32，构建 `B_g` 也需约 **1,233,125,376 MAC/层/步**，大于上述 P=8 完整输出路径的总运算量。gate 仅为统一标量等特殊情形才可直接复用静态 sketch。不能将旧方案“权重 sketch 可跨步缓存”的成本当成含 gate 方案的成本。

低维 sketch 仍可作为后续折中：所有 head 共享 R，并用独立验证信息检查自适应候选。候选依赖 R，简单引用固定向量的 JL 保证不足以给出本次候选误差保证。当前最小路线省去这一步。

## 5. 复用实际量化 Linear 做候选验证

已核实的调用路径是：

```python
# 示意结构：精确 kwargs 来自当前 MixedPrecisionOps.Linear 的同一路径。
with CastBiasWeightContext(module, input=None,
        dtype=module.weight.dtype, device=O.device, bias_dtype=O.dtype,
        offloadable=True, compute_dtype=O.dtype, want_requant=True) as (weight, bias):
    weight = weight.to(dtype=O.dtype)
    # 仍为 QuantizedTensor；不要调用 .dequantize()。
    probe_y = torch.nn.functional.linear(probe_rows, weight, bias)
    # 量化 layout 真实分派 → comfy_kitchen.int8_linear
    full_y = torch.nn.functional.linear(selected_full_rows, weight, bias)
```

在同一 cast/offload context 内，`TensorWiseINT8Layout.get_plain_tensors(weight)` 提供 Q 与 scale，`weight._params` 提供已核实的 ConvRot 配置。实际代理必须保留 `run_every_op`、输入 dtype、原 scaling 和权重函数条件；首版仅支持已验证的当前无 LoRA／无输入预缩放 INT8 路径，其他路径直接采用原模块的固定 `.25`。示意代码尚未接入运行时。

验证取另一组 P_v=8 queries，将三组输入合成24行：

\[
O_p,\quad O_p+.25D_p,\quad O_p+\operatorname{concat}_h(a_hD_{ph}).
\]

用同一 F 计算后乘同一个 gate，比较相对原始 O 的增量能量。若还要覆盖残差加法的低精度舍入，可以保留这些 query 的原始 x，复用 `addcmul` dtype 和运算顺序后比较三组残差，而非只比较 `g·ΔF`。两者应明确分别记为 branch contribution 和实际 sampled residual delta。

三组 P_v=8 的量化投影约 **924,844,032 MAC/层**；量化/GEMM临时 buffer 由原后端管理。先按批合并避免逐 head 调内核。直接逐 head 做 black-box 有限差分需要 `8×57=456` 行，约 **17,572,036,608 MAC/层**，还不能解决非线性组合问题，不作为首选。

候选只有在实际量化／残差验证能量不超过固定 `.25` 的统一预算容差、值有限、基准能量可靠时采用，否则整层回 `.25`。验证后的 full-video projection 正常执行一次；没有额外 DiT、VAE 或 RGB 模型。少量 query 只能检查这些位置，完整视频的能量统计仍须单独记录。输入行数可能改变 CUDA 内核路径，容差需用后端一致性检查确定，不能写成逐比特等价。

## 6. 分配问题：凸预算，保留原效用

保持当前 `heads_budget_strength` 的效用 `c_h=e_hu_h` 不变：e 是现有完整输出的 pre-W_o head 修正能量，u 是已实现的切向特征占比。只修改约束；同时将 c 改成输出能量加权，会把“更换度量”和“更换效用”混在一起。

设 `a₀=.25·1`，`D_G=diag(G)`，建议的凸问题是

\[
\max_{0\le a\le .5}\ c^Ta,\qquad
a^TGa\le a_0^TGa_0,\qquad
a^TD_Ga\le a_0^TD_Ga_0.
\]

第一个约束以固定 `.25` 的实际线性代理输出能量为额度；第二个限制各 head 独立能量，防止通过交叉抵消获得不受控的单头修正。固定 `.25` 总是可行。用相同能量**上限**作比较允许预算不用满；强制 `aᵀGa=E₀` 是非凸曲面。即使 G=I，两个等能量可行向量的中点也会落到球内部。

这是一项56维、两个凸二次约束加 box 的 QCQP，也可写成 SOCP。含交叉项后，当前逐 head 独立的 water-filling 闭式解不再适用。

若后续决定实现优化器，可对预算矩阵除以各自基准能量、对效用统一归一化，在 CPU float64 上解小问题。拉格朗日乘子 λ、ν≥0，box 的活跃变量固定后，自由变量满足

\[
(2\lambda G_{FF}+2\nu D_{G,FF})a_F
=c_F-2\lambda G_{FA}a_A.
\]

配合二次约束的互补松弛和 box KKT 检查。退化矩阵需有稳定解法；加入固定的小严格凸先验能获得唯一解，但这属于另一目标，应明确消融。不要靠向 G 添加 εI 后放松真实能量约束来隐藏零空间。

**当前最合理的可执行第一步仍是已有候选的可行性过滤。** `prototype.py::ray_budget_guard` 已实现：保留现有 head 分配候选，clip box 后统一缩放到 G 和对角预算内。它不是上述 QCQP 的最优解。若过滤后的原效用低于固定 `.25`，直接选 `.25`；再通过上一节的实际量化验证。这样先确认预算位置有没有实际意义，不同时引入新的求解器。

近零 reference 能量、强抵消、无效 gate、未知量化路径、无可靠效用或验证失败均回固定 `.25`。这些 fallback 应记录原因及比例；基准近零时不使用能量比。

## 7. 与已有方法的关系及执行顺序

该度量是输出映射诱导的标准 pullback 二次型；在线性和固定 gate 下，对输入修正就是 `W̄ᵀdiag(g²)W̄`。本文未定义概率模型及其 Fisher 信息，故不将它命名为 Fisher，也不把这一恒等式作为独立原创机制。

与当前实验相比，它只改变 head 分配的剂量单位。它仍使用同一 m、同一同时间 attention、同一切向效用和同一 α 上限。动作、外观和遮挡仍可能共享该特征变化方向，这是效用识别问题，不是 Gram 的正定性问题。

建议顺序：

1. 先在固定 `.25` 与现有 head-budget 上记录投影前、投影后、含 gate 后的实际增量比例；此时不改变生成结果。
2. 若差异稳定且足够大，再只换预算度量，采用现有候选过滤和实际量化验证。先两例，保留原效用，报告 fallback 与实际能量。
3. 如果大量回 `.25` 或滤波后的有效剂量降低，先检查误差和匹配剂量对照，不急于加复杂 QCQP。
4. layer 版本另做；上一采样步的各层局部能量只能给下一步预测预算。当前整步真实能量和最终 latent 能量仍需区分。

## 8. CPU 证据与尚需验证的工程项

`cpu_proof_20261023.py` 在本地 Python 标准库运行，11项通过，结果为 `CPU_EVIDENCE_20261023.json`。覆盖：无界投影放大、gate遗漏、MLP后续放大、PSD与交叉能量恒等式、跨两head的ConvRot稀疏投影、gate与sketch不可交换、动态量化非加法、等能量曲面非凸、两个预算过滤、实际验证失败回退，以及真实源码的调用接口检查。

模型源码 SHA：`0d5edcf32b4b98d704eaa51de60ed71f507d0c7d9845947f566647dc76fb8dfe`。接口定位：

- `innovation/partial_rope/sources/host41_model.py`：Attention 158–200；`_mod_gate` 242–246；DiTBlock 291–297；block replacement 749–762。
- `feasibility_sources/comfy_ops.py`：1337–1429 的量化 Linear/cast 路径。
- `feasibility_sources/kitchen_tensor_int8.py`：264–295 的量化分派。
- `feasibility_sources/kitchen_backends_cuda___init__.py`：1865–1985 的输入量化与 ConvRot 分支。
- `feasibility_sources/kitchen_tensor_int8_utils.py`：真实 regular Hadamard 符号与分组约定。
- `feasibility_evidence.json`：已读取的模型 header、量化配置、源码哈希与当时后端分派证据。

本轮没有读取远端、下载、运行 CUDA 或改动现有文件。未测工程项是：局部 gate 代理与原 hooks/prefetch 的等价、实际 INT8 probe 调用的数值容差、分块 GEMM 的真实耗时，以及全视频上的度量覆盖。待 field/layer 两例结果完成后，由主线程决定是否进入第一项只记录统计的接入实验。
