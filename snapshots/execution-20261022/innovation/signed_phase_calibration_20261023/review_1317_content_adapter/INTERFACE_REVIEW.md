# 单前向 adapter 接口审查（实现前）

结论：现有新 live native 的 step 9/19 实际 packed x 与 raw packed x0 已足以准备有限前向，原包装域可由现有 finite SAMPLER 接口进入。无需重新构造整条 Euler 轨迹。真实零扰动复放尚未完成，接口可执行性与科学输出可靠性分开核验。

## 实际调用链

`SamplerCustomAdvanced → CFGGuider.sample/outer_sample/inner_sample → process_conds → KSAMPLER.sample → finite sampler_function → KSamplerX0Inpaint → CFGGuider → sampling_function → BaseModel.apply_model → MiniMaxH3Model.forward → _forward`。

- `CFGGuider.inner_sample` 设置两流 latent_shapes，执行一次 process_conds，保存完整 21 个 sample_sigmas；外围最终执行 process_latent_out。
- finite sampler 接收已经建好的 model_k，直接用新 live 保存的 FP32 packed x 替代初始 sampler input，调用一次 `model_k(x, sigma_step, **extra_args)`。不能再次给它 process_latent_in/noise_scaling，不能绕过到 diffusion._forward。
- raw packed x 是视频 schedule 上的双流变量。H3.forward 按 sigma_a/sigma_v 将音频 carry 转回模型域，并将输出速度转回 carried variable；这些必须只执行一次。比较完整 raw packed x0，不仅视频；外围的音频 /4 不是模型输入操作。
- 完整 sigma 列表参与 FinalLayer 计算，不可只传局部两点。native 仍保留原 50 层 H3Study wrapper/Flash 入口，单前向步计数可在独立新状态中定位 9 或 19，之前的空计数必须标为未运行。

## 条件与噪声

准备后的 CONDConstant payload 包含 refs、cond_video_latents、layout、text_token_tags、audio_scale 和 seed。只独立复制改动的容器及新 Z；`refs[0].latent` 和 `cond_video_latents[0]` 必须引用同一个新 Z。原始列表、张量、layout/position_ids、缓存和经过 refiner 的 multimodal context 不变。需要异常后恢复临时包装器/条件。

原 `_cond_video_rows` 每个条件独立重置 CPU Generator(seed=2026101701)，先 patchify 成 [30176,96] FP32 rows，再抽同形状 FP32 N，执行 `.999*r + .001*N`（遵循源码的 Python 标量与 Torch 算术）。N 不随内容换位，不按 latent shape 抽取，也不加 step。可在实例级包住原方法：调用原方法、用同设备原算术独立验证返回 rows、记录 SHA 并返回原对象。不全局替换 torch.randn。

完整原始缓存与 position/model/core 身份有小 JSON 证据；实际 coordinate N 旧时没有单独存盘。CPU 重建可核算法，真实 gate 才能核当前 prepared input 与旧 live 计算等价。保持 Qwen3VL 视觉 context 与 target x 固定意味着这是 reference VAE 路径干预，不是所有条件联合交换。

## 最小实际 gate（尚未执行）

分别 step 9 与 19 原条件：实际新 state/contract/capture/cache/model/core SHA 精确匹配；full sigma/AV scale/shape/backend 相同；只有 1 个模型调用和 50 个 block。raw 完整 AV x0 逐元素等于本次 live 保存值；layer25 原始与实际 Q_C/Q_R/K_R 全56 heads、8 probes逐元素匹配；输入/坐标/噪声/位置无修改。先两个 zero 均通过，再独立批准两个 swap，旧 historical REPLAY=false 保持不变。

backend 不能仅依靠配置名，记录实际 INT8 dispatch（Triton/CUDA/eager）与原新 live 的相同调用结构；权重/core SHA 只证明源身份，不证明 kernel 数值路径。

若 exact zero 失败：保留结果定位具体域/包装/后端差异。只有明确缺失的 prepared-input 值无法恢复时，最小替代是新的原 native 完整轨迹在9/19被动保存该值和 condition noise，再进行同状态有限前向；不以重跑整片代替当前可完成的接口检查。

## 待实现独立测试

实际 KSAMPLER/CFGGuider/AV 原 AST 的 CPU fixture；一次 process_conds/carry/输出 normalize 计数；full schedule与state身份失败注入；临时 condition/noise/QK 包装异常恢复；zero gate 任一流或任一 QK 分支单元素变更即拒绝；缺 step、假旧 gate、错缓存/seed/backend不允许模型调用。


## 已与作者对齐的执行域（13:17轮）

同一次 guider.sample/process_conds 中顺序执行 zero9、zero19；仅两条均通过后才可执行 swap9、swap19。每条使用各自保存的原 packed x，并从同一未使用 native router 模板建立新的局部计数；从不把前一条 x0 喂入后一条。每条 model_k 内部增量应为1次 forward、50 blocks、200次实际 Triton INT8；预处理 token refiner 计数另列。最后返回 raw x0 仅满足外层 SAMPLER 类型，不记录成20步轨迹或新视频。

缓存 reference Z 的原 device/dtype 必须保持。`_cond_video_rows` 在 Z 所在 device 做 patchify 和噪声乘加，最后才搬到目标 device；提前移动 Z 可能引入 CPU/GPU 舍入差异。噪声同一性以生成值的 tensor SHA 而非只凭 seed 校验。所有临时 payload、condition、方法与hook都需 finally 恢复。
