# H3CausalLayerBudget 交接

程序已完成，25 项 CPU 测试通过；未部署或排队。源文件和精确哈希见 READY.json；详细公式及因果边界见 DESIGN.md。

- 节点：`H3CausalLayerBudget`；包：`innovation/feature_layer_budget`。
- 第一轮：`mode=layer_budget, alpha_prior=.25, alpha_max=.5, probes=8, basis=centered`，原样例完整时间范围，20步50层。节点没有 μ 或 collateral 输入；复用 anchor 函数仅取归一质量。
- 第一和第二个完整采样步固定 .25；每一步50层全部完成后计算下一步层预算。每层内仍是原同时间修正，所有head/时间bin共享该层alpha。
- `mode=fixed` 保留基线等价验证；禁用节点直接返回原 MODEL。已有注意力patch会拒绝叠加。
- 审计：`h3-causal-layer-budget-v1`，逐层结果继续在 `feature_forward_summaries`，完整层预算与三类预算/漂移在 `layer_budget_summaries`。
- 旧 frozen H3Study依赖按SHA验证，服务器可设置 `H3_COVERAGE_FROZEN_ROOT`；无新增依赖或权重下载。
- 测试仅在 .9 独立目录 `/tmp/h3_layer_budget_node_cpu_20261023`，`CUDA_VISIBLE_DEVICES=''`；没有操作任何线上服务/队列。
- 先由父线程独立核对源码、审计和预算，再决定单pilot；原运行中的 scalar anchor、gain field 和 heads 包未改。
