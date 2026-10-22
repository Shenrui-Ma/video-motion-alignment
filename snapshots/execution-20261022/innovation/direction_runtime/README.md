# 参考时间方向 Attention 强度控制

状态：独立 PyTorch 实现及 CPU 小张量／伪 Comfy block 验证；尚未部署到 Comfy 服务，也未运行 GPU 或视频实验。文件只属于 `innovation/direction_runtime/`，主队列冻结实现保持原文件。

## 数学与作用范围

对指定输出视频 query，复用冻结 Flash Attention 的完整输出 `O`、参考子组输出 `R` 和 LSE，得到 `m_ref`；复用冻结 `_aligned_attention` 得到同时间 bin 输出 `S_t`。候选修正为 `D=m_ref*(S_t-R)`。

每个 head、每个 query 时间 bin 使用固定 2×2 四分位空间网格，微小网格去重。对同一个采样 query，计算全部参考时间 bin 的概率分布及前后邻 bin 条件输出；两端用真实相邻 bin 的单边差分。内部参考重心偏差 `e` 与参考特征差分 `T` 构成 `U=e*T`。逐采样点计算 `max(0,cos(D,U))²`，低信号、分布弥散、偏差过小、非法或非有限输入返回零。该 bin 的 gate 为采样 gate 均值，UNKNOWN 也按零计入。

在合并 heads **之前**应用 `O'=O+alpha*gate*D`。系数落在 `[0,1]`，故在同一组 Q/K/V 上等价于只在参考视频内部对原分布和同时间分布作凸组合；参考总概率及其他 key 的权重保持，指定 query 外输出原样保留。该代数性质不等同于未来层、后续采样步或最终像素不变。

内部参考重心与特征差分是研究信号。与成片动作时间、编辑质量之间的关系需配对视频实验检验。

## 实现与开关

- `runtime.py`：向量化 gate、流式分块参考 logits、Attention 修正、GPU 上的统计累积。生产默认调用冻结 CUDA Flash；CPU dense backend 只由测试显式注入。每个分块 logits 最大为 `[1, heads, query_chunk, key_chunk]`，不保存完整输出视频×参考视频矩阵。
- `nodes.py`：独立 `H3DirectionGatedSchedule` 节点，子类化冻结 `ScheduleState`／`ScheduleBlockPatch`，复用原布局校验与 block 顺序守卫。没有 VAE 解码、人体检测、训练或额外完整 DiT 前向。
- `frozen.py`：只读导入冻结 `core.py`、`layout.py`、`schedule.py`，导入前验证 SHA256；不执行冻结节点的 `__init__.py`，不改冻结文件。
- `test_runtime.py`：dense Attention oracle、纯 Python 公式对照与伪 block 测试。
- `verify_cpu.py`：执行测试并生成包含源码哈希的 `cpu_verification.json`。

`mode=direction_gated` 为新方法；`mass_preserve` 为同一适配中的统一强度控制；`native`、`alpha=0`、`enabled=false` 或 `selected_layers=none` 均关闭修正。关闭后每 block 仅保留一次原生 Flash 输出计算与审计，符合冻结 Attention backend；要完全移除补丁则从实验图移除新节点，使用原模型输出。

`selected_layers` 支持 `all`、`none`、`0,2,7` 或 `0-9,20-29`。首版只有显式层集合，**未实现动态选层**。层集合与冻结 `schedule` 同时满足才启用修正。默认 gate 阈值仍为原型暂定值 `offset=0.25`、`concentration=0.15`、`tangent_norm=1e-6`，正式实验须预先冻结；alpha 应填该配对基线实际登记值，节点默认值为 0.45。

首版只支持 `radius=0`、`time_offset=0` 的同时间修正；不足两个参考 bin 时关闭方向分支。幅度上限、等能量控制生成、打乱 head gate 对照尚未加入。

## 独立接入方式

未来获准使用的独立 Comfy 进程中，将本目录放在 `custom_nodes/H3DirectionRuntime/`，同时确保冻结 `H3Study` 原文件可读。默认查找本研究目录中的冻结包或同级 `H3Study`；也可给该独立进程指定 `H3_DIRECTION_FROZEN_ROOT=/absolute/path/to/frozen/H3Study`。依赖哈希不匹配会直接拒绝加载。

图中用新节点替换原 `H3StudySchedule`，输入同一个尚未安装 Attention／block 补丁的模型及 positive conditioning。保持其余权重、prompt、seed、sampler、sigma、shape、LoRA、步数与对照一致。节点拒绝已有 block/Attention override；调用过程中还检查原 Attention 入口、单次 override 调用、顺序和完整布局。原生 Comfy 节点加载与真实模型兼容性仍待独立进程 smoke test。

这里仅提供接入文件，没有复制到运行服务、重启服务、编辑任何已排队 graph 或提交新的采样作业。

## 日志与成本

每个 forward 边界落盘一次：层集合、schedule、每 head/bin gate/有效 alpha、平均内部偏差和浓度、各 UNKNOWN/冲突原因数量、选中比例、修正能量/RMS、累计原候选及实际修正能量、元素数。原有冻结 block25 周期诊断未调用，方向分支自身已记录全部选中层的统计。

每个正常启用层通常是 5 次 Attention primitive：完整、参考、同时间、前邻 probe、后邻 probe；统一 `mass_preserve` 是 3 次，关闭是 1 次。流式参考概率另记录 `probe_logits_matmul_calls`、最大 tile 尺寸。heads 与采样 queries 在 GPU 张量上同时计算，但时间 bin／tile 调度仍为 Python 循环，真实规模的启动开销需要测量。

可选 CUDA events 在 forward 结束时集中读取，分别记录 Attention 类别与 probe 分布耗时；host 值明确标为提交耗时。嵌套计时不能相加成完整采样时间。正式 GPU 实验须另测真实分辨率每步 wall time、峰值显存、整体开销及最终视频指标，当前记录不包含这些结果。

## CPU 验证

在已有 PyTorch 环境、`innovation` 为工作目录时运行：

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python -m direction_runtime.verify_cpu
```

无本地 PyTorch 时，可将小文件与三份冻结依赖复制到独立 CPU 测试目录并设置 `H3_DIRECTION_FROZEN_ROOT`。验证器要求 CUDA 隐藏，并记录测试结束时 CUDA 仍未初始化。dense oracle 只接受 CPU 张量。

覆盖 alpha0／native identity、参考常量 V、冻结统一强度兼容、dense 概率参考总质量保持和其他模态权重保持、指定 query 外精确不变、双边界、分块概率与内存 tile 上界、单参考 bin、float32/bfloat16 CPU 有限性、固定采样位置、显式层／步选择、伪 block 接入与 JSON 审计。结果属于算法与接入契约的 CPU 证据；视频效果、CUDA Flash kernel 及真实运行成本待测。
