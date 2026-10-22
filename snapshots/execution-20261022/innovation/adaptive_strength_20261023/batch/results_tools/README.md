# 新方法结果的只读增量收集

运行 `python3 collect.py --jobs all_jobs.json --output latest`。只通过内网 SSH 读取文件、计算已生成视频的 SHA256；不调用提交、重启、队列修改或 GPU 接口。

`all_jobs.json` 是收集器专用的原 8 项 + anchor 2 项合并清单。原 `batch/jobs.json` 保持原样。机舱 5 项归 `.41`，饮酒 5 项归 `.60`；两条 anchor 的归属与资源交接 ready request 核对，并保存 receipt SHA。饮酒 `dynamic_dof` 根据 `SATURATION_HOLD.json` 单列 `research_hold`，不计为 pending 或 failed，也不进入科学指标分母。以后若恢复该任务，应先更新此收集清单的 hold 记录；若 held 任务已有提交或结果，收集器报归属冲突，避免静默覆盖新证据。

可显式传 `--jobs ../jobs.json` 单独检查原 8 项。调用 `merge_plans` 可由原清单、附加清单、hold receipt 与 source ownership receipt 重建收集清单；它不修改输入对象或远端队列。`sources.json` 按 task 配置唯一生产服务器，重复/遗漏归属会立即拒绝。

运行中的完整 layer 记录检查有限值、α 范围、闭式公式和 head 能量预算。anchor 额外逐层重放首个有效步创建锚、A0/B0 固定、当前 A/B 归一化及 constrained closed form；首步和 fallback 使用 prior。成片后复用 `batch/audit.py` 完整核验 20 步 × 50 层，并核对实际 attempt、producer result 和媒体 SHA。任何异常写入 `attention_required`，脚本不会停止推理。

输出默认在 `latest/`：

- `status.json`：10 项状态、research hold、实际 attempt/prompt、生产服务器、审计及媒体 SHA、实际耗时、异常和清单 SHA。
- `alpha_curves/<job_id>.json`：实际每步/每层/head α，修正能量、fallback；anchor 包含 temporal/complement energy（A/B）、anchor temporal/complement（A0/B0）、normalized_temporal/complement、anchor_step、anchor_created、used_anchor。不插值、不将离线反事实列为执行结果。
- `official_metrics.json`：只对已完成、审计通过、媒体 SHA 核验通过的样例汇总。unfinished 与 hold 在 `collection_selection` 单列；科学指标分母只包含真实成片。每次读取 `.81/evaluation/summary.json` 的原始 rows，配对参考、native、global_weak；AWQ IS/CF 与 QA 适用范围单列。没有读取旧 aggregate means 或本地 current_summary。
- `snapshots/`：来源、抓取时间、SHA 与内容快照。JSON 只有大小/纳秒修改时间变化时重取；媒体同理。缓存仅在远端本轮确认版本未变后使用。

SSH 失败时该来源本轮待确认，并记录错误；不会把旧快照冒充实时证据。该脚本不启动 evaluator 或 relay；生产结果须经既有 relay 登记后才出现官方指标。审计通过表示执行与控制器完整性，视频质量和动作保真由独立评测决定。

`python3 collect.py --dry-run --jobs all_jobs.json --output dry_run_anchor` 不访问远端：此次确认 9 pending、1 research_hold、0 成片、0 指标值。

`python3 -m unittest test_collect -v` 的 16 项测试均为临时目录中的合成数据，包括原 8 项回归、新 anchor 实时锚检查、A/B 曲线、完整成片入口、hold 状态、双源唯一归属和完成成片分母；不计入实验结果。
