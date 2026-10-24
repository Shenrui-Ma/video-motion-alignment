# short_0177 独立官方指标评测

本轮已于 2026-10-24 19:29:34（北京时间）完整完成：参考视频与六个新成片共 7 个视频，63 项数值指标全部 done，7 个 QA N/A，0 失败；每项实际评分只有 1 次 attempt。结果直接复用本目录文件。

19:15:17 在 .81 空闲 GPU2（UUID `GPU-REPLACE-WITH-DEVICE-UUID`）启动，UID 1016、boot `1c482131-87c4-4d3f-9db6-de1cc593c5be`，run PID 27382/start 795358586、durable PID 27390/start 795358610。总耗时 857.585 秒；run、durable 与全部 metric worker 自然退出，exit code 0。19:31:14 现场核验 GPU2 无计算进程、24214 MiB 空闲、利用率 0%。

本地交付入口：

- `SUMMARY.json`：7 方法完整九指标及原始结果行；SHA `f3b0ebda813f84223206a908c51231f9e54f6134bc67e9ab3da56664e6e5011d`。
- `raw/evaluation/results/`：70 个原始指标 JSON、7 个 job JSON、63 份运行日志；`raw/evaluation/states/` 保留 63 个单次 attempt 记录。
- `RUN.json`、`LAUNCH_RECEIPT.json`、`EXIT.json`、`POST_EXIT.json`：身份、启动条件、自然退出及 GPU 释放现场。
- `FINAL_VERIFIED.json`：63+7、各项单次尝试、视频与 manifest/job/cohort 绑定、官方 commit、结果 SHA、完整退出检查通过。
- `RAW_BUNDLE_RECEIPT.json`、`raw_bundle.tar.gz`：227 个完整归档文件及 SHA；包含部署源码、预检、取帧 metadata 与全部运行日志。
- `PREFLIGHT.json`：162 个共享源码 SHA、7 视频上传 SHA、每条 60 个有效帧通过；`prepared/PREPARED.json` 保留 root 完成 gate 与七视频原始 SHA/probe。

部署时 CPU 取帧发现登录 PATH 未包含既有 ffmpeg。按原 `metrics/watch_outputs.py` 的入口，将 `/data3/research-user/vsr11/bin` 加到此次评测进程 PATH；实际 ffmpeg 7.1.1，SHA `328c15c06f1f62faf35aab6d5756bea04e25db51e1615e3ad85b5b82341f8a9b`。`FFMPEG_PATH_RECEIPT.json` 与 `raw/CPU_PREFLIGHT.log` 保存处理证据，评分源码与公式保持原样。原始评测库为 Torch `2.6.0+cu124`。

source/source MF 实测 1.0。各成片 MF：native 0.713849164、early 0.719503110、fixed 0.714032349、late 0.709743831、split 0.722347596、global_weak 0.702639363。其余八项完整数值见 `SUMMARY.json`。

## 数据及指标口径

- 方法：source、native、early、fixed、late、split、global_weak。
- 原始视频统一为 73 帧、1312×736、24 fps；评分取前 60 个有效帧，crop `[16,8,1280,720]`，保持既有 short_0177 口径。
- 官方 metadata 与指令：`Replace the tiger with a lion`；seed `2026101701`。输入源 SHA 为 `d5da95935608029e1c458def4cb1c09a3ce42ea7e6d60cc9a44c9c6575f801f2`。
- 九项：subject_consistency、background_consistency、temporal_flickering、motion_smoothness、vtss、overall_semantic_consistency、phrase_semantic_consistency、semantic_fidelity、motion_fidelity。
- QA 官方只适用于 quantity_modification；本任务 category 为 subject_editing，因此 7 条均记 N/A。
- source/source 的 MF 重新实际计算，各编辑 MF 相对参考差为 `MF(source, edited) - MF(source, source)`。
- V1.1 展示九项数值与动作标注；AWQ 指令／内容评分另列。原精度 IS/CF 未运行。本次新七视频的 IS/CF、AWQ 均未运行，输出状态明确保留；历史其他视频分数不代入新片。

## 运行与隔离

目标主机 `H3_HOST_CONFIGURE_LOCALLY`（.81），UID 1016。隔离目录：

```text
/data/research-user/h3_metrics_interval_short0177_20261024
```

只读复用既有 runtime：

```text
/data/research-user/h3_metrics_20261022/venv/bin/python
/data/research-user/h3_metrics_20261022/code/official_source
/data/research-user/h3_metrics_20261022/code/dino
/data/research-user/h3_metrics_20261022/code/model_paths.yml
/data/research-user/h3_metrics_20261022/weights
```

