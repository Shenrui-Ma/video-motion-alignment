# R107 long0174 同条件时序引导

2026-10-19 恢复支路负责人：`/root/recover_41_r96_r103`。

## 实验依据与内容

R96 long0174 原生编辑已经完成“女子白衣变黑衣”。145 个有效帧逐帧检查发现，女子被男子遮挡、从男子右侧重新出现、男子转身抬臂等动作延迟约 8–20 帧。最后抬臂阶段落在有效片段之外，按右删失记录，不声称确切缺失。检查记录在 R96 consumer 的 `audit/recovery_full_review_long0174/REVIEW.json`。

本次只补同一实际 Native 的固定时序引导结果：`mass_preserve`、alpha=1、50 层、去噪步骤索引 6–14、有效参考帧 0–144。20 NFE，450 routed calls。输入、六项条件、初始 AV noise 与去噪前六次预测必须和真实 R96 Native 一致。158 总帧、145 有效帧、1312×736，展示裁剪为 [16,8,1280,720]。此单例检验既有引导机制；方法创新结论由后续整体实验决定。

## 当前状态

生产 seal：72 文件，`b12267486bf6abdb635a6bfa8f5356dcec07326ab1a4c16dacb5bbd78593a351`。
本地和 `.41` 各 99 项 CPU 测试通过；9 个实际 core 文件、6 个数值文件与父包一致。
consumer 17 项 CPU 测试通过，freeze：`ea630d42068b038135fddaf9310e6ba920c5e9b28cc927137f96fef34bf11580`。

`.41` 共享 cgroup 的原始余量受文件缓存影响。root 已审阅并授权管理层准入修订：排除 shmem/mapped/dirty/writeback，保留 6 GiB 缓存，高限额余量至少 64 GiB、硬限额余量至少 76 GiB、主机 MemAvailable 至少 64 GiB、PSI avg10≤1%。详见 `scripts/working_set_capacity.py`、`configs/cgroup_policy.json` 与 `audit/CAPACITY_PROPOSAL.md`。不主动清缓存、不修改 cgroup 限额。

attempt1 在 root launcher 的真实启动前复核因余量小幅下降被拒，尚未创建任何 H3 服务或 CUDA 分配。失败凭证保留在远端 `audit/root_long0174_guidance_attempt1/FAILURE.json`。root 随后将额外保留缓存预算从 8 GiB 调到 6 GiB，其他门不变；旧等待器 exact PID1224436 已释放。attempt2 在 fresh high65.72/max77.72GiB 后已由原 launcher 注册，root controller PID1226019；后续服务/GO/进度以真实记录为准。其进程和实时状态以远端 `audit/CAPACITY_WAIT_OWNER_root_long0174_guidance_attempt2.json`、`CAPACITY_WAIT_SAMPLES.jsonl`、`ROOT_LAUNCH_root_long0174_guidance_attempt2.json` 为准。

## 机器与路径

- SSH `H3_SERVER_B`，UID 1004，GPU2 `GPU-REDACTED`，port 8570。
- 远端根目录 `/data4/researcher/h3_runs/timing_ive_long0174_guidance_r107_20261019`。
- 本地 consumer `/Users/researcher/DevProjects/h3-ive-long0174-guidance-metrics-r107-20261019`。
- 本次 `.41` 只运行一个 H3 服务，R103 和 MF 均等待 R107 完成并释放。

## 成片后

1. 确认真实 `analysis/postrun/long_0174/PAIR_RUNTIME_GATE.json` 通过，包括条件、noise、prefix0–5 相等；确认同 attempt 的 `ROOT_EXIT_RECEIPT.json` 和 `COMPLETE.json`。
2. 本地用 ComfyUI-dev venv 执行 consumer 的 `scripts/consume.py --source long_0174`。所有展示按 145 有效帧、同时间戳，不做时移。
3. 检查基本换色任务、同一动作事件帧与全片质量；待实际视频后补官方 IVE MF。metrics agent 已收到仅 CPU 准备请求。
4. R107 完成、精确 PID/CUDA 释放后再考虑 R103 两项 FlexiAct 修复任务；R103 当前仍按原冷载门，不直接套用本次门而不复查实际峰值。

R96 原始账本和结果均未改写。R103 通过独立后验审阅凭证准入，具体状态见其 `RECOVERY_HANDOFF.md`。

## 实际完成与审阅

R107 attempt2 已完成20步/450次路由，实际条件、raw AV noise及预测0–5与R96完全匹配。PAIR_RUNTIME_GATE、COMPLETE、ROOT_EXIT_RECEIPT均通过；服务PID1226044/start15372732已从/proc与NVML消失。

完整145帧审阅在consumer `audit/full_frame_review/REVIEW.json`。基础黑衣编辑完成；绕行被挡、另一侧出现的延后仍为0.33–0.75秒、0.38–0.71秒。手臂抬升分量提前，但转头与抬臂联合动作被拆开，末段伸臂未在有效域内完成。按整体时序改善阴性归档。

官方IVE MF由独立评测支路完成：普通0.9424339286、固定0.9299472260，变化−0.0124867026。实际路由sampled m_ref均值0.16275，修正/Attention输出RMS比均值0.20497，同既有R85/R89量级。缺少投影后/residual后与主体局部范数，不能用此统计解释全部成片行为。详见consumer `audit/EXISTING_ROUTER_STATISTICS.json`。

单任务总4545.58秒，采样含capture3842.86秒，decode/save67.43秒。session内存峰值54.11GiB，父级high计数增加10572，max/oom/oom_kill均0。详见 `audit/ACTUAL_RESOURCE_SUMMARY.json`。

root后续选择独立R111 spatial_marginal结构对照，优先于R103；R103尚未启动。
