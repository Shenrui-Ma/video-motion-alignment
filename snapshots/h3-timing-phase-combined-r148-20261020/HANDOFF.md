# R148 固定引导＋相位对齐：启动交接

当前五包以 `FINAL_FIVE_CASE_HANDOFF.json` 为准。所有推理由 root 负责启动。

启动链已从注册图提取实际 HTTP 节点类型，组合图提交回归通过；四条原任务的科学文件和输入保持冻结。Sam 保留原图片＋视频条件、seed2026101311、第50–65帧窗口。

| 场景 | GPU | 端口 | seal SHA256 |
|---|---:|---:|---|
| 05_real_megumi_v | 2 | 8632 | 811b6be7e19a268b71478ec74d17ac784c8156bc1b723166a867d33ca20aff58 |
| long_0039 | 2 | 8630 | d30c6a5409c8d2e40eb6ca7d48408f7039184b60e50f88568abe72b1cd5cb362 |
| long_0059 | 1 | 8631 | 5a0dfe1164d5efcd29551e7473f52e1cf8d53b25df4b1351da13f2f6188d6f27 |
| short_0252 | 2 | 8628 | d2ebc59e79b4a3a563722fcdcaade3229c693df413d4eb4b6feb3ede7c5e5908 |
| short_0358 | 1 | 8629 | a16f52f3418997509ca9937e69d82398c6fd628c75b6888d1d757702e107105a |

Sam 原 embedding 从 R33 同 SHA 缓存恢复，五个条件张量、原 AVnoise 逐文件与实际 tensor 校验通过。目标环境 CPU import/reconstruction 无 CUDA 初始化、无模型加载，29 项 CPU tests 通过。

根控制器命令：`python3 -u audit/root_run_batch.py --execute --attempt <唯一attempt名>`。同时运行第二张卡时加 `--peer-root <另一条当前准确root>`。root 写入当前 seal 的 ROOT_PRELAUNCH_REVIEW，并核资源与前置释放。

成功输出从 `analysis/postrun/<source_id>/COMBINED_RUNTIME_GATE.json` 的 `runs.fixed_phase.video` 读取，并匹配 COMPLETE / ROOT_EXIT；精确路径与 schema 见 JSON。

Sam 首次实际组合推理的数值、输出及释放结果待运行回执。历史完整证明与旧 seal 保留在各包 audit；启动包无需重新加载四条旧缓存。
