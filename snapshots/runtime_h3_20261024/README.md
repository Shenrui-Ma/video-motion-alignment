# H3 实际运行源码快照（2026-10-24）

本目录把 short_0177 六配置实验使用的模型主干、编码器、双 VAE、采样器、量化实现、路由干预及输入输出链放在一个可按调用关系阅读的目录中。[完整阅读索引与精度说明](../../reports/research_sources_20261024/H3_RUNTIME_AND_PRECISION.md)。

| 目录或清单 | 内容与身份 |
|---|---|
| [core/](core/) | 运行中的 ComfyUI 0.35.0 源码副本：显式 H3 入口、静态本地 import 依赖、动态模型/编码器/VAE 选择项、tokenizer 资源。原运行树没有 `.git`，以逐文件 SHA 标识。 |
| [overlay/](overlay/) | 实际依赖覆盖目录的 comfy-kitchen 0.2.33、comfy-aimdo 相关 Python 源码、CUDA 头文件和原许可证。 |
| [external/](external/) | 该链路动态使用的外部 tokenizer 实现、配置和出处。 |
| [lane_gpu7/](lane_gpu7/) | 本轮 native / global_weak 通道的实际 H3Study、启动脚本、审计、作业图和配置。其它四配置见原六配置实验包。 |
| [headers/](headers/) | 四个 safetensors 权重的原始 JSON 文件头；只含名称、形状、dtype 与偏移。 |
| [HEADER_SUMMARY.json](HEADER_SUMMARY.json) | 文件头 SHA、存储精度、各层张量与几何汇总。 |
| [QUANTIZATION_METADATA.json](QUANTIZATION_METADATA.json) | DiT 和文本编码器的小型 `comfy_quant` 配置，逐项读取后解码；含读取字节量与 SHA。 |
| [SOURCE_INVENTORY.json](SOURCE_INVENTORY.json) | 实际来源、版本、文件 SHA、import 边、采集范围与编译扩展身份。 |
| [official_reference/](official_reference/) | MiniMaxAI 官方 Ref2VA 配置和模型许可；与实际 Comfy 运行源码分别保存。 |
| [kitchen_release_reference/](kitchen_release_reference/) | v0.2.33 的官方 CUDA/C++ 发布源码，含 INT8 线性与 ConvRot 计算；[固定 commit 和匹配记录](KITCHEN_RELEASE_MANIFEST.json)。 |
| [report_support/](report_support/) | 动作事件偏移、报告结果组装、旧展示生成器、模板与必要静态输入；[来源和已有媒体映射](report_support/SOURCE_MANIFEST.json)。 |
| [EXPORT_MANIFEST.json](EXPORT_MANIFEST.json) | 公开文件相对路径、原始 SHA、导出 SHA、大小和占位替换情况。 |

## 实验与结果连接

- [完整六配置实验](../execution-20261022/supervision/interval_short0177_20261024/README.md)：实际 graph、逐步路由、时间、输出 SHA、63 项数值指标和视觉事件。
- [本轮实际运行身份](evidence/ACTUAL_RUNTIME.json)：四个模型的既有全文件 SHA、现场 stat、实际软件版本与 21 个关键源码身份。
- [最终六配置验收](../execution-20261022/supervision/interval_short0177_20261024/ROOT_SIX_ARMS_VERIFIED.json)：20 次前向、每次 50 block、完整视频与配置绑定。
- [原生后端记录](../execution-20261022/supervision/interval_short0177_20261024/collection/native/backend.json)：已安装的后端与实际调用数量分别列出。

`lane_gpu7/` 的部署地址已替换为占位值；它保存历史完成作业的程序与参数。复现实验需配置本地模型、输入、设备与依赖。历史报告生成器包含输出保护，请阅读其入口和源数据绑定后使用。

## 来源、许可与复核

ComfyUI 保留 [GPL-3.0 许可证](core/LICENSE)，comfy-kitchen 保留 [Apache-2.0 许可证](overlay/comfy_kitchen-0.2.33.dist-info/licenses/LICENSE)和 [NOTICE](overlay/comfy_kitchen-0.2.33.dist-info/licenses/NOTICE)，其它第三方组件保留原目录中的声明。模型使用 [MiniMax-H3 Community License](official_reference/LICENSE)，原权重从官方及 Comfy Hugging Face 发布页取得。新增说明文件未改变各组件的许可归属。

外部依赖的 compiled `.so` 与模型大张量保留在原存储；清单记录版本、来源及已核验身份。CUDA 发布源码与已安装的 47 个 Python/header 文件逐字节一致，编译扩展的构建身份另以实际 `.so` SHA 记录。全部采集为文件读取，无模型推理与 GPU 负载。

在仓库根目录执行：

```bash
python3 tools/verify_runtime_snapshot.py
```

检查 SHA、文件大小、JSON、Python 语法和相对文档链接；无需安装 Torch 或加载模型。
