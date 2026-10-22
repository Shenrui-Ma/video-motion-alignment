只读汇总现有 router/job JSON，适用于 R63、R65、R66 的成对结果。
Python标准库，无torch、CUDA、网络调用或模型推理。

python3 summarize_pair.py \
  --native-router /path/to/native_router.json \
  --forced-router /path/to/forced_router.json \
  --native-job /path/to/native_job.json \
  --forced-job /path/to/forced_job.json \
  --pair-gate /path/to/PAIR_RUNTIME_GATE.json \
  --output /path/to/new_summary.json

job与pair-gate可省略；输出文件必须是新文件。所有输入只读。
输出实际NFE、routed调用数、active步骤，以及每一步的采样ref mass、
采样attention输出correction ratio。汇总先读取每步的层平均，再按active
step等权平均。缺失统计保留null；零路由、实际路由但零变化、实际路由且
采样attention变化都有对应布尔值。动作改善仍由成片和独立动作指标判断。

correction_ratio = RMS(O_after−O_before)/max(RMS(O_before),1e−8)
原记录每层至多采样8 heads×128 queries×16 channels；该比值描述这些
attention输出的变化。refmass只对采样heads/queries求平均。
job墙钟包括加载、编码、采样、解码与轮询，避免将首条加载差异解读为方法提速。

这只是日志汇总，producer的实际PAIR_RUNTIME_GATE仍由原verifier给出。
