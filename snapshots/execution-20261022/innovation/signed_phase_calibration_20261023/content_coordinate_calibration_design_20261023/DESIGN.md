# 固定坐标下的参考编码内容干预：只读设计

状态：设计完成，未实现 runner，未读取真实张量，未作扰动、GPU 前向或部署。现有同环境原生轨迹是输入来源；本设计的孤立前向复放尚未核验。旧历史 REPLAY_GATE=false 保持不变。

## 1. 这一步要解决的具体问题

上一步固定 layer 25、全部 56 heads × 8 个保留身份的 query probes、4 个同一步 native↔weak 测试通过 124/124 零移位定位。它同时改变了旧方案的空间对应保留方式和 head 聚合方式，提升不能单因果归给空间池化。纯位置码也能通过零移位测试。

本设计仅问：保持位置、RoPE、目标 AV 状态和 sigma 不动，只移动参考编码内容，固定原 K_R 字典读出的新 Q_R 指纹更像原内容位置，还是当前坐标位置？这是坐标依赖与内容敏感性的受控诊断，尚非动作相位控制器。

## 2. 已核对的实际输入链

当前 short_0358 单个无参考音频的视频条件：

`H3TrustedConditionCache.reconstruct → positive[0][1]['minimax_refs'][0]['latent'] → MiniMaxH3.extra_conds → minimax_payload['cond_video_latents'][0] → MiniMaxH3Model._cond_video_rows → patchify_video → video_patch_proj → 50 个 block`。

实际 model_base.py 的 MiniMaxH3 源码在 `replay/sources/HOST41_AV_SOURCE.json`，其 SHA 与同环境 INPUT_IDENTITY 一致。extra_conds 把 refs 原样放进 payload，并把 r['latent'] 加进 cond_video_latents；这里没有新增 process_latent_in 对参考条件二次归一化。缓存加载器输出的 latent 就是此接口应收的值。优先在 extra_conds 之后对 payload 做独立副本，替换其条件列表中的这一个张量；refs 的 latent 引用也应指向同一新张量以保持一致，但形状、kind 和 layout 元数据不变。原 payload、缓存和布局张量禁止原位修改。

已编码参考路径：
`/data/research-user/h3_inference_20261023/run/innovation_cache/short_0358/27b35d491b84f5c12a5b0f91ec91c2bb1b94b6b5c249a3e55476e0f2cb443e22.pt`

文件 SHA `3c1cb0d2668f72169873271782be51aad0d2295203a1790e4c57f16884595dfd`；tensor SHA `1ad0955cfa27b1215d5e8c8334d844944143040ce9e8f0f8a8e9618dc13d1081`；Z 形状 `[1,24,32,46,82]` float32。仅置换第三轴，整份 C/H/W slice 一起搬，不改变空间 probe。

patch=(1,2,2)，每 bin 有 23×41=943 rows，每 row 96 输入维。序列布局为 text `[0,5125)`、reference `[5125,35301)`、target audio `[35301,35657)`、target video `[35657,65833)`；参考行号 `5125+943*t+p`，目标行号 `35657+943*t+p`。固定 probes `[0,135,269,404,538,673,807,942]`。Q_R/K_R 原始采样形状 `[32,8,56,128]`。实际执行时仍须从 capture/layout 逐项断言这些值，不凭设计文档替代校验。

位置缓存 `[65833,3]` float64 tensor SHA `737b24445da7970b17f41a34dedaf2e091cca1cbe827e904ea178a849053dd01`。H3 时间角色 `FRAME_PER_TOKEN=(1,4,4,4,4)`，RoPE 时间步长另乘 `FRAME_RESCALE=5/3`。因此 ±5 bins 保持 t mod 5，对应名义 17 视频帧和 85/3 个 RoPE 坐标单位；本实验位置坐标一个数都不移动。

