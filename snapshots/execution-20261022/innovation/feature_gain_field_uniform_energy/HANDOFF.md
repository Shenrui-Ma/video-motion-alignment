# 等修正能量、时间均匀 α 对照

状态：CPU_VERIFIED_NOT_DEPLOYED / review_only。未修改原 field、线上清单或服务。

独立节点 H3TemporalGainFieldUniformEnergy 保留原 field 的同 query probes、锚与 QP 候选；仅对 solver_succeeded bins，使用完整分辨率 D_t 能量加权 RMS 将候选变为时间均匀 α。端点、新锚、无信号和失败区间保持 .25。匹配本次前向候选的 pre-W_o 能量，后续实际轨迹会改变。

验证：53 个 CPU 单测、2 个冻结图差分测试通过。真实 wrapper 20×50 调用审计通过；11 个失败注入全部拒绝。候选非均匀调用950次，最大相对能量误差8.155e-8，最大QP KKT残差7.024e-8。

最终完整 fixture 仅保存在 .9 临时目录 /tmp/h3_uniform_energy_cpu_20261023/fixture_release/uniform_complete.json；本地只取小型摘要 CPU_INTEGRATION.json。临时目录保留给独立复核，不含模型或新视频，完成主线程审查后可整体清理。

准备图在 pilots/，只有节点14输出路径和50方法改变，原 prompt/seed/cache/model/geometry/sampler/QP 参数保持。两图 max_attempts=1，仅待审，不在 active manifest。默认 enabled=False；部署决定由主线程执行。

READY.json 固定所有源码、图、说明和测试摘要的 SHA256。uniform.py 对有限元素但 FP64 总和溢出的输入明确拒绝；最终总能量日志用 FP64 归约。实际修正 dtype 和原各bin能量测量保持不变。
