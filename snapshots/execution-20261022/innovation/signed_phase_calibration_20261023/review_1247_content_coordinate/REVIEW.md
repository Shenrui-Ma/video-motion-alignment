# 参考内容／坐标分离设计：独立只读审查

**建议进入隔离 CPU 构造与 adapter 验证阶段。当前不具备 GPU 前向或 alpha 准入。** 内部 `[5,10)` 与 `[10,15)` 的同角色双射对换，是现有缓存可定义的有限干预；它比补边的整段平移更干净。它检验的是“layer25 指纹对参考 VAE 内容通路的敏感性”，解释应保留下面的非对称性。

## 已核源码与输入事实

INPUT_MAP 列出的10个小源码/记录 SHA 全部匹配。实际链为缓存中已规范化的参考 latent → `minimax_refs` → `extra_conds` 的 `cond_video_latents` → `_cond_video_rows` → `patchify_video`/增强 → `video_patch_proj`。`extra_conds` 不再对该参考 tensor 调用 `process_latent_in`。

参考形状 `[1,24,32,46,82]`，patch `(1,2,2)`。patchify 先按时间、空间patch排成 `[30176,96]`，每bin943行。置换完整时间slice，等价于对这30176行做对应943行块重排。设计索引是完整双射且自逆、所有 `t mod5` 不变、只动5…14、bin31不动；A/B的名义中心差分别为+17/−17帧。这些是位置映射，不是精确VAE感受野。

原 native 观察器校验过 seed=2026101701、完整21项sigma、audio_scale=4、实际 packed AV 状态和50层路由生命周期。新前向必须在原 sampler model-wrap 输入域调用；完整sample_sigmas仍供FinalLayer使用，不能缩成一两个sigma，也不能对已带carry的audio重复缩放。

## 条件 noise：CPU可以证明什么

实际源码每个视频条件都重新执行：

    r = patchify_video(z.float(), (1,2,2))
    g = torch.Generator('cpu').manual_seed(payload['seed'])
    N = torch.randn(r.shape, generator=g, dtype=torch.float32)
    augmented = aug*r + (1-aug)*N.to(r.device)

这里的随机数形状必须是 `[30176,96]`，**不是先生成 `[1,24,32,46,82]` noise 再patchify**；两者随机序列在线性内存上的分配不同。它也不是初始目标AV noise文件。seed不随step变化，不能擅自加step号。当前源码固定aug=.999，实际运行仍应核prepared payload及默认常量。

正确干预为 `a·P r +(1−a)·N`，而非 `P(a·r +(1−a)·N)`。后者把坐标noise一起交换；两式的数学差为 `(1−a)(N−PN)`。实现测试应按原FP32运算顺序核结果，而不是要求重排后的实数恒等式在浮点下逐元素相等。

CPU可完成三类验证：① 从真实源码抽取patchify/增强函数，给小型合成tensor做索引、双射、同角色和noise不移动的独立oracle；② 确认独立Generator不改变全局RNG、重复相同完整调用得到同一N、payload/container副本与原tensor无可写别名；③ 另获授权后，在实际同版本CPU环境按精确seed/完整row形状重建N、记录原运算设备/dtype/版本和noise、augmented rows签名，再与adapter实际使用值核对。第三项不需要加载视频模型，但本次没有执行或读取真实大tensor。

现有capture没有历史条件N及augmented rows的独立签名。故CPU重建可证明实现符合被核源码与RNG配方，**不能从历史x0/QK反演或单独证明历史N的逐元素身份**。缓存加载器把latent放CPU，payload绕过常规BF16展开；仍需adapter记录实际增强时的`r.device/dtype`，不能只依据缓存初始设备推断完整调用链。

## 干预的识别力和主要混淆

固定原同step K字典、用新Q_R形成概率指纹是正确选择。定义完整31候选距离 `d_t(j)`，对交换区报告：

    content_margin_t = d_t(t)² − d_t(π(t))²

正值更偏内容来源，负值更偏当前位置；还须保留全局最近集合，区分来源/当前位置/第三位置/并列，不能因二者竞争获胜便忽略第三位置更近。每步10交换bin和21未交换有效bin全部保留。

**未改的5125-token Qwen3VL conditioning embedding也是原参考多模态presentation，不是纯文本；target x_n也已积累原轨迹上下文。** 本干预固定它们，因而只动一个参考条件通路。更认π(t)可支持该读出对VAE参考内容通路敏感；仍认t时，可能来自位置/RoPE、固定noise、未动Qwen视觉信息或target上下文恢复原顺序，不能单独归因为位置码。无需为消除这些因素而在本轮叠加更多改动；在冻结解释中写清即可。

另有两项边界：① “target AV固定”指模型输入固定，经过全局attention的target隐藏状态会因参考交换而变化，再反馈至参考query；② 两块交换形成新的接缝/顺序冲突，模型不要求对它严格置换等变。未交换区可观测全局溢出，不能默认其内部特征完全不变。即便π(t)检索成功，仍只是编码参考内容的干预证据。

## 新零扰动 gate 是前置条件

先只做两个独立的zero-perturbation资格检查：同step原packed_x、原prepared payload、完整schedule、模型/精度/backend和位置。每次须满足实际1次完整model forward/50block；两完整流的raw x0、原raw与actual Q_R/K_R（以及已保存Q_C）逐元素匹配，hook不得替换返回对象。两个step均通过后，才可单独释放两个交换前向；若零扰动失败，交换必须0次。

prepared条件副本应同时替换`cond_video_latents[0]`与新`refs[0]['latent']`，二者引用同一新tensor；原payload/list/ref字典/tensor不改。layout、position/RoPE、modulation、embedding/tags、所有非目标条件和原target输入签名保持；中途异常清理hook与临时patch。不能借用已失败的历史REPLAY gate，也不能把20步live observer记录改成一次前向“完成”。

## 最小CPU反例与下一步

- 纯位置码：新读出仍认t；明确不能凭此前124/124排除。
- 纯内容码：新读出应认π(t)；固定K才能测试这个映射。
- 固定坐标noise占主导：内容确实交换但仍认t，不应误判“操作没生效”。
- Qwen/target原上下文占主导：与上一反例相同输出，说明单次负结果无法分离原因。
- 全局交互模型：交换区外也变化；保留全部21未交换bin。
- 周期/重复内容和来源/坐标混合：保留并列及第三候选，不强制映射成一个动作延迟。

有界下一步是冻结这一个swap POLICY，完成CPU输入/数学/失败注入和单次adapter审查；随后由root另行决定是否放行最多2次零扰动与2次交换。真实静态、外观不变和自然时间平移条件尚未准备好，不算这4次已覆盖。当前设计不新增部署、完整视频、参数搜索或alpha方法。