官方 commit `2dcf8900ee65197f43854c76f61c66a32bb8dbfc`。`metric_worker.py`、`durable_metrics.py`、`prepare_frames.py` 是既有已运行文件的字节相同快照。`HOST81_READONLY.json` 固定 162 个远端评测源码文件 SHA，启动前逐项复核。实际模型文件与运行库记录在 `MODEL_INPUTS_READONLY.json`。本次只新增输入、帧缓存、结果与监督文件。

只读资源检查时 .81 GPU1/2/3/4 各有 24214 MiB 可用，旧 metric_service/metric_worker/durable_metrics 无活进程。资源快照时间见 `HOST81_READONLY.json`。root 启动时重新选卡；执行器接受显式 UUID，并要求该卡没有 compute 进程、显存余量至少 18000 MiB。

## 七个视频的上传位置

所有 source 和六个成片都上传，复用权重，无权重搬运：

```text
<isolated_root>/videos/source.mp4
<isolated_root>/videos/native.mp4
<isolated_root>/videos/early.mp4
<isolated_root>/videos/fixed.mp4
<isolated_root>/videos/late.mp4
<isolated_root>/videos/split.mp4
<isolated_root>/videos/global_weak.mp4
```

source 原文件：`/workspace/research-user/DevProjects/video-motion-alignment/execution-20261022/inference/host9b/input/short_0177_video.mp4`。六个成片使用 root 本轮完成审计后的本地文件路径。原文件不修改、不重新编码。

帧处理生成 `<isolated_root>/frames/<method>/short_0177/000001.png ... 000060.png`。全部指标通过官方 metadata 指向这些目录；MF、SF 等需要 source 与 target 两侧，质量与文本指标使用 target 帧及原官方 metadata。

| 指标 | 复用模型与文件 |
|---|---|
| SC | `weights/dino_deitsmall16_pretrain.pth`，官方 DINO ViT-S/16 架构 |
| BC | 用户缓存 `.cache/clip/ViT-B-32.pt`，CLIP ViT-B/32 |
| TF | 帧像素计算，无模型 |
| MS | `weights/amt-g.pth`，官方 `quality/amt/cfgs/AMT-G.yaml` |
| VTSS | `weights/infer.pth`，官方 Koala 配置 |
| OSC、PSC、SF | `weights/VideoCLIP-XL-v2.bin`，官方 VideoCLIP-XL-v2 |
| MF | `weights/baseline_offline.pth`，CoTracker3 |

## 本次准备与执行步骤（历史记录）

1. 复制 `bindings.example.json` 为本目录下的 `bindings.json`，填入全部七文件绝对路径与真实 SHA。`completion_gate` 指向 root 的六 arm 完成审核 JSON；该文件必须有 `passed: true`。准备器还会独立核视频 SHA 与 ffprobe 几何。

2. 在本目录执行本地 CPU 准备，`prepared` 必须为新目录：

```sh
python3 prepare_metrics.py --bindings bindings.json --output prepared
```

3. 上传七视频与最小执行代码，并运行远端 CPU 取帧／哈希检查：

```sh
python3 deploy_metrics.py --prepared prepared
```

部署器要求隔离远端目录首次创建；若上传中断，先核已有文件和哈希，再补齐上传。它不会调用 CUDA 评分。

4. root 现场确认空闲 GPU UUID 后启动恰好一轮。示例 UUID 对应既有 GPU2，实际采用现场选定值：

```sh
ssh H3_HOST_CONFIGURE_LOCALLY 'nohup /data/research-user/h3_metrics_20261022/venv/bin/python -u /data/research-user/h3_metrics_interval_short0177_20261024/code/run_metrics.py --execute --gpu GPU-REPLACE-WITH-DEVICE-UUID > /data/research-user/h3_metrics_interval_short0177_20261024/run.log 2>&1 < /dev/null &'
```

执行器有独占锁；每个实际指标独立进程、单次尝试、40 分钟超时，七视频完成后退出。成功项按本隔离结果复用，失败项保留日志。无后台常驻调度、无恢复旧队列的动作。运行身份、boot、GPU UUID、manifest SHA 写 `RUN.json`。

## 报告接入

- `prepared/manifest.json`：7 个 `jobs`，ID 为 `interval20261024_short_0177__<method>`，cohort 为 `interval_short0177_20261024`。
- 远端 `evaluation/results/<job_id>/<metric>.json`：官方原始分数、实际运行库、seed、耗时、结果明细。
- 远端 `SUMMARY.json`：`rows`、`method_scores`、`numeric_done/expected_numeric=63`、`qa_not_applicable=7`、失败数、IS/CF 状态及 source-self MF 差。
- `rows` 保留 `job_id/task_id/method/cohort/metric/status/score`；报告 Agent 已确认此契约。`SUMMARY.passed` 仅在63项全部done、7个QA N/A、0失败时为true。
- 本目录五个 CPU 单元检查覆盖七项齐备、完成门槛、缺 arm、SHA 变化和源 SHA 错误；本轮正式评分及最终原始结果核验均已通过。
