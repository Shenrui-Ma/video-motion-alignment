# 保留 query probe 身份的参考坐标停止检验

只检验固定 layer25、56 heads × 8 query probes 的等权联合指纹能否在同一步的两种参考上下文之间，唯一辨认全部31个有效 nominal bins。两个 step 各做两方向，共124个相关测试格点，来源仍是一段参考视频。没有生成侧概率、事件标签、模型调用、GPU或 alpha 输出。

本包实现 `review_1216_next_readout/NEXT_READOUT_REVIEW.md` 中的单项检验。`POLICY.json` 在读取任何实际 capture 数组之前写入并冻结；本包实现阶段只使用合成数组，真实执行仍待 root 检查并单独记录。

## 计算

对每个时刻，将全部对应的 head/query-probe 的平方根概率拼接，除以 `sqrt(56*8)`。query probe 的顺序和身份保留，key 仍是原分析中聚合八个位置后的时间分布。逐 query 用 float64 直接平方差求和得到31×31距离矩阵，不使用 Gram 矩阵相减，不重新拟合、缩放概率、搜索半径或选择 head/step/时刻。

检索不使用 query 的时间标签，不限制对角邻域。评价时才用已知的同一参考坐标计算 `margin=min(非对应列距离)-对应列距离`。唯一并列容差是 `64*float64_eps`，作用于[0,2]中的平方距离；它只处理浮点并列，不是语义置信度或扰动鲁棒性门槛。

四方向全部31行都唯一正确且 margin 大于容差，结果为 `CONTINUE_TO_INDEPENDENT_CONTENT_CALIBRATION_ONLY`。任一行失败则为 `STOP_FULL_SUPPORT_ZERO_SHIFT_OBSERVER`。停止范围只针对这套固定等权指纹的**全支持零移位定位**；未评估稀疏或允许拒绝的其他控制器，不否定所有 Attention 信息。

纯位置码 `C_t=e_t` 即使画面静止也能完全通过。因此通过只允许讨论后续独立的“内容发生已知位移而位置坐标固定”校准。生成域、外观不变性、真实动作相位和修正方向导数均未由此建立。

## 输入与产物

`inputs.remote.json` 复用原已核验真实配对分析的远端 STATUS 和两份 NPZ 路径，没有复制或重新读取真实 tensor。POLICY 锁定原 STATUS、summary、NPZ 的 SHA，以及完整 shape、valid mask、spans、spatial ids。

解码白名单只有 `qrn_kn`、`qrw_kw`、`valid_bins`、`physical_frame_spans_inclusive`、`spatial_ids`。所有输入先通过身份与内容校验，再开始计算。缺失/未完成输出 pending；身份、shape、padding、概率或来源错误输出 invalid，均只有 STATUS，没有诊断数组/summary。已经存在的输出目录拒绝覆盖。生产 CLI 会先核对 READY 中的源文件/POLICY哈希，不支持修改阈值、步、分支、几何的参数。

root 检查并放行后，将包部署到已存在的远端 CPU 环境，在远端运行：

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python run.py --inputs inputs.remote.json --output NEW_RESULT_DIRECTORY
```

`NEW_RESULT_DIRECTORY` 必须是新路径，不能覆盖历史诊断。4份 NPZ 保存每方向完整矩阵、margin、并列mask、正确标记、误差上下界和几何；保留远端。小 `summary.json` 保留4方向及全部逐bin margin、并列集合、名义bin/帧误差，不以argmin悄悄选早时刻；空缺不补0。只回传 summary/STATUS/receipt。

实现阶段 CPU 验证命令：

```sh
/workspace/research-user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest -v test_diagnostic.py
```

26项合成测试通过，含静态、周期、非对角但唯一、空间身份丢失/置换、纯位置码、外观冒充、直接求差、损坏generated成员未被解码、SHA/metadata/支持/来源/输出覆盖错误。它们验证计算和隔离边界，不计作真实时间读出的成功。
