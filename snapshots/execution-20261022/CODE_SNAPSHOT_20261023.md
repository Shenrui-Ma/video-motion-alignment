# 2026-10-23 方法源码增量备份

本批次保存 feature_guidance、coverage_blend、adaptive_strength_20261023 的程序、测试和方法研究，以及自然任务边界交接与每任务尝试次数上限的代码模板。共 35 个源文件；逐文件原始与导出 SHA-256 见 `CODE_SNAPSHOT_20261023.json`。旧 `EXPORT_MANIFEST.json` 继续对应此前备份，本增量使用独立清单。

原始实验目录未修改。导出副本仅替换本机路径、账号路径、SSH 主机别名和 GPU UUID；需要恢复这些配置后再部署。未包含任务/部署 JSON、真实评测或审计结果、媒体、模型、缓存、凭据。`batch/build.py` 与 `publish.py` 还需要本地保留的输入及部署清单，本快照不能直接替代运行环境。

## 方法入口

- `innovation/feature_guidance/attention.py` 与 `controller.py`：基于参考时间切向的 DOF 动态强度和 pre-W_o 等能量 head 分配。
- `innovation/coverage_blend/attention.py` 与 `routing.py`：同帧分配与跨时间覆盖的混合。
- `innovation/adaptive_strength_20261023/design.md`、`research.md`：数学设计、原论文核查和近邻区别；研究假设与实现检验各自标明。
- `innovation/adaptive_strength_20261023/batch/audit.py`：完整 forward、有限值、DOF 统计和能量预算审计。
- `innovation/adaptive_strength_20261023/batch/summarize.py`：独立 cohort 配对汇总，官方九项指标、AWQ IS/CF、QA 适用范围及真实分母。
- `supervision/overnight_methods_20261023/boundary_guard.py`：完成当前批次后才交接已校验的代码和任务。
- `innovation/adaptive_strength_20261023/batch/durable_comfy_queue.after.py`：保留事务恢复逻辑的每任务 max_attempts 上限。

`feature_guidance/REVIEW.md` 是实现演进中的历史审查；其早期边界说明随后已调整。以当前 `attention.py` 为准：邻 bin 限于所选时间窗口，首尾 probes 不参与控制器统计，全部选中 bins 仍获得引导。这样避免单侧差分含 same-bin 造成自相关。该历史审查本身没有被重写。

## 恢复与验证

冻结 H3Study 的 core/layout/schedule 依赖已存在于 `inference/package/custom_nodes/H3Study`，本次确认其 SHA-256 与源文件和新 frozen loader 一致。Python/torch、Flash Attention、ComfyUI、模型与数据均需另行配置。

下列 CPU 审计与汇总测试只使用合成记录，不代表真实模型效果：

```sh
cd innovation/adaptive_strength_20261023/batch
python3 -m unittest -v test_audit.py test_summarize.py
python3 verify_queue_attempt_limit.py
```

完整方法测试需要已有 torch 环境；不要执行 `gpu_probe.py`，除非明确分配了测试设备。备份操作未启动任何 GPU、队列或服务器任务。测试结果与凭据/私有标识扫描证据另由提交时的验证记录给出。
