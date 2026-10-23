# H3AnchoredGuidance 独立包

- 节点类：`H3AnchoredGuidance`；包目录：`innovation/feature_anchor`。
- `mode=anchor`，`alpha_prior=.25`，`alpha_max=.5`，`prior_weight=1`，`probes=8`，`basis=centered`。`mode=fixed` 只提供等价路径与独立固定对照。
- `collateral` 输入已移除；其有效值由 `(1−alpha_prior)/alpha_prior` 决定，默认 3。
- 原 run_id、audit_dir、帧/步/层范围等节点输入保持。新 schema：`h3-anchored-guidance-v1`。
- 依赖仍为 SHA 固定的 H3Study 三个模块。服务器可设置 `H3_COVERAGE_FROZEN_ROOT` 指向原 H3Study；没有新依赖或模型下载。
- `attention.py` 的 `State.anchors` 逐层保存本 run 的因果锚点。完整采样后禁止重用同一 patched MODEL；每次推理通过独立 run_id 创建节点状态。
- 机制与纯函数接口见 `innovation/adaptive_strength_20261023/prototype/anchor_design.md`。
- CPU 证据见同目录 `anchor_test_result.json`。测试只在 .9 独立临时目录执行，`CUDA_VISIBLE_DEVICES=''`；没有部署节点、修改线上队列或启动 GPU 模型。
- 最新源码哈希与就绪状态见本目录 `READY.json`。部署前请按这些文件重新核对，原 `feature_guidance` 不修改。
