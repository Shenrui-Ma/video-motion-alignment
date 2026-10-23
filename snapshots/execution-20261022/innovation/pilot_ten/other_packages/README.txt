部分时间 RoPE 与跨时刻覆盖：主十组独立实验包

位置：每个方法目录有 jobs.json、pilot_jobs.json、graphs/、verification.json。
partial_temporal_rope 与 temporal_coverage 各 10 条，先 short_0252、short_0358。
由 direction_package 的同十图复制，仅改节点 50（方法）和节点 14（输出目录）。
输入、历史六组缓存及 SHA、prompt、seed、采样器、sigma、几何、后处理保持逐字段相同。
metadata.cohort=innovation；原主实验与扩展集不会混入新方法均值。

部分时间 RoPE
H3PartialRoPE 节点 optional delta_mode=reference_origin。
首个 DiT block 收到实际 PackedLayout 后，校验参考/输出视频全部时间 bin 的位置坐标符合
H3 的 [1,4,4,4,4] 帧跨度与 5/3 缩放，再计算
  delta_frames = (reference_origin_rope - output_origin_rope) / (5/3)。
运行图中的 delta_frames=0 只是保留旧接口字段，reference_origin 模式使用上式的实际值。
低频后八对时间通道旋转；空间通道、joint Attention 原分支保持原计算。
原 adapter 默认 explicit 行为保留。
审计 JSON 新增 delta_mode、delta_resolved、delta_derivation 和实际 rotation 参数。

该独立实验的计算是：
  O' = O + 0.25*m_ref*[Attention(R_low(delta)Q,K_ref,V_ref) - Attention(Q,K_ref,V_ref)]。
其中两次额外 Attention 都读取全部参考视频 K/V。
用来比较的原全程弱引导使用同时间 bin 参考 K/V。
因此这轮比较的是“部分频带相位匹配”与“同时间 bin 匹配”两种参考分支，未叠加两者。

跨时刻参考覆盖
H3TemporalCoverage 节点，20 步全程、50 层、alpha=0.25。
radius=2、entropy=0.5、temporal_penalty=0.25、iterations=128、tolerance=0.0002、
min_quality_span=0.001、minimum_mean_gap=0。
起止视频范围为每条样本全部有效帧；其余与 direction_package 相同。

验证与部署
部分 RoPE 原有 23 项 + 新增 9 项 CPU 测试共 32 项通过；实验包另 5 项通过。
新测试覆盖实际坐标差与符号、非零时间窗、5/3 映射错误、空/非有限/错位布局拒绝、
旧 explicit 行为、审计写入、二十图节点接口/连线和输入逐字段保留。
GPU 执行、显存峰值、最终图像效果等待运行核验。本目录没有提交或执行远端任务。
deployment_files.json 是源码 SHA 清单。部署 H3PartialRoPE 整个包和 temporal_coverage
模块时使用对应已验证版本；不可只上传图而遗漏 adapter 新 delta_mode 接口。
共享输入和旧六组缓存使用 direction_package/assets.json 与 cache_manifests/。
十图仍写 host9a 路径；部署 host9b 时由调度者统一转换运行根路径与缓存位置。
