# 跨输出时刻分配参考视频时间覆盖

状态：独立 CPU 原型；未接入主 64 条推理。新增文件全部位于本目录，冻结 `inference/package/custom_nodes/H3Study/{core,layout,schedule}.py` 保持原样。模块导入不会注册节点、patch 模型或连接服务；`enabled=False` 是适配器默认值。

## 研究假设和现有修正的关系

冻结实现的 `mass_preserve` 是 `O′ = O + α m_ref (O_same − O_ref)`。`m_ref = exp(min(0, LSE_ref − LSE_full))` 按每个 head、每个空间 query 保留参考视频组总概率，`O_same` 在同时间 bin 或指定邻域内重新分配参考条件概率。`layout.py` 要求参考和输出时空几何匹配，bin 的位置跨度采用 `(1,4,4,4,4)` 循环；`schedule.py` 只决定去噪步集合。

本原型将 `O_same` 替换为 `O_cover(t,q) = Σ_j P[t,j] O_j(q)`，其中 `O_j(q)` 是 query 对参考第 j 个 bin 的原有 QK softmax/V 输出。每个输出 bin 共享一行粗粒度时间分配 P，空间匹配仍由各 query 在参考 bin 内独立完成。全部参考视频 keys 仍用于计算 `O_ref` 和 `m_ref`；P 的分配范围仅限原计划所选事件窗口。

具体假设：如果多个输出时刻对同一参考时刻重复取得很高 QK 相似度，独立 query 的最大相似选择会遗漏参考时间过程。把这些输出时刻联合分配到固定覆盖预算，可减少这种重复。收益仍需在视频实验中验证，QK 质量可能反映背景相似度或位置编码，采样也可能漏掉小主体。

## 求解器

1. 固定均匀采样最多 8 个空间 query 和 4 个 heads。对每个参考 bin 的全部空间 K 分块计算 logsumexp，块长默认 256，得到每个样本的参考时间概率。对空间/head 取均值后取 log，作为 `quality[t,j]`。采样是确定性的，不消耗随机数；不增加 DiT 前向。
2. 在有效的 T×T 时间矩阵上最大化 `〈P,Q−λd²〉 + εH(P)`，约束每个有效行和为 1、每个有效列和为 1、`P≥0`、`|t−j|≤radius`。默认 `ε=0.5`、`λ=0.25`、radius=2；采用 log-domain Sinkhorn，最后检查列和残差不超过 `2e-4`。行归一化保证条件概率，边界不会复制参考 bins。
3. 若期望参考时间倒序，取保持约束的最大 `β`，令 `P←βP+(1−β)I`，使相邻有效输出的期望参考时间差不小于 `minimum_mean_gap`（默认 0）。该凸混合保留行列预算和局部 support。**顺序约束是期望时间非降，单个分配边仍可交叉；不是逐 token 路径单调匹配。**
4. `radius=0` 或单 bin 时 P 为 identity，直接复现同时间修正。低信号、非有限质量、无有效 bin、对角 anchor 不可用、Sinkhorn 未收敛或修正非有限时返回原生输出并记录原因。数学上可行但不含 identity anchor 的自定义 support 也被保守拒绝；本原型不做一般二分图可行性求解。

**覆盖的单位**是每个 latent bin 的参考条件概率。有效列和位于 `1±tolerance`；它不是 `(1,4,4,4,4)` 物理帧时长覆盖，也不是乘 `m_ref` 后的总概率流量均匀分配。由于 `m_ref` 随空间 query/head 变化，实际参考流量仍会不同。部分窗口只协调该窗口内的时间覆盖；窗口外参考条件概率通过原有 α 混合与 `O_ref` 保留。

独立求解器支持一维 bool `valid_mask` 对两轴一致 padding，无效行列严格为零；支持附加 bool `allowed_mask`。H3 适配器复用严格完整帧布局，拒绝非整帧与不匹配几何，不把 padded keys 送入 Flash。

## 内存、开销和接口

- `routing.py`: `CoverageConfig`、`solve_temporal_coverage`、`sampled_time_quality`。只依赖已有 PyTorch。
- `attention.py`: `coverage_attention` 接受返回 `(output,LSE)` 的 attention callback；生产预期传冻结 `core.flash_attention_lse`。按时间 offset 批处理帧对，除完整和参考组 attention 外，最多增加 `2r+1` 次帧对 Flash 调用。
- `make_h3_patch_classes(core)`：显式绑定冻结 core 的 `RouterState/EventBlockPatch`，复用布局、RoPE、block 顺序、去噪计数及 audit。适配器的覆盖摘要使用独立 schema。
- `attach_h3_coverage(...)`：关闭时直接返回同一模型对象；开启时要求新鲜、没有既有 block/attention patch 的 H3 50-block 模型，clone 后安装独立 patch。默认步区间 `[6,15)` 与 frozen fixed schedule 相同，block 区间默认 `[0,50)`；不修改现有 `SCHEDULES`。

