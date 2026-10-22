R59：可见上肢反馈与弱引导对照（CPU 候选，2026-10-17）

问题与改动
R55 的 arm descriptor 入口依赖躯干尺度有效。本版直接复用 R56 已冻结的肩—肘、肘—腕单位方向，不要求髋部可见。左臂、右臂、双臂仍是原来的三种 descriptor。缺失的一侧保留 UNKNOWN，另一侧独立参与原算法。

原判断规则保留
每个去噪 step 0..19 解码当前 Native endpoint；在有效源视频前缀扫描 16/32 帧窗口，stride4，补最后完整窗口。原 confidence 0.3/0.5、coverage≥0.8、最少8帧、lag±24、双阈值 lag 差≤2、|lag|>2、gain>0.5、原残差/歧义检查、连续两次同方向且同部位窗口重叠≥0.5 均沿用。完整观测的 window×descriptor 行逐项验全。

四臂
Native：普通编辑；计划直接复用 R57 P1 的真实完成结果。
Visible-Only：原 signed selector 控制局部时间路由；UNKNOWN 当前采用 Native。
Visible+fallback：Visible 触发时 alpha1；否则仅当前所有行 baseline=unknown 且 index6..14 时，alpha.25 全画布路由。
Weak-only：index6..14 固定 alpha.25 全画布路由；控制完全不请求 observer。

兜底边界
有任一可靠行、gain 不足、gain common-support 失败但已有可靠 lag、等待第二次 persistence，均不触发兜底。空 rows、缺 response、错误时间步/域/枚举、技术异常按失败处理。旧版本空 unknown_visibility 不符合本版完整观测协议。兜底不写入 selector candidate history、不虚构动作位置或 lag。

执行器
每个 block：O' = O + alpha*m_ref*(O_same_time_ref - O_ref)。
Visible 时间区间内全部空间 query，alpha1；弱引导全部27时间bin/全部空间query/50个block，alpha.25。检测部位决定可靠性，执行器目前没有人体空间 mask。完整 bin 操作可覆盖 padding，bin_coverage 逐决策记录；统计与评分只用原有效前缀。
Native/Full 使用同一个当前 x、sigma、条件、RNG；只返回选定 endpoint，由原 sampler 做一次 Euler 更新。20次更新，Native20 forward，Weak29，动态反馈20..39。

数据与状态
固定原五例 short_0210/0230/0263/0352/0370，seed2026101701，同 R57 P1 prompt、20 Euler CFG1、1312×736×90@24，valid prefix87/86/74/78/89。20个图用于四臂准备；Native优先复用未来真实R57结果。所有 R57 actual noise/condition/capture/archive 父链目前 PENDING，节点入口及 preflight --live 拒绝运行。没有复制视频/模型，没有部署或启动GPU。

工程与验证
原 R55 v4 decoder 资源余量准入、精确自有PID、2卡上限、600秒有界资源等待、780秒阶段预算、typed CUDA OOM重试、自有child释放沿用；源字节与差异见 audit/SOURCE_INHERITANCE.json 与 audit/CANDIDATE_DIFF.json。正式 service/queue/consumer 以及资源证书需后续基于实际 R57 绑定和新运行门完成。历史容量不能视为本候选已测。
CPU测试使用现有 ComfyUI-dev venv 的 numpy/torch、CUDA_VISIBLE_DEVICES 为空。合成事务运行本候选实际 PredictionProbe 和 SamplerAudit，但模型 forward、Comfy接口和物理GPU未验证。attention使用CPU dense oracle，生产算子代码原字节保留。

评价
保留全部五例，先报告编辑完成和动作类别/顺序，再报告可信时移/UNKNOWN、官方MF、forward次数与耗时。Visible对Native检验反馈；fallback对Visible检验增量；Weak-only用于判断同样改善是否由固定先验解释。本候选尚无新生成效果和创新成立结论。
