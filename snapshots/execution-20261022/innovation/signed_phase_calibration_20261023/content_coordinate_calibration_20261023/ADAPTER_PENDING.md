# 单前向接口尚未实现

以后若推进，在新的运行包中实现，不修改已冻结live runner。输入必须来自实际同环境native state，不用历史近似x0重建；保持原ModelSamplingAV/NestedTensor、audio carry、sample_sigmas、cfg、原conditioning、actualTriton和量化/offload路径。

按固定先后顺序进行：
1. 验证POLICY/源码/原state/QK/condition/model与core来源，来源不符零模型调用。
2. 准备完整原调用域。原capture未单存coordinate noise；原CPU Generator(seed)可定义重建，但实际exact恢复尚待证实。保存一次noise与augmented_rows SHA并固定同一noise给每个条件。不能把noise和内容一起换。
3. step9、19分别先原条件前向，所有输入SHA不变，完整rawAV x0、raw/actual Q_R/K_R逐元素匹配原capture；1forward/50blocks、backend、layout/position/RoPE核验。任何差异须定位；不能借旧REPLAY_GATE=false过关或调容差。
4. 两步均通过后，才各一次交换latent条件前向；新Q_R始终读同一步原K_R。全31bin与所有56×8保留，包括未交换区上下文溢出，不做标签驱动筛选。
5. 新零扰动门槛、原噪声恢复、源哈希与输入角色均是新证据。本CPU包尚未提供任何这些实际结果。

不能直接把packed_x喂给diffusion_model._forward，也不能拿现有要求20 callbacks的observer伪装成单前向。若无法精确复放，替代方案是在新完整控制中被动记录prepared inputs和condition noise；届时另立有限运行计划。本次未安排该控制重跑。

条件噪声原源码是patchify之后的[30176,96] rows上采样；每条件重建同seed CPUGenerator，不能按latent形状采样再patchify，不能加step。真实adapter的payload副本须保证refs[0].latent与cond_video_latents[0]指向同一新Z，同时原list/dict/layout/tensor不变。这些接口未在本包实现。