`_cond_video_rows` 原样使用 aug=.999、固定 seed，逐坐标加入 `.001*noise`。新条件应先置换 Z 再由原函数加同一坐标噪声；不得连噪声一起置换、修改 aug 或重采 seed。保持坐标噪声意味着它本身仍可能携带坐标识别线索，结果需一起解释。当前 capture 没有单独保存该条件 noise tensor；源码可由相同 CPU torch.Generator、seed、shape、float32 和相同软件环境重建，但本次没有实际重建或核验。后续 adapter 应在新零扰动核验中生成一次并保存 noise/augmented_rows 的 SHA与 RNG/torch版本，所有扰动复用同一份逐坐标 noise；同时要求完整 raw x0/QK 对原记录逐元素相等。若条件噪声不能精确恢复，就需要新完整控制中的被动条件噪声记录，不得借历史失败 REPLAY 过门槛。

## 3. 边界与唯一可立即定义的无补帧候选

107 名义帧中有效帧为 105（0…104）；完整有效 bins 为 0…30。bin 30 只含帧 102，bin 31 跨 103…106，不能当成完整有效 bin，也不能搬入有效支持。

对整段定义 `Z'_t=Z_(t-δ)`、δ=±5，32-bin 现有缓存不含外侧上下文。不能循环、重复末帧、置零，不能只删分析边缘后称整个模型无边界影响：所有 block 的全局 attention 会传播边缘改变。自然窗口的双向平移还需前后各 17 个名义视频帧及 VAE 编码相位/边界行为证据；当前只有 VAE 文件哈希，未审其完整编码源码及源视频额外上下文。严格整段平移此刻阻塞。

可执行替代候选：内部两个完整同角色五-bin 块做双射对换，先提议 A=[5,10)、B=[10,15)，其余原样。定义 π(t)=t+5（t∈A），t−5（t∈B），t（其他），然后 `Z'=Z[:,:,π,:,:].clone()`。这是 π 的逆等于自身的置换，无生成值、无丢失值、无外边界填充；bin 31 完全原样。A/B 分别覆盖帧 17…33 和 34…50，保持每个 bin 的1/4帧角色。此索引由固定内部五-bin 网格给出，不根据已有收益或事件挑选；尚未冻结为执行 POLICY。

新 query t 的已知内容来源是 π(t)，当前位置是 t。两个候选解释必须同时报告。两个采样步各报告所有10个交换 bins（共20个相关 query）和其余21个有效未交换 bins（共42个相关 query）；分母预定，不挑成功 head/probe/bin。不把同一前向内的 query 当独立样本。

可选第二种距离对照是 A=[5,10)、C=[15,20) 对换（±10 bins）。它会增加两次前向；当前建议先最小 ±5 对换，不默认扩展。

这是**编码内容对换**，不是自然平滑视频的时间平移。接缝、动作次序打乱以及跨时间上下文变化都真实存在。它避免伪造边界，但不能要求 layer25 的表示严格置换等变，也不能由成功直接推断自然动作延迟可被准确读出。

## 4. 固定目标状态与固定原 K 字典

只用新同环境 native 的 step_zero_based 9、19，各自独立。完整 saved packed_x `[1,1,2908288]` float32，包括 video `[1,24,32,46,82]` 与 audio `[1,32,2,178]`。sigma 分别为 .936170220375061、.3870967626571655；完整原 schedule 一并固定。精确 state/QK 路径与文件/tensor SHA 已提取到 INPUT_MAP.json，来源是已经完成的 native_OBSERVATION 与 actual_run inputs，不读真实 tensor。

调用位置必须在原 sampler 的 model-wrap 输入域，以该 packed_x 和相同 sigma 调用完整的原模型路径，保留 process_conds、NestedTensor 拆包、ModelSamplingAV 音频 carry、audio_scale=4、视频/音频 shift12/3及原 sample_sigmas。不能把 packed_x 直接塞给 diffusion_model._forward，也不能把已带 carry 的音频再次缩放。此隔离 adapter 还未实现；现有 live observer 要求完整20次 callback，不能直接拿它伪装成单次合格轨迹。

先为每一步独立做原条件零扰动前向，核对：输入 packed_x SHA；全部原条件与位置 tensor SHA；两个完整 AV raw x0 和原 capture Q/K 的逐元素相等；固定50 block/1 forward；实际 backend/精度与保存轨迹一致。任何零扰动差异都先定位，不事后放宽误差阈值，不改旧门槛。新 gate 单独命名和保存。两步全部通过之后，才准许各自的条件对换前向。

