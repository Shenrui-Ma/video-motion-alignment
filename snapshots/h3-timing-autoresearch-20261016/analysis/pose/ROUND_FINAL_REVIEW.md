# H3 动作时间错位：本轮独立结果审查（最终版）

定稿时间：2026-10-16（Asia/Shanghai）。本轮最强的新增证据是：在同一故障样例、同为9次路由调用的条件下，调用6–14使目标事件延迟从13帧降至1帧，而调用11–19仍延迟11–12帧。它支持干预区间与轨迹历史相关，但本轮没有完成可发表的新架构证明。

所有时间差以帧表示，24fps；正数表示编辑后的动作较晚。`unknown` 是冻结观察器拒判，不是零延迟、动作遗漏或删除。表中阈值0.3/0.5是检测置信度敏感性检查，不是统计置信区间。

| Run ID | 用途 | 0.3：既定窗口 lag | 0.5：既定窗口 lag |
|---|---|---|---|
| `s05_seed1_native` | resolution-control native | -1 / -1 / +0 / -1 | -1 / unknown / +0 / -1 |
| `s05_seed1_mass` | resolution-control routing | +0 / -1 / +0 / -1 | +0 / unknown / +0 / -1 |
| `s05_full_seed1_native_x0` | discovery native | +13 / +10 / +8 / +4 | +13 / unknown / unknown / +4 |
| `s05_full_seed1_phase_zero_x0` | exact-replay control | +13 / +10 / +8 / +4 | +13 / unknown / unknown / +4 |
| `s05_full_seed1_mass_x0` | all-step same-bin mass route | +0 / -1 / +0 / -1 | +0 / unknown / +0 / -1 |
| `s05_full_seed1_hard_x0` | all-step hard baseline | +0 / -1 / +0 / -1 | +0 / unknown / +0 / -1 |
| `s05_full_seed1_mass_late11_x0` | late mass | +11 / +10 / +8 / +4 | +12 / unknown / +8 / +4 |
| `s05_full_seed1_mass_late6_x0` | earlier-start mass | +1 / +0 / +1 / +1 | +1 / unknown / +1 / +1 |
| `s05_full_seed1_hard_late11_x0` | late hard | +13 / +10 / +8 / +4 | +12 / unknown / unknown / +4 |
| `s05_full_seed1_phase_plus12_x0` | relative coordinate +12 | +13 / +11 / +10 / +5 | +13 / unknown / unknown / +5 |
| `s05_full_seed1_phase_minus12_x0` | relative coordinate -12 | +3 / +2 / +1 / +1 | +3 / unknown / +1 / +1 |
| `s05_full_seed1_offset4_x0` | wrong reference bin +4 | unknown / unknown / +1 / +1 | unknown / unknown / +1 / +1 |
| `s05_full_seed1_offsetm4_x0` | wrong reference bin -4 | +11 / +9 / +8 / +4 | +11 / unknown / +8 / +4 |
| `s05_full_seed1_phase_minus12_late11_x0` | late relative coordinate -12 | +13 / +10 / +8 / +4 | +13 / unknown / unknown / +4 |
| `s05_full_seed1_mass_6to14_x0` | equal-nine-call mass6..14 | +1 / +0 / +1 / +1 | +1 / unknown / +1 / +1 |
| `s05_full_seed2_native_x0` | second seed native | +15 / +15 / +16 / +17 | +15 / unknown / +16 / +17 |
| `s05_full_seed2_mass_x0` | second seed mass | -1 / -2 / -1 / -1 | -1 / unknown / -1 / -1 |
| `s07_full_seed1_native_x0` | related recording native | +15 / unknown / -5 | unknown / unknown / unknown |
| `s07_full_seed1_mass_x0` | related recording mass | -1 / -1 / -2 | -1 / -1 / unknown |
| `s05_semantic_b_p6_t6` | semantic factorial B | +5 / unknown / +3 / +2 | +5 / unknown / +3 / +2 |
| `s05_semantic_c_p0_t6` | semantic factorial C | +13 / unknown / +9 / +5 | +13 / unknown / +9 / +5 |
| `s05_semantic_d_p6_t0` | semantic factorial D | +13 / +10 / +8 / +4 | +13 / unknown / unknown / +4 |

