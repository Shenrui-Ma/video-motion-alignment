# 缓存复用核查与最小只读采集计划

状态：**规范已准备，未实现/安装 hook，未启动 GPU 重放。** 固定饮酒0358和手帕0059各 native/global_weak；零基层25、零基去噪步9和19、8个既有固定空间 probes、全部56heads。四条是旧对照的诊断重放，不新增实验变体。

## 1. 本轮实际只读核查

通过 .41/.9 既有 Python 环境在服务器 CPU 原地读 `x0_step009.pt`、初始 noise 和 manifest；CUDA_VISIBLE_DEVICES为空，三种线程环境为1，torch线程1，结果均 `cuda_initialized=false`。仅回传小 JSON，未复制 tensor 文件。本目录 `cache_41.json`、`cache_9.json` 保留精确路径、SHA、shape 和元数据。

| 对照 | 20份x0文件 | step9 video/audio | 初始 noise |
|---|---|---|---|
| 饮酒 native | 齐 | [1,24,32,46,82] / [1,32,2,178]，FP32 | 两个相同shape的完整流，seed2026101701 |
| 饮酒 weak | 齐 | 同上 | 两流齐 |
| 手帕 native | 齐 | [1,24,47,46,82] / [1,32,2,263]，FP32 | 两流齐 |
| 手帕 weak | 齐 | 同上 | 两流齐 |

核对源码 `H3X0Readout.PassiveRecorder.record`：保存的是预测 x0 经 process_latent_out 的 video/audio，实际 noisy x 参数未保存。video原样，audio除以4。`CachedNoise.generate_noise` 保存完整嵌套两流及各自hash。**不存在需要随意补出 audio 的理由，也不能把x0当x_n。** 本轮只对step9的tensor内容重算SHA；其余20份检查存在性和manifest记录，没有声称重新读取全部大张量。

已保存的初始双流noise、所有双流x0、sigma网格为无churn Euler递推提供输入；audio须乘回4并保留原FP32计算次序。是否能复用为同一采样中间状态，下一步仍须验证 noise_scale/空目标、latent处理、所有sigma、原模型/条件/LoRA和实际算子身份。当前记录支持**尝试完整AV递推复用**，尚未签认中间state精确一致。

最小顺序：先CPU重建完整AV状态并保存身份/运算顺序证据；然后对指定第9、19步只做控制重放，将新预测x0与旧保存x0的video和audio分别核对。终点sigma=0可能掩盖此前状态误差，只验final不足。若身份缺失或重建比较失败，改为四条完整20步控制重放；不得用video-only x_n代替。是否启动由主线程下一阶段决定。

## 2. 被动捕获的精确张量

每个指定层/步记录对应layout与实际Q/K dtype的：

1. `Q_canvas[T,P,H,D]`、`Q_reference[T,P,H,D]`、`K_reference[T,P,H,D]`，P=8、H=56、D=128。
2. 每个probe的真实packed token索引、时间bin、空间索引、query/reference origin、模态/时间调制行；有效帧与padding mask、名义起止/中心时间。
3. 该层实际RoPE表的选中行、rot_dim、Q/K RMSNorm参数及源文件SHA；采样run/step/layer、完整输入/conditioning/权重身份。

H3的 fused RMSNorm+RoPE 原位修改QKV缓冲。最轻被动路径是**正常融合调用后** clone已选中的Q/K和实际旋转表，在副本上用转置逆旋转得到内容诊断视图；同时保留旋转后原值用于对照。其“旋转前值”是对已舍入结果的逆变换，须与独立小张量的实际归一化→旋转路径核对误差，不冒充未舍入真值。不要为捕获替换原有fused kernel、关掉RoPE或改变被模型消费的storage。

本轮仅采集e所需Q/K，不存V，不做额外attention/FFN/W_o调用，不实现s。后续若e校准失败，停止；e通过后，才研究真实局部有限差分。

## 3. 体积与采样口径

若全32/47物理bins均保存再以mask排除padding，三个BF16/FP16张量每次为10.5/15.421875MiB。每例2种方法×2步，两例共 **103.6875MiB**，在服务器保存，回传只含必要时间分布/统计和hash的小结果。实际dtype若FP32体积翻倍，记录真实字节数。layout/RoPE选中行元数据另计。

源和生成均只取固定8个空间probes。CPU时间概率采用每参考bin的这8个keys；它是稀疏observer，不能标成全参考attention质量或保证没有漏掉小动作。所有heads保留，冻结事件逐一报告；原source self与native/weak共用同一采样。

## 4. 不改输出的验收要求

被动hook实现后、GPU诊断前需独立CPU小张量测试：原对象/底层buffer不写入；return值与无hook逐元素一致；只在预定layer/step记录，重复调用拒绝；非视频tokens不变；异常只记录并使诊断失败，不静默改走另一attention后端；捕获副本与序列/角色映射核对。

真实 GPU hook 首次验证还应记录同一输入状态、有hook和无hook的完整video/audio x0、原attention输出或抽样hash及容差，保证捕获没有改变数值路径。该双跑验证只是诊断成本，不能写成零开销。输入身份、内存layout、量化batch行为、fused kernel均保持；clone/CPU搬运引入同步需单独计时。

仅校准已有事件，不生成新的效果claim。首批不挑新层/步、不调head、不增加RGB检测、不按收益选样本。当前规范和CPU证据都没有触发GPU任务。
