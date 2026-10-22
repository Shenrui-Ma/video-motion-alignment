# 最终 Native 的延后在原观察器中可见

已补齐书本、饮酒两例最终 Native 的 CPU pose。按原 R133/R138 候选规则，三例最终 Native 都有延后候选：

| 案例 | 有效帧 / 总帧 | source/Native 支持行 | 可靠符号候选 | 合格候选 | 合格 lag |
|---|---:|---:|---:|---:|---|
| 书本 R122 long_0039 | 106 / 107 | 46 / 132 | 延后 38 | 37 | +15 或 +16 帧，0.625–0.667 秒 |
| 饮酒 R123 short_0358 | 105 / 107 | 132 / 132 | 延后 97 | 93 | +10…+18 帧；中位/众数 +13，约 0.542 秒 |
| 手帕 R126 long_0059（复用） | 144 / 158 | 37 / 186 | 延后 17、提前 1 | 13 | +15 或 +16 帧，0.625–0.667 秒 |

分母为 16/32 帧窗口与双臂/左臂/右臂特征的组合。支持要求原置信度 0.3/0.5 同时满足 lag 0 的 coverage ≥ 0.8、有效帧 ≥ 8。合格候选继续经过原可靠 lag、共同支持及 `min_gain > 0.5` 规则；计数包含重叠窗口。

书本 37 个合格候选全部为左臂，26 个 lag +15、11 个 +16；合并 span `[0,95]`，代表窗口 `[12,27]`，lag +15，min_gain 0.9649。其主要拒绝原因是 93 行 lag 检测覆盖不足，1 个可靠延后候选的共同支持不足，另有平坦/多峰。

饮酒合格候选包含双臂 32、左臂 32、右臂 29 行；合并 span `[8,95]`，代表窗口 `[80,95]`，lag +12，min_gain 0.9328。lag 分布为 `10:1, 11:15, 12:16, 13:37, 14:18, 15:4, 17:1, 18:1`。4 个可靠延后候选因 gain ≤ 0.5 被拒；另有 19 行 lag 检测覆盖不足、9 行在 ±2 帧容差内，其余包含低收益/多峰及置信度间不一致。

这些是最终成片上的离线资格统计，没有连续采样步的观察记录，因此未评价在线 persistence。手帕使用原 confidence-only 规则；已有画面边界诊断中排除画面外肘部后候选为 0，该诊断未并入本次原规则。

## CPU 提取凭据

两例依次在独立目录 `/data4/researcher/h3_runs/r144_final_native_observer_audit_20261020/native_pose_completion` 执行。复用 source 的原 `pose_probe.py`、ONNX CPU detector 和 TorchScript CPU pose；四个权重/源码 SHA、软件版本及视频 SHA 均核齐。显式空 `CUDA_VISIBLE_DEVICES`、4 线程、仅 `CPUExecutionProvider`、`map_location='cpu'`、禁止下载。主体 selector 固定为书本 bbox x 中心 `[0.5,1.0]`、饮酒 `[0,0.4]`；保留原 largest/IoU 选择且不重新选择人，两例均未被 ROI 剔除帧。

| CPU 任务 | 启动 adjusted high | 结束 adjusted high | 用时 | 完成 / 子代际退出 |
|---|---:|---:|---:|---|
| 书本 | 57.83 GiB | 57.11 GiB | 125.27 秒 | 是 / 是 |
| 饮酒 | 56.99 GiB | 49.54 GiB | 142.24 秒 | 是 / 是 |

每例实际启动前均满足 ≥18 GiB，PSI 全量记录为诊断。运行结果及进程 UID/start_ticks/cmd hash 见各例目录的 `EXIT.json`、`CHILD.json`、`CAPACITY_BEFORE.json`、`CAPACITY_AFTER.json`；最终释放复查见 `PROCESS_RELEASE.json`。

`EXTRACTION_MANIFEST.json` 记录原视频、缓存模型、脚本、source pose 和 selector。`INPUTS.json` 绑定补齐的 Native pose；`RESULTS.json` 给出全部候选、lag 和拒绝理由。`frozen/` 原数值实现与旧审计相同，手帕完整扫描继续逐行重现历史结果。

原缺失状态审计保留在父目录，原 FREEZE SHA256 仍为 `cdd762fbc5099884a2cdb1c0ffbf741ad8e84f553e3d109cb69ab0a0e1956be7`。本子目录另有新 `FREEZE.json`。未修改线上 R144 或原策略。

仅重算现有 pose 的离线统计：

```sh
cd /Users/researcher/DevProjects/h3-r144-final-native-observer-audit-20261020/native_pose_completion
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv/bin/python audit_final_native.py
```
