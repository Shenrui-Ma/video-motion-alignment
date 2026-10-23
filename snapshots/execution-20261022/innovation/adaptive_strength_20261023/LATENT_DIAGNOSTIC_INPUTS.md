# 无需重采样的 latent 相位诊断输入

2026-10-23。只读检查本地代码／清单和远端小 JSON、文件 stat；没有下载 latent、加载模型或占用 GPU。

## 结论

**可以直接用现有参考 latent、生成的逐步预测 x₀ 和最终 latent 做已知移位校准，无需重新跑 20 步视频。** 推荐饮酒 `short_0358` 与手帕 `long_0059`：两例都有 source/native/global_weak，native 有已冻结的明显时差，weak 接近对齐，可形成读出诊断的正／负对照。

这些文件不是实际 noisy latent xₙ。旧 `H3X0Readout.PassiveRecorder.record(step,x0,x,total_steps)` 保存 x0，未保存参数 x。已保存初始 noise、全部 20 个预测 x₀ 和 Euler sigma，所以有离线递推 xₙ 的条件；那属于**重建状态**，应另做数值验证，不冒充实录。读出校准本身不依赖 xₙ。

## 两例身份与形状

| 项目 | 饮酒 short_0358 | 手帕 long_0059 |
|---|---|---|
| 编辑 | 给饮酒男子戴眼镜 | 将手帕改为条纹 |
| seed | 2026101701 | 2026101701 |
| source／生成 video latent | `[1,24,32,46,82]` FP32 | `[1,24,47,46,82]` FP32 |
| audio latent（本次不用） | `[1,32,2,178]` FP32 | `[1,32,2,263]` FP32 |
| 生成／有效帧 | 107／105，24fps | 158／144，24fps |
| 图像几何 | 1312×736，评测裁剪 `[16,8,1280,720]` | 同左 |
| 冻结 native 事件误差 | 0.5、9、10.5 帧，均值 6.667 | 0、0、16 帧，均值 5.333 |
| 冻结 weak 事件误差 | 0.5、−1、−2.5 帧，均值 1.333 | 0、0、1 帧，均值 0.333 |
| 完整历史 prompt SHA256 | `5ea69610fb7e51081d4bdc30ba4f6ab27dff99f9bef9f0157c541cb2250acad4` | `9a80385c1d187e238bcdab38247d32a9cc40b28327c7b52c7b833a8aa183aee6` |

这里的 prompt 是历史完整结构化 prompt，不是表中的一句编辑说明。原文存于以下 conditioning JSON 的 `prompt`；seed 与 prompt SHA 可经本地 graph、原始运行 gate、远端 manifest 三者互查。两例 weak 适合近零时差回归，不能据其亚 bin 的误差要求 latent 读出有同等帧精度。

## 确切输入路径

`.41` 的 SSH alias 为 `H3_HOST_CONFIGURE_LOCALLY`；`.9` 为 `H3_HOST_CONFIGURE_LOCALLY`。以下远端目录已实际读到 complete manifest，21 个 `.pt` 均有 stat，未读取大张量。

### 饮酒：三份都在 .41

参考 latent（纯 tensor，11,589,965 bytes）：

```text
/data4/research-user/h3_runs/benchmark_schedule_20261022/innovation_cache/short_0358/27b35d491b84f5c12a5b0f91ec91c2bb1b94b6b5c249a3e55476e0f2cb443e22.pt
```

conditioning：同目录 `r123_short_0358_shared_conditioning.json`。参考 tensor 内容 SHA：`1ad0955cfa27b1215d5e8c8334d844944143040ce9e8f0f8a8e9618dc13d1081`；文件 SHA：`3c1cb0d2668f72169873271782be51aad0d2295203a1790e4c57f16884595dfd`。

native 捕获目录：

```text
/data4/research-user/h3_runs/timing_ive_prompt_envelope_full_format_r123_20261020/audit/x0/r123_short_0358_seed2026101701_native/
```

weak 捕获目录：

