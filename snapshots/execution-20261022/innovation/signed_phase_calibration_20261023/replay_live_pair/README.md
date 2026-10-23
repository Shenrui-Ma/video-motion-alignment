# 同环境两条完整控制轨迹的被动观察

状态：CPU 已验证，待独立签审及资源方接入。本目录没有提交 GPU 作业。

此前历史一步重放的 off/on 输出逐元素相同，但历史 x0 数值门槛失败。已确认历史 CUDA 与当前 Triton 后端不同；旧 gate 保持失败。本方案重新生成饮酒 native 和全程 α=.25 两条完整控制轨迹，观察信号与本次实际视频绑定，不依赖历史轨迹数值相等。

## 唯一科学变化

原 checkpoint、conditioning cache、双流初始 noise、seed、20 步 Euler、完整 21 个 FP32 sigma、107 帧、视频/音频几何均冻结。原 H3StudySchedule attention 输出保持，native 使用原 fixed 步集合与 native 模式，global_weak 使用20步 mass_preserve α=.25。所有旧输出路径移到独立目录。

新增 `H3LivePhaseObservation` 只包裹原 SAMPLER_SAMPLE 的 callback。真实 Euler callback8完成后安装 layer25 的捕获 hook；下一次实际 model call 即 step9，callback9关闭 hook 并保存该次真实完整 packed x_n、raw denoised x0、Q/K。18→19同理。wrapper不调用模型、sampler、随机数或VAE；调用原 executor 一次，并原样返回其结果对象。最终视频与音频 VAE 解码仍是原图节点11/12，仅采样结束后执行。

每次采集：全部56 heads、固定8空间位置；Q_C、Q_R、K_R各保存 qkv投影后的raw与实际RMS/RoPE后的post。实际norm权重/eps、完整表中对应RoPE、位置坐标、物理帧区间、有效时间mask一起保留。完整有效bin由实际layout推导，不能把尾部padding当动作。

## 数据与 gate 契约

部署root：`/data/research-user/h3_inference_20261023/live_phase_pair_20261023`。

- 新ID：`live_phase_short0358_native_20261023`、`live_phase_short0358_global_weak_20261023`。
- contracts放 `contracts/`；图及SHA在本目录 `plans/`。
- 完整观察清单：`audit/live_phase/<trajectory_id>/OBSERVATION.json`。
- 同目录 `state_step009.pt/state_step019.pt`，包含实际完整FP32 packed_x/raw_packed_x0、两流shape和完整sigma。
- `qk_step009.pt/qk_step019.pt`，沿用 h3-passive-qk-capture-v1，增加独立的 forward_identity。
- 原方法 audit：`audit/router/<trajectory_id>.json`。
- 新成片：`output/<trajectory_id>/...mp4`。

每个capture的 forward_identity 含 trajectory_id/case/method/step_zero_based/layer_zero_based、science_contract_sha256、state_file_sha256、packed_x与raw_packed_x0的shape/dtype/SHA/finite、sample_sigmas_video、noise_sha256。此对象在QK和OBSERVATION中必须相同。它不包含未来视频SHA，避免循环依赖。

OBSERVATION只有在20 callback、20个实际H3 forward、1000个原router block全部完成且两个capture成功时写complete。extra_model_forward_calls=0由实际model计数与逐callback router计数共同验证。若任一步出错，保留原异常，清除所有hook，记录failed。失败记录写盘也失败时不覆盖最初异常。实例禁止复用。

资源方在正常decode和视频SHA完成、对应history/图/科学资产核对后，另写 `h3-live-phase-trajectory-gate-v1`，绑定 actual_video_sha256、observation_manifest_sha256、科学contract、20/1000/0/20计数和两capture及forward_identity。Root的calibration_live工具只接受此新gate。未完整成片或失败清单不生成passed gate。新视频按原3个事件定义重新标注，旧输出的区间不直接复用。

## 开销与计时

每个视频两次保存实际完整AV状态与稀疏Q/K；文件留在服务器，不回传大tensor。没有额外DiT forward或attention计算。复制/磁盘I/O使实际总墙钟增加，`sampling_seconds`包含这部分。原ScheduleState的forward_wall_seconds继续保存，它是Python dispatch墙钟口径；原20步tqdm也保留。不得把新旧跨硬件耗时差解释成方法计算开销。

## CPU证据

20项回归通过。实际源码AST：Euler、KSAMPLER（包括其内部k_callback）、CFGGuider、EventBlockPatch；选中layer25执行实际H3 Attention/RMS/RoPE。其他block体使用廉价identity，逐block计数由真实EventBlockPatch维护。此fixture验证观察生命周期和采样接口，不声称完整训练模型数值已在CPU重放。

关键检查：20×50计数、原callback原样调用、on/off逐步x和最终输出逐元素相同、返回原对象、RNG不变、原始noise/sigma/模式绑定；真实模型失败、capture保存失败、原callback失败、失败清单二次写盘失败、部分hook注册失败全部保留原异常并卸载hook。节点/图测试核对原完整采样路径、冻结科学字段及路径隔离。

CPU环境为.9独立 `/tmp/h3_live_phase_cpu_20261023`，CUDA_VISIBLE_DEVICES为空，OMP/MKL/OPENBLAS和torch线程均1。该临时目录仅小源码与测试，测试生成tensor由TemporaryDirectory清理。没有模型加载、GPU调用或队列操作。

## 顺序

先native一条完整审计、视频和自然服务退出，再weak。不得并行提交或将原失败historical gate改成通过。两条计划处于review_only，运行权限由root与资源代理按最终READY/签审执行。
