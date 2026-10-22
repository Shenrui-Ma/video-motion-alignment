# R150 评测接收

本目录扩展 R149，复用已有媒体与经过 SHA 固定的 CPU 接收、裁帧和展示工具。原三组、生产包、用户报告均不修改。

根代理已选七个新增任务；加上 R149 三任务，共十任务、九个独立源视频。Musk05 与原 Sam05 共用源视频。新增输出共 31 条：书本、手帕、红发、外星人各四种 schedule；Musk05、流萤06、Sam07 各补一次同 bin 固定 7–15，再运行四种 schedule。

`EVALUATION_EVENTS.json` 固定七组的动作定义、源和普通版区间及搜索帧域。事件未出现记 `null`，并记录原因。红发与外星人的旧记录只有宽阶段，应按保持性审阅；阶段中点不是已测得的动作时差。每条新结果均须完成全有效片段的编辑、身份、场景和动作检查。

`EVALUATION_MANIFEST.json` 可执行接收已经绑定的案例。其余已选任务的历史资料放在 `selected_history/`，实际新 producer 合同到齐后增加运行绑定。`legacy_weight3` 不占用 `fixed` 对照列。

## 收取单条真实结果

使用生产代理给出的实际 gate 和视频 SHA。`collect_job` 仅获取小 gate 与一次 MP4，不取 x0。

```sh
cd /Users/researcher/DevProjects/h3-guidance-schedule-eval-r150-20261021
python3 run.py collect_job --case long_0039 --schedule early \
  --expected-gate-sha ACTUAL_GATE_SHA --expected-video-sha ACTUAL_VIDEO_SHA

MEDIA_PY=/Users/researcher/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
"$MEDIA_PY" run.py ingest --case long_0039 --schedule early \
  --video "$PWD/actual/long_0039/early/video.mp4" \
  --gate "$PWD/actual/long_0039/early/GATE.json"
"$MEDIA_PY" run.py make_full_frame_sheets --case long_0039 --schedule early
"$MEDIA_PY" run.py make_contact_sheets --case long_0039 --schedule early --start 0 --end 105
```

随后按冻结事件制作必要的原分辨率局部图，写该臂 `REVIEW.json`，再调用 `summarize_review`。同一服务继续下一臂时保留 `BATCH_RELEASE_PENDING`。单臂 gate 不充当整组释放。

## 整组完成

```sh
python3 run.py finalize_batch --case long_0039 \
  --gate ACTUAL_AGGREGATE_JSON --complete ACTUAL_COMPLETE_JSON \
  --release ACTUAL_ROOT_EXIT_JSON
python3 run.py prepare_mf --case long_0039 --schedule early
```

仅使用真实 aggregate、COMPLETE 和 ROOT_EXIT。MF 复用同帧域、同像素和同 checkpoint 的源轨迹；GPU 启动由根代理另行安排。

## 验证范围

`audit/CPU_PREPARATION.json` 记录两个真实封存 producer 的八条绑定与合成 gate 拒绝测试。`audit/EVENT_FREEZE.json` 绑定源事件。`run.py` 会拒绝未经复核而改变的复用脚本。

本阶段为 CPU 接收准备；不声称新视频、GPU 评分或浏览器视觉验收已完成。页面验收限源结构和媒体，禁止 headless 或 HTTP 绕过已有浏览器访问限制。
