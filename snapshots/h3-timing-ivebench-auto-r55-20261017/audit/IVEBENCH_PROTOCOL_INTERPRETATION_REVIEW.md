# IVEBench 五条 H3 测试的协议与结论审查

2026-10-17。只读审查当前协议、已归档官方源码，并核对 arXiv 原文。本文件提出结果解释与补充评价建议；没有修改实验、筛选输出或运行 GPU。

当前测试适合回答：**在五条预先选定的外观编辑任务上，自动时序干预是否改善运动保持，同时完成编辑。** MF、局部时差和编辑成功需要分别呈现。

## 1. 五条样例的结论范围与官方 benchmark 不同

IVEBench 覆盖指令编辑的多种任务；当前保留官方 `edit_prompt`，使用一段视频、零张人物参考图，任务输入与 instruction-guided editing 对应。五条具体是三条主体替换、两条颜色修改；动作应保持，均适用官方 MF。

选择记录是 600 条 → 替换/颜色 88 条 → 短片 60 条 → 下载并查看源帧 12 条 → 固定 5 条；选择时查看 H3 输出数量为 0。这是依据源内容挑选的开发小集合。报告可称“IVEBench 五条原任务的 H3 适配测试”，并给逐条结果；总体有效率的推断范围限于这五条、一个固定 seed。

FlexiAct 的当前五条来自公开 human 子集的 39 对，每种动作取固定 CSV 第 0 行；H3 使用统一动作迁移指令，官方 captions 仅留作元数据。它与 IVEBench 的纯视频指令编辑、FlexiAct 论文的 250 对完整评价各有不同范围。两套结果分别列出，MF 也分别标注评测器名称。

