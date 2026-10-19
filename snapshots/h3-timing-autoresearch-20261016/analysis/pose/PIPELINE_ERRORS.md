# 测量管线事件记录

## 2026-10-16：文件名前缀误匹配 benchmark

等待正式 `s05_seed1_native` 输出时，初版等待器使用 `s05_seed1_native*.mp4`，错误纳入 `s05_seed1_native_g2_bench2_00001_.mp4`。它是仅执行2步、未完成去噪的计时输出，并非20步正式基线。

这条 benchmark 已发生 CPU 姿态提取；后续度量因为没有可靠躯干锚点失败，没有生成可引用时间偏移结论。不得把“没有可靠姿态”作为排除正式失败视频的规则；本次排除理由是它的 job 身份本来就是 benchmark。

影响范围：约一段CPU提取开销；没有启动GPU任务、没有改变生成配置、没有把benchmark纳入结果表。保留源视频原地；提取日志、姿态JSON、检查图转移到远程 `analysis/pose/excluded_benchmark/`，带 `EXCLUDED.json`，不删除审计材料。

修正：等待器只读 ComfyUI `/history`，精确匹配 `H3TemporalRouter.inputs.run_id`；只在 history 的 `success` 且 `completed=true` 后取 `SaveVideo` 对应的输出文件名，不再通过前缀 glob 猜文件。随后从该run的job config读取尺寸、帧数、fps并检查；1024筛选和1312原分辨率复验各自验证，配置快照与哈希留存。未成功生成、history输出缺失、尺寸失败、姿态提取失败、姿态度量失败分别写入正式 run inventory 的 failure JSON，不静默丢弃。原始姿态、原片和错误原因保留。

当前正式基线 prompt ID：`db887de8-4476-4ff3-9ead-266ff76afd19`，run ID：`s05_seed1_native`。所有后续解释应使用 history provenance，而不是目录中的近似名字。
