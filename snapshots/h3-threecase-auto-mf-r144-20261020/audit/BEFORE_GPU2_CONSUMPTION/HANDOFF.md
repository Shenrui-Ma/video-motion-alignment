# R144 三例 automatic 的官方 IVEBench MF

状态：CPU 准备完成，等待真实自动成片及既有 runtime gate / release。未上传、未启动 GPU、未安装依赖。仅新增 automatic 各 1 次 tracker，合计 3 次；复用 3 份源轨迹和 6 个 Native/fixed 分数。

本地：`/Users/researcher/DevProjects/h3-threecase-auto-mf-r144-20261020`

目标：`H3_SERVER_B:/data4/researcher/h3_runs/threecase_auto_mf_r144_20261020`

| 任务 | 既有对照 | 有效帧 / 全输出帧 | Native MF | fixed MF |
|---|---|---:|---:|---:|
| 饮酒眼镜 short_0358 | R123 full_context | 105 / 107 | 0.8917583268279772 | 0.8810650134062523 |
| 书本 long_0039 | R122 generic_retention | 106 / 107 | 0.8777332312340698 | 0.8626603286262191 |
| 手帕 long_0059 | R126 full_context | 144 / 158 | 0.8050170051044884 | 0.8037195712200009 |

沿用 24 fps、有效前缀、`crop=1280:720:16:8,trim=end_frame=N,setsar=1`；lossless H.264 qp0 / yuv420p 的 score 视图逐帧核对原视频裁剪像素与 PTS。不评估 padding、拼图或字幕覆盖视频。官方 commit `2dcf8900ee65197f43854c76f61c66a32bb8dbfc`；CoTracker3 offline、grid10、query frame0、backward=false、window60、max_frames=None；权重 SHA `da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df`。官方轨迹匹配公式不变。

书本原 INPUTS 的 `source_cache=null` 表示那批首次生成源轨迹；已完成结果中的 `source_report` 精确绑定现成源轨迹，当前已校验后转为缓存。源视频、score 视图、报告、轨迹和 remote 路径均列在 `audit/SOURCE_CACHE_VERIFIED.json` 与 `audit/REMOTE_REUSE_PLAN.json`。

成片后逐例执行（将四个变量设为实际收集文件与 root 选定的新 inventory ID）：

```sh
R144_MF=/Users/researcher/DevProjects/h3-threecase-auto-mf-r144-20261020
PYTHONDONTWRITEBYTECODE=1 python3 "$R144_MF/audit/bind_automatic.py" \
  --case "$R144_CASE" --gate "$R144_ONLINE_GATE" \
  --release "$R144_ROOT_EXIT" --video "$R144_RAW_AUTO_MP4" \
  --inventory-id "$R144_AUTO_INVENTORY_ID"
```

`R144_CASE` 依次为 `short_0358`、`long_0039`、`long_0059`。每例 producer 目录为 `/data4/researcher/h3_runs/threecase_auto_r144_20261020/cases/{case}/`；gate 为 `analysis/postrun/ONLINE_RUNTIME_GATE.json`；退出记录使用该次实际 `audit/root_.../ROOT_EXIT_RECEIPT.json`。Gate 必须通过、run 必须为 `r144_{case}_seed2026101701_visible_only`、视频 SHA/帧域须一致、service 及其退出世代须完全匹配。零触发也以真实 automatic 成片计分并保留实际触发结果。

三例绑定完成后，在本地封存：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 "$R144_MF/audit/finalize.py" --gpu "$R144_MF_GPU_UUID"
```

Root 检查最终 `SEAL.json` 后，写入沿用的 `ROOT_REVIEW.json`：`passed=true`、`GPU_execution_authorized=true`、正确的 `seal_sha256` 与 `gpu`。这次准备封存不授权启动。将 `audit/DEPLOY_FILES_AFTER_FINALIZE.txt` 中的小文件和新增 automatic 视频上传目标目录，再单独上传 root review；runtime/source cache 均使用已有远端文件，不上传或重算。

目标机 CPU 检查与启动命令：

```sh
cd /data4/researcher/h3_runs/threecase_auto_mf_r144_20261020
PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python audit/materialize_existing.py
PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python audit/verify_inputs.py
R144_MF_GPU_UUID=$(/data3/researcher/ComfyUI/.venv/bin/python -c 'import json; print(json.load(open("configs/RUNTIME.json"))["gpu"])')
CUDA_VISIBLE_DEVICES="$R144_MF_GPU_UUID" PYTHONDONTWRITEBYTECODE=1 \
  nohup /data3/researcher/ComfyUI/.venv/bin/python scripts/run_batch.py \
  --attempt actual_context_mf_attempt1 --gpu "$R144_MF_GPU_UUID" \
  --review ROOT_REVIEW.json --maximum-new-trackers 3 \
  > audit/launcher.log 2>&1 < /dev/null &
```

按 R141b 原生命周期串行运行；逐次 admission 与 ready/go 均重新核验显存≥40 GiB、cgroup/host memory、OOM、现存作业。先完成自动生成并确认实际服务及 observer 释放；本包不登记跨任务 peer、不改其他目录。保护既有 PID1646285 / UID1004 / start_ticks20299235 / GPU5 / port8189，精确身份见 `configs/EXISTING_SERVICES.json`。仅 `run_batch.cleanup` 做了 PID 世代修正，其他 9 个执行脚本和 4 个辅助脚本逐字复用 R141b。

Wrapper 真正退出后执行：

```sh
PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python \
  audit/final_release.py --attempt actual_context_mf_attempt1
```

随后在本地执行 `PYTHONDONTWRITEBYTECODE=1 python3 "$R144_MF/audit/collect.py"`，交给唯一 inventory owner 的内容是 3 个 `results/{case}/automatic.json`、`audit/RESULTS_VERIFIED.json`、`audit/FINAL_RELEASE_VERIFIED.json`；当前包不写 inventory 或展示页。

CPU 证据：11 项测试覆盖源协议、书本已完成缓存晋升、真实 gate 格式、错帧域/错 case/错服务世代拒绝、observer 未释放拒绝、旧 PID 复用不等待也不发信号。三例原始裁剪像素和 PTS 已实查；.41 的 60 个现存报告/轨迹/数值代码文件 hash 已只读核对。目标权重目前仅检查存在与大小，启动前 `verify_inputs.py` 必须重新核对实际权重 hash。真实 automatic 视频尚未出现，未进行其绑定、tracker 或评分。
