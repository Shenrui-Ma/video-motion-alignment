# 同位置组切向消融（边界原算子）

状态：独立节点已通过CPU检查，未部署、未入队、未做GPU推理。节点 `H3TemporalGainFieldRole5`；审计schema `h3-temporal-gain-field-role5-v1`。

## 唯一科学干预

复制并逐文件核验原 `feature_gain_field/READY.json`。`controller.py`、`components.py`、`frozen.py` 保持原字节。主修正仍是 `O + alpha*m*(S_same−R_all)`，参考质量、先验.25、上限.5、每层每bin首个有效步锚、原QP和平滑全部保留。

在现有窗口 `[lo,hi)` 内，仅当 `lo+5 ≤ t < hi−5`，将切向改为同Q下的 `S(t+5)−S(t−5)`；其他位置仍用原±1。首尾probe的mass=0不变，不新增固定先验区，不断开接缝的QP边。短于11bin的窗口完全沿用原算子。±5只改变参考K/V的时间索引，查询Q保持当前t。

该干预同时改变位置组匹配和时间跨度：5bin为17个名义帧，两端跨度约34帧。它是混合时间尺度消融，不能称全片纯±5，也不单独归因于编码role。较长跨度可能抹去快速转折。

## 同Q shadow与状态

仅在step `{0,9,19}`、layer `{8,25,42}` 且存在±5内部位置时，额外计算±1的两个probe attention。shadow共享同一次Q、D、m、probe位置，只记录共同内部区。shadow使用独立的step0 ±1锚；step0缺失/无效时保持无归一化证据，不在step9偷建首步锚。shadow字典和主controller字典分离，既不调用第二次QP，也不反馈alpha或主状态。

正常调用5次attention；9个检查点各7次，共额外18次小probe attention。完整DiT forward和VAE decode额外次数均为0。`controller_host_dispatch_seconds` 与 `shadow_diagnostic_host_seconds` 是host墙钟/dispatch统计，不宣称纯GPU核函数耗时。主统计3×T transfer口径保持不变；shadow另列其3×T transfer bytes。

每层记录实际neighbor索引、完整role5 mask、全部bin A/B/计数/锚/回退/alpha；四个接缝两侧bin单独列出。最终alpha和修正能量的统计均在W_o前。

## CPU证据和独立审计

`test_result.json`：51项CPU测试通过，CUDA初始化前后均false；isolated tmp运行，未复制到任何活跃Comfy custom_nodes。包含独立head×time×probe dense循环、非零lo索引、短窗口回退、首步与固定.25逐元素等价、shadow开关输出与主状态逐元素等价、QP边保留、锚独立与因果、重复MODEL消耗保护、实际冻结RouterState的20×50完整调用。

`CPU_full_complete.json` 是真实wrapper调用产生的dense随机QKV测试fixture，**不是生成视频实验结果**。该fixture有9个shadow、15个shadow bin锚、4000条接缝记录；故障注入验证错误邻域、修改shadow锚和额外attention调用均被拒绝。

独立torch-free接口：

```bash
python3 audit.py runtime.json
```

或调用 `check_role5(doc)`。审计原schema、完整20×50计数、真实应用alpha、能量、QP KKT、主锚不可变、精确邻域、shadow排程/独立首步锚/归一化以及接缝记录。底层数值审计复用原 `field_audit.py` 的冻结副本；仅在副本中适配已验证的schema和额外probe调用数，不修改输入审计文件。

## 两份图

`../adaptive_strength_20261023/batch/role5_pilots/` 保存0252与0358。从原field图复制，只改节点14输出前缀与节点50独立class/audit目录；prompt、seed、缓存、模型、sampler、所有几何以及节点50其他科学参数完全相同。`SCIENCE_CHECK.json` 和两项graph测试记录这一点。仅准备 `jobs.json`，没有创建发布标记或ready请求。

主线程审核后再决定部署、collector接入和GPU验证。新schema需要调用本包audit；原field审计器不会直接接受新schema。
