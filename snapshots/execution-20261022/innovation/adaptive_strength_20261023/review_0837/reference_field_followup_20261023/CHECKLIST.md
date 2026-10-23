# 独立审查范围

本目录审查两条独立支线，源代码、旧结论、阈值和队列均保持冻结。审查者不部署、不发起GPU任务。

## Reference-only CPU入口

- 只允许读取qrn_kn/qrw_kw。NPZ内其他键及成片收益不得进入拟合、选择或阈值设置。
- 两方法×两step×全部56heads；8probes按偶奇及反向留出；每fold独立模板/谱/预测，31有效bin，padding排除，时间坐标来自冻结spans。
- 完整距离矩阵、所有间距分离度曲线、逐probe留出误差/epsilon、线性谱与逆增益；无仅展示正例head/step。
- 用同一留出集最大残差得经验epsilon，只作该参考集合稳定性诊断，不冒充独立coverage/可迁移generated保证。
- 静态、周期/角色、近奇异、双峰与外观同指纹反例；列置换不变性；退化/非finite明确处理。
- 强制真实输入/gate/policy/hash契约；缺项pending无结果，身份不符invalid；允许运行诊断不等于放行controller。

## 原field单条环境复现

- 源码与原field READY相同，六运行文件SHA；原±1邻时刻、原QP、锚、边界、先验.25/上限.5/mu1/smoothness.625/probes8，全20×50。
- .81新pair同环境/core/checkpoint/完整prompt/缓存payload/保存noise；AVsigma、shift12/3、1312×736、107输出/105有效帧、24fps相同。
- 图差异应只有方法和必要隔离路径/审计包装；每项非路径差异解释，保存noise不能退回仅同seed。
- 后端证据必须来自实际新jobPID；开关不替代dispatch计数。捕获/观察器无额外模型调用、不改变采样结果，若保留须先通过兼容验证。
- 完整动态alpha审计，成片绑定新SHA；全3冻结事件重新标注，官方9指标同crop/版本。失败不改参数、不重抽种子。
- 主比较新field对新weak；只标记已知正例复现，不重置整体方法已搁置状态。
