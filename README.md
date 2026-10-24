# Video Motion Alignment

动作细粒度控制视频编辑研究。现有实现基于 MiniMax H3，在 MM Self-Attention 中调节生成视频 query 对参考视频 tokens 的时间读取；数据与任务来自 FlexiAct、IVEBench 及记录在案的历史素材。

## 报告与已有结果

- [研究进展 V1.1](reports/cloud/视频编辑中动作时间对齐-研究进展V1.1.html)：方法、同帧对照、实际结果与历史状态。
- [全部报告与视频展示](reports/cloud/README.md)：下载整个 `reports/cloud/` 后离线打开 HTML，保留 `assets/` 相对位置。
- [相关工作资料](reports/RELATED_WORK_RESEARCH_20261024.md)：论文的机制、模型、指标、来源与阅读覆盖。
- [相关论文完整来源索引](reports/research_sources_20261024/literature_sources.json)及[数据集与评测来源](reports/research_sources_20261024/benchmark_sources.json)。
- [实际 H3 架构、精度与完整推理链路](reports/research_sources_20261024/H3_RUNTIME_AND_PRECISION.md)：四个权重组件、pruned/INT8 ConvRot/NVFP4 的实际语义、从输入到成片及指标的源码位置。

2026-10-24 最新区间展示包含 **10 个 IVEBench、1 个 FlexiAct 和 4 个历史样例**。新增 short_0177「老虎替换为狮子」已完成六配置、63 项数值指标和逐事件标注，见 [R150 展示](reports/cloud/R150_十组引导区间对照_单文件.html)及[完整证据](snapshots/execution-20261022/supervision/interval_short0177_20261024/README.md)。

当前用户选定固定弱引导 α=.25。direction、partial RoPE、coverage、多种动态强度与分配方法已有 GPU 实验，内部 Attention 诊断也保存了实际读取结果。具体效果以配对指标、视频和审计记录为准。研究推理与评测队列当前按用户要求暂停；本次同步只整理已有资料。

## 实现与完整证据入口

| 资料 | 位置 |
|---|---|
| 当前固定 Attention 引导 | [H3Study](snapshots/execution-20261022/inference/package/custom_nodes/H3Study/) |
| 实际 H3 主干、加载器、编码器、VAE、采样及量化源码 | [2026-10-24 实际运行源码包](snapshots/runtime_h3_20261024/README.md)、[按推理链路阅读](reports/research_sources_20261024/H3_RUNTIME_AND_PRECISION.md) |
| 早期冻结模型与包装层 | [冻结模型来源](snapshots/execution-20261022/innovation/signed_phase_calibration_20261023/replay_live_pair/sources/) |
| 旧 main10（9 IVE + 1 Flex）完整指标 | [main10](snapshots/execution-20261022/summaries/main10_20261022/) |
| 旧 main10 逐事件时间标注 | [event_offset_completion](snapshots/execution-20261022/timing/event_offset_completion_20261022/) |
| 第十个 IVE 的六配置完整结果 | [short_0177](snapshots/execution-20261022/supervision/interval_short0177_20261024/README.md) |
| direction / coverage / partial 等结果 | [innovation summaries](snapshots/execution-20261022/summaries/innovation_20261022/) |
| 扩展二十对完整九指标 | [extension_metrics.json](reports/research_sources_20261024/evidence/extension_metrics.json) |
| 昨夜23条动态/控制实验 | [完整指标、实际曲线、分组结果](snapshots/execution-20261022/innovation/adaptive_strength_20261023/batch/results_tools/latest/) |
| field同环境饮酒复验 | [FINAL_PAIRED_1451.json](snapshots/execution-20261022/supervision/field_environment_reproduction_20261023/FINAL_PAIRED_1451.json) |
| Attention内部诊断 | [signed_phase_calibration](snapshots/execution-20261022/innovation/signed_phase_calibration_20261023/) |
| IVEBench评测实现 | [metric_worker.py](snapshots/execution-20261022/metrics/metric_worker.py)、[官方源码](snapshots/execution-20261022/metrics/official_source/) |
| 早期完整样例清单 | [FlexiAct / IVEBench inventory](snapshots/h3-benchmark-all-results-showcase-20261018/inventory/) |
| 所有已同步研究文件 | [PROJECT_FILE_INDEX.json](reports/research_sources_20261024/PROJECT_FILE_INDEX.json) |
| 本地视频和报告媒体映射 | [MEDIA_INDEX.json](reports/research_sources_20261024/MEDIA_INDEX.json) |

## 仓库与恢复

`snapshots/` 按原研究目录保存源码、配置、测试、实验和分析。`snapshots/execution-20261022/` 是最新统一流水线及后续方法的公开副本。早期各目录中的计划、“待运行”和运行约束均保留原时点记录；后续实际完成记录与对应结果同时存在。

```bash
git clone https://github.com/Shenrui-Ma/video-motion-alignment.git
cd video-motion-alignment
python3 tools/verify_export.py
python3 tools/verify_handoff.py
python3 tools/verify_runtime_snapshot.py
```

[历史导出清单](EXPORT_MANIFEST.json)与[本次资料清单](reports/research_sources_20261024/EXPORT_MANIFEST.json)记录原始 SHA、公开副本 SHA 和文件位置。大于 5 MiB 的科学文本以完整无损 gzip 分发，可用 Python 的 `gzip.open(path, 'rt')` 读取。媒体按 SHA 去重，保留原文件字节。

本仓库是研究快照，尚未整理成单一可安装软件包。服务器路径和设备标识已替换为配置占位符；模型权重、原始大张量及部分服务器全分辨率视频有独立存储。公开包包含可访问视频、原始指标、输入/输出 SHA 和来源记录。用户手工报告与本地实验目录保持原样。

## 数据和代码来源

- [FlexiAct](https://github.com/shiyi-zh0408/FlexiAct)
- [IVEBench](https://github.com/RyanChenYN/IVEBench)
- H3及所用社区实现、其它论文与仓库见相关工作来源记录。

第三方代码、数据和模型各自适用其原许可；本备份不新增对第三方内容的许可授权。
