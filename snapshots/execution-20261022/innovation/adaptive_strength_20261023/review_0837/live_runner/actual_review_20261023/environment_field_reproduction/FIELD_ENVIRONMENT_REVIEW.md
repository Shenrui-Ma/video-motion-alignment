# 饮酒 field 与新 live pair 的环境核对

建议下一步只在新 live pair 的 .81 环境复跑一次**原冻结 temporal_gain_field**。这是既有正例的环境复现，直接与新 weak 配对；参数、方法和事件集合均保持不变。没有启动 GPU，也没有修改队列或共享报告。

## 已核实的对应关系

旧 field 是 `adapt41_short_0358_temporal_gain_field`，历史 API `769dad83-5c6a-46c6-a12c-3f03c5c78f6b`。history 的执行时间1792700985.685–1792702146.949处于 PID86424 的服务日志区间内；前一例为同包机舱，下一服务启动在1792702197.194。该区间记录 Torch2.11.0+cu130、NORMAL_VRAM、模型19996.14MB全加载、CUDA后端enabled。field 的Flash Attention审计只证明注意力算子，不能代替INT8线性层派发证据。

新 native/weak 采用 Torch2.5.1+cu121、LOW_VRAM和权重卸载，CUDA kitchen后端disabled。新 weak PID32141的实际结束计数为Triton INT8成功4000、CUDA0。旧 field 的结束计数已未在所查记录中保存；当前 .41 的计数属于后来PID285001，Oct20的CUDA8000计数属于历史控制，都没有借来证明 field 的实际派发。

两端cache manifest仅重定位路径：原视频、完整结构化prompt、conditioning JSON、四个tensor文件及tensor signature、几何、seed和所记录core兼容源码哈希逐项相同。模型loader、Euler、完整sigma列表和video/audio shift节点相同。H3Study四个当前源码字节相同；field六个运行源码与冻结READY及部署manifest均相同。旧 field 用RandomNoise(seed2026101701)，新pair加载已保存原noise；旧field自身未保存noise张量，因此bitwise noise相等尚无独立证据。新模型checkpoint已全文件核hash，旧field记录的是相同loader名称，没有把当前hash倒推成旧时刻证明。

## 已有数值

| 输出 | MF | 三事件平均绝对偏移（帧） |
|---|---:|---:|
| 历史 native | 0.891873632804 | 6.6667 |
| 历史 weak | 0.898977821490 | 1.3333 |
| 历史 field | 0.904060610139 | 0.5 |
| 新 native | 0.890069217866 | 6.6667 |
| 新 weak | 0.901973657267 | 1.3333 |

旧field相对旧weak为+0.005082789；新weak相对旧weak为+0.002995836，新native相对旧native为-0.001804415。旧field与新weak相减只剩+0.002086953，这是跨环境描述，不能作为field方法效应。环境、数值内核和卸载同时变化，当前记录没有隔离它们各自造成的差值。

## 单次复现的最小门槛

1. 沿新pair的 .81 环境、checkpoint/core/缓存payload/保存noise哈希；沿用105有效帧、107输出帧、1312×736、24fps、原完整prompt、20步Euler、AV shift12/3。记录新PID实际INT8派发，不只记录backend开关。
2. 原field源码及参数逐字冻结：alpha先验.25、上限.5、mu1、平滑.625、8probes、原±1邻时刻切向、原边界与锚、全部20×50层步。无role5、固定能量、额外动作文字或参数搜索。
3. 成片前核完整20×50审计、finite/实际alpha/锚/KKT；同源105有效帧及crop[16,8,1280,720]计算官方九指标。对新视频重新标注全部三个既定事件[14,18]、[37,40]、[80,84]，保留输出区间的不确定性。
4. 主比较是**新field−新weak**。若MF和全事件对齐收益一起复现且编辑保持，记录这一个已知正例的局部复现；若消失/反转，记录未在第二环境复现，保留原结果，不在此样例上调参。若只有微小MF变化而事件区间相同，按指标变化报告。

该实验比继续为平方切向能量proxy调系数更有信息：它先检验目前唯一较明显正例是否跨当前执行环境保持。两例/四例整体消融与“已搁置”的方法状态不因单个正例翻转；也不把这次复现用作新相位读数可控性的证据。

证据：同目录 `field41_evidence.json`、`live81_evidence.json` 保存只读摘录；结构化核对与必要hash见 `FIELD_ENVIRONMENT_REVIEW.json`。旧历史AV replay失败gate保持原状。
