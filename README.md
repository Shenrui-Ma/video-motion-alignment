# Video Motion Alignment

研究视频编辑与动作迁移中的动作时间错位，以及推理阶段的时序控制。当前主要实验模型为 MiniMax H3，素材来自 FlexiAct 和 IVEBench。

本仓库是研究源码备份，保存主要方法、实验版本、运行脚本、评测代码、提示词与展示页生成器。各版本放在 `snapshots/` 下，名称对应本地实验目录，方便恢复与核对历史修改。

## 2026-10-22 代码备份

最新批次代码位于 [execution-20261022 快照](snapshots/execution-20261022)。包含冻结的时间对齐 Attention、持久推理队列、服务器进程管理、IVEBench 评测与三项待 GPU 验证的独立实现。

- [按修正方向调整 heads 与强度](snapshots/execution-20261022/innovation/direction_runtime)：17 项 CPU 测试通过；层范围手动指定。
- [部分时间 RoPE 频带补偿](snapshots/execution-20261022/innovation/partial_rope)：23 项 CPU 测试通过。
- [跨时刻参考覆盖分配](snapshots/execution-20261022/innovation/temporal_coverage)：22 项 CPU 测试通过。
- [R148 相位组合](snapshots/h3-timing-phase-combined-r148-20261020)、[R150 区间对照](snapshots/h3-guidance-schedule-r150-20261021)、[双向 Attention](snapshots/h3-reference-feedback-r151-20261021) 保留对应实现及配置。

原始运行目录及用户手工编辑的报告保留在本机；本仓库同步脱敏副本。模型、素材与成片继续保存在实验服务器。恢复运行前需重新配置服务器、路径与设备标识。

## 早期代码入口

| 内容 | 路径 |
|---|---|
| 参考 Attention 输出的时序重分配 | [R113 / H3TemporalRouter](snapshots/h3-timing-oxygen-seed-replication-r113-host41-20261019/extensions/H3TemporalRouter) |
| 对应点匹配与跨时刻 Value 读取 | [R115 / H3TemporalRouter](snapshots/h3-timing-ive-long0174-correspondence-r115-20261019/extensions/H3TemporalRouter) |
| 自动窗口与在线动作观察器原型 | [R86 / H3AutomaticWindowRouter](snapshots/h3-timing-oxygen-online-r86-20261018/extensions/H3AutomaticWindowRouter) |
| 原始架构实验与分析 | [R2](snapshots/h3-timing-architecture-r2-20261016) |
| 配对推理、噪声与时间轴核验 | [R113 / postrun](snapshots/h3-timing-oxygen-seed-replication-r113-host41-20261019/analysis/postrun) |
| 按任务展示实验结果 | [展示页生成器](snapshots/h3-benchmark-all-results-showcase-20261018/scripts/build_task_showcase.py) |
| 实验视频清单与已有指标 | [实验清单](snapshots/h3-benchmark-all-results-showcase-20261018/inventory) |

## 实验协议

普通编辑与引导编辑使用相同提示词、输入、随机种子和采样设置。先检查人物或物体编辑是否完成，再比较动作顺序、幅度和事件发生时间。官方 Motion Fidelity 与逐事件时间检查分别记录，保留失败和效果接近的结果。

2026-10-19 起，新实验优先逐字使用 benchmark 提供的任务文本：IVEBench 使用 `edit_prompt`；FlexiAct 保留对应官方任务描述。提示词写法的变化单独作为实验变量。此前已有简短指令、六段 H3 适配提示词等历史版本，均按实际记录保留。

当前固定引导在部分样例中改善局部事件时间。对应点 Value 读取的新增实验表现接近普通编辑。自动观察器仍有可见性与触发覆盖问题；各实现的实际状态以对应实验记录为准。

## 备份与恢复

`EXPORT_MANIFEST.json` 记录每个源文件和导出文件的 SHA-256。上传前对凭据、账号路径和服务器标识做了处理。模型权重、视频、图片、latent、运行环境和第三方 vendor 目录另行存放。

恢复到新机器时，需要配置模型、数据及服务器路径，并重新生成部署清单。历史代码中保留的文件哈希描述原始实验；脱敏后的文件使用 `export_sha256` 校验。该快照保存研究过程，运行入口及依赖以具体实验目录的配置为准。

校验本次备份文件：

```bash
python3 tools/verify_export.py
```

## 数据与方法来源

- [FlexiAct](https://github.com/shiyi-zh0408/FlexiAct)：将参考视频中的动作迁移到目标图片主体，允许目标场景和构图变化。
- [IVEBench](https://github.com/RyanChenYN/IVEBench)：根据编辑指令修改原视频，评估编辑完成与保留内容。
- 论文与社区实现的具体引用保留在相关方法说明中。参考 Attention、时空对应和位置编码等已有思路的来源应随后续论文继续列明。

本仓库尚未统一整理为可安装的软件包。第三方依赖各自适用其原许可；当前备份不新增对第三方代码的许可授权。
