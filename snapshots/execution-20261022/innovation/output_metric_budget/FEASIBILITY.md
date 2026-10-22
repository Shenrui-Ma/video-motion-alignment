# H3 输出投影度量：实现可行性

状态：只读源码核对及 CPU 数学原型；未新增 GPU 方法、节点或推理任务。

结论：投影后的 Gram 能描述各 attention head 在输出空间中的放大、相关与抵消，比拼接 head 后的欧氏范数更接近当前层实际修正。但本实验使用 INT8 激活量化，真实输出投影是输入相关的非线性算子。第一版应把 Gram 当作候选分配的线性代理，再用原量化算子检查候选修正，检查失败回到 α=.25。

## 1. 实际架构与权重证据

H3 `Attention.forward` 在 `optimized_attention` 返回后调用 `self.out_proj(out.squeeze(0))`。投影输入为 56×128=7168 维，输出为 5376 维，无 bias；之后才经过 DiT 的 AdaLN gate 和残差加法。这里的预算对应 attention 输出投影位置，不是最终视频 latent 的改变量。

本批 graph 的模型为 `minimax_h3_ref2va_pruned_int8_convrot.safetensors`。只读其 95,416 字节 safetensors header 与少量 72 字节配置，确认：

- `blocks.0.attn.out_proj.weight`：INT8，形状 `[5376,7168]`。
- `weight_scale`：FP32，`[5376,1]`，逐输出通道缩放。
- `comfy_quant`：`{"format":"int8_tensorwise","convrot":true,"convrot_groupsize":256}`；第49层同格式。
- 当前服务的 dispatch 审计记录实际调用 `cuda.int8_linear`，而非仅从启动参数猜测后端。

读取证据、源文件 SHA 和当时 dispatch 快照保存在 `feasibility_evidence.json`；没有读取 checkpoint 的大权重张量。

源码位置：缓存 `host41_model.py:158–200,291–297,749–762`；`feasibility_sources/comfy_ops.py:1337–1429`；`kitchen_tensor_int8.py:264–295`；`kitchen_backends_cuda___init__.py:1865–1985`。

## 2. 为什么不能直接把 out_proj 当精确线性层

外层配置 `quantize_input=False` 仅表示不在 `MixedPrecisionOps.Linear.forward` 中预先创建量化输入。实际 `TensorWiseINT8Layout` 的 `F.linear` 分派进入 `int8_linear` 后，还会对每一行输入做 Hadamard 旋转、按该行幅度确定 scale、舍入为 INT8，再执行整数 GEMM。

设分组正交旋转为 H，存储权重为 Q、逐输出行 scale 为 s。忽略算术舍入时，反量化权重的线性代理是

\[
\bar W=\operatorname{diag}(s)QH^T,\quad L(x)=x\bar W^T.
\]

真实算子近似为

\[
F(x)=\widehat{Q}_x(xH)Q^T\operatorname{diag}(s),
\]

其中 \(\widehat{Q}_x\) 包含输入相关的逐行量化与反量化。因此通常

\[
F(x+\delta)-F(x)\ne L(\delta),\qquad F(x+\delta)-F(x)\ne F(\delta).
\]

CPU 小张量已验证该非加法现象。原型只用于数学检查，不是 CUDA kernel 的逐比特仿真。LoRA、`pre_quant_scale`、不同量化 layout 或强制反量化会改变路径；最小实现应明确拒绝未验证路径，使用原 `.25` 修正。

## 3. 获取有效权重与复用投影调用

当前路径在 `CastBiasWeightContext` 内取得设备上的实际 weight，完成必要 offload 同步和权重函数处理，随后 `weight.to(input.dtype)` 再 `F.linear`。这里 `QuantizedTensor.to(dtype)` 更新原始计算 dtype 元数据，通常仍保留 INT8 存储；主动 `.dequantize()` 才会生成完整浮点权重。一个 out_proj 的完整 BF16 权重约 73.5 MiB，FP32 约 147 MiB。

普通 module forward pre-hook 只看见尚未 cast 的 `module.weight`，拿不到这个上下文内的最终 weight。不能直接在全局 Linear 类上挂补丁，也不能持有失效的 offload 权重引用。

可执行的最小接入位置是 H3 已有 block replacement 的 `args['attention']`：

1. 为当前 block 调用构造一个局部 attention 视图，复用原 qkv、norm 和 RoPE；不替换共享模型对象上的属性。
2. 该视图的 out_proj 使用独立闭包。attention override 提供原输出 O 和修正 D；延后到闭包内确定 head 强度。
3. 闭包只进入一次原 `CastBiasWeightContext`，从当前 weight 的真实 layout 参数取得 Q、s、ConvRot 标志；构建或校验小 sketch，检查候选，然后执行一次完整视频投影。
4. 同步和释放沿用原 context。首步、缓存无效、未知 layout 或验证不通过均用 `.25`。不额外执行 DiT、VAE 或 RGB 模型。

局部 attention 视图要由源码哈希和 dense equivalence 测试约束；它是后续可实施设计，目前未写入线上包。若实现时发现无法保留原 cast/LoRA 语义，应停止该接入，不靠重复调用整个 out_proj 掩盖问题。

