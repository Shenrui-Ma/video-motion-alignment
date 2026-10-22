# R144 观察器性能核查

**已完成 5 条已存 step 0–4 视频的 GPU 后端验证，所有自有进程与 CUDA 占用已释放。停止继续扩展 RGB 路线，代码保持独立诊断用途。**

## 慢在哪里

饮酒前 5 步现有记录，平均每次观察 208.05 秒。主采样进程在 `live_observer.py:39` 同步等待观察器。

|阶段|平均秒/步|真实代码位置|
|---|---:|---|
|解码、保存 RGB 视频及该阶段准备/释放|54.98|`scripts/run_observer.py:55`，`decode_live_child.py:239–268`|
|ONNX 人物检测阶段|77.66|`pose_probe.py:102` 固定 CPU；`:121–133` 前后处理与 session.run；`:189–191` 计时|
|TorchScript 姿态阶段|46.74|`pose_probe.py:103` CPU load；`:158–176` 五人裁剪批次、模型与后处理|
|其余逐帧读取、裁剪、选择及循环|2.62|`pose_probe.py:178–215`；由帧循环总时减上两项|
|原候选扫描|2.09|`scan_current_pose.py:29–48`，132 行|
|提取导入/加载/hash、序列化与扫描启动等残差|8.56|`pose_live_child.py:24–39` 内，扣除帧循环与扫描|
|进入上项计时前的验证/启动等残差|15.30|`pose_live_child.py:8–19`；`:10` 经 `transport.py:148–155` 重验外部文件 hash|

检测与姿态计时包含各自前后处理。8.56 / 15.30 秒是嵌套墙钟的差值，单独的模型加载耗时尚未打点。CPU 锁平均等待约 0.00008 秒。每一步重新启动进程并加载两模型，发生在 `run_observer.py:56–57` → `pose_live_child.py:22–24` → `pose_probe.py:81–109`。逐帧模型推理占主要时间。

当前检测到的所有人物都会进入 pose 批次（`:205–209`），然后才在 `pose_live_child.py:29–33` 过滤目标人物。本轮保持这一顺序。

## 5 条实测结果

固定原 MP4、模型 SHA、FP32、全 107 帧、RGB、640×640 detector 输入、288×384 pose 输入、5 裁剪批次、NMS 0.45 / 人物分数 >0.3、人物跟踪与原 policy；TF32 关闭。`.41` 原 CPU 为 Torch 2.11 / ORT 1.23，`.9` 实测为 Torch 2.5.1 / ORT 1.16.3，属于跨机工程验证。

|步骤|原 CPU 提取秒|GPU 提取秒|连续原 policy 动作（CPU/GPU 相同）|
|---:|---:|---:|---|
|0|118.86|28.43|OFF|
|1|130.29|25.99|OFF|
|2|127.61|16.92|ON，帧 44–59，α=1|
|3|129.87|17.34|OFF|
|4|128.46|17.12|ON，帧 72–87，α=1|

提取累计 **635.08 → 105.80 秒，6.00×**。这项加速对应保存视频到 pose 的阶段；原每步约 55 秒 VAE/RGB 阶段仍在前面。

- 五条解码 RGB SHA 完全一致；每帧检测人数、所选人物、目标范围过滤相同。
- ORT profile 实际 CUDA kernel 事件为 33,491 + 133,964；Torch 模型在 `cuda:0`。两次进程分别 35.04 / 88.54 秒，采样显存峰值 1,368 / 1,364 MiB。
- 五条共 660 行扫描，4 行离散诊断有变化：3 行 lag 变化，1 行 gain 跨过 0.5。五步最终 ON/OFF、物理窗口、latent bins、α、分组数及起停原因一致。
- 分数 ≥0.3 的关节最大坐标差 1.667 px，目标人物手臂最大 1.449 px。全 raw 最大差 174.70 px，来自 step 2 低置信右膝（约 0.200）；具体条目保存在 `comparison_all5/KEYPOINT_DETAIL.json`。
- 0.3 阈值共 1 次翻转，为未选中人物右膝 0.299996→0.300026；0.5 阈值翻转 0。

## 现有依赖与最小设备改动

`.9` 默认 ORT CUDA 插件需要 CUDA 11 / cuDNN 8。复用了本人已有 conda 缓存，在验证进程内设置：

```
LD_LIBRARY_PATH=/home/researcher/miniconda3/pkgs/cudatoolkit-11.8.0-h6a678d5_0/lib:/home/researcher/miniconda3/pkgs/cudnn-8.9.2.26-cuda11_0/lib
```

`pose_probe_gpu.py:80` 显式 GPU UUID；`:98–99` 关闭 TF32；`:119–122` CUDA ORT 与 FP32 TorchScript；`:184` 将同一批输入放到 GPU；`:271` 验证实际 provider 事件。其余观察规则沿用原脚本。`GPU_PATCH_PROVENANCE.json` 记录源 SHA 和修改范围。

`.41` ORT 1.23.2 的只读动态库检查也通过：已有 cuDNN 目录为 `/data3/researcher/ComfyUI/.venv/lib/python3.10/site-packages/nvidia/cudnn/lib`。该检查没有创建推理 session、没有初始化 CUDA。根据最新指示，`.41` 未执行 GPU 观察器验证或集成。

活动实现仍在 `pose_live_child.py:9`、`pose_probe.py:78/102–105`、`live_observer.py:51` 明确限定 CPU。独立 probe 保留这些差异的真实 provenance；生产文件保持原状。

## 释放与文件

目标仅 `.9 GPU2 / GPU-REDACTED`，两次启动均由 `BEFORE.json` 核验 free≥8 GiB。

|验证|GPU PID|UID|start_ticks|退出|
|---|---:|---:|---:|---|
|step 0|22090|1016|2651279298|0，世代消失、CUDA PID 消失|
|step 1–4|43874|1016|2651305351|0，世代消失、CUDA PID 消失|

`FINAL_RELEASE.json` 做了最后一次独立复核。原有 GPU2 进程 7231 / 16169 保持运行；未向其他任务发送信号。

本地目录：`/Users/researcher/DevProjects/h3-threecase-auto-evaluation-r144-20261020/performance_review/`

远端诊断目录：`/data5/researcher/h3_runs/r144_pose_backend_probe_20261020/`

核心记录：`SUMMARY.json`、`HOST41_READONLY.json`、`comparison_all5/RESULT.json`、`comparison_all5/KEYPOINT_DETAIL.json`、`FINAL_RELEASE.json`；原 CUDA profile 留在远端。复制/转发的资料为已存小 MP4 与 JSON，权重未传输。没有 H3 新推理、依赖安装或用户报告改动。