```text
/data4/research-user/h3_runs/guidance_schedule_r149_final_global_host41_20261020/cases/short_0358/audit/x0/r149_short_0358_seed2026101701_global_weak/
```

每目录内有 `manifest.json`、`x0_step000.pt` 至 `x0_step019.pt`、`sampler_final.pt`；每个 PT 约 11.64 MB。两份 manifest SHA 分别为：

- native：`19bc711dda60c773f8a113d6353acaf4de58957cf5e5931988b48d5504213298`
- weak：`d886e75a7d40496bc64e9a64e36a625591c5a1fa982663f8ff6c2c3b5916f9f4`

两份目录分别向上两级的 `audit/` 下有同名 `r123_short_0358_seed2026101701_noise.pt`，11,635,813 bytes。native／weak 的初始 video noise 内容 SHA 都为 `794e76b6affb86f07727fb10ac46aa950350165c73d8a6f91eb603a15328c29c`。

### 手帕：native 在 .9，weak／参考副本在 .41

.41 参考 latent（纯 tensor，17,021,000 bytes）：

```text
/data4/research-user/h3_runs/benchmark_schedule_20261022/innovation_cache/long_0059/090756dca6b1ff75fcd0c17fcf78a4f166676f0d26f8f832adde9ec951b68f24.pt
```

conditioning：同目录 `r126_long_0059_shared_conditioning.json`。参考 tensor 内容 SHA：`4f2eb8a7892d4c5a7f827bed3693150bf4f4340ed731b408c398c244d67f8323`；文件 SHA：`e11885c4d9e91c95f9942dbaae33ba85ff04d960bae691fcbabdd72f93ece7c0`。

.9 原始参考文件在：

```text
/home/research-user/h3_runs/timing_ive_handkerchief_full_context_r126_20261020/audit/tensor_blobs/090756dca6b1ff75fcd0c17fcf78a4f166676f0d26f8f832adde9ec951b68f24.pt
```

这个原始路径由已校验的 cache manifest 记录；实施 CPU 读取时再检查文件 SHA，避免复制大文件。

.9 native 捕获目录：

```text
/home/research-user/h3_runs/timing_ive_handkerchief_full_context_r126_20261020/audit/x0/r126_long_0059_seed2026101701_native/
```

.41 weak 捕获目录：

```text
/data4/research-user/h3_runs/guidance_schedule_r150_20261021/cases/long_0059/audit/x0/r150_long_0059_seed2026101701_global_weak/
```

两者均有 20 份 x₀ 与 final；每个 PT 约 17.09 MB。manifest SHA：

- native：`de8e5d935980e17f8d421f281f328dacf691e4084cc0e0dc6823cdbdfbaea02b`
- weak：`628b49efbb5614894085f89e155347469e34c7292ad37a8ed8fd769e752447ce`

.41 的 weak audit 下已确认 `r126_long_0059_seed2026101701_noise.pt`，17,088,786 bytes，video noise 内容 SHA `e49f05c1380fef662b900f1d46afd64952c7aa81f65a4772f8ccb8f9f6c99187`。

## 时间轴、归一化与读取方法