## 4. 不展开大浮点权重的共享 sketch

取所有 head 共用的输出投影矩阵 \(R\in\mathbb R^{5376\times k}\)，定义

\[
B=\bar W^TR=H Q^T\operatorname{diag}(s)R.
\]

按 Q 的输出行分块，将小块转为浮点累加 \(Q^T\operatorname{diag}(s)R\)，再对 B 的输入维执行完整的 256 维分组旋转。只需暂存 `7168×k` 的 B 和一个权重小块。

**ConvRot 的 256 维组跨两个 128 维 attention head。必须先完成组内逆旋转，再把 B 切为56个 head。** 先按 head 切 INT8 存储列会用错坐标系。H3 使用的是源码中的 regular Hadamard 矩阵，不能随意换为另一种符号顺序的 Hadamard。

对同一批 query probe 的 head 修正 \(D_h\)，计算

\[
Z_h=D_hB_h,\quad \widetilde G_{hg}=\langle Z_h,Z_g\rangle.
\]

该 Gram 对称半正定。所有 head 必须共享 R；每个 head 独立随机矩阵会破坏跨 head 内积。

以29个时间 bin、每bin8个probe、56 heads、k=32估算：

| 操作 | 规模 |
|---|---:|
| 一次构建 B | 约12.33亿 MAC/层；静态权重可跨采样步复用 |
| 每层计算全部 head 的 Z | 约5322万 MAC |
| 每层计算 Gram | 约2328万 MAC |
| Z 临时 FP32 | 约1.59 MiB |
| 50层 B 的 FP32 总缓存 | 43.75 MiB |
| 256行权重块转 FP32 | 7 MiB 临时空间 |

这些是运算量和张量大小，不是已测 GPU 延迟。缓存必须绑定模型/权重版本、量化布局、LoRA/权重函数、dtype、设备和投影随机种子。若任何一项变化，失效重建或回退。

## 5. 防止 head 抵消与 sketch 零空间被利用

线性代理下，head 强度向量 a 的输出能量为 \(a^TGa\)。head 之间可能互相抵消，使某个强度组合落在近零特征值方向；单纯约束这个二次型会容许各 head 很大的修正。

建议同时保留：

\[
a^TGa\le a_0^2\mathbf1^TG\mathbf1,\quad
a^T\operatorname{diag}(G)a\le a_0^2\operatorname{tr}(G),\quad 0\le a\le .5.
\]

第二个约束限制各 head 的独立能量，不让跨 head 抵消提供无限额度。若基准共同修正几乎抵消、非有限或没有可靠质量信号，返回 a=.25。

k=32 的随机 sketch 不能仅凭一个 JL 口号保证所有自适应候选方向准确。优化器知道这个 sketch 后可能找到其不可见方向；CPU 检查已构造一个 sketch 能量接近0、真实能量为1的方向。小 k 是计算折中，必须用独立信息验证。注意把 query 和输出维一起展开后，整体 Gram 未必秩≤k；风险是投影损失的信息，不能仅用 k 与 head 数作简单秩判断。

## 6. 候选的实际量化投影检查

最小第一版沿用已有 head 质量产生一个候选 a，不再同时研究另一套复杂最优化器。用 Gram 与对角约束缩放候选；在与估计probe分离的少量固定验证query上调用同一量化算子，计算

\[
\Delta_0=F(O+a_0D)-F(O),\quad
\Delta_a=F(O+\textstyle\sum_h a_hD_h)-F(O).
\]

比较真实量化能量比 \(\|\Delta_a\|^2/\|\Delta_0\|^2\)，并记录与 Gram 预测的差异。若超预算、基准近零、非有限或误差超过预定统一容差，整层回 `.25`。不得按样例调验证阈值。

这增加少量 projection probe 调用，没有额外完整 DiT。若取16个验证query、三种输入合并为48行，投影约18.50亿 MAC/层，远小于完整视频的数万行投影；它仍有实际内核调度开销，应先测。INT8量化按行进行，但 batch 大小可能改变 CUDA 内核路径，因此验证必须记录 layout/后端并使用合理数值容差，不能承诺逐比特一致。

这些检查只约束所选内部probe的当前投影修正。完整视频的实际输出范数、MF与动作偏移仍需记录。该方法是否比 `.25` 更有效，留待当前 gain-field 与 layer pilot 完成后再决定实验；本次只交可行性。

## 7. CPU 检查与产物

`projection_feasibility.py` 提供纯 torch 小张量函数：regular Hadamard、分块量化权重 sketch、参考逐行 INT8 算子。`test_projection_feasibility.py` 的四项检查覆盖：

1. 分块 sketch 与完整反量化矩阵相等；跨head旋转正确；Gram半正定。
2. 输入动态量化的非加法性；逐行处理在数值容差内不依赖其他行。
3. 自适应候选可落入 sketch 零空间，独立验证能观察到其能量。
4. 旋转正交与错误维度保护。

测试环境是 `.9` 既有 torch 的独立 `/tmp/h3_wo_feasibility_cpu_20261023`，`CUDA_VISIBLE_DEVICES=''`。完整记录见 `TEST_RESULTS.json`。没有修改运行中的方法代码、队列、模型服务或用户报告。