出处：[IVEBench 官方 README 的任务与评价说明](https://github.com/RyanChenYN/IVEBench/blob/2dcf8900ee65197f43854c76f61c66a32bb8dbfc/README.md#-highlight)；本地 [IVEBench 选择记录](/Users/researcher/DevProjects/h3-ivebench-pilot-20261017/inputs_selection/PILOT_5_MANIFEST.json:4) 第 4–32 行；[FlexiAct H3 协议](/Users/researcher/DevProjects/h3-timing-flexiact-native-r49-20261017/design/PROTOCOL.json:3) 第 3–27、343–352 行；[FlexiAct 论文 §4.1](https://arxiv.org/html/2505.03730v1#S4.SS1)。

## 2. 当前物理时间处理支持方法内配对比较，仍有采样分辨率限制

五条输入统一为 1312×736、90 帧、24 FPS。按原始 PTS 取最近帧后，有效前缀依次为 87/86/74/78/89 帧；评分统一裁掉固定黑边，保留 1280×720 的同时间前缀。两种方法输入、评分域一致。

转换中 `short_0230` 的原始 107 帧使用了 86 个唯一帧，`short_0352` 的 81 帧使用了 78 个。仅存在于未取样原帧中的瞬时事件，不能据此归为编辑模型遗漏。当前动作时间评价对象是实际送入 H3 的 24 FPS 视频，一帧约 41.67 ms。尾部补帧虽被评分与检测排除，仍进入模型条件；时序引导完整位置 bin 也可能覆盖少量补尾，协议已经记录该范围。

官方 README 允许依据模型能力缩放和采样；当前适配应完整披露，并用同一适配后输入对方法做配对比较。与论文表格比较时需要同时核对样本、采样、分辨率及完整指标。

出处：[IVEBench README 第 172–178 行](/Users/researcher/DevProjects/h3-ivebench-pilot-20261017/literature/official_source/README.md:172)；[固定采样映射](/Users/researcher/DevProjects/h3-ivebench-pilot-20261017/inputs_selection/PILOT_5_MANIFEST.json) 的各条 `input_protocol`；[评分裁边/前缀实现](/Users/researcher/DevProjects/h3-timing-ivebench-auto-r55-20261017/analysis/postrun/release_prefix.py:77) 第 77–120 行；[在线补尾规定](/Users/researcher/DevProjects/h3-timing-ivebench-auto-r55-20261017/configs/protocol.json:290) 第 290–293、362 行。

## 3. MF 升高支持轨迹相似度改善，动作类型与短时事件仍需核查

IVEBench 当前固定源码使用 CoTracker3 offline、10×10 全画面网格。轨迹相似度由位置项 0.7、速度项 0.3 组成，以轨迹空间跨度归一化；Hungarian 匹配后，只平均相似度大于 0.3 的匹配。

代码有三个直接影响本课题解释的性质：

- 每条轨迹先删除 visibility≤0.5 的位置，再把剩余点的序号均匀映射到 `[0,1]`。例如有效帧 `[0,1,4]` 会按 `[0,0.5,1]` 插值，原本的不可见时间间隔被压缩。MF 中的同步序列与真实动作发生时刻因此可能有差别。
- 全画面网格和最终平均没有“抬手、落杯、翻页”等语义标签，也没有专门提高短事件或人体区域的权重。大面积保留背景能够贡献高分；错误的局部匹配若低于 0.3，会离开最后平均的分母。
- 相同的静止轨迹可得到 1。由公式可知，保留很多静止区域与少数局部动作出错可以同时发生；这是一项指标性质推断，未据此判断当前任一视频已经出错。

FlexiAct 发布的 MF 则对相邻位移做单位化，计算方向余弦，随后每条轨迹取最大匹配并平均。位移幅度被单位化除去，源码没有使用跟踪器返回的 visibility，也没有一对一匹配约束。它与 IVEBench MF 的数值和含义不同。

出处：[IVEBench 官方 MF 源码](https://github.com/RyanChenYN/IVEBench/blob/2dcf8900ee65197f43854c76f61c66a32bb8dbfc/metrics/fidelity/motion_fidelity.py)；本地对应 [插值](/Users/researcher/DevProjects/h3-ivebench-pilot-20261017/literature/official_source/metrics/fidelity/motion_fidelity.py:182) 第 182–204 行、[相似度](/Users/researcher/DevProjects/h3-ivebench-pilot-20261017/literature/official_source/metrics/fidelity/motion_fidelity.py:206) 第 206–243 行、[筛选匹配](/Users/researcher/DevProjects/h3-ivebench-pilot-20261017/literature/official_source/metrics/fidelity/motion_fidelity.py:293) 第 293–348 行；[FlexiAct 归档官方 MF](/Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/literature/benchmark_selection_20261017/sources/flexiact_eval__motion_fidelity__motion_fidelity.py:13) 第 13–39 行。

## 4. 编辑成功与内容保持应成为共同判读条件

IVEBench 分开评价 Video Quality、Instruction Compliance、Video Fidelity。其 Instruction Satisfaction 检查是否执行编辑，Content Fidelity 检查应保留的内容。当前只计算 MF，尚不能覆盖这三类目标。[IVEBench 论文 §4.2–4.3](https://arxiv.org/html/2510.11647v2#S4.SS2)

对当前五条，至少需要独立判断：目标人物/颜色是否确实改变，原有动作事件与顺序是否保留，有无新增明显畸形或无关内容变化。若普通编辑与干预版都没有完成编辑，二者的运动分数仍可报告，但应将编辑状态列为失败。若干预提升 MF 却撤销了编辑，也应在同一行明确呈现这个代价。源视频原样输出可形成很高的运动保真，因此单看 MF 容易奖励欠编辑。

FlexiAct 的公开 `appearance_consistency.py` 计算的是输出首帧与后续帧的 CLIP 相似度，函数没有输入目标参考图。它能反映输出内部的外观稳定性，目标人物是否替换成功仍需额外确认。[归档实现](/Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/literature/benchmark_selection_20261017/sources/flexiact_eval__appearance_consistency.py:57) 第 57–94 行；[FlexiAct 论文 §4.2](https://arxiv.org/html/2505.03730v1#S4.SS2)。

## 5. 五条固定分母、UNKNOWN、失败应按各自含义呈现

建议主表始终保留五个 ID，每行至少给 `普通编辑 MF / 自动干预 MF / 配对差值 / 编辑状态 / 局部时序状态`。表注写明以下规则：

| 状态 | 报告方式 |
|---|---|
| 五条均成功生成且 MF 可计算 | 报各方法五条均值、逐条配对差值及改善/持平/退化条数 |
| 某条仍在生成或评分 | 标 `PENDING`，显示已完成 `k/5`；该条差值留空 |
| 推理或评分技术失败 | 标失败原因，保留在固定五条；有效子集均值注明 `k/5`，配对比较使用两种方法均有结果的相同 ID |
| 检测器 `UNKNOWN` | 表示局部动作时间当前无法可靠判定，保留 MF；时差留空，同时报告可判定条数与覆盖率 |
| 模型输出了视频但编辑没完成 | 标编辑失败，保留其实际 MF，计入编辑成功率的五条分母 |
| 官方 MF 因无有效轨迹返回 0 | 保留实际 0，并注明跟踪覆盖问题；与姿态检测 `UNKNOWN`、技术异常区分 |

官方 MF 批处理会把排除任务、缺文件、异常记作 −1，再跳过均值。当前适配器已额外保留 `fixed_denominator=5`、`valid_count`、`failure_count`，仅五条全有效时产生完整均值，应沿用这些字段。

当前控制器的信号来自上肢方向。`no_qualifying_signed_proposal` 可以由证据不足、未越过阈值等原因产生；它本身不证明动作完全正确。一个样例内重叠窗口、多个去噪步也不能作为独立样本扩大统计分母。

出处：[官方 MF 排除/异常/平均逻辑](/Users/researcher/DevProjects/h3-ivebench-pilot-20261017/literature/official_source/metrics/fidelity/motion_fidelity.py:351) 第 351–465 行；[当前评分适配器](/Users/researcher/DevProjects/h3-ivebench-pilot-20261017/literature/metric_runtime/ive_mf_adapter.py:145) 第 145–159 行；[当前检测特征与 UNKNOWN 规定](/Users/researcher/DevProjects/h3-timing-ivebench-auto-r55-20261017/configs/protocol.json:273) 第 273–293 行；[策略筛选与停止原因](/Users/researcher/DevProjects/h3-timing-ivebench-auto-r55-20261017/scripts/automatic_window_policy.py:59) 第 59–70 行。

## 最小补充：五条全覆盖的盲法人工检查

优先补一次人工检查表，覆盖全部五条的普通编辑和自动干预输出。两位评阅者看源视频、原编辑指令、匿名且随机排列的两种输出，先独立填写，再记录分歧。若先由一人完成，标为初步核查。

检查分三栏：①编辑执行：完成/部分完成/失败/无法判断；②源动作事件：保留/遗漏/替换成其他动作/无法判断，并给时间位置；③编辑之外新增的明显内容或结构变化。源事件清单依据源视频确定，包含起止顺序和可见性，避免只挑改进最明显的瞬间。对可识别的同一事件记录原始帧号差，按实际 24 FPS 换算毫秒；展示保留物理时间。

汇报“编辑完成且源事件保留”的条数 `/5`，并同时列部分完成、失败、无法判断数；时序改善只在可识别的同一事件上比较。它直接补足 MF 对编辑语义和动作类型的空缺，成本低于再部署一套大模型评价器。这属于补充人工诊断，字段名称与官方 IS/CF 分数分别标注。

审查使用的关键源码 SHA256：IVEBench MF `4be44656ba92ef7f12af58be2db500ec70d3dda93d9d91d81c9681e7ffd3c0ef`；FlexiAct MF `e92c1d7e1b1e6c7299ad47a8a1da486f559299e0194c35161ed04ddbe91fd4b8`。IVEBench commit `2dcf8900ee65197f43854c76f61c66a32bb8dbfc`；数据 revision `1e6cb655c0a537f6093edcf18e2607fb03e76734`。此次审查未依据输出质量改动五条集合。

## 补充：人体上肢动作适用性子集的准备条件

本地已有完整 [600 条任务元数据](/Users/researcher/DevProjects/h3-ivebench-pilot-20261017/inputs_selection/ALL_600_TASKS.json)、官方短/长任务 JSON、[88 条替换/颜色候选及源审查理由](/Users/researcher/DevProjects/h3-ivebench-pilot-20261017/inputs_selection/REPLACEMENT_COLOR_88_CANDIDATES.json)，以及 [12 条源视频的帧数与 PTS](/Users/researcher/DevProjects/h3-ivebench-pilot-20261017/inputs_selection/SOURCE_TIMEBASE.json)。12 条 MP4 位于 [candidate_sources](/Users/researcher/DevProjects/h3-ivebench-pilot-20261017/inputs_selection/candidate_sources)。目前不需要重新收集元数据。

按原始标签计数，候选中的 `attribute_editing / color adjustment` 有 45 条，`subject_editing / replace existing subject` 有 43 条，共 88 条，其中短片 60、长片 28。其余主体/属性子类包括添加主体 41、删除主体 50、主体缩放 27、位置修改 22。全库还有 92 条 `subject_motion_editing`、50 条 `camera_motion_editing`；这些请求本身要求改变动作或镜头运动，适用目标不同，应单独设计评价。官方元数据没有“肩肘腕可见”标签，类别数量无法回答全库有多少可测上肢动作。

除当前五条外，本地另有 `short_0085/0122/0167/0220/0309/0343/0394` 七条源片。已有的八帧源审查将它们分别记录为：手臂出框或主要头脸变化、布料遮挡和镜头运动、人物近静止、镜面多人物等原因。它们可用于适用性复核，但现有证据不支持把这七条直接算作适用的新测试。原有十二条的目视检查也不足以推断整个 600 条“多数是小物件/近景”。

建议后续另立一个 source-only 子集版本，保持当前固定五条及其结果完整：

1. 从 88 条的两个官方子类开始，按任务 ID 排序审查。先依据 `source_prompt/edit_prompt` 判断是否是人体、编辑是否仅涉及人物外观或衣物颜色、目标形态是否仍适合当前人体姿态表示。文本筛选只产生候选，保留逐条理由。
2. 全片检查实际采样后的源视频。记录目标人物是否清楚、是否有镜面/多人歧义、肩肘腕是否在画面内，以及是否有可观察的上肢运动。当前观察器需要可测的手臂方向；腿部是否完整入画并非必要条件。单独的手指动作、持物变化或面部变化不能直接当作它已覆盖的动作类型。
3. 采用现有姿态模型与既定置信度/可靠性规则做源侧适用性检查，记录每条的有效帧覆盖率、最长连续可见段与可评估窗口数。候选进入主适用集合至少需要一个完整的 16 帧运动窗口能满足现有源侧规则；具体额外覆盖率门槛如要使用，应先统一冻结。静止片可另留作预先规定的控制组。源侧检查不依赖生成结果，也不保证生成后仍可测。
4. 依据上述固定规则纳入全部合格片；资源不足时按冻结随机 seed 抽样，并按两类编辑分别记录分母。最终生成后的欠编辑、动作改变、遮挡和 `UNKNOWN` 全部保留。源侧适用性窗口仅服务于入组说明，在线方法继续扫描完整有效片段。
5. 报告筛选链 `600 → 88 → 文本候选 → 已下载/全片检查 → 源侧可测 → 实际生成/评分`，以及每种排除原因数量。将结论明确写为“人体上肢运动可观测的外观编辑任务”；更广的手部、动物、镜头和物体动作，需要相应观察器与独立验证。

所需新增工作集中在全片源可见性核查和源侧姿态覆盖统计。现成十二条可直接启动此审查；剩余 76 条候选源片需要之后获分配再下载。本轮仅给出库存与选择协议，没有下载、生成或修改检测阈值。

## 优先补充：先诊断 H3 的 prompt 适配

### 已核实的输入差异

R54 的 [prepare_inputs.py](/Users/researcher/DevProjects/h3-timing-ivebench-native-r54-20261017/scripts/prepare_inputs.py:73) 第 73–76 行把原始 `edit_prompt` 直接作为模型文本；`source_prompt/target_prompt` 保留在元数据中。当前五条与后续干预版都遵循同一输入规定。因此配对试验可以评价该输入下的干预效果；H3 的一般编辑能力、动作类型改变的原因，还包含 prompt 适配这一未分离因素。

IVEBench [公开仓库](https://github.com/RyanChenYN/IVEBench/tree/2dcf8900ee65197f43854c76f61c66a32bb8dbfc) 提供数据处理和评价程序，没有逐后端的生成 wrapper。README 同时提供 source/edit/target 三种 prompt；论文 Appendix D 说明模型配置、帧数和失败处理，没有逐模型披露这三个字段的映射。本次能核实的是以下**各方法上游接口**；IVEBench 作者具体评测时的映射仍未公开核实：

| 后端 | 官方接口已核实的文本用途 |
|---|---|
| InsV2V | `gradio_demo.py` 的 `get_splitted_batch_and_conds` 将 `edit_promt` 编码为条件文本；示例使用直接编辑指令。[源码](https://github.com/amazon-science/instruct-video-to-video/blob/6a51b4865d74e41797c74fa216017a272b13a524/gradio_demo.py) |
| AnyV2V | 第一帧图像编辑接收 instruction；后续视频生成另有描述性 `editing_prompt`，反演模板的 `prompt` 默认为空。两阶段的文本作用不同。[第一帧说明](https://github.com/TIGER-AI-Lab/AnyV2V/blob/bc540befacafddb9689ee86a396e7738bfed0e4f/README.md#first-frame-image-edit)、[视频编辑配置](https://github.com/TIGER-AI-Lab/AnyV2V/blob/bc540befacafddb9689ee86a396e7738bfed0e4f/i2vgen-xl/configs/group_pnp_edit/group_config.json)、[反演模板](https://github.com/TIGER-AI-Lab/AnyV2V/blob/bc540befacafddb9689ee86a396e7738bfed0e4f/i2vgen-xl/configs/group_ddim_inversion/template.yaml) |
| StableV2V | `--prompt` 定义为编辑后视频的描述；InstructPix2Pix 的指令通过 `--external-guidance` 提供。[README 参数表与说明](https://github.com/AlonzoLeeeooo/StableV2V/blob/68aff43cd01aed58159f57fee626e5f1bb72aef3/README.md)、[inference.py](https://github.com/AlonzoLeeeooo/StableV2V/blob/68aff43cd01aed58159f57fee626e5f1bb72aef3/inference.py) |
| VACE | UserGuide §3.1 明确要求描述输出内容的 prompt，采用描述式文本；README 另提醒纯文本扩写可能与输入视频冲突。[UserGuide](https://github.com/ali-vilab/VACE/blob/48eb44f1c4be87cc65a98bff985a26976841e9f3/UserGuide.md#31-vace-recognizable-inputs) |

H3 官方 [Ref2VA prompt guide](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/references/ref-en.txt) 规定：`<Video 1>` 指明被编辑的源视频；`summary` 用 `[video editing]` 标明任务；`retention_analysis` 说明哪些参考内容保留或修改；`detailed_description` 描述目标动作与场景。其 [实际 Ref2VA 请求示例](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/scripts/readme/reproducible-768p-ref2va-request.sh) 直接提交这种分节文本。对应 guide §2.3、§3、§4、§5；单句指令是否足够需要实验确认。

这表明当前短指令与官方展示的输入组织有差异，尚不能确定它造成了哪些失败。若完整视频确认阅读变成行走、站立变成坐姿，应记录为动作/内容保持失败；在确认同一动作事件仍存在后，再测事件时间差。某个方向序列能拟合出 lag，并不足以将不同动作归为同一事件延后。

### 下轮诊断的预注册草案

此诊断优先于扩展 source-only 子集。当前 R54/R55 批次继续按已冻结协议完成并保留全部结果；新诊断采用独立版本。

1. 固定原五条、原 seed、原采样/模型/视频输入，先只运行普通 H3 编辑。比较 `P0 = 原 edit_prompt` 与 `P1 = 固定模板适配后的 prompt`。已核实完整原输入记录的 P0 可复用，因此最少新增五次生成。
2. 五条 P1 在生成前一起冻结并记录 SHA；只用官方 `source_prompt/edit_prompt/target_prompt` 及通用保留要求。没有逐样例动作时间标注、失败位置强调或按生成结果追加描述；没有新身份图片。预先人工核对模板没有新增与原任务矛盾的动作。
3. P1 采用下列统一模板。`{source_prompt}`、`{edit_prompt}`、`{target_prompt}` 原文替换；保留语句为所有五条共享的实验设计，不宣称是官方提供的逐条 prompt。声音字段仅说明未提出声音要求，视觉评价范围与当前任务相同。

```text
subject_definitions:
<Video 1> is the source video for this editing task.
Source context: {source_prompt}

summary:
[video editing] The target video is an edited version of <Video 1>.
Requested edit: {edit_prompt}

retention_analysis:
<Video 1>: partially_preserved - apply the requested appearance edit.
Preserve the source actions and their order, timing and duration,
body pose, camera framing and movement, and unedited scene content.

detailed_description:
{target_prompt}
The visible action sequence follows <Video 1> throughout the clip.

overall_soundscape:
No specific soundscape is requested.

non_diegetic_music:
No specific music is requested.
```

4. 先做前述全五条匿名人工核查：编辑是否完成、原动作类型/顺序是否保留，再看同一事件的时差与 MF。记录 P1 改善、持平和退化的所有条数；P0 中已经出现的语义变化不会因 P1 成功而被删掉。
5. 若 P1 普遍恢复动作类型，下一轮方法验证应在同一冻结 P1 下比较普通编辑与自动干预，明确区分 prompt 适配收益和时序干预收益。若 P1 仍发生动作类型替换，则继续报告内容保持失败；仅有 MF 或局部 lag 改善无法证明解决了这类失败。

两种 prompt 足以检验“官方风格的输入适配整体上是否影响结果”。P1 同时增加源/目标描述、参考绑定、保留要求和分节格式，因此其收益只能归因于这个整体改动。`target_prompt` 单独一组可作为第二阶段，检验仅提供目标描述是否已经足够；它仍无法单独分离格式与信息量。若需要解释格式贡献，追加一组包含与 P1 完全相同事实和保留要求的普通段落文本，才具有对应的控制关系。首次诊断不需要为了形式完整新增这些组。