Source05四窗：50–65、69–81、80–92、99–111。Source07三窗：54–69、75–88、98–111。表内每条lag按该视频自身可见关节估计，不能把不同支持集的误差直接做公平比较；相同支持的独立报告另存。完整精度、拒判原因、实际尺寸、prompt ID和MP4 SHA见`round_metrics_index.json`。

## 目前成立的现象与不成立的强结论

在选定的source05、第一种子、1312×736样例中，编辑后短事件的可靠局部延迟为13帧（约0.54秒），后续几个事件的偏移依次约10、8、4帧。它是非均匀的局部时间错位，不能概括成整段恒定慢放，也没有证明动作在语义上被删除。原视频预处理检查、VAE encode/decode控制及重放审计没有发现本例的固定帧率或17帧chunk延迟；这不等于证明VAE保留了所有视觉细节。

全程同时间bin路由、普通hard mask和已归档×3参考增强都能把第一种子主窗移回约0帧。故不能称质量守恒是必要机制，不能称其优于简单mask或旧增强。它是有用的可操作因果干预，但不是独立架构创新的证明。

source05第二种子提供同一素材上的重复方向：native主窗+15→mass−1。两条视频都把大片白色窗帘/墙面变为黑色，属于明确的背景保存失败。不能把动作改善当作整个编辑成功，不能把native已有的黑背景归因给mass。source07是相关舞蹈的另一段真人录像，主窗右臂+15→−1较稳定，但native双臂高阈值本身拒判，且mass在作用窗前0–51帧的误差略增。它不是新独立种子或无条件泛化成功。

## 条件、观察器和技术控制

本轮为依次看到结果后增加对照的探索性研究。新增条件在各自运行前登记并冻结，但并非整个22条计划都在最初一次性预注册，也不是盲验证；同一source/seed的多次条件不构成独立重复。

- 全分辨率条件：1312×736、141帧、24fps、20次Euler、无TurboLoRA，冻结提示词/输入/种子/数值路径。1024×576两条单独是本来正确的配置控制，不能混入故障修复统计。
- 所有正式输出依据history status=success和history中真实文件名准入，核验帧数/FPS/尺寸和SHA；不使用prefix猜测。早期误选2步benchmark被保留在excluded_benchmark并明确排除；transfer首次root guard失败为采样前技术失败，不计方法成败。
- CPU DWPose保存所有检测人物、选择策略、缺失与置信度。使用肩/髋中心及躯干尺度归一，主特征为四段手臂单位方向；原始像素MSE不作为跨身份动作指标。
- 固定±24帧局部搜索，拒绝低覆盖、多峰、边界解、移位收益不足以及对齐后形状残差>0.5；所有拒判保留。±36只为事前登记的phase0/±12探索敏感度，未取代主指标。
- 合成shift0/±2/±7/±13、缺失、重复/静止、幅度扰动只校准玩具数据上的行为；不能证明真实视频估计器普遍可靠。一个腕部幅度扰动出现误报已保留。没有实现动作缺失/幅度不足的类型分类器。
- 全片DTW不是主指标。已有同pose近oracle后处理基线可降低拟合误差，但141帧只用125个独立源帧，16次重复、16帧未用，存在跳帧和卡顿风险；优化/评价同一pose也有循环论证，尚需人工质量比较。
- 旧native→fullnative→被动native_x0以及phasezero有逐帧/逐tensor重放控制。source07旧新输出并非逐像素相等，即使实际输入与噪声审计相同，已知执行图接口差异仍在；不能称精确重放。

## 早晚干预及观察时刻

mass从调用11开始（共9次）主窗仍+11/+12，hard从11开始仍+13/+12，未达到预登记至少4帧的部分修复门。mass从调用6开始（共14次）达到+1/+1，原首窗方向门通过；其他特征也必须保留拒判，尤其腕部相对坐标因本来误差小、移位收益不足而拒判。

所有相应干预前快照由parent做逐元素video/audio一致性控制，详audit/late11_preintervention_tensor_equality.json、late6_preintervention_tensor_equality.json及hard_late11审计。不能把late11的失败推成所有晚期干预不可逆。call11实际video sigma约0.90756，不能称接近零噪声的最后阶段。

