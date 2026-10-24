# short_0177 发布集合与验收

本文件是本次实验结果发布操作说明。代码准备阶段只读取仓库与现有结果，没有修改正式 HTML、运行 Git 提交或推送。

## 现有仓库约定

- 远端仓库：`https://github.com/Shenrui-Ma/video-motion-alignment.git`。
- `execution-20261022/` 与本地 `reports/*` 默认忽略。实验文本使用 `snapshots/execution-20261022/` 脱敏快照。
- `reports/cloud/**` 与 `reports/research_sources_20261024/**` 显式允许纳入 Git。媒体按原始字节 SHA-256 命名，单文件上限沿用 95 MiB。
- `tools/export_reports.py` 负责将单文件报告中的内嵌媒体抽出，并保留可离线使用的相对路径。
- `tools/export_handoff.py` 提供既有文本脱敏与确定性 gzip 规则。其现有监督目录白名单不含本次 short_0177；整次运行还会遍历其他实验 MP4。
- 私人 `reports/handoff_20261024/` 保持本地。此次导出使用明确的 short_0177 文件集合。

## 本次文件范围

| 发布路径 | 内容与关联 |
|---|---|
| `snapshots/execution-20261022/supervision/interval_short0177_20261024/` | 源事件、冻结参数、本轮 v3 graph / router / queue / worker 实现、六条收集回执和运行审计、逐步计时、评分代码与逐条指标、视觉标注、报告数据与生成代码 |
| 同目录 `collection/{native,early,fixed,late,split,global_weak}/` | `result.json` 的 job / attempt / video SHA 关联 `router.json`、`timing.json`、`verified.json`、评分 manifest 和最终报告 |
| 同目录 `ROOT_SIX_ARMS_VERIFIED.json`、`ROOT_SIX_ARMS_BINDINGS.json`、`verify_six_local.py` | 六路完整成片验收、七视频绑定与实际本地验证代码 |
| 同目录 `ALL_LANES_EXIT_VERIFIED.json`、`report/MEDIA_VISUAL_VERDICT.json` | 三条通道的进程/API退出证据，以及生成对照媒体的视觉验收 |
| 同目录 `EXPORT_MANIFEST.json` | 原始文本 SHA、导出文本 SHA、源目录映射、全部本次媒体位置、两个 cloud 报告的媒体引用 |
| 同目录 `README.md` | 结果、源码、指标、标注入口，以及原片和逐帧审阅接触表的相对媒体链接 |
| `reports/cloud/R150_十组引导区间对照_单文件.html` | 10 个 IVE、1 个 Flex、4 个历史例子；其余例子完整保留 |
| `reports/cloud/视频编辑中动作时间对齐-研究进展V1.1.html` | 已在本地发布的增量小节副本 |
| `reports/cloud/assets/<sha256>.<ext>` | 六条新输出原片、源视频、七列对比视频、同帧图、各方法审阅接触表及 REVIEW 引用的全分辨率帧；保留原始媒体字节 |
| `reports/cloud/manifest.json` | 仅替换上述两份报告的记录，重算媒体索引，其余报告记录保留 |
| `reports/research_sources_20261024/EXPORT_MANIFEST.json` | 在原有文件和媒体记录中合并本次集合 |

不纳入此集合的文件包括：旧失败尝试、服务器占用调查、权重、GPU 原始张量、私人 CVPR 交接文档。失败运行的本地证据继续保留。

文本记录中机器路径、SSH 别名和 GPU UUID 按已有规则处理。原始文件 SHA 与导出 SHA 同时保存；视频和图片 SHA 保持原值。报告中的样例身份、指标、α、采样步数和事件区间保持原值。

## 完整 gate

`export_completed_cohort.py` 在写发布目录前检查：

1. `collection/LOCAL_COLLECTION.json` 六配置全部完成、无收集错误；各本地文件的大小与 SHA 匹配收集回执。
2. 每条 `verified.json` 通过，20 个完整 forward、1000 个 block；最终计时通过且具有20步。
3. 报告 INPUT、视频 SHA、实际 attempt、路由步集合、7条评分作业、63项有限数值、7项 QA 不适用状态相互匹配。
4. `ASSEMBLY_GATE.json` 的三个输入文件 SHA、六份 root_verified REVIEW SHA 与冻结源事件 SHA 相符，指标状态已完整；最终视觉标注使用冻结的两条源事件及源区间。共同事件为0时 MAE保留 null；单方法可见事件和覆盖数继续保存。输入组装说明、媒体绑定和验收文件一并导出。
5. `report/PUBLISHED.json` 为已发布状态，正式 R150 / V1.1 的 SHA 与该回执一致；R150为15例且主 IVE 为10例。
6. 所有待导出媒体 SHA 正确，单文件不超过95 MiB。

## 执行命令

以下相对路径从仓库根目录执行。先按本次报告说明完成 `build_reports.py --publish`，然后：

```sh
python3 execution-20261022/supervision/interval_short0177_20261024/report/export_completed_cohort.py
```

默认只做 gate 和容量计算，写入本地 `report/PUBLICATION_PLAN.json`。其中列出每个快照、媒体目标、各媒体字节数与文本总容量。检查通过后执行：

```sh
python3 execution-20261022/supervision/interval_short0177_20261024/report/export_completed_cohort.py --export
```

导出结束会再次核对全部本次文本与媒体 SHA，以及两个 cloud 报告的每个相对媒体引用，写入本地 `report/PUBLICATION_EXPORT.json`。其中 `stage_paths` 是本次相关文件的精确集合，交由主线程按原有 Git 约定提交与推送。脚本自身不运行 Git。

不要仅复制两个 cloud HTML；应保留 `assets/` 及其相对目录。原始成片另在本次快照 README 和导出清单中链接。

## 当前容量与验证

准备时可读的源视频为 **17,720,446 bytes**，native 成片为 **2,806,661 bytes**。已备 v3 文本集合为 **82个文件、535,669 bytes**；当时9张已生成接触表合计 **3,998,104 bytes**。其余配置、完整评分与最终对比媒体由完成后的 `PUBLICATION_PLAN.json` 给出精确容量。

现有 cloud 共有10份报告、446个去重媒体、713,223,519 bytes。增量导出沿用已有 SHA 地址，重复资产不再存第二份。

已执行的验证：

- 实际未完成数据调用默认命令，返回 `All six immutable collections must pass before export`，无导出文件写入。
- 两项独立发布测试：未完成 gate 在报告检查前退出；隔离临时仓库内完成脱敏、SHA媒体去重、两份报告更新、旧报告与旧索引保留、逐文件验证，私人交接文档未进入集合，输入文件保持原样。
- 8项报告测试覆盖完整合同、旧14例保留、Flex独立展示、缺失事件MAE为 null、动作均值有效分母6/10与旧6例数值一致。

```sh
cd execution-20261022/supervision/interval_short0177_20261024/report
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_reports.py test_publication_export.py
```

网页验证继续使用离线 HTML / JavaScript 与媒体逐帧检查；不启动网页服务器或切换浏览器。
