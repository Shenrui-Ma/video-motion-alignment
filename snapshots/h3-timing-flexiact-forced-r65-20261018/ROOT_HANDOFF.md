# R65 FlexiAct：fitness / one_leg 固定引导诊断

可执行的四条队列：`fitness Native → fitness forced → one_leg Native → one_leg forced`。使用新目录与同一 .41 GPU1 normal/reserve8 服务产生各自成对结果。保留 R49 的原视频、角色图、完整原提示词、种子2026101701、1152×768×158@24、20 Euler和原sigmas、INT8 DiT、FP4文本编码器；直接复用原路由数学和内核。每条20次模型预测、20次Euler更新，采集中间20组与最终AV张量。

这两条是原固定五例里的 development 诊断子集。选择依据是已知 R49 前2秒手臂动作约250–375ms延后、角色外观已实现。原五例状态与人工检查证据完整保存在 `configs/R49_evidence/NATIVE_FIVE_SUMMARY.json` 和 `EDIT_ATTAINMENT_ROOT_NOTE.json`。前者是当时的Native统计快照；其中旧Auto完成计数不表示当前总进度。

|原五例|已有证据|本批选择|
|---|---|---|
|chest|原角色未成功替换；MF高不能代表编辑成功|保留完整历史|
|crouch|蹲下明显晚且画面/外观变化大；动作测量不可用|后续复杂失败诊断|
|fitness|外观成功；前2秒手臂延后250–375ms|第一对|
|one_leg|外观成功；前2秒手臂延后250–375ms；脚部超出画面|第二对，仅评可见手臂|
|rotate|外观成功；检查帧未发现稳定延后|保留完整历史|

## 干预位置

两臂的物理支持参数均为0…146帧；ON是 `mass_preserve`、alpha1、50个DiT块、零基去噪索引6…14。Native模式保留相同物理支持参数但实际路由次数为0。ON路由计数450。

原49帧8fps各重复3次，共147有效24fps输入帧；再追加11帧尾padding，得到158帧。物理0…146映射到44个H3位置bin（0…43）。最后bin覆盖145…148，包含2帧边界padding；纯padding bins44…46对应149…157，保持原生注意力。此边界是H3离散位置映射，未改变视频或VAE。

`O' = O + m_ref (O_same_time − O_ref)`：保持原参考视频组总注意力质量，重分配为同一时间bin的参考特征。角色图、文本等组保持原来的贡献，未增加在线观察器。

## 启动

本地目录：`/Users/researcher/DevProjects/h3-timing-flexiact-forced-r65-20261018`

远端：`/data3/researcher/h3_runs/timing_flexiact_forced_r65_20261018`

GPU1 UUID：`GPU-REDACTED`；端口8535。等待R55释放及root重新检查实际资源后启动。其他用户正常运行；最多使用自己两张GPU。输入总量约11.7MB。

复用R63执行流程：

1. root同步目录，核对实际GPU/index、显存、RAM及自己现有进程，在configs/admission.json登记准确hashed进程身份并置ready_for_launch=true。
2. `python3 scripts/preflight.py`
3. `python3 scripts/execution_gate.py seal`
4. `python3 scripts/execution_gate.py approve-first-pair --root-admitted`
5. `python3 scripts/launch_remote.py --service-only`
6. root登记service身份后，原样原子复制cuda_gate_ready.json→cuda_gate_go.json。
7. HTTP端口8535的H3TemporalRouter就绪后：`python3 scripts/start_controller.py --pid PID --start-ticks TICKS`。

首对仍作为实际容量试运行，freshfree下限20GiB，未伪造完整容量已通过。OOM/failure只清理精确登记的自有进程，root决定新的offload运行配置，并为两臂重新配对。Native与ON之间保留Comfy缓存，审计实际用时。

## 首对核验与第二对

`CUDA_VISIBLE_DEVICES='' /data3/researcher/ComfyUI/.venv/bin/python analysis/postrun/verify_pair.py --source fitness`

生成 `analysis/postrun/fitness/PAIR_RUNTIME_GATE.json`，检验实际条件8种tensor blob、初始AV噪声、两臂前6个x0预测相等、20次真实模型forward、全部21组AV tensor、有效44bin支持、输出158帧24fps、冻结runtime/代码。成片质量由后续动作/编辑评估判断。

第一对完成后队列等待root：`python3 scripts/execution_gate.py approve-rest --root-admitted`，绑定上述receipt SHA后自动继续one_leg。第二对同样用 `--source one_leg` 核验。完成后将queue.json的finalize设为true，或等待1800s有界空闲后释放；root按实际任务安排处理驻留。

评估采样沿原协议取输出索引 `0,3,6,…,144` 共49帧@8fps。不得把147有效24fps帧或158含padding帧直接当作官方49帧序列。source/portrait原件与完整provenance都在inputs。

## CPU验证

19项测试覆盖固定4图、原R49数值与输入保留、角色图哈希、44bin边界、纯padding query原样、注意力公式dense tensor oracle、首对门与后续门、真实PT/condition/noise故障检测；另全部Python编译和preflight通过。证据在audit/CPU_VERIFICATION.json、CPU_TESTS.txt、PARENT_GRAPH_DIFF.json。准备agent未启动GPU。
