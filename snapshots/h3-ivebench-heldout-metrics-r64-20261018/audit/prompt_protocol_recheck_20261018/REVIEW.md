# H3 编辑提示适配复核

当前 P0 的失败含输入协议这一未分离因素。R54/R55/R63 的 short0210 都只把原始 `edit_prompt` 传入 H3，例如 `Replace the woman with a man`。当前 R64/R69 仍保留其原始 P0 协议。它们能回答该协议下固定时序引导相对普通编辑的效果；不能单独解释 H3 为何改变动作或场景。

## 已有 P1 工作与实际运行状态

R57 已在此前完成原五条 P1 模板、元数据、图、输入绑定及 CPU 运行程序。其队列依次为 0210、0230、0263、0352、0370，均为 Native。此前审查见 R55/audit/IVEBENCH_PROTOCOL_INTERPRETATION_REVIEW.md 的“优先补充：先诊断 H3 的 prompt 适配”。因此这项诊断属于已登记而尚未见成片的工作。

本次只读核验的 .41 R57 正式目录中 scripts 与 analysis/postrun 存在，logs、output、processes 均不存在；本地亦未找到实际 P1 完成记录。此检查范围内没有 P1 成片证据。R57 的五条登记及 CPU 准备不应计为五条已生成结果。精确路径与本次文件 SHA 在 EVIDENCE.json。

## 官方约定与本地接口

官方 [Ref2VA rewrite guide](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/references/ref-en.txt) §2.3 以 `<Video N>` 表示源视频及整体时序结构；§3 标记编辑任务；§4 说明保留关系；§5 描述目标动作与场景。它属于 rewrite 输出写法，尚不足以断言短指令会被解析器拒绝。已登记 P1 采用这套组织方式，是实验模板，不是逐字复制官方示例或官方重写器的输出。

官方 [可复现 Ref2VA 请求](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/scripts/readme/reproducible-768p-ref2va-request.sh) 同时提交分节文本及 role=reference 的视频，明确哪些镜头、环境内容保留，以及要编辑的内容。它支持适配诊断的必要性，不能证明当前失败已由提示格式导致。

本地实际节点见 source_snapshot/comfy_extras/nodes_minimax_h3.py：242–255 定义图像/视频/音频引用标签；314 起处理视频，343 编码 VAE，359 调用 `clip.tokenize(prompt, minimax_ref_items=ref_items)`，360 编码条件。视频条件确实接入；该节点原样传递提示文本，没有自动添加完整保留语义。不能把 P0 解释为“根本没传入参考视频”。

H3EventAudit 在 tokenize 前记录 qwen_presentation，内容是抽帧 RGB 与采样时间。联合 Qwen conditioning_embedding、token_tags 与 packed position 会受不同文本影响；跨 P0/P1 只要求原始 RGB、VAE 参考 latent、编码前 Qwen 抽帧和初始 AV 噪声一致，分别核验每版联合条件的完整性。

## 已准备的最小实际对照 R71

Root 批准对原登记第一条 short0210 在 .9 同一个新服务运行 fresh P0 Native 与冻结 P1 Native。R71 逐字复用 R57 P1；同源、同种子、同模型、同采样、同原始 AV noise。两版各用独立文本缓存，20 步全为 Native，无在线 observer、无时序引导。21 份实际 AV 状态和条件张量保留；不要求预测轨迹前六步相等，因为提示文本从第一步就发生作用。

R71 目录：`/Users/researcher/DevProjects/h3-timing-ivebench-prompt-pair-r71-20261018`。27 项 CPU 测试通过；本次准备尚未启动 GPU。该试验回答整个提示适配组合是否改变结果：参考标签、源/目标描述、保留要求与分节格式共同变化，单对实验无法分离这几种因素。先看主体编辑是否成功、源动作类型/镜头/场景是否保留，再讨论相同动作的时间差。结果属于已观察 development source 的输入诊断。

R64 的新道具/环境编辑不能直接套用 P1 中“appearance edit”一句。若以后扩展，须单独冻结通用任务模板；本次 R71 仍沿既有角色替换模板逐字执行。当前 R64/R69 P0 批次保留全部结果，提示适配收益与时序方法收益分别报告。
