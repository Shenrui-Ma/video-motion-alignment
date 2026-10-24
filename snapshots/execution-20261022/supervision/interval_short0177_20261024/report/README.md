# short_0177 区间对照报告整合

本目录准备新样例的媒体与报告。正式 HTML 在 `build_reports.py --publish` 时更新；默认构建只写 `staging/`。六条视频、63项数值评分、逐帧动作标注全部通过校验后再构建。十项 IVE 为原九项加本轮 short_0177；FlexiAct 蹲起独立成组，四项自有历史样例继续保留，共15条展示。

## 输入文件

复制 `INPUT.example.json` 为 `INPUT.json`，填写本轮事实。路径相对 INPUT.json 所在目录解析，也接受绝对路径。

- `cohort` 固定 `interval_short0177_20261024`。
- `job_ids`：七个指标 job ID，source/native/early/fixed/late/split/global_weak。metrics agent 使用 `interval20261024_short_0177__<role>`。
- `inference_job_ids`：六个实际推理 queue job ID，与指标 ID 分开。
- `video_sha256`：七视频原始字节SHA；所有评分、标注、拼接都绑定这一组。
- `result_files`：六个 queue_state/results 完成JSON。验证 job/attempt/task/method/cohort、prompt、seed、有效帧及成片SHA。
- `router_files`：同一 attempt 的完整路由audit。验证20×50、逐步50block、实际路由步集合/次数、α和有效物理帧范围。
- `metrics_manifest`：含 `jobs` 数组，七项均需要 id、task_id、method、cohort、sha256、valid_frames、fps、crop_xywh。
- `metrics_rows`：含 `rows` 数组或数组本身。每项需要 job_id、task_id、method、cohort、metric、status、score。九项数值每角色齐全且done；IS/CF可缺失、记录未测；QA用实际not_applicable记录。
- `annotation`：本次动作标注，结构同旧ANNOTATION；必须包括 case_id、valid_frames60、fps24、annotation_source、review_completed=true、video_sha256七项、events。events每项有id/label/source/native/early/fixed/late/split/global_weak闭区间；缺失动作填null并在status_by_role写原因。源事件取上级SOURCE_EVENTS.json；覆盖60有效帧、完成事件边界复核后填review_completed。
- `presentation`：下述render_media生成的PRESENTATION.json。
- `display_summary`：视频、指标、动作事件的简明事实结论。

这里使用旧 `action_offsets.py::measure` 的计算：零基闭区间中点差、正值延后；六方法共同可定位事件先求每视频绝对偏移均值，再按视频等权。旧冻结SUMMARY/CSV原样保留，新汇总写入 `staging/ACTION_OFFSET_SUMMARY.json`。原Flex事件和原14例媒体/指标均保留。

## 制作七配置媒体

填写 `MEDIA_BINDINGS.example.json` 为 `MEDIA_BINDINGS.json`，每角色给原始本地file、metrics job_id、sha256。全部输入必须为本轮指定源/成片，24fps、至少60帧、支持同一crop `[16,8,1280,720]`。

```sh
/workspace/research-user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 render_media.py --bindings MEDIA_BINDINGS.json --output media
```

仅CPU：逐视频核SHA/ffprobe，裁剪60有效帧，保持帧索引0–59；生成1920×1232三行视频（参考居首行，六编辑后两行，底部80像素播放器空间）、第30帧七列截图及PRESENTATION。Pillow使用内置中文字体，编码为libx264 CRF19；原始视频保持原样。

## 构建、检查、发布

```sh
python3 build_reports.py --input INPUT.json
node validate_report.js staging/R150_十组引导区间对照_单文件.html
```

浏览器检查暂存的R150与V1.1：15条媒体、三个指标范围、同帧截图、Flex事件表、分组、全屏/截图按钮及新增V1.1小节。实际画面与评分身份在BUILD_RECEIPT、PRESENTATION、INPUT所列审计中对应。

```sh
python3 build_reports.py --input INPUT.json --publish
```

发布先在 `backups/` 按SHA保留原R150/V1.1，再原位写入；同步旧eval目录 `index.html`。旧eval目录同名R150 symlink仍指向主文件。`PUBLISHED.json`建立后，旧refresh_showcase.py会提示使用本构建器，避免旧14项逻辑覆盖15项展示。

V1.1保留原文，使用标记区块在discussion前追加本轮案例、六配置MF/动作偏移、10IVE均值、同帧图与比较视频。同一标记重复构建时替换该追加块。旧混合十项统计保留历史口径。

公开副本仍由项目 `tools/export_reports.py` 导出至 `reports/cloud/`；是否同步远端由主线程按本轮授权处理。

## 校验

```sh
python3 -m unittest -v test_reports.py
```

覆盖完整输入、旧cohort混入拒绝、未完整20×50拒绝、评分视频SHA不一致拒绝、缺少数值指标拒绝、原14例媒体/事件/指标保留、Flex独立展示、V1.1追加区块外逐字不变及追加幂等。
