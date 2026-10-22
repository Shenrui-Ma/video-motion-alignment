# 2026-10-23 锚归一化与监督器安全增量

在 `9fe7dea` 源码快照之后，保存首步锚控制器、输出投影度量原型、时间增益场原型、结果采集与报告生成程序，以及任务边界、显存分配器和端口占用安全修复。源文件与导出文件的 SHA-256 见同名 JSON 清单。

## 方法与状态

- `innovation/feature_anchor/`：独立 H3 节点；同一 query 读取参考视频相邻时刻的 K/V，分解时间切向与正交补能量。每层首次有效 A₀/B₀ 作为固定锚，随后逐步求闭式强度；首步与无可靠统计时取 .25。节点记录真实逐层审计，拒绝同一已耗尽 MODEL 再次采样。
- `innovation/output_metric_budget/`：**仅离线 CPU 原型**。检查 Wₒ 后跨 head 项与修正能量约束；尚未纳入真实推理节点。
- `innovation/temporal_gain_field/`：**仅离线 CPU 原型**。时间 bin 增益场、箱约束三对角 QP 与因果层内状态；READY 中的五个文件 SHA 已逐项核对，19 个 CPU 合成测试通过。未完成的 `feature_gain_field` 运行包不在本快照中。
- `innovation/adaptive_strength_20261023/batch/`：首步锚审计、配对指标汇总、只读 collector、同帧对照素材准备和单文件报告生成器。实际运行数据与视频需在恢复后接入；缺失数据保持待测，不填零。报告浏览器检查因文件协议安全策略阻止，仅静态与媒体检查完成。
- `supervision/anchor_boundary_20261023/`：哈希保护的自然任务边界交接、进程所有权、API/锁状态、容量审计和安全恢复。
- `supervision/host9_allocator_aware_20261023/`：显存预算与已有缓存口径；`port_claim_fix/` 保留自己持有的有效 claim，保护其他活跃进程与监听端口。
- `supervision/host60_inference_20261023/`：配套工作进程与服务管理代码模板。

## 导出边界

没有修改原始实验程序。导出副本替换账号路径、SSH 别名、设备 UUID 和私有 IP；这些值是部署占位符，需要按实际环境配置。原始部署/任务清单、媒体、模型、缓存、完整运行日志、凭据与 SSH 配置均未包含。备份传输 helper 不进入仓库。

唯一额外测试导出调整：`prototype/test_anchor_controller.py` 中依赖 `anchor_real_energy_fixture.json` 的历史轨迹回归，在该可选文件缺失时明确跳过。该文件记录旧 DOF 轨迹的能量，不属于新视频结果，源码快照不携带它。其他合成控制器、节点与数值边界测试正常运行。

冻结依赖为已有 `inference/package/custom_nodes/H3Study/`；其 core/layout/schedule SHA 仍由 loader 校验。PyTorch、ComfyUI、Flash Attention、模型与实验输入另行提供。本备份没有部署或启动任何推理任务。

## 验证入口

```sh
cd innovation/adaptive_strength_20261023/batch
python3 -m unittest test_audit test_summarize
cd results_tools
python3 -m unittest test_collect
```

方法包测试使用 PyTorch CPU 环境并设置 `CUDA_VISIBLE_DEVICES=''`。具体通过数量、可选跳过、秘密扫描与逐文件校验记录见 `CODE_SNAPSHOT_ANCHOR_20261023_VERIFICATION.json`。
