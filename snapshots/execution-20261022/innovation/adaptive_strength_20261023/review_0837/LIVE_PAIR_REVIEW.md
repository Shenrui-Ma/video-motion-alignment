# 当前环境 native / weak 两条控制的独立审查

状态：独立签审通过，仅允许 short_0358 的两条新控制按 native→global_weak 顺序执行。最终签审与 SHA 见同目录 LIVE_PAIR_SIGNOFF.json。旧历史重放 gate 保持失败。

## 科学取舍

旧 first probe 的捕获 off/on 完整 AV 输出逐元素相等，但与旧历史的 video/audio NRMSE 分别为 0.0227143 / 0.0284199。回调源码未发现步偏一或 x0/x_n 混淆，原 native attention 计算 AST 与现有路径相同；资源核查发现旧环境 CUDA int8 与本次 Triton 路径不同。当前证据优先支持采集当前环境的真实状态，不继续依赖旧轨迹回放取得动作标签。

预先选定 short_0358 原素材与同一 prompt、seed、cache、20 步、几何，执行 native 和全程固定 .25 weak 各一条。全部结果保留。同三个饮酒事件的名称与源视频区间冻结；新 native/weak 成片分别标注事件区间与可匹配性，允许数值与旧区间一致，但标注视频身份必须指向新输出。该小控制对用于读出可辨识性校准，不增加泛化结论。

## 只读采集的必要契约

- 保留真实 SAMPLER_SAMPLE executor / Euler / BasicGuider；只加观察 wrapper，不替换 sampler function，不改 sigma / alpha / 模型输入或返回值。
- 实际 Euler callback 在当前步 x 更新前执行。因此 callback 8 后装 layer 25 hook，callback 9 保存同次原始 x_n 与 x0 并卸载，能准确观察 step 9；18→19 同理。不能把 callback 8 的 x 当作 step 9 状态。
- 两处直接保存完整 raw carried AV x_n 与 raw denoised x0，FP32、shape/finite/content SHA；若另保存 process_latent_out 版本，必须单独标注 audio/4，不能覆盖 raw 字段。
- 每个 callback 对照完整 21 sigma 与真实 router state，确认恰好 20 次模型 forward、每次 50 层、无额外 forward、实际 selected steps/mode 与计划相同。
- 每个捕获含全部 56 heads、8 固定空间 probes、全部实际时间 bins 与完整 positions/rotary/norm metadata；保存与该次 x_n/x0、case/method/step/sigma 的关联。
- 观察 wrapper 返回原 executor result 对象；原 callback 原样调用。异常时清理所有 hook，保留首个异常，完整 manifest 不得在失败时生成。
- 新视频 SHA 必须唯一绑定本次完整轨迹、两个 step 9/19 捕获和科学身份。最终视频尚未产生时不放行动作相位分析。

## 最小 CPU 验证

使用真实 sample_euler / KSAMPLER AST 与明确标识的小模型：wrapper 开关的最终值、返回对象、随机数状态不变；20 模型调用，无第 21 次；只捕获9/19；真实 callback 顺序与 state 计数一致。故障注入覆盖 step 9 前模型错误、捕获写盘错误、重复/错序 callback、错 sigma、缺少音频、非有限值、未完成轨迹。异常退出后 hook 数必须为零。

离线分析使用新的 TRAJECTORY_GATE；旧历史 validator 与失败 receipt 不改。缺失/不可匹配事件显式保留，禁止以零偏移或静默删分母替代。


## 最终独立证据

最终 READY `7e562c75a3e89a1c7cda0274fd421f4ddff7d478b2cf40c0ffe3f2e22096ed0a` 的25个资产逐项 SHA 相同。独立CPU副本重跑20项runtime测试通过（3.853秒），实际Euler/KSAMPLER/CFGGuider/EventBlockPatch生命周期及layer25真实Attention参与；其余block体为identity，测试不声称复现完整训练模型。实际新GPU轨迹尚未由本审查执行。

离线工具20项CPU回归通过（15项原测试、5项独立dense/置换/全head-probe/padding/常量偏置反例）。修复了cross-key secondary读取可将1head广播成56head的问题。两份analysis contract已独立对照runtime原文件字节SHA、完整sigma、noise tensor SHA、冻结数值policy SHA，均逐项相同。

主读数采用同一query时间的 `E[p_weak]−E[p_native]`，源事件窗口只作固定聚合。按各自产生事件时间查询的 `t−E[p]` 有标签循环反例，保留作描述，不用于证明相位读出有效。参考自身漂移、去DC、交叉K归因均作为次级诊断，原始主读数保持。实际语义评价要等这两条新轨迹各自完整成片、SHA绑定与新标注后执行。