1. 文件 `.pt` 用 `torch.load(path,map_location='cpu',weights_only=True)`；参考为 tensor，预测／final 为 `{'video':tensor,'audio':tensor,'metadata':...}`。不要调用 Comfy 节点的 `load/reconstruct/publish`，它们会加载其他条件并写 audit。
2. source 是实际 VAE encode 输出，生成 video 已 `process_latent_out` 且 scale=1，视频保持不变；audio 已除以4。VAE 的 mean/std 仍留待 decode，本诊断完全不解码。参考／生成视频处于可比较的 latent 坐标口径。
3. `x0_step009.pt` 是零基第9步、模型第10次调用、当前 σ=0.936170220375061 的 clean estimate，**不是当前 noisy state**。`sampler_final.pt` 是采样器真实端点 σ=0；step19 的 x₀ 与 final 可能有 FP32 Euler 舍入差，不能用二者文件名互换。
4. 物理帧覆盖采用 `s_t=(1,4,4,4,4)[t mod 5]`，`a_t=Σ_{j<t}s_j`，帧区间 `[a_t,a_t+s_t−1]`，代表中心 `c_t=(a_t+(s_t−1)/2)/24` 秒。它是分组代表时间，不是声称 VAE 的卷积感受野仅覆盖这些帧。原模型 `_video_t_grid` 的 RoPE 坐标用 **exclusive cumsum 起点** `origin+(5/3)a_t`，并非上述中心；诊断物理时间不使用跨模态 packed origin。
5. 饮酒有效帧为0..104，完整有效 bin 为0..30；bin31覆盖103..106，跨入补帧应整 bin 排除。手帕有效帧0..143，完整有效 bin为0..41；bin42覆盖141..144跨界，bin43覆盖145..148已完全无效，均排除。实施时用公式生成 mask，勿用此处文字硬编码。
6. 已知移位只在 source 与 displaced tensor 共同有效区间比较。不能 `roll` 后保留回绕部分，也不能把最后重复帧算成真实动作。移位 bin 对应的秒数随 `c[t]−c[t−δ]` 变化，不能统一乘4/24。

## xₙ 的后续重建入口

已审阅的旧 `H3X0Readout/core.py` 强制 `sample_euler`、20步、无 churn。实际 `comfy/k_diffusion/sampling.py` 使用

```text
d_n = (x_n - denoised_n) / sigma_n
x_(n+1) = x_n + d_n * (sigma_(n+1) - sigma_n)
```

从真实 noise 文件与已保存的全部预测可逐步递推；视频 clean estimate 可直接使用，音频要乘回4再与 packed sampler 口径一致。初始 FLOW_AV 在 σ=1、空目标 latent 下由真实 noise 起步，需同时核对实际 sampling class/noise_scale，保留原 FP32 运算顺序。

这种离线递推无需 DiT，但当前尚未执行、也没有 intermediate x 实录用于逐步比对。最后一步 σ=0 会把前面状态误差大幅消去，所以只比较最终端点不能证明第9步重建逐元素正确。若后续做单步干预，先重建基线并做一次模型输出与已保存第9步 x₀ 的一致性检验；差异超出预设容差时才需要新的状态捕获。

## 最小离线方案与可复用入口

优先在 .41 `/data3/research-user/ComfyUI/.venv/bin/python` 运行饮酒两组和手帕 weak；手帕 native 在 .9 `/home/research-user/miniconda3/envs/comfyui/bin/python` 原地读取。设置 `CUDA_VISIBLE_DEVICES=''`、`OMP_NUM_THREADS=1`、`MKL_NUM_THREADS=1`，脚本显式 CPU；只传回小型 JSON 和特征／代价矩阵，不下载大 latent。

先读每例 reference 与 native/weak 的 `sampler_final.pt` 做 ±2/±1/0 bin 自移位、静态通道偏置不变性；再对 `x0_step009.pt` 做同样检查，最后按完全相同参数计算 source→native/weak 的相位。保留失败、歧义及无信息区域。native 9/10.5帧、16帧延迟是外部粗粒度检查；weak 的小误差用于识别明显误报，不要求分辨亚 bin。

现成代码入口：

- `/workspace/research-user/DevProjects/h3-guidance-schedule-r149-20261020/cases/short_0358/extensions/H3X0Readout/core.py`：捕获语义、文件 schema、signature、normalization。
- 同目录 `H3EventAudit/__init__.py::CachedNoise`：初始 noise 原始文件及签名。
- 同目录 `H3CachedCondition/__init__.py::checked_tensor`：参考缓存验证口径；诊断仅复用逻辑，不调用会发布文件的节点。
- `/workspace/research-user/DevProjects/video-motion-alignment/execution-20261022/inference/package/custom_nodes/H3Study/layout.py`：frame_spans。
- 本地 `metrics/manifest.json`、`timing/event_offset_completion_20261022/SUMMARY.json`：有效帧、冻结事件、seed、原始 gate 来源。

后续独立 CPU 脚本与 prereg 放在 `innovation/latent_phase_calibration_20261023/`；不改变以上旧产物。
