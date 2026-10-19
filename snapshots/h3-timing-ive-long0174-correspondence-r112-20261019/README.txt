R112 correspondence control preparation

主方案：design/PROPOSAL.txt
部署补充与近邻边界：design/DEPLOYMENT_ADDENDUM.txt
算子：extensions/H3TemporalRouter/correspondence.py
接入：extensions/H3TemporalRouter/core.py
两组注册：configs/scientific_contract.json / configs/graphs/
旧 CPU 包：source_snapshot/cpu_preparation/（49 文件及原 seal 完整归档）
部署封存：scripts/prepare_deployment_seal.py；结果 audit/DEPLOYMENT_PREPARATION_RESULT.json
实际历史 prefix 核验：audit/ACTUAL_HISTORICAL_PREFIX_CHECK.json

本包尚未部署或启动 GPU。GPU review 绑定新 deploy_manifest.json SHA。完整 CPU cgroup 门、R103 COMPLETE 及精确释放前置、同服务串行两组和独立后处理 gate 已准备。实际 consumer 由独立 metrics agent 绑定。

两组都在 steps 0–5 使用原推理；每个 block 从 step5 原 V 建立冻结 bank。第二组必须与第一组所有 bank 和真实前6次 video/audio x0 一致。steps6–14 执行一步 Value 时间推进。固定坐标与互惠对应版本共用接受 mask，只改变目标空间索引。

CPU 测试覆盖原 PassiveRecorder 的 step5 原子写入先于 step6，以及50bank完整/配对验证。GPU计算未验证，首个真实运行仍执行严格一致性 gate，失败保留证据并精确释放。

每组写 analysis/postrun/<run_id>/RUNTIME_GATE.json；两组完成写 analysis/postrun/long_0174/PAIR_RUNTIME_GATE.json，包含 R96普通编辑、R107同帧、固定坐标一步、互惠对应一步四个结果的绑定。视觉审核首先验证编辑任务、人物与物品、动作路径，再比较预登记事件时间。失败和中性结果保留。
