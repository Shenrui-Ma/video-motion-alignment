# 最终 Native pose 的原观察器离线资格统计

手帕最终 Native 的原观察器能检出约 15–16 帧延后，并留下 13 个合格窗口；书本、饮酒没有找到已缓存的最终 Native pose，因此这两例只报告 source 支持率，最终候选数留空。本次没有提取 pose 或运行 GPU。

| 案例 | 有效帧 / 总帧 | 窗口×特征行数 | source 支持行 | source/Native 支持行 | 可靠符号候选 | eligible |
|---|---:|---:|---:|---:|---:|---:|
| 书本 R122 long_0039 | 106 / 107 | 132 | 46 | 未测 | 未测 | 未测 |
| 饮酒 R123 short_0358 | 105 / 107 | 132 | 132 | 未测 | 未测 | 未测 |
| 手帕 R126 long_0059 | 144 / 158 | 186 | 37 | 37 | 18 | 13 |

支持行按原两种置信度 0.3/0.5 同时满足 coverage ≥ 0.8、有效帧 ≥ 8 计数；source 支持用自身 lag 0，source/Native 支持用双方 lag 0。132/186 的分母是 16/32 帧窗口、步长 4（含末端对齐窗口）与双臂/左臂/右臂三类描述符的组合，不是独立事件数。

手帕的 18 个可靠符号候选包括 17 个延后和 1 个提前。5 个候选未达到原 `min_gain > 0.5` 门槛，留下的 13 个全部是左臂延后：

- 12 个窗口的两种置信度均为 +15 帧，1 个均为 +16 帧，即 0.625–0.667 秒。
- 16 帧窗口：`[68,83] [72,87] [76,91] [80,95] [84,99] [88,103] [92,107]`。
- 32 帧窗口：`[56,87] [60,91] [64,95] [68,99] [72,103] [76,107]`。
- 原分组产生一个重叠组 `[56,107]`，代表窗口 `[92,107]`，lag +15，min_gain 0.8082。

手帕共有 149 行检测覆盖不足；另有 10 行在 ±2 帧容差内，5 个可靠符号候选的 gain 不足，其他拒绝包含平坦/多匹配相位。详细拒绝标签可重叠，见 `RESULTS.json`。这里使用原 confidence-only 规则；既有 content-boundary 诊断中排除画面外肘部后为 0 候选，记录在原 `h3-pose-content-boundary-review-20261020/R126_REPLAY_RESULT.json`，没有混入本次门槛。

这是最终成片的离线 eligibility；没有连续采样步的观察记录，因此没有运行在线 persistence，也没有产生在线 ON 结论。扫描 API 的 index=0 仅为参数占位。

## 复用与核验

原 R133、R138 和 R144 的九个相关扫描/特征/指标/候选/几何文件逐字节一致，复制到本目录 `frozen/`。只使用 CPU namespace 空初始化文件，避免导入节点和模型；原数值文件未改。输入 pose 的视频 SHA 与各例历史 Native/source 绑定核齐。手帕新扫描的全部 `windows` 与既有 R126 `actual/SCAN.json` 精确相等，重现 13 个候选；Ruff 通过，运行时确认未导入 torch。

书本/饮酒搜索过本地匹配消费者及 DevProjects 的现有 pose 文件，以及 .41 对应 MF case、R123 生产、R144 input_audit 和 .9 R122 生产目录。找到两例 source pose，未找到对应最终 Native pose；远端只读取目录元数据，结果存于 `HOST41_CACHE_SEARCH.json`、`HOST9_CACHE_SEARCH.json`。没有创建新提取任务。

复现命令：

```sh
cd /Users/researcher/DevProjects/h3-r144-final-native-observer-audit-20261020
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv/bin/python audit_final_native.py
```

`INPUTS.json` 记录原视频、pose、规则路径与 SHA；`RESULTS.json` 给出统计、全部候选和逐行拒绝理由；`long_0059_FINAL_NATIVE_SCAN.json` 保存完整诊断曲线；`FREEZE.json` 固定本次产物。R144 实现和 policy 均未修改。