字典固定为**同一步原 native 捕获的 raw_K_R**，使用原 k_norm_weight/eps 得到 pre-RoPE 内容 K；新 Q_R 使用原 q_norm_weight/eps。不要使用对换后 K 重建字典，那会让坐标和内容共同移动。也不跨 step 复用字典。

沿已有 evaluate_probabilities 的定义：每个 head/probe 的 query 与31个有效 key bins各8个 key probes求 dot/sqrt(128)，先对8个 key probes log-mean-exp，再对31 bins softmax。所有 query-probe 身份和56 heads保留。与原 refself 概率指纹按 `sqrt(p)` 等权拼接，距离为float64逐差平方和/448（范围[0,2]），禁止 Gram 相消。η=64eps只判断浮点并列；对每个 query 保留全31候选距离、最小集合、当前位置与内容来源的 margin。主报告当前 t 与来源 π(t) 的竞争；未交换区是上下文溢出对照。不得挑 head、阈值、step 或只报告最近值。

## 5. 静态与外观对照：现有缓存能定义到哪里

- 复制某一个 latent bin到所有 t 会混淆1帧/4帧角色，不能称自然静态视频。
- 每个 t 按 t mod5 复制同一五-bin块可严格定义，但它是一个17名义帧周期的编码条件；应允许同角色周期多候选，不能要求唯一绝对时刻。可作为周期反例，不能替代静态控制。
- 真正静态条件应由预先固定的一张源帧复制形成完整107帧，再用同一 VAE 编码一次，审清其因果/分块/填充和归一化规则。此处只做一次离线条件生成，不是推理每步RGB检测；当前缓存没有该条件，必须新建并单列，未授权为本次默认四前向的一部分。
- 时间不变的 latent 全局缩放/平移或通道旋转可数学定义，但没有证据它只改变外观而保留运动，不能作为跨身份外观鲁棒性对照。真实外观改变可用全帧一致的已定义光度变换并重新编码、或经过验证的另一外观同动作参考；它是另一个条件批次，需要新的 source/encoder 证据，当前缓存不足。
- 纯位置编码反例和周期反例可全部在 CPU 合成概率上测试，不需要新模型调用。它们应在执行前纳入 adapter/readout 测试。

## 6. 有限前向数、反例与停止点

最小候选：native step9、19各一次零扰动核验（2），通过后各一次内部±5双射对换（2），**总计最多4次独立完整模型前向**，零采样轨迹续跑，零视频生成/解码。每次读取固定 layer25 后仍跑完整模型以核 raw AV；不在同一前向内叠加多扰动。可选±10再加2次；角色周期编码反例若独立通过方案审查再加2次。真实静态/真实外观对照不计入现有4次计划，也没有被部署。

执行前须在新目录实现并验证：互换双射及反演；角色/边界不变；原条件无别名；全部冻结输入保持；错误SHA/缺原gate零模型调用；计数/异常恢复；概率字典不随新K变化。CPU有限反例至少包括：纯位置码（零移位全过，对换仍定位当前t）；纯内容码（可区分内容应定位πt）；位置+内容混合；重复/周期内容（并列正确保留）；固定坐标增强噪声造成伪位置；全局上下文导致未交换区改变；全局latent通道扰动改变运动而非仅外观。不得把反例成功或零扰动124/124当实际内容敏感性结果。

如果零扰动复放不过，下一步是修复隔离调用域/后端一致性，或在新完整 native 控制运行内被动保存可直接复用的 prepared payload与调用入参；不能从旧 approximate x0重建后宣称等价。若对换观察仍只认坐标，结论限于固定layer25、这些完整56×8联合指纹及该内容干预；若更认内容，进入新自然时移/外观校准设计，而非立即用它控制alpha。

## 7. 本次明确完成与待做

完成：只读实际 H3/ref缓存/同环境状态/概率定义映射，来源哈希记录，严格边界与双射替代设计。未读NPZ/PT实际数组；没有代码部署、前向、扰动、指标或新GPU结果。

待做：root选择并冻结下一POLICY；独立审查；单前向adapter及其CPU/失败注入测试；现场输入/后端核验和新零扰动gate；之后才考虑4次真实前向。完整VAE编码与额外源上下文证据仍待读取，严格自然视频平移、自然静态和跨外观对照因此未就绪。