最大显式相似度暂存是 `[sampled_heads,T×sampled_queries,key_chunk]`，另有 O(T²) 时间路由和正常 O(H×T×S×D) attention 输出/批处理张量；生产路径没有完整 token N×N 矩阵。求解器的数值/可行性判断和适配器有限值判断包含设备到主机同步，尚未验证其 GPU 时延。CPU 测试的 dense oracle 仅使用小张量。

接入示例只用于未来独立实验的构图代码，不执行现有服务变更：

```python
from temporal_coverage import CoverageConfig
from temporal_coverage.attention import attach_h3_coverage

# frozen_core 是调用方已加载的 H3Study.core 模块对象。
candidate = attach_h3_coverage(
    fresh_model, positive, core=frozen_core, enabled=True,
    config=CoverageConfig(radius=2), alpha=1.0,
    start_frame=event_start, end_frame=event_end,
    block_start=0, block_end=50, step_start=6, step_end=15,
    run_id=unique_run_id, audit_dir=isolated_audit_directory,
)
```

适配器使用现有完整参考值 V；它不叠加 partial-RoPE、动态值分量或其他 attention override。独立实验应分别比较原生、同时间质量守恒（radius=0）、邻域独立路由、覆盖路由，并保持模型/采样器/步数/窗口/α 相同。

## 有限官方来源核对（2026-10-22）

| 来源 | 官方材料描述的机制 | 与本原型关系 |
| --- | --- | --- |
| [Cuturi, Sinkhorn Distances, NeurIPS 2013](https://arxiv.org/abs/1306.0895) | 用熵正则和平衡矩阵缩放求解输运 | 本原型直接使用该类既有算法；Sinkhorn、熵正则和双边预算均不作为原创 |
| [TokenFlow, ICLR 2024，作者项目页](https://diffusion-tokenflow.github.io/) | 从原视频扩散特征提取跨帧最近邻对应，并传播少量编辑后的关键帧特征 | 共享“利用模型内部对应保持视频时序”的思想；本原型从当前 H3 QK 估计 bin 质量，并联合分配时间列预算，不构造反演关键帧传播流程 |
| [FLATTEN, ICLR 2024，作者代码](https://github.com/yrcong/flatten) | 用光流路径约束跨帧 patch attention | 同属训练免费 attention 约束；本原型的局部 support 是时间 bin 邻域，未使用光流轨迹或光流模型 |
| [ChordVideo, arXiv:2608.00769v1，作者稿 §3.3–3.4](https://arxiv.org/html/2608.00769v1) | 因果时间核聚合运动对齐的 Chord 编辑场，可用光流或隐式匹配；用低能量输运解释稳定化 | 都涉及时间聚合和输运语言；其稿件中的核聚合作用于编辑场，本原型的平衡列预算作用于 H3 参考条件概率。此处只核对方法结构，未复现其结果 |

这次核对用于区分机制和引用来源，范围为以上材料。原型贡献表述限定为一个待检验的组合：**有界 QK 采样 → 联合参考时间覆盖 → 期望时间顺序修复 → 保留每 query 参考组总概率的 H3 输出修正**。

## 验证与待验证项

在既有 H3_SERVER_A `comfyui` Python 环境运行 CPU 小张量测试，显式设置 `CUDA_VISIBLE_DEVICES=''`、`OMP_NUM_THREADS=1`、`MKL_NUM_THREADS=1`。可复跑入口（工作目录为本包父目录）：

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m temporal_coverage.verify_cpu
```

测试覆盖：行概率、列覆盖上界、所有输出偏好同一参考时刻、边界邻域、倒序均值修复、padding/NaN 隔离、identity、自定义 support、不可行/低信号/未收敛回退、质量估计与小 dense oracle 一致、临时 matmul 形状上界、开关和 α=0、原生输出回退、每 query 参考总概率保持、窗口外和非参考权重不变、输入不被原地修改。

证据见 `cpu_validation.json`、`cpu_test_output.txt`，包含 Python/Torch 版本、源码 SHA-256、测试计数及 `cuda_initialized_after_tests=false`。本地另通过 `py_compile` 语法检查。未运行 CUDA/Flash、ComfyUI 模型 patch 的完整集成、H3 推理、VAE 解码、视频指标或性能测量；也未修改主任务图、运行服务及冻结 core。