native x0在已采样快照5的图像本身清晰，但双臂观察器因右臂置信度低而拒判；左臂/全身有延迟线索。第10快照主观察器才首次可靠检测+13，6–9没有采样，所以不能确定最早可检测时刻。late6是离线固定区间试验，不是在线闭环；不能事后改用左臂阈值来宣称在线监控已成功。

phase−12从调用11开始主窗仍+13/+13，未达到部分修复门；干预前005/010 video/audio逐元素等于native。这个执行器的全程+3收益也未延续到late11。等9次调用的mass6..14现已完成，主窗+1/+1，四窗0.3为+1/0/+1/+1、0.5为+1/unknown/+1/+1。固定55/86的灰衣、白色房间保留，首窗方向门通过；body_xy则因本来误差小、移位收益不足而拒判。五臂共同主窗支持1.0/.828，early9误差.143/.148，而late9为.769/.783。该例在调用数相同时仍有区间/轨迹历史差异，削弱了“仅因多调用”的解释。

即便调用次数相同，sigma-dose仍不同：early9受影响更新的原始video sigma跨度约.1655，late9约.9076，且区间在11..14重合。这不是精确关键时窗、普遍早期优越性或在线控制的证明；尾部15..19只在这条较早已修正轨迹下对当前端点并非必需。实际输入/噪声配对、1000次block调用与仅6..14的450次路由全部通过；005相对native、005/010相对late6的video/audio均逐位相同。证据为audit/early9_actual_operator_gate.json、early9_native_prefix_tensor_equality.json、early9_late6_prefix_tensor_equality.json及native-to-mass_6to14配对审计。

## 参考时间对应的负对照

保持同一窄query窗、相同key数，把参考bin改成±4。offset−4主窗可靠+11，未修复；offset+4在主窗出现转背/遮挡/动作形状变化，不能当成干净的符号相位响应。

0/+4/−4三臂共同可见支持下，0.3覆盖0.922、同帧方向误差0.104/1.020/1.039；0.5覆盖只有0.672、误差0.100/1.030/1.055。**双阈值预登记specificity门失败**。低阈值强差异可描述为探索性时间对应线索，不能删除高阈值、改用右臂或称机制检验已经通过。固定query窗只覆盖约47–67帧，也不能要求完整±13/16帧事件位移都留在窗内。

## 相对RoPE坐标试验

相对参考时间坐标+12帧等价扰动使主窗仍+13；−12使主窗+3（部分改善，未达±2完全对齐）。探索±36结果一致。输出不是简单的正负对称线性相位执行器；存在单侧饱和。parent审计确认真实执行，+12不是no-op。

原始query−reference的235RoPE单位时间差用于打包参考区分，等于141帧坐标跨度，绝不是动作真实延后141帧。RoPE空间/时间修改已有RoPECraft/OmniTransfer等相关工作，不能因这条单例有效就声称新架构。

## 语义抽帧/时间标签2×2

A=P0/T0；B=P6/T6；C=P0/T6；D=P6/T0。P6改变Qwen语义参考的物理抽帧约0.25秒，T标签由于原格式舍入改变约0.3秒；它们不是同一个数。dense VAE/noise/token count/tag/packed position固定；条件embedding允许随语义图像/文字故意改变，不能使用要求embedding全等的generic pair checker。A0只验证实际编码等价，不是独立输出。

完整A/B/C/D主窗分别+13/+5/+13/+13，两阈值一致。C−A=0，B−D=−8，D−A=0，B−C=−8，interaction=−8。两个预登记的跨factor一致主效应门均不通过：单独变图像或单独变标签在另一factor=0时无收益，联合改变才有部分改善。这是单个已挑故障的条件性交互线索，不是统计显著性或双时钟错误证明。

四臂主窗共同支持0.3/0.5为1.0/.922，误差A/B/C/D分别1.131/.651/1.119/1.128与1.145/.659/1.124/1.144。高阈值中间两窗共同支持只有.731/.673，必须拒判。固定55/86的B/C/D保留灰衣和白色房间；B仍有+5帧延迟，不能称完全恢复。

