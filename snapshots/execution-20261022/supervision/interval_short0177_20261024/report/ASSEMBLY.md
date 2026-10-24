# 本轮报告输入组装

`assemble_inputs.py` 只读取本地收集与审阅证据，输出文件位于本目录。正式报告生成仍由 `build_reports.py` 执行。

## 门槛与输出

- `collection/LOCAL_COLLECTION.json` 的六路全部完成；逐路重新校验收集文件 SHA、v3 attempt、20×50 路由、20 步计时、原始成片和后端验收。
- 六份 `visual/<method>/REVIEW.json` 都为 `review_completed: true`、`root_verified: true`，源事件文件 SHA、成片 SHA 与 60 帧审阅范围相符。
- `ANNOTATION.json` 合并原有两项冻结事件，原样保留各方法的 status、output_interval、offset、evidence 与完整 REVIEW；缺失事件保留 null，独立观察的动作放在 `observable_actions_by_role`。
- `MEDIA_BINDINGS.json` 按参考、native、early、fixed、late、split、global_weak 绑定七条原始视频。文件同时包含 `case_id`、`task_id`、`completion_gate`，供七列媒体与指标准备入口使用。
- `INPUT.json` 使用根 agent 提供的 `display_summary`。指标未齐时为 `awaiting_metrics`；逐项核过 63 个数值、7 个 QA 不适用及成片绑定后为 `metrics_complete`。媒体生成与正式发布各有后续校验。
- `ASSEMBLY_GATE.json` 最后写入，保存源事件 SHA、六份 REVIEW SHA 与三个生成文件 SHA。`passed` 表示六路成片及六份视觉审阅门槛通过；指标状态在 `metrics_readiness` 单独记录。

## 执行

从本目录运行；结论文本文件由根 agent 提供：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 assemble_inputs.py \
  --display-summary-file /absolute/path/to/root-display-summary.txt \
  --check-only

PYTHONDONTWRITEBYTECODE=1 python3 assemble_inputs.py \
  --display-summary-file /absolute/path/to/root-display-summary.txt
```

默认指标入口为 `../metrics/prepared/manifest.json` 和 `../metrics/SUMMARY.json`；实际文件放在其他目录时传入 `--metrics-manifest`、`--metrics-summary`。指标回收完成后使用相同结论文本重跑，可把输入状态更新为 `metrics_complete`。

七列对照和同帧截图：

```sh
/workspace/research-user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  render_media.py --bindings MEDIA_BINDINGS.json --output media
```

完成指标与媒体后，先运行 `python3 build_reports.py --input INPUT.json` 生成 staging 并校验；正式发布命令见本目录 `README.md`。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  test_assemble_inputs.py test_reports.py test_publication_export.py
```
