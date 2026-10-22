R64 四源 Native / 固定时序引导复核

CPU 复核通过：113 个文件与准备清单完全一致，26 项测试通过，8 个任务的 preflight 通过。6 个数值核心文件同时与归档父版本和当前 R63 逐字节一致。生产文件未修改，未部署或调用 GPU。

| 官方任务 | 输出帧 / 有效帧 | 视频 latent bins | 参与引导 bins | 纯尾部 padding bins |
|---|---:|---:|---|---|
| 0092 移除植物 | 73 / 58 | 22 | [0,18) | [18,22) |
| 0114 篮球换霓虹球 | 107 / 105 | 32 | [0,32) | 无 |
| 0126 床边加猫 | 124 / 109 | 37 | [0,33) | [33,37) |
| 0392 移除壁炉 | 73 / 57 | 22 | [0,18) | [18,22) |

每对使用相同官方原 prompt、seed2026101701、输入、条件、初始 AV 噪声、20 步 Euler 和 1312×736 画布。固定 ON 在零基去噪步6–14、全部50层运行 alpha=1 mass_preserve，对所有有效视频时间对应的 bins 引导；末 bin 与有效帧重叠时允许该 bin 覆盖少量 padding。原生臂使用相同窗口参数与 mode=native。没有在线 observer，源事件标注仅用于人工评估。

实际生成后 verify_pair 会核验：同一服务 generation、精确图和形状、6 份干净条件、AV 初始噪声、21 份 AV capture、前6步逐位相等、Native0次 / ON450次改动、实际输出帧率和帧数。CPU 测试含被改条件、噪声、前缀、纯 padding 和参考形状的拒绝案例。

部署顺序

1. 等 root 选择可用资源。包当前绑定 .41 GPU2 / UUID GPU-REDACTED / port8534，当前 GPU2 已有 R66，必须在 root 资源排程下启动。若 root 改设备，需先更新行政 runtime 绑定再封存；每对保持同一设备和内存配置。
2. 被动复制到 /data3/researcher/h3_runs/timing_ivebench_heldout_r64_20261018，核113项输入/代码 SHA、模型与 Comfy core SHA、实际 CPU preflight、端口；由 root 填写自身进程精确登记与 admission。service 保留 normal / reserve-vram8，foreign 进程按显存容量准入，自有 GPU 总数最多2。
3. 运行 scripts/execution_gate.py seal。root 对首对设置实际容量门，执行 approve-first-pair，再 launch_remote.py --service-only，核 exact ready/PID/start/cmd 后放行 cuda_gate_go，启动 controller。
4. 首对0092完成后运行 analysis/postrun/verify_pair.py --source short_0092。root审核 actual runtime gate、显存和画面，再决定剩余队列准入。
5. T73 首对不能认证 T107/T124 的容量。approve-rest 本身只验证首对 gate，代码没有对后续更大形状单独做容量认证。root 在释放其余6条前应依据已有同环境更大形状实测或进行单独容量检查；20480MiB 只是工程试跑下限。保持科学数值和每对内存配置一致。
6. 四对均完成各自 verify_pair；消费包需按各自有效帧与裁剪[16,8,1280,720]采样，并绑定本轮原片/运行环境。展示完整有效时域，报告官方任务编辑成功、人体动作保存、MF和可测时序；分母固定4，失败与不可测分别列出。

任务范围：本批是官方道具/环境编辑、要求保留可见人体运动，区别于此前5条人物/服饰编辑。原0392包含音频，准备参考输入全部静音且图无 ref_audio，不能据此评价音视频保持。实际推理与容量尚待 root 执行。
