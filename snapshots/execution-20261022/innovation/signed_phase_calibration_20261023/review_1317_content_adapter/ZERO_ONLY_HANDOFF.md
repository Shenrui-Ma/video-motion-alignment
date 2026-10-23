# 实际两次 zero 的发布接口（资源安排前不运行）

本轮生产scope仅 `two_zero_only`：新 live native state step9与19各一次，共2次 model_k调用；最大attempt1。原合成四调用测试仅测试内部条件控制流，未授予swap。真实zero后先由root核验，再决定独立后续方案与资源。当前优先服从 .41 压力测试的资源安排。

最小图从冻结 `replay_live_pair/plans/native_graph.json` 派生：保留1模型加载、41 shift12/3、5原条件缓存、6原noise、9完整21σ、50 native H3Study科学参数、7 BasicGuider。7的model直接接50，移除52二十步observer。10替换新 `H3ContentCoordinateReplay`，输入noise6、guider7、sigmas9、latent5.output1及锁SHA的新release/output。移除VAE加载/解码、CreateVideo/SaveVideo和无用KSamplerSelect。50仅run_id/audit_dir改隔离路径，科学参数不改。

发布绑定：最终科学READY及所有小源码、POLICY/native_contract/live_inputs/input_identity、已审核派生图；原state9/19与qk9/19文件SHA；原noise文件与tensor身份；缓存manifest及全部5 payload；模型full-SHA既有receipt与当前inode/mtime/size；9个core源码SHA；H3Study、H3TrustedConditionCache、H3HistoricalNoise导入依赖的冻结源码。runtime还需同live的Torch/CUDA版本、兼容/offload/INT8行分块策略和实际backend auditor；传入additional_frozen_runtime_assets并在启动前核验。复用现有权重与缓存，不下载模型或大tensor。

模型域：一次guider.sample/process_conds、full AV target、cfg1、ModelSamplingAV shift12/audio3/multiplier1000/noise_scale1，实际saved packed x FP32保持不再scale。原payload多模态context、reference device与dtype保持，条件噪声按[30176,96] CPU FP32 private Generator(seed2026101701)重建。

每个zero必要真实证据：1 forward/50 blocks；完整六backend-operation增量200成功Triton、其余0/错误0；完整raw AV x0与原live逐元素相同；layer25 raw/actual Q_C/Q_R/K_R及norm、RoPE、位置与所有56×8/31valid支持逐元素一致；target、prepared context、原ref不变；condition rows与原Torch生成路径exact且两zero的N SHA相同；最终outer视频identity/audio÷4 exact。GATE只能在外层归一化通过后passed。任一项失败保留证据、停止，不能使用旧historical failed gate或放宽容差。

只由root和资源owner另行启动；本独立审查不创建服务、不提交模型任务、不操作队列/显存。