Native标签一位小数舍入：A paired mean.25→label.2，有−.05s误差；B mean.5→label.5。B-only结果无法排除量化、完整图文上下文交互。它不等于一般抽帧phase收益，不证明Qwen2fps丢动作，也不证明RoPE时钟问题。实际all-arm编码验收已通过；semantic GPU0真实native重放也已完整通过：实际图除管理路径外一致、条件与噪声相同、20×50次native调用、5份video/audio快照逐位相同、141/141帧解码RGB相同，尺寸1312×736、24fps、time_base 1/12288及5.875秒时长相同。见analysis/replication/semantic_gpu0_native_replay_gate.json。这排除了该次相同native图在两GPU/runtime之间出现输出差异的混淆，不把B的机制解释提升为确定事实，也不增加独立样本数。详情见semantic_factorial/full_factorial_complete/REVIEW.md。

## 方法贡献边界和下一步证据

已有工作直接覆盖局部attention增强、动态门控、latent/flow运动引导、时间运输、显式时间路由、外观/运动分离和RoPE修改。详literature/guidance_collision_audit.md，重点TST、TS-Attn、TCR、OmniTransfer、MOFT、FlowMotion、MotionGrounder、RoPECraft；DIAL和相关时间控制专审由并行研究审查提供。没有证据可保证不存在同类工作。

并行审查还找到TokenFlow明确每步随机关键帧以减轻选择敏感性、NOVA直接研究稀疏关键帧间隔鲁棒性。因此把新方向改称“多phase融合/轮换使稀疏观察稳定”也不能直接视为新架构。其精确同构检索边界和官方代码证据见literature/semantic_phase_robustness_prior_art.txt与final_claim_review.txt。

质量守恒重分配与一组归一化logit偏置数学等价；“softmax后操作”不是独立创新。普通hard删除非对齐参考key时，若原参考总质量为m、对齐比例s，新参考总质量m*s/(1−m+m*s)≤m；它并未增加参考组总概率。跨轨迹的QKV会变化，不能把单步恒等式外推为全程身份守恒。

本轮尚未训练模型，没有教师模型，没有实现自动检测后开启/关闭的闭环控制器，也没有证明超过既有最强方法。当前支持“所选条件下存在可干预的局部相位偏移”，不足以支持“新架构普遍解决短动作遗漏”。后续选择必须受本轮固定对照和已有简单baseline共同约束，不能追加参数搜索后只报告最好的样例。

## 归档与运行记录

原始视频在outputs；exact-history/config/conditioning/noise/route audit/SHA位于analysis/pose/pilot/<run>_provenance；观测、overlay和拒判都在pilot；共同支持曲线在pairs、full_support、offset_specificity和semantic_factorial。主索引round_metrics_index.json记录22条预列条件，包括重放/配置控制，**不代表22个独立样本**。

22条原视频已逐文件SHA核对，见ROUND_RUN_INVENTORY.json：20条采用统一完整archive_manifest，最初两条1024控制保留其旧准入记录而未伪造新增expected_geometry/config_sha字段。CPU_FINAL_COMPLETION.json确认六组consumer全部exit0、requested/completed集合匹配、无本lane活跃watch/pose进程、冻结指标SHA未变。GPU进程与显存释放由parent负责核验，本lane未启动任何GPU或H3服务。

## 最终决策

本轮完成了可重复的局部时间错位诊断、可控推理干预及必要否定对照。最值得保留的是等9次调用的区间对照；最应放弃的表述是“质量守恒公式本身新”“已证明纯时间对应机制”“语义抽帧的两个独立主效应成立”“在线闭环已成功”。不同方法仍可能在其他条件奏效，但本轮没有相应证据。

若继续投入，先把这个固定区间效应作为待复现的经验现象，在预先固定的新素材/新种子上验证，并与普通mask、×3增强及后处理retiming共同比较；不要直接把已有局部门控、RoPE调整或多phase融合改名为新架构。只有在新证据排除简单解释、保持编辑质量并明确超出既有工作后，才能收紧成论文贡献。这里不预支未运行实验的成功。
